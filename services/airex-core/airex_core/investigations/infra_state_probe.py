"""
Infrastructure state probe.

Orchestrates cloud infrastructure queries (ASG/MIG status, VPC Flow Logs)
to identify scaling issues, unhealthy instances, or network anomalies
that may correlate with an incident. Runs as an automatic secondary
probe when cloud context is available.

This probe:
  - Detects the cloud provider from incident meta (_cloud field)
  - Queries Auto Scaling / MIG status in parallel with VPC Flow Logs
  - Combines results into a single ProbeResult with structured metrics
  - Flags scaling issues, unhealthy instances, and rejected traffic
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

from airex_core.investigations.base import (
    Anomaly,
    BaseInvestigation,
    InvestigationResult,
    ProbeCategory,
    ProbeResult,
)

logger = structlog.get_logger()


def should_run_infra_state_probe(meta: dict) -> bool:
    """Check if infra state probe should run for this incident.

    Requires cloud context with at least a provider and a target resource.
    """
    cloud = (meta.get("_cloud") or "").lower()
    if cloud not in ("aws", "gcp"):
        return False
    return bool(
        meta.get("_instance_id") or meta.get("_private_ip") or meta.get("_resource_id")
    )


class InfraStateProbe(BaseInvestigation):
    """
    Probe that queries cloud infrastructure state.

    Routes to AWS (ASG + VPC Flow Logs) or GCP (MIG + VPC Flow Logs)
    based on the _cloud field in incident meta. Runs scaling and
    network queries in parallel for speed.
    """

    alert_type = "infra_state"

    async def investigate(self, incident_meta: dict) -> InvestigationResult:
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        private_ip = incident_meta.get("_private_ip", "")
        region = incident_meta.get("_region", "")
        project = incident_meta.get("_project", "")
        zone = incident_meta.get("_zone", "")
        tenant_name = incident_meta.get("_tenant_name", "")

        log = logger.bind(
            cloud=cloud,
            instance_id=instance_id,
            probe="infra_state",
        )

        # Load tenant config
        tenant_config = None
        if tenant_name:
            try:
                from airex_core.cloud.tenant_config import get_tenant_config

                tenant_config = get_tenant_config(tenant_name)
            except Exception:
                pass

        if not project and tenant_config and tenant_config.gcp.project_id:
            project = tenant_config.gcp.project_id
        if not region and tenant_config and tenant_config.aws.region:
            region = tenant_config.aws.region
        if not zone and tenant_config and tenant_config.gcp.zone:
            zone = tenant_config.gcp.zone

        start_time = time.monotonic()

        # Run scaling + flow log queries in parallel
        if cloud == "aws":
            scaling_result, flow_result = await asyncio.gather(
                self._query_aws_asg(instance_id, region, tenant_config, log),
                self._query_aws_vpc_flows(
                    instance_id, private_ip, region, tenant_config, log
                ),
                return_exceptions=True,
            )
        elif cloud == "gcp":
            sa_key = tenant_config.gcp.service_account_key if tenant_config else ""
            scaling_result, flow_result = await asyncio.gather(
                self._query_gcp_mig(instance_id, project, zone, sa_key, log),
                self._query_gcp_vpc_flows(
                    project, instance_id, private_ip, zone, sa_key, log
                ),
                return_exceptions=True,
            )
        else:
            scaling_result = _empty_scaling()
            flow_result = _empty_flows()

        # Handle exceptions from gather
        if isinstance(scaling_result, BaseException):
            log.warning("scaling_query_exception", error=str(scaling_result))
            scaling_result = _empty_scaling()
        if isinstance(flow_result, BaseException):
            log.warning("flow_query_exception", error=str(flow_result))
            flow_result = _empty_flows()

        duration_ms = round((time.monotonic() - start_time) * 1000, 1)

        # Build output text
        sections = self._format_output(scaling_result, flow_result, cloud)
        raw_output = "\n".join(sections)

        # Build metrics
        metrics: dict[str, Any] = {
            "cloud_provider": cloud.upper(),
            "instance_id": instance_id or "N/A",
        }

        # Scaling metrics
        if scaling_result.get("asg_name") or scaling_result.get("mig_name"):
            metrics["scaling_group"] = (
                scaling_result.get("asg_name") or scaling_result.get("mig_name") or ""
            )
            metrics["instance_count"] = scaling_result.get("instance_count", 0)
            metrics["healthy_count"] = scaling_result.get("healthy_count", 0)
            metrics["unhealthy_count"] = scaling_result.get("unhealthy_count", 0)
            metrics["scaling_in_progress"] = scaling_result.get(
                "scaling_in_progress", False
            )
            metrics["desired_capacity"] = scaling_result.get(
                "desired_capacity", scaling_result.get("target_size", 0)
            )

        # Flow log metrics
        metrics["flow_total_records"] = flow_result.get("total_records", 0)
        metrics["flow_rejected_count"] = flow_result.get(
            "rejected_count", flow_result.get("denied_count", 0)
        )

        # Build anomalies
        anomalies: list[Anomaly] = []

        unhealthy = scaling_result.get("unhealthy_count", 0)
        if unhealthy > 0:
            anomalies.append(
                Anomaly(
                    metric_name="unhealthy_instances",
                    value=float(unhealthy),
                    threshold=0.0,
                    severity="critical" if unhealthy >= 2 else "warning",
                    description=(f"{unhealthy} unhealthy instance(s) in scaling group"),
                )
            )

        if scaling_result.get("scaling_in_progress"):
            anomalies.append(
                Anomaly(
                    metric_name="scaling_in_progress",
                    value=1.0,
                    threshold=0.0,
                    severity="warning",
                    description="Scaling activity is currently in progress",
                )
            )

        rejected = flow_result.get("rejected_count", flow_result.get("denied_count", 0))
        if rejected > 5:
            anomalies.append(
                Anomaly(
                    metric_name="rejected_traffic",
                    value=float(rejected),
                    threshold=5.0,
                    severity="critical" if rejected > 20 else "warning",
                    description=(f"{rejected} rejected/denied network flows detected"),
                )
            )

        log.info(
            "infra_state_complete",
            has_scaling=bool(
                scaling_result.get("asg_name") or scaling_result.get("mig_name")
            ),
            flow_records=flow_result.get("total_records", 0),
            anomaly_count=len(anomalies),
            duration_ms=duration_ms,
        )

        return ProbeResult(
            tool_name=f"infra_state_{cloud}",
            raw_output=raw_output,
            category=ProbeCategory.INFRASTRUCTURE,
            metrics=metrics,
            anomalies=anomalies,
            duration_ms=duration_ms,
            probe_type="secondary",
        )

    # ── AWS queries ──────────────────────────────────────────────

    async def _query_aws_asg(
        self,
        instance_id: str,
        region: str,
        tenant_config: Any,
        log: structlog.stdlib.BoundLogger,
    ) -> dict[str, Any]:
        try:
            from airex_core.cloud.aws_autoscaling import query_asg_status

            aws_config = tenant_config.aws if tenant_config else None
            return await query_asg_status(
                instance_id=instance_id,
                region=region or "us-east-1",
                aws_config=aws_config,
            )
        except Exception as exc:
            log.warning("infra_asg_failed", error=str(exc))
            return _empty_scaling()

    async def _query_aws_vpc_flows(
        self,
        instance_id: str,
        private_ip: str,
        region: str,
        tenant_config: Any,
        log: structlog.stdlib.BoundLogger,
    ) -> dict[str, Any]:
        try:
            from airex_core.cloud.aws_vpc_flows import query_vpc_flow_logs

            aws_config = tenant_config.aws if tenant_config else None
            return await query_vpc_flow_logs(
                instance_id=instance_id,
                private_ip=private_ip,
                region=region or "us-east-1",
                aws_config=aws_config,
            )
        except Exception as exc:
            log.warning("infra_vpc_flows_failed", error=str(exc))
            return _empty_flows()

    # ── GCP queries ──────────────────────────────────────────────

    async def _query_gcp_mig(
        self,
        instance_id: str,
        project: str,
        zone: str,
        sa_key_path: str,
        log: structlog.stdlib.BoundLogger,
    ) -> dict[str, Any]:
        try:
            from airex_core.cloud.gcp_mig import query_mig_status

            return await query_mig_status(
                instance_id=instance_id,
                project=project,
                zone=zone,
                sa_key_path=sa_key_path,
            )
        except Exception as exc:
            log.warning("infra_mig_failed", error=str(exc))
            return _empty_scaling()

    async def _query_gcp_vpc_flows(
        self,
        project: str,
        instance_id: str,
        private_ip: str,
        zone: str,
        sa_key_path: str,
        log: structlog.stdlib.BoundLogger,
    ) -> dict[str, Any]:
        try:
            from airex_core.cloud.gcp_vpc_flows import query_gcp_vpc_flow_logs

            return await query_gcp_vpc_flow_logs(
                project=project,
                instance_id=instance_id,
                private_ip=private_ip,
                zone=zone,
                sa_key_path=sa_key_path,
            )
        except Exception as exc:
            log.warning("infra_gcp_vpc_flows_failed", error=str(exc))
            return _empty_flows()

    # ── Output formatting ────────────────────────────────────────

    def _format_output(
        self,
        scaling: dict[str, Any],
        flows: dict[str, Any],
        cloud: str,
    ) -> list[str]:
        sections: list[str] = [
            f"=== Infrastructure State: {cloud.upper()} ===",
            "",
        ]

        # Scaling group section
        group_name = scaling.get("asg_name") or scaling.get("mig_name")
        if group_name:
            group_type = (
                "Auto Scaling Group" if cloud == "aws" else "Managed Instance Group"
            )
            sections.append(f"--- {group_type}: {group_name} ---")

            desired = scaling.get("desired_capacity", scaling.get("target_size", 0))
            sections.append(f"  Desired/Target: {desired}")
            sections.append(
                f"  Instances: {scaling.get('instance_count', 0)} "
                f"(healthy: {scaling.get('healthy_count', 0)}, "
                f"unhealthy: {scaling.get('unhealthy_count', 0)})"
            )

            if scaling.get("scaling_in_progress"):
                sections.append("  *** SCALING IN PROGRESS ***")

            # Recent activities (AWS)
            activities = scaling.get("recent_activities", [])
            if activities:
                sections.append(f"  Recent activities ({len(activities)}):")
                for act in activities[:5]:
                    sections.append(
                        f"    {act.get('start_time', '')} | "
                        f"{act.get('status', '')} | "
                        f"{act.get('description', '')[:80]}"
                    )

            # Unhealthy instances
            unhealthy_list = scaling.get("unhealthy_instances", [])
            if unhealthy_list:
                sections.append(f"  Unhealthy instances ({len(unhealthy_list)}):")
                for inst in unhealthy_list[:5]:
                    sections.append(
                        f"    {inst.get('instance_id', '')} | "
                        f"{inst.get('health_status', '')} | "
                        f"{inst.get('lifecycle_state', '')}"
                    )
            sections.append("")
        elif scaling.get("error"):
            sections.append(f"Scaling group: {scaling['error']}")
            sections.append("")
        else:
            sections.append("Scaling group: Not applicable")
            sections.append("")

        # VPC Flow Logs section
        total = flows.get("total_records", 0)
        if total > 0:
            sections.append(f"--- VPC Flow Logs ({total} records) ---")
            rejected = flows.get("rejected_count", flows.get("denied_count", 0))
            accepted = flows.get("accepted_count", 0)
            if accepted or rejected:
                sections.append(f"  Accepted: {accepted}, Rejected/Denied: {rejected}")

            top_rejected = flows.get("top_rejected_ports", [])
            if top_rejected:
                sections.append("  Top rejected ports:")
                for entry in top_rejected[:5]:
                    sections.append(
                        f"    Port {entry.get('port', '?')}: "
                        f"{entry.get('count', 0)} rejections"
                    )

            top_sources = flows.get("top_sources", [])
            if top_sources:
                sections.append("  Top source IPs:")
                for entry in top_sources[:5]:
                    sections.append(
                        f"    {entry.get('ip', '?')}: {entry.get('count', 0)} flows"
                    )

            bytes_in = flows.get("bytes_in", 0)
            bytes_out = flows.get("bytes_out", 0)
            bytes_total = flows.get("bytes_total", 0)
            if bytes_in or bytes_out:
                sections.append(
                    f"  Traffic: {_format_bytes(bytes_in)} in, "
                    f"{_format_bytes(bytes_out)} out"
                )
            elif bytes_total:
                sections.append(f"  Traffic: {_format_bytes(bytes_total)} total")
        elif flows.get("error"):
            sections.append(f"VPC Flow Logs: {flows['error']}")
        else:
            sections.append("VPC Flow Logs: No records found")

        return sections


def _format_bytes(b: int) -> str:
    """Format bytes into human-readable string."""
    if b < 1024:
        return f"{b} B"
    elif b < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    elif b < 1024 * 1024 * 1024:
        return f"{b / (1024 * 1024):.1f} MB"
    else:
        return f"{b / (1024 * 1024 * 1024):.1f} GB"


def _empty_scaling() -> dict[str, Any]:
    return {
        "asg_name": "",
        "mig_name": "",
        "instance_count": 0,
        "healthy_count": 0,
        "unhealthy_count": 0,
        "error": "",
    }


def _empty_flows() -> dict[str, Any]:
    return {
        "total_records": 0,
        "rejected_count": 0,
        "denied_count": 0,
        "error": "",
    }
