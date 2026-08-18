import json
import os
import boto3
from datetime import datetime, timezone

events = boto3.client("events")
BUS = os.environ["TARGET_BUS"]


def from_codepipeline(detail, region, account):
    stage = detail.get("stage")
    action = detail.get("action")
    pipeline = detail.get("pipeline")
    exec_id = detail.get("execution-id")

    return {
        "source_system": "codepipeline",
        "severity": "high",
        "component": f"{pipeline}/{stage}" + (f"/{action}" if action else ""),
        "summary": f"Pipeline {pipeline} failed at stage {stage}",
        "identifiers": {
            "pipeline": pipeline,
            "stage": stage,
            "action": action,
            "execution_id": exec_id,
        },
        "console_url": (
            f"https://{region}.console.aws.amazon.com/codesuite/codepipeline/"
            f"pipelines/{pipeline}/executions/{exec_id}"
        ),
        "raw_reason": detail.get("execution-result", {}).get("external-execution-summary"),
    }


def from_alarm(detail, region, account):
    name = detail.get("alarmName")
    state = detail.get("state", {})
    reason = state.get("reason")

    return {
        "source_system": "cloudwatch-alarm",
        "severity": "medium",
        "component": name,
        "summary": f"Alarm {name} entered ALARM",
        "identifiers": {
            "alarm_name": name,
            "previous_state": detail.get("previousState", {}).get("value"),
        },
        "console_url": (
            f"https://{region}.console.aws.amazon.com/cloudwatch/home"
            f"?region={region}#alarmsV2:alarm/{name}"
        ),
        "raw_reason": reason,
    }


def lambda_handler(event, context):
    source = event.get("source")
    detail = event.get("detail", {})
    region = event.get("region")
    account = event.get("account")

    if source == "aws.codepipeline":
        payload = from_codepipeline(detail, region, account)
    elif source == "aws.cloudwatch":
        payload = from_alarm(detail, region, account)
    else:
        print(f"Ignoring unrecognised source: {source}")
        return {"skipped": True}

    payload["occurred_at"] = event.get("time") or datetime.now(timezone.utc).isoformat()
    payload["account"] = account
    payload["region"] = region
    payload["original_event_id"] = event.get("id")

    print(json.dumps(payload))

    events.put_events(
        Entries=[{
            "EventBusName": BUS,
            "Source": "todoapp.failures",
            "DetailType": "NormalisedFailure",
            "Detail": json.dumps(payload),
        }]
    )

    return {"published": True, "component": payload["component"]}