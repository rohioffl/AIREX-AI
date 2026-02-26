"""
GCP Audit Log query module.

Queries Cloud Logging for audit log entries related to a specific resource
within the last hour. Used by the change detection probe to identify
deployments, config changes, or IAM modifications that may correlate
with an incident.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

import structlog

logger = structlog.get_logger()


async def query_gcp_audit_logs(
    project: str,
    resource_id: str = "",
    lookback_minutes: int = 60,
    sa_key_path: str = "",
    max_results: int = 20,
) -> dict[str, Any]:
    """
    Query GCP Cloud Audit Logs for recent changes.

    Filters for admin activity and data access audit logs.

    Returns a dict with:
      - events: list of simplified event dicts
      - total_count: number of events found
      - high_risk_changes: list of events flagged as high-risk
      - deployment_detected: bool
    """
    if not project:
        return _empty_result(resource_id, lookback_minutes, "no project specified")

    try:
        from google.cloud import logging as gcp_logging

        if sa_key_path:
            client = gcp_logging.Client.from_service_account_json(
                sa_key_path, project=project
            )
        else:
            client = gcp_logging.Client(project=project)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=lookback_minutes)

        # Build filter for audit logs
        time_filter = (
            f'timestamp >= "{start_time.isoformat()}" '
            f'AND timestamp <= "{end_time.isoformat()}"'
        )
        audit_filter = (
            'protoPayload.@type="type.googleapis.com/google.cloud.audit.AuditLog"'
        )
        resource_filter = ""
        if resource_id:
            resource_filter = (
                f' AND (resource.labels.instance_id="{resource_id}"'
                f' OR protoPayload.resourceName="{resource_id}")'
            )

        full_filter = f"{audit_filter} AND {time_filter}{resource_filter}"

        # Query logs (sync client, run in executor)
        import asyncio

        loop = asyncio.get_running_loop()
        entries = await loop.run_in_executor(
            None,
            lambda: list(
                client.list_entries(
                    filter_=full_filter,
                    order_by=gcp_logging.DESCENDING,
                    max_results=max_results,
                    resource_names=[f"projects/{project}"],
                )
            ),
        )

        events = _parse_entries(entries)
        high_risk = [e for e in events if e.get("is_high_risk")]
        deployment = any(e.get("is_deployment") for e in events)

        return {
            "events": events,
            "total_count": len(events),
            "high_risk_changes": high_risk,
            "deployment_detected": deployment,
            "lookback_minutes": lookback_minutes,
            "resource_id": resource_id,
            "project": project,
        }

    except ImportError:
        logger.warning("gcp_audit_logging_not_installed")
        return _empty_result(
            resource_id, lookback_minutes, "google-cloud-logging not installed"
        )
    except Exception as exc:
        logger.warning("gcp_audit_query_failed", error=str(exc))
        return _empty_result(resource_id, lookback_minutes, str(exc))


def _parse_entries(entries: list) -> list[dict[str, Any]]:
    """Parse GCP audit log entries into simplified dicts."""
    parsed = []
    for entry in entries:
        payload = entry.payload if hasattr(entry, "payload") else {}
        if isinstance(payload, dict):
            method_name = payload.get("methodName", "")
            resource_name = payload.get("resourceName", "")
            principal = payload.get("authenticationInfo", {}).get("principalEmail", "")
        else:
            method_name = ""
            resource_name = ""
            principal = ""

        timestamp = str(entry.timestamp) if hasattr(entry, "timestamp") else ""

        is_high_risk = _is_high_risk_method(method_name)
        is_deployment = _is_deployment_method(method_name)

        parsed.append(
            {
                "method_name": method_name,
                "resource_name": resource_name,
                "principal": principal,
                "timestamp": timestamp,
                "severity": str(entry.severity) if hasattr(entry, "severity") else "",
                "is_high_risk": is_high_risk,
                "is_deployment": is_deployment,
            }
        )
    return parsed


# GCP methods that indicate high-risk changes
_HIGH_RISK_METHODS = {
    "compute.firewalls.delete",
    "compute.firewalls.patch",
    "compute.firewalls.insert",
    "compute.instances.stop",
    "compute.instances.delete",
    "compute.instances.setMetadata",
    "iam.serviceAccounts.create",
    "iam.serviceAccounts.delete",
    "iam.roles.update",
    "storage.buckets.setIamPolicy",
    "cloudfunctions.functions.delete",
    "run.services.delete",
}

# GCP methods that indicate deployments
_DEPLOYMENT_METHODS = {
    "run.services.replaceService",
    "cloudfunctions.functions.update",
    "cloudfunctions.functions.create",
    "container.deployments.create",
    "container.deployments.update",
    "clouddeploy.releases.create",
    "appengine.versions.create",
    "compute.instanceGroupManagers.patch",
    "compute.instanceTemplates.insert",
}


def _is_high_risk_method(method: str) -> bool:
    return method in _HIGH_RISK_METHODS


def _is_deployment_method(method: str) -> bool:
    return method in _DEPLOYMENT_METHODS


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
