"""
AWS CloudTrail query module.

Queries CloudTrail LookupEvents for recent changes to a specific resource
within the last hour. Used by the change detection probe to identify
deployments, config changes, or IAM modifications that may correlate
with an incident.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any

import structlog
from structlog.contextvars import get_contextvars

logger = structlog.get_logger()


def _get_correlation_id() -> str:
    value = get_contextvars().get("correlation_id")
    return str(value) if value is not None else ""


async def query_cloudtrail_events(
    resource_id: str,
    region: str,
    lookback_minutes: int = 60,
    aws_config: Any = None,
    max_results: int = 20,
) -> dict[str, Any]:
    """
    Query CloudTrail for recent events related to a resource.

    AWS APIs/permissions used:
      - CloudTrail LookupEvents (`cloudtrail:LookupEvents`).
      - Optional STS AssumeRole via shared aws_auth path when tenant role config exists.

    Returns a dict with:
      - events: list of simplified event dicts
      - total_count: number of events found
      - high_risk_changes: list of events flagged as high-risk
      - deployment_detected: bool
    """
    try:
        from airex_core.cloud.aws_auth import get_aws_client

        loop = asyncio.get_running_loop()
        client = await loop.run_in_executor(
            None,
            lambda: get_aws_client("cloudtrail", aws_config=aws_config, region=region),
        )

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=lookback_minutes)

        lookup_attrs: list[dict[str, str]] = []
        if resource_id:
            lookup_attrs.append(
                {
                    "AttributeKey": "ResourceName",
                    "AttributeValue": resource_id,
                }
            )

        params: dict[str, Any] = {
            "StartTime": start_time,
            "EndTime": end_time,
            "MaxResults": max_results,
        }
        if lookup_attrs:
            params["LookupAttributes"] = lookup_attrs

        response = await loop.run_in_executor(
            None,
            lambda: client.lookup_events(**params),
        )

        events = _parse_events(response.get("Events", []))
        high_risk = [e for e in events if e.get("is_high_risk")]
        deployment = any(e.get("is_deployment") for e in events)

        return {
            "events": events,
            "total_count": len(events),
            "high_risk_changes": high_risk,
            "deployment_detected": deployment,
            "lookback_minutes": lookback_minutes,
            "resource_id": resource_id,
        }

    except ImportError:
        logger.warning(
            "cloudtrail_boto3_not_installed",
            correlation_id=_get_correlation_id(),
        )
        return _empty_result(resource_id, lookback_minutes, "boto3 not installed")
    except Exception as exc:
        logger.warning(
            "cloudtrail_query_failed",
            error=str(exc),
            correlation_id=_get_correlation_id(),
        )
        return _empty_result(resource_id, lookback_minutes, str(exc))


def _parse_events(raw_events: list[dict]) -> list[dict[str, Any]]:
    """Parse CloudTrail events into simplified dicts."""
    parsed = []
    for event in raw_events:
        event_name = event.get("EventName", "")
        username = event.get("Username", "")
        event_time = event.get("EventTime")
        resources = event.get("Resources", [])
        resource_names = [r.get("ResourceName", "") for r in resources]

        is_high_risk = _is_high_risk_event(event_name)
        is_deployment = _is_deployment_event(event_name)

        parsed.append(
            {
                "event_name": event_name,
                "username": username,
                "event_time": str(event_time) if event_time else "",
                "resources": resource_names,
                "is_high_risk": is_high_risk,
                "is_deployment": is_deployment,
                "event_source": event.get("EventSource", ""),
            }
        )
    return parsed


# Events that indicate high-risk changes
_HIGH_RISK_EVENTS = {
    "DeleteSecurityGroup",
    "RevokeSecurityGroupIngress",
    "AuthorizeSecurityGroupIngress",
    "ModifyInstanceAttribute",
    "StopInstances",
    "TerminateInstances",
    "DeleteLoadBalancer",
    "DeregisterTargets",
    "UpdateFunctionCode",
    "DeleteFunction",
    "PutBucketPolicy",
    "DeleteBucketPolicy",
    "CreateUser",
    "AttachUserPolicy",
    "DetachUserPolicy",
    "DeleteRole",
}

# Events that indicate deployments
_DEPLOYMENT_EVENTS = {
    "UpdateService",
    "CreateDeployment",
    "RegisterTaskDefinition",
    "UpdateFunctionCode",
    "UpdateStack",
    "ExecuteChangeSet",
    "StartPipelineExecution",
    "PutImage",
    "UpdateApplication",
    "CreateDeploymentGroup",
}


def _is_high_risk_event(event_name: str) -> bool:
    return event_name in _HIGH_RISK_EVENTS


def _is_deployment_event(event_name: str) -> bool:
    return event_name in _DEPLOYMENT_EVENTS


def _empty_result(resource_id: str, lookback: int, error: str = "") -> dict[str, Any]:
    return {
        "events": [],
        "total_count": 0,
        "high_risk_changes": [],
        "deployment_detected": False,
        "lookback_minutes": lookback,
        "resource_id": resource_id,
        "error": error,
    }
