"""
Change detection probe.

Orchestrates cloud audit log queries (AWS CloudTrail / GCP Audit Logs)
to identify recent infrastructure changes that may correlate with an
incident. Runs as an automatic secondary probe when cloud context is
available in incident meta.

This probe:
  - Detects the cloud provider from incident meta (_cloud field)
  - Queries the appropriate audit log service (CloudTrail or GCP Audit)
  - Formats results as a ProbeResult with structured metrics
  - Flags high-risk changes and deployments for the anomaly detector
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from app.investigations.base import (
    Anomaly,
    BaseInvestigation,
    InvestigationResult,
    ProbeCategory,
    ProbeResult,
)

logger = structlog.get_logger()


def should_run_change_detection(meta: dict) -> bool:
    """Check if change detection probe should run for this incident.

    Requires cloud context with at least a provider and a target resource.
    """
    cloud = (meta.get("_cloud") or "").lower()
    if cloud not in ("aws", "gcp"):
        return False
    # Need at least one resource identifier to query audit logs
    has_resource = bool(
        meta.get("_instance_id") or meta.get("_private_ip") or meta.get("_resource_id")
    )
    return has_resource


class ChangeDetectionProbe(BaseInvestigation):
    """
    Probe that queries cloud audit logs for recent changes.

    Routes to AWS CloudTrail or GCP Audit Logs based on the _cloud
    field in incident meta. Returns structured results including
    change count, high-risk changes, and deployment detection.
    """

    alert_type = "change_detection"

    async def investigate(self, incident_meta: dict) -> InvestigationResult:
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        resource_id = incident_meta.get("_resource_id", "") or instance_id
        region = incident_meta.get("_region", "")
        project = incident_meta.get("_project", "")
        tenant_name = incident_meta.get("_tenant_name", "")

        log = logger.bind(
            cloud=cloud,
            resource_id=resource_id,
            probe="change_detection",
        )

        # Load tenant config for auth credentials
        tenant_config = None
        if tenant_name:
            try:
                from app.cloud.tenant_config import get_tenant_config

                tenant_config = get_tenant_config(tenant_name)
            except Exception:
                pass

        # Fill defaults from tenant config
        if not project and tenant_config and tenant_config.gcp.project_id:
            project = tenant_config.gcp.project_id
        if not region and tenant_config and tenant_config.aws.region:
            region = tenant_config.aws.region

        start_time = time.monotonic()

        if cloud == "aws":
            result = await self._query_aws(
                resource_id=resource_id,
                region=region,
                tenant_config=tenant_config,
                log=log,
            )
        elif cloud == "gcp":
            result = await self._query_gcp(
                project=project,
                resource_id=resource_id,
                tenant_config=tenant_config,
                log=log,
            )
        else:
            result = _empty_audit_result(resource_id, "unsupported cloud provider")

        duration_ms = round((time.monotonic() - start_time) * 1000, 1)

        # Build output text
        sections = self._format_output(result, cloud)
        raw_output = "\n".join(sections)

        # Build metrics
        metrics: dict[str, Any] = {
            "cloud_provider": cloud.upper(),
            "resource_id": resource_id,
            "total_changes": result.get("total_count", 0),
            "high_risk_count": len(result.get("high_risk_changes", [])),
            "deployment_detected": result.get("deployment_detected", False),
            "lookback_minutes": result.get("lookback_minutes", 60),
        }

        # Build anomalies for high-risk changes
        anomalies: list[Anomaly] = []
        if result.get("deployment_detected"):
            anomalies.append(
                Anomaly(
                    metric_name="deployment_detected",
                    value=1.0,
                    threshold=0.0,
                    severity="warning",
                    description="A deployment was detected in the lookback window",
                )
            )
        high_risk_count = len(result.get("high_risk_changes", []))
        if high_risk_count > 0:
            anomalies.append(
                Anomaly(
                    metric_name="high_risk_changes",
                    value=float(high_risk_count),
                    threshold=0.0,
                    severity="critical" if high_risk_count >= 3 else "warning",
                    description=(
                        f"{high_risk_count} high-risk change(s) detected in "
                        f"the last {result.get('lookback_minutes', 60)} minutes"
                    ),
                )
            )

        log.info(
            "change_detection_complete",
            total_changes=result.get("total_count", 0),
            high_risk=high_risk_count,
            deployment=result.get("deployment_detected", False),
            duration_ms=duration_ms,
        )

        return ProbeResult(
            tool_name=f"change_detection_{cloud}",
            raw_output=raw_output,
            category=ProbeCategory.CHANGE,
            metrics=metrics,
            anomalies=anomalies,
            duration_ms=duration_ms,
            probe_type="secondary",
        )

    async def _query_aws(
        self,
        resource_id: str,
        region: str,
        tenant_config: Any,
        log: structlog.stdlib.BoundLogger,
    ) -> dict[str, Any]:
        """Query AWS CloudTrail for recent changes."""
        try:
            from app.cloud.aws_cloudtrail import query_cloudtrail_events

            aws_config = tenant_config.aws if tenant_config else None
            return await query_cloudtrail_events(
                resource_id=resource_id,
                region=region or "us-east-1",
                lookback_minutes=60,
                aws_config=aws_config,
                max_results=20,
            )
        except Exception as exc:
            log.warning("change_detection_aws_failed", error=str(exc))
            return _empty_audit_result(resource_id, str(exc))

    async def _query_gcp(
        self,
        project: str,
        resource_id: str,
        tenant_config: Any,
        log: structlog.stdlib.BoundLogger,
    ) -> dict[str, Any]:
        """Query GCP Audit Logs for recent changes."""
        if not project:
            return _empty_audit_result(resource_id, "no GCP project specified")
        try:
            from app.cloud.gcp_audit import query_gcp_audit_logs

            sa_key = tenant_config.gcp.service_account_key if tenant_config else ""
            return await query_gcp_audit_logs(
                project=project,
                resource_id=resource_id,
                lookback_minutes=60,
                sa_key_path=sa_key,
                max_results=20,
            )
        except Exception as exc:
            log.warning("change_detection_gcp_failed", error=str(exc))
            return _empty_audit_result(resource_id, str(exc))

    def _format_output(self, result: dict[str, Any], cloud: str) -> list[str]:
        """Format audit log results into human-readable text."""
        sections: list[str] = [
            f"=== Change Detection: {cloud.upper()} ===",
            f"Resource: {result.get('resource_id', 'N/A')}",
            f"Lookback: {result.get('lookback_minutes', 60)} minutes",
            f"Total changes: {result.get('total_count', 0)}",
            "",
        ]

        if result.get("error"):
            sections.append(f"WARNING: {result['error']}")
            sections.append("")

        if result.get("deployment_detected"):
            sections.append("*** DEPLOYMENT DETECTED ***")
            sections.append("")

        high_risk = result.get("high_risk_changes", [])
        if high_risk:
            sections.append(f"--- High-Risk Changes ({len(high_risk)}) ---")
            for event in high_risk:
                if cloud == "aws":
                    sections.append(
                        f"  {event.get('event_time', '')} | "
                        f"{event.get('event_name', '')} | "
                        f"by {event.get('username', 'unknown')}"
                    )
                else:
                    sections.append(
                        f"  {event.get('timestamp', '')} | "
                        f"{event.get('method_name', '')} | "
                        f"by {event.get('principal', 'unknown')}"
                    )
            sections.append("")

        events = result.get("events", [])
        if events:
            sections.append(f"--- All Changes ({len(events)}) ---")
            for event in events[:10]:  # Limit to 10 for readability
                if cloud == "aws":
                    sections.append(
                        f"  {event.get('event_time', '')} | "
                        f"{event.get('event_name', '')} | "
                        f"{event.get('event_source', '')} | "
                        f"by {event.get('username', 'unknown')}"
                    )
                else:
                    sections.append(
                        f"  {event.get('timestamp', '')} | "
                        f"{event.get('method_name', '')} | "
                        f"by {event.get('principal', 'unknown')}"
                    )
            if len(events) > 10:
                sections.append(f"  ... and {len(events) - 10} more")
        else:
            sections.append("No changes detected in the lookback window.")

        return sections


def _empty_audit_result(resource_id: str, error: str = "") -> dict[str, Any]:
    return {
        "events": [],
        "total_count": 0,
        "high_risk_changes": [],
        "deployment_detected": False,
        "lookback_minutes": 60,
        "resource_id": resource_id,
        "error": error,
    }
