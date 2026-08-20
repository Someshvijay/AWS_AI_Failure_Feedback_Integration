"""Gather build evidence — hardened.

Changes vs v1:
  Point 2: logs are read TAIL-FIRST (startFromHead=False, paging backwards),
           so a huge log can never push the actual error out of the window.
           Error matching now ignores npm/deprecation noise and, when
           CodeBuild reports failed-phase timestamps, the excerpt is scoped
           to those phase windows first.
  Point 3: full evidence is offloaded to S3; the payload returned to Step
           Functions carries only the excerpt (hard byte cap) + the S3 key,
           so the 256KB state-payload limit can't be hit.
  Point 4: everything that leaves this function is passed through redact().
"""
import json
import os
import re

import boto3

from redact import redact

codebuild = boto3.client("codebuild")
logs = boto3.client("logs")
s3 = boto3.client("s3")

MAX_LINES = int(os.environ.get("MAX_LINES", "150"))
TAIL_FETCH_LIMIT = int(os.environ.get("TAIL_FETCH_LIMIT", "5000"))
MAX_EXCERPT_BYTES = int(os.environ.get("MAX_EXCERPT_BYTES", "60000"))
EVIDENCE_BUCKET = os.environ.get("EVIDENCE_BUCKET")

ERROR_PATTERNS = re.compile(
    r"(\berror\b|\bfailed\b|\bfailure\b|\bcannot\b|can't find|✕|✗|"
    r"assertionerror|\bexpected\b|\breceived\b|\bdenied\b|accessdenied|"
    r"not found|exit (status|code) [1-9])",
    re.IGNORECASE,
)
# Lines that match ERROR_PATTERNS but are almost always noise in JS builds.
NOISE_PATTERNS = re.compile(
    r"(npm WARN|npm notice|npm timing|DeprecationWarning|ExperimentalWarning|"
    r"\bdeprecated\b|peer dep|EBADENGINE)",
    re.IGNORECASE,
)


def fetch_log_tail(group, stream, max_lines):
    """Page BACKWARDS from the end of the stream. Newest lines are kept
    no matter how long the log is — the opposite of the old head-first read."""
    events = []
    token = None
    while True:
        kwargs = {
            "logGroupName": group,
            "logStreamName": stream,
            "startFromHead": False,
            "limit": 10000,
        }
        if token:
            kwargs["nextToken"] = token
        resp = logs.get_log_events(**kwargs)
        batch = [
            {"ts": e["timestamp"], "msg": e["message"].rstrip("\n")}
            for e in resp.get("events", [])
        ]
        events = batch + events  # older pages are prepended: order stays chronological
        new_token = resp.get("nextBackwardToken")
        if not batch or new_token == token or len(events) >= max_lines:
            break
        token = new_token
    return events[-max_lines:]


def phase_windows(build):
    """Millisecond windows (with 5s padding) for phases that actually failed."""
    windows = []
    for phase in build.get("phases", []):
        if phase.get("phaseStatus") in ("FAILED", "FAULT", "TIMED_OUT"):
            start, end = phase.get("startTime"), phase.get("endTime")
            if start and end:
                windows.append((
                    int(start.timestamp() * 1000) - 5000,
                    int(end.timestamp() * 1000) + 5000,
                ))
    return windows


def extract_relevant(events, windows):
    # Prefer lines emitted during the failed phase(s), if that leaves enough signal.
    if windows:
        scoped = [e for e in events
                  if any(s <= e["ts"] <= t for s, t in windows)]
        if len(scoped) >= 10:
            events = scoped

    lines = [e["msg"] for e in events]
    hits = [i for i, l in enumerate(lines)
            if ERROR_PATTERNS.search(l) and not NOISE_PATTERNS.search(l)]
    if not hits:
        return lines[-MAX_LINES:]

    keep = set()
    for i in hits:
        keep.update(range(max(0, i - 4), min(len(lines), i + 6)))
    selected = [lines[i] for i in sorted(keep)]
    return selected[-MAX_LINES:]


def cap_bytes(text, limit):
    encoded = text.encode()
    if len(encoded) <= limit:
        return text
    return encoded[-limit:].decode(errors="ignore")  # keep the tail on overflow


def offload_to_s3(key, payload):
    if not EVIDENCE_BUCKET:
        return None
    try:
        s3.put_object(
            Bucket=EVIDENCE_BUCKET,
            Key=key,
            Body=json.dumps(payload, default=str).encode(),
            ContentType="application/json",
            ServerSideEncryption="AES256",
        )
        return f"s3://{EVIDENCE_BUCKET}/{key}"
    except Exception as e:  # offload failure must never fail triage
        return f"offload_failed: {e}"


def lambda_handler(event, context):
    detail = event if "identifiers" in event else event.get("detail", {})
    ids = detail.get("identifiers", {})
    build_id = ids.get("build_id")

    evidence = {
        "evidence_type": "codebuild",
        "component": detail.get("component"),
        "raw_reason": redact(str(detail.get("raw_reason") or "")),
        "build_id": build_id,
        "sufficient": False,
    }

    if not build_id:
        evidence["gather_error"] = "No build_id in the event payload"
        return {"failure": detail, "evidence": evidence}

    try:
        builds = codebuild.batch_get_builds(ids=[build_id]).get("builds", [])
    except Exception as e:
        evidence["gather_error"] = f"batch_get_builds failed: {e}"
        return {"failure": detail, "evidence": evidence}

    if not builds:
        evidence["gather_error"] = f"No build found for {build_id}"
        return {"failure": detail, "evidence": evidence}

    build = builds[0]

    failed_phases = []
    for phase in build.get("phases", []):
        if phase.get("phaseStatus") in ("FAILED", "FAULT", "TIMED_OUT"):
            failed_phases.append({
                "phase": phase.get("phaseType"),
                "status": phase.get("phaseStatus"),
                "messages": [redact(c.get("message") or "")
                             for c in phase.get("contexts", [])],
            })
    evidence["failed_phases"] = failed_phases
    evidence["build_status"] = build.get("buildStatus")
    evidence["source_version"] = build.get("resolvedSourceVersion")

    log_info = build.get("logs", {})
    group, stream = log_info.get("groupName"), log_info.get("streamName")
    evidence["log_deep_link"] = log_info.get("deepLink")

    if not group or not stream:
        evidence["gather_error"] = "Build has no associated log stream"
        return {"failure": detail, "evidence": evidence}

    try:
        tail = fetch_log_tail(group, stream, TAIL_FETCH_LIMIT)
    except Exception as e:
        evidence["gather_error"] = f"Log fetch failed: {e}"
        return {"failure": detail, "evidence": evidence}

    evidence["fetched_log_lines"] = len(tail)

    excerpt_lines = extract_relevant(tail, phase_windows(build))
    excerpt_text = cap_bytes(redact("\n".join(excerpt_lines)), MAX_EXCERPT_BYTES)
    evidence["log_excerpt"] = excerpt_text
    evidence["sufficient"] = len(excerpt_lines) > 5

    # Point 3: full (redacted) tail goes to S3; only the excerpt rides the state machine.
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", build_id)
    evidence["evidence_s3_uri"] = offload_to_s3(
        f"evidence/build/{safe_id}.json",
        {
            "failure": detail,
            "evidence_meta": {k: v for k, v in evidence.items()
                              if k != "log_excerpt"},
            "full_log_tail": redact("\n".join(e["msg"] for e in tail)),
        },
    )

    return {"failure": detail, "evidence": evidence}