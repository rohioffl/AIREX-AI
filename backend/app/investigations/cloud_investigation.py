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

from app.investigations.base import (
    BaseInvestigation,
    InvestigationResult,
    ProbeCategory,
    ProbeResult,
)
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

        # Fill project from tenant config if not in meta
        if not project and tenant_config and tenant_config.gcp.project_id:
            project = tenant_config.gcp.project_id
        if not region and tenant_config and tenant_config.aws.region:
            region = tenant_config.aws.region

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
        gcp_config = tenant_config.gcp if tenant_config else None
        sa_key = tenant_config.gcp.service_account_key if tenant_config else ""

        # Resolve SSH user for this specific machine (per-server > per-tenant > cloud API > fallback)
        from app.cloud.ssh_user_resolver import resolve_ssh_user

        os_user = await resolve_ssh_user(
            cloud=cloud,
            tenant_name=tenant_name,
            private_ip=private_ip,
            instance_id=instance_id,
            instance_name=instance_id,
            project=project,
            zone=zone,
            region=region,
            aws_config=aws_config,
            gcp_config=gcp_config,
        )
        log.info("ssh_user_resolved", os_user=os_user)

        if cloud == "aws" and instance_id:
            # Prefer SSM; only use EC2 Instance Connect when SSM is not available.
            log.info("investigating_via_aws_ssm")
            sections.append("--- Diagnostics via AWS SSM ---")
            ssh_output = await self._run_aws_ssm(
                instance_id, commands, region, aws_config
            )
            sections.append(ssh_output)

            # SSM failed (agent not installed / not managed) → fall back to EC2 Instance Connect (no stored keys).
            if ssh_output.strip().startswith("SSM ERROR") and private_ip:
                zone_for_connect = zone or await self._get_aws_instance_zone(
                    instance_id, region, aws_config
                )
                if zone_for_connect:
                    sections.append("")
                    sections.append(
                        "--- Diagnostics via EC2 Instance Connect (no keys stored) ---"
                    )
                    try:
                        ec2_out = await self._run_aws_ec2_connect_ssh(
                            private_ip=private_ip,
                            instance_id=instance_id,
                            zone=zone_for_connect,
                            commands=commands,
                            region=region,
                            aws_config=aws_config,
                            os_user=os_user,
                        )
                        sections.append(ec2_out)
                    except Exception as exc:
                        sections.append(f"EC2 Instance Connect ERROR: {exc}")
                else:
                    sections.append(
                        "(EC2 Instance Connect requires instance AZ; discovery may not have run.)"
                    )

        elif cloud == "gcp" and (private_ip or instance_id):
            log.info("investigating_via_gcp_ssh")
            if not private_ip and instance_id:
                private_ip = await self._resolve_gcp_ip(instance_id, project, zone)

            if private_ip:
                sections.append("--- Diagnostics via GCP OS Login SSH ---")
                ssh_output = await self._run_gcp_ssh(
                    private_ip, commands, instance_id, project, zone, sa_key, os_user
                )
                sections.append(ssh_output)
            else:
                sections.append(
                    "WARNING: Could not resolve private IP for GCP instance"
                )
                sections.append(
                    f"Instance: {instance_id}, Project: {project}, Zone: {zone}"
                )

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

        # Optimize the output before returning
        raw_output = "\n".join(sections)
        from app.investigations.evidence_optimizer import optimize_evidence_output

        raw_output = optimize_evidence_output(raw_output, alert_type=alert_type)

        return ProbeResult(
            tool_name=f"cloud_investigation_{cloud or 'fallback'}",
            raw_output=raw_output,
            category=ProbeCategory.INFRASTRUCTURE,
            probe_type="primary",
            metrics={
                "cloud_provider": cloud.upper() or "UNKNOWN",
                "alert_type": alert_type,
                "instance_id": instance_id or "N/A",
                "private_ip": private_ip or "N/A",
                "region": region or "N/A",
                "has_ssh_output": "Diagnostics via" in raw_output,
                "has_cloud_logs": "Log Explorer" in raw_output
                or "CloudWatch" in raw_output,
            },
        )

    async def _run_aws_ssm(
        self,
        instance_id: str,
        commands: list[str],
        region: str,
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

    async def _get_aws_instance_zone(
        self, instance_id: str, region: str, aws_config=None
    ) -> str:
        """Resolve instance to Availability Zone for EC2 Instance Connect."""
        from app.cloud.aws_ssh import get_instance_availability_zone

        return await get_instance_availability_zone(
            instance_id=instance_id, region=region, aws_config=aws_config
        )

    async def _run_aws_ec2_connect_ssh(
        self,
        private_ip: str,
        instance_id: str,
        zone: str,
        commands: list[str],
        region: str,
        aws_config=None,
        os_user: str = "ubuntu",
    ) -> str:
        """Execute diagnostic commands via EC2 Instance Connect (no stored keys)."""
        from app.cloud.aws_ssh import aws_ec2_connect_run_command

        return await aws_ec2_connect_run_command(
            private_ip=private_ip,
            instance_id=instance_id,
            zone=zone,
            commands=commands,
            region=region,
            aws_config=aws_config,
            os_user=os_user,
        )

    async def _run_gcp_ssh(
        self,
        private_ip: str,
        commands: list[str],
        instance_name: str,
        project: str,
        zone: str,
        sa_key_path: str = "",
        os_user: str = "",
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
                os_user=os_user,
            )
        except Exception as exc:
            return f"SSH ERROR: {exc}"

    async def _resolve_gcp_ip(self, instance_name: str, project: str, zone: str) -> str:
        """Resolve GCP instance name to private IP via Compute API."""
        try:
            from app.cloud.gcp_ssh import gcp_resolve_private_ip

            ip = await gcp_resolve_private_ip(instance_name, project, zone)
            return ip or ""
        except Exception:
            return ""

    async def _query_gcp_logs(
        self,
        project: str,
        instance_id: str,
        private_ip: str,
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
        self,
        instance_id: str,
        region: str,
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
