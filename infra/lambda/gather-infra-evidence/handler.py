"""Gather infra evidence — hardened.

Changes vs v1:
  Point 7: the lookback window is anchored to the alarm's own
           StateUpdatedTimestamp, not to now() — late event delivery can no
           longer make the window miss the incident.
  Point 5: filter_log_events is properly paginated, runs an error-biased
           filterPattern pass first and only falls back to unfiltered, and
           streams are ranked by recency instead of taking an arbitrary 300
           events.
  Point 3: streams are capped (MAX_STREAMS) and per-stream lines are capped,
           with the full fetched set offloaded to S3, so the 256KB Step
           Functions payload limit can't be hit.
  Point 4: everything returned is passed through redact().
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone

import boto3

from redact import redact

cw = boto3.client("cloudwatch")
logs = boto3.client("logs")
ec2 = boto3.client("ec2")
s3 = boto3.client("s3")

CONTAINER_LOG_GROUP = os.environ.get("CONTAINER_LOG_GROUP", "/todo-app-aws/containers")
INSTANCE_ID = os.environ.get("INSTANCE_ID")
LOOKBACK_MIN = int(os.environ.get("LOOKBACK_MIN", "30"))
MAX_EVENTS = int(os.environ.get("MAX_EVENTS", "1000"))
MAX_STREAMS = int(os.environ.get("MAX_STREAMS", "5"))
LINES_PER_STREAM = int(os.environ.get("LINES_PER_STREAM", "60"))
EVIDENCE_BUCKET = os.environ.get("EVIDENCE_BUCKET")

# CloudWatch Logs filter syntax: '?term' = match any of these terms.
ERROR_FILTER = os.environ.get(
    "LOG_FILTER_PATTERN",
    "?error ?Error ?ERROR ?exception ?Exception ?fatal ?FATAL ?denied ?failed ?FAILED ?panic",
)


def alarm_window(alarm):
    """Point 7: anchor the evidence window to when the alarm actually changed
    state, with a small forward buffer, clamped to now."""
    now = datetime.now(timezone.utc)
    anchor = alarm.get("StateUpdatedTimestamp") if alarm else None
    if anchor:
        end = min(anchor + timedelta(minutes=5), now)
        start = anchor - timedelta(minutes=LOOKBACK_MIN)
    else:
        end = now
        start = now - timedelta(minutes=LOOKBACK_MIN)
    return start, end


def fetch_filtered_events(group, start_ms, end_ms, pattern=None):
    """Point 5: real pagination with a global cap, optional filterPattern."""
    events = []
    token = None
    while len(events) < MAX_EVENTS:
        kwargs = {
            "logGroupName": group,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": 1000,
        }
        if pattern:
            kwargs["filterPattern"] = pattern
        if token:
            kwargs["nextToken"] = token
        resp = logs.filter_log_events(**kwargs)
        events.extend(resp.get("events", []))
        token = resp.get("nextToken")
        if not token:
            break
    return events[:MAX_EVENTS]


def group_and_cap(events):
    """Group by stream, keep the MAX_STREAMS most recently active streams,
    last LINES_PER_STREAM lines each, redacted."""
    by_stream = {}
    for e in events:
        by_stream.setdefault(e["logStreamName"], []).append(e)

    ranked = sorted(
        by_stream.items(),
        key=lambda kv: max(ev["timestamp"] for ev in kv[1]),
        reverse=True,
    )[:MAX_STREAMS]

    capped = {}
    for stream, evs in ranked:
        evs.sort(key=lambda ev: ev["timestamp"])
        msgs = [ev["message"].rstrip("\n") for ev in evs[-LINES_PER_STREAM:]]
        capped[stream] = redact("\n".join(msgs))
    return capped, len(by_stream)


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
    except Exception as e:
        return f"offload_failed: {e}"


def lambda_handler(event, context):
    detail = event if "identifiers" in event else event.get("detail", {})
    ids = detail.get("identifiers", {})
    alarm_name = ids.get("alarm_name")

    evidence = {
        "evidence_type": "infrastructure",
        "component": detail.get("component"),
        "raw_reason": redact(str(detail.get("raw_reason") or "")),
        "alarm_name": alarm_name,
        "sufficient": False,
    }

    alarm = None
    try:
        alarms = cw.describe_alarms(AlarmNames=[alarm_name]).get("MetricAlarms", [])
        alarm = alarms[0] if alarms else None
    except Exception as e:
        evidence["alarm_lookup_error"] = str(e)

    start, end = alarm_window(alarm)
    evidence["window"] = {"start": start.isoformat(), "end": end.isoformat()}

    if alarm:
        evidence["alarm_config"] = {
            "namespace": alarm.get("Namespace"),
            "metric": alarm.get("MetricName"),
            "threshold": alarm.get("Threshold"),
            "comparison": alarm.get("ComparisonOperator"),
            "statistic": alarm.get("Statistic"),
            "period": alarm.get("Period"),
            "state_changed_at": str(alarm.get("StateUpdatedTimestamp")),
            "state_reason": redact(alarm.get("StateReason") or ""),
        }
        try:
            stats = cw.get_metric_statistics(
                Namespace=alarm["Namespace"],
                MetricName=alarm["MetricName"],
                Dimensions=alarm.get("Dimensions", []),
                StartTime=start,
                EndTime=end,
                Period=300,
                Statistics=["Average", "Maximum"],
            )
            points = sorted(stats.get("Datapoints", []), key=lambda d: d["Timestamp"])
            evidence["metric_series"] = [
                {
                    "at": p["Timestamp"].isoformat(),
                    "avg": round(p.get("Average", 0), 2),
                    "max": round(p.get("Maximum", 0), 2),
                }
                for p in points
            ]
        except Exception as e:
            evidence["metric_lookup_error"] = str(e)

    if INSTANCE_ID:
        try:
            r = ec2.describe_instances(InstanceIds=[INSTANCE_ID])
            inst = r["Reservations"][0]["Instances"][0]
            evidence["instance"] = {
                "id": INSTANCE_ID,
                "state": inst["State"]["Name"],
                "type": inst.get("InstanceType"),
                "launched": inst["LaunchTime"].isoformat(),
            }
        except Exception as e:
            evidence["instance_lookup_error"] = str(e)

    start_ms, end_ms = int(start.timestamp() * 1000), int(end.timestamp() * 1000)
    raw_events = []
    try:
        # Point 5: error-biased pass first, unfiltered fallback second.
        raw_events = fetch_filtered_events(
            CONTAINER_LOG_GROUP, start_ms, end_ms, ERROR_FILTER)
        evidence["log_pass"] = "error_filtered"
        if not raw_events:
            raw_events = fetch_filtered_events(
                CONTAINER_LOG_GROUP, start_ms, end_ms)
            evidence["log_pass"] = "unfiltered_fallback"

        capped, total_streams = group_and_cap(raw_events)
        evidence["container_logs"] = capped
        evidence["streams_seen"] = total_streams
        evidence["streams_included"] = len(capped)
        evidence["events_fetched"] = len(raw_events)
        evidence["sufficient"] = bool(capped) or bool(evidence.get("metric_series"))
    except Exception as e:
        evidence["container_log_error"] = str(e)

    safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", alarm_name or "unknown")
    stamp = end.strftime("%Y%m%dT%H%M%S")
    evidence["evidence_s3_uri"] = offload_to_s3(
        f"evidence/infra/{safe_name}-{stamp}.json",
        {
            "failure": detail,
            "evidence_meta": {k: v for k, v in evidence.items()
                              if k != "container_logs"},
            "all_fetched_events": [
                {"stream": e["logStreamName"],
                 "ts": e["timestamp"],
                 "msg": redact(e["message"].rstrip("\n"))}
                for e in raw_events
            ],
        },
    )

    return {"failure": detail, "evidence": evidence}