"""
Cloud-aware investigation plugin.

Routes to the correct cloud connector based on tags in incident meta:
  - cloud:aws  → AWS SSM RunCommand (uses IAM roles)
  - cloud:gcp  → GCP OS Login SSH (uses service accounts)

Also pulls logs from:
  - GCP → Cloud Logging (Log Explorer)
  - AWS → CloudWatch Logs

Falls back to the simulated plugins when no cloud context is available.
"""

from __future__ import annotations

import structlog

from app.investigations.base import BaseInvestigation, InvestigationResult
from app.cloud.diagnostics import get_diagnostic_commands

logger = structlog.get_logger()


class CloudInvestigation(BaseInvestigation):
    """
    Cloud-aware investigation that SSHes / SSMs into real servers.

    The investigation service injects `_cloud`, `_private_ip`, `_instance_id`
    etc. into the meta dict after parsing Site24x7 tags.
    """

    alert_type = "cloud_aware"

    async def investigate(self, incident_meta: dict) -> InvestigationResult:
        cloud = incident_meta.get("_cloud", "").lower()
        private_ip = incident_meta.get("_private_ip", "")
        instance_id = incident_meta.get("_instance_id", "")
        project = incident_meta.get("_project", "")
        zone = incident_meta.get("_zone", "")
        region = incident_meta.get("_region", "")
        tenant_name = incident_meta.get("_tenant_name", "")
        alert_type = incident_meta.get("alert_type", "cpu_high")
        host = incident_meta.get("host", instance_id or private_ip or "unknown")

        log = logger.bind(cloud=cloud, host=host, alert_type=alert_type)

        # Load per-tenant cloud config for auth
        tenant_config = None
        if tenant_name:
            try:
                from app.cloud.tenant_config import get_tenant_config
                tenant_config = get_tenant_config(tenant_name)
            except Exception:
                pass

        # Get the diagnostic commands for this alert type
        commands = get_diagnostic_commands(alert_type)

        sections: list[str] = [
            f"=== Cloud Investigation: {host} ===",
            f"Cloud: {cloud.upper() or 'UNKNOWN'}",
            f"Alert Type: {alert_type}",
            f"Instance: {instance_id or 'N/A'}",
            f"Private IP: {private_ip or 'N/A'}",
            "",
        ]

        # ── Run diagnostics on the server ────────────────────────
        aws_config = tenant_config.aws if tenant_config else None
        sa_key = tenant_config.gcp.service_account_key if tenant_config else ""

        if cloud == "aws" and instance_id:
            log.info("investigating_via_aws_ssm")
            sections.append("--- Diagnostics via AWS SSM ---")
            ssh_output = await self._run_aws_ssm(instance_id, commands, region, aws_config)
            sections.append(ssh_output)

        elif cloud == "gcp" and (private_ip or instance_id):
            log.info("investigating_via_gcp_ssh")
            if not private_ip and instance_id:
                private_ip = await self._resolve_gcp_ip(instance_id, project, zone)

            if private_ip:
                sections.append("--- Diagnostics via GCP OS Login SSH ---")
                ssh_output = await self._run_gcp_ssh(
                    private_ip, commands, instance_id, project, zone, sa_key
                )
                sections.append(ssh_output)
            else:
                sections.append("WARNING: Could not resolve private IP for GCP instance")
                sections.append(f"Instance: {instance_id}, Project: {project}, Zone: {zone}")

        else:
            sections.append(
                f"NOTE: No cloud connector available (cloud={cloud}, ip={private_ip}, instance={instance_id})"
            )
            sections.append("Falling back to simulated diagnostics.")
            sim_output = await self._run_simulated(alert_type, incident_meta)
            sections.append(sim_output)

        # ── Pull cloud logs ──────────────────────────────────────
        sections.append("")
        if cloud == "gcp":
            log.info("querying_gcp_logs")
            sections.append("--- GCP Log Explorer ---")
            log_output = await self._query_gcp_logs(
                project=project,
                instance_id=instance_id,
                private_ip=private_ip,
                sa_key_path=sa_key,
            )
            sections.append(log_output)

        elif cloud == "aws":
            log.info("querying_cloudwatch_logs")
            sections.append("--- AWS CloudWatch Logs ---")
            log_output = await self._query_aws_logs(
                instance_id=instance_id,
                region=region,
                aws_config=aws_config,
            )
            sections.append(log_output)

        return InvestigationResult(
            tool_name=f"cloud_investigation_{cloud or 'fallback'}",
            raw_output="\n".join(sections),
        )

    async def _run_aws_ssm(
        self, instance_id: str, commands: list[str], region: str,
        aws_config=None,
    ) -> str:
        """Execute diagnostic commands via AWS SSM."""
        try:
            from app.cloud.aws_ssm import ssm_run_command
            return await ssm_run_command(
                instance_id=instance_id,
                commands=commands,
                region=region,
                aws_config=aws_config,
            )
        except Exception as exc:
            return f"SSM ERROR: {exc}"

    async def _run_gcp_ssh(
        self,
        private_ip: str,
        commands: list[str],
        instance_name: str,
        project: str,
        zone: str,
        sa_key_path: str = "",
    ) -> str:
        """Execute diagnostic commands via GCP OS Login SSH."""
        try:
            from app.cloud.gcp_ssh import gcp_ssh_run_command
            return await gcp_ssh_run_command(
                private_ip=private_ip,
                commands=commands,
                instance_name=instance_name,
                project=project,
                zone=zone,
            )
        except Exception as exc:
            return f"SSH ERROR: {exc}"

    async def _resolve_gcp_ip(
        self, instance_name: str, project: str, zone: str
    ) -> str:
        """Resolve GCP instance name to private IP via Compute API."""
        try:
            from app.cloud.gcp_ssh import gcp_resolve_private_ip
            ip = await gcp_resolve_private_ip(instance_name, project, zone)
            return ip or ""
        except Exception:
            return ""

    async def _query_gcp_logs(
        self, project: str, instance_id: str, private_ip: str,
        sa_key_path: str = "",
    ) -> str:
        """Query GCP Log Explorer."""
        try:
            from app.cloud.gcp_logging import query_gcp_logs
            return await query_gcp_logs(
                project=project,
                instance_id=instance_id,
                private_ip=private_ip,
                severity="WARNING",
                lookback_minutes=30,
                sa_key_path=sa_key_path,
            )
        except Exception as exc:
            return f"Log Explorer ERROR: {exc}"

    async def _query_aws_logs(
        self, instance_id: str, region: str,
        aws_config=None,
    ) -> str:
        """Query AWS CloudWatch Logs."""
        try:
            from app.cloud.aws_logs import query_cloudwatch_logs
            return await query_cloudwatch_logs(
                instance_id=instance_id,
                region=region,
                lookback_minutes=30,
                aws_config=aws_config,
            )
        except Exception as exc:
            return f"CloudWatch ERROR: {exc}"

    async def _run_simulated(self, alert_type: str, meta: dict) -> str:
        """Fall back to the original simulated investigation."""
        from app.investigations import INVESTIGATION_REGISTRY

        plugin_cls = INVESTIGATION_REGISTRY.get(alert_type)
        if plugin_cls is None:
            return "No simulated plugin available for this alert type."

        plugin = plugin_cls()
        result = await plugin.investigate(meta)
        return result.raw_output
