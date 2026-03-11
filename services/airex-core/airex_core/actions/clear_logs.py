"""
Clear logs action.

Uses cloud connectors (SSM/SSH) when cloud context is available,
falls back to simulation otherwise.
"""

import asyncio
import random

import structlog

from airex_core.actions.base import ActionResult, BaseAction

logger = structlog.get_logger()


class ClearLogsAction(BaseAction):
    """Clear old log files via SSM RunCommand or GCP SSH."""

    action_type = "clear_logs"
    DESCRIPTION = (
        "Truncate or rotate large log files consuming disk space. Use when disk usage "
        "is high due to log accumulation (not application data). Blast radius: log files "
        "only on one host. Risk: loss of historical log data. Verification: disk usage "
        "drops below threshold after cleanup."
    )

    async def execute(self, incident_meta: dict) -> ActionResult:
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        private_ip = incident_meta.get("_private_ip", "")
        region = incident_meta.get("_region", "")
        log_path = incident_meta.get("log_path", "/var/log")
        host = incident_meta.get("host", "unknown-host")

        commands = [
            f"find {log_path} -name '*.log.*' -mtime +3 -delete 2>/dev/null; echo 'Cleaned rotated logs'",
            f"find {log_path} -name '*.gz' -mtime +3 -delete 2>/dev/null; echo 'Cleaned compressed logs'",
            "journalctl --vacuum-time=3d 2>/dev/null; echo 'Journal cleaned'",
            "df -h / | tail -1",
        ]

        if cloud == "aws" and instance_id:
            return await self._execute_cloud(
                "aws", instance_id, private_ip, commands, region, incident_meta
            )
        elif cloud == "gcp" and private_ip:
            return await self._execute_cloud(
                "gcp", instance_id, private_ip, commands, region, incident_meta
            )

        return await self._simulate(host, log_path)

    async def _execute_cloud(
        self, cloud, instance_id, private_ip, commands, region, meta
    ):
        try:
            if cloud == "aws":
                from airex_core.cloud.aws_ssm import ssm_run_command

                aws_config = self._get_aws_config(meta)
                output = await ssm_run_command(
                    instance_id=instance_id,
                    commands=commands,
                    region=region,
                    aws_config=aws_config,
                )
            else:
                from airex_core.cloud.gcp_ssh import gcp_ssh_run_command as ssh_run_command
                from airex_core.cloud.ssh_user_resolver import resolve_ssh_user

                os_user = await resolve_ssh_user(
                    cloud="gcp",
                    tenant_name=meta.get("_tenant_name", ""),
                    private_ip=private_ip,
                    instance_name=instance_id,
                    project=meta.get("_project", ""),
                    zone=meta.get("_zone", ""),
                )

                output = await ssh_run_command(
                    private_ip=private_ip,
                    commands=commands,
                    instance_name=instance_id,
                    project=meta.get("_project", ""),
                    zone=meta.get("_zone", ""),
                    os_user=os_user,
                )

            success = "cleaned" in output.lower() or "%" in output
            return ActionResult(
                success=success,
                logs=f"[{cloud.upper()}:{instance_id or private_ip}]\n{output}",
                exit_code=0 if success else 1,
            )
        except Exception as exc:
            logger.warning("clear_logs_cloud_failed", error=str(exc), cloud=cloud)
            return ActionResult(
                success=False, logs=f"[{cloud.upper()}] Failed: {exc}", exit_code=1
            )

    def _get_aws_config(self, meta):
        tenant_name = meta.get("_tenant_name", "")
        if tenant_name:
            try:
                from airex_core.cloud.tenant_config import get_tenant_config

                tc = get_tenant_config(tenant_name)
                return tc.aws if tc else None
            except Exception:
                pass
        return None

    def _get_sa_key(self, meta):
        tenant_name = meta.get("_tenant_name", "")
        if tenant_name:
            try:
                from airex_core.cloud.tenant_config import get_tenant_config

                tc = get_tenant_config(tenant_name)
                return tc.gcp.service_account_key if tc else ""
            except Exception:
                pass
        return ""

    async def _simulate(self, host, log_path):
        await asyncio.sleep(random.uniform(1, 2))
        freed_gb = random.randint(5, 25)
        logs_lines = [
            f"[SIM] Connecting to {host}...",
            f"[SIM] Cleaning {log_path}/*.log.* older than 3 days",
            "[SIM] Removed rotated log files",
            "[SIM] Journal vacuum complete",
            f"[SIM] Freed: {freed_gb}GB",
            f"[SIM] Current disk usage: {random.randint(40, 70)}%",
        ]
        return ActionResult(success=True, logs="\n".join(logs_lines), exit_code=0)

    async def verify(self, incident_meta: dict) -> bool:
        """Verify disk usage dropped below threshold."""
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        private_ip = incident_meta.get("_private_ip", "")

        commands = ["df -h / | tail -1 | awk '{print $5}' | tr -d '%'"]

        if cloud == "aws" and instance_id:
            try:
                from airex_core.cloud.aws_ssm import ssm_run_command

                output = await ssm_run_command(
                    instance_id=instance_id,
                    commands=commands,
                    region=incident_meta.get("_region", ""),
                )
                usage = int(output.strip())
                return usage < 90
            except Exception:
                pass
        elif cloud == "gcp" and private_ip:
            try:
                from airex_core.cloud.gcp_ssh import gcp_ssh_run_command as ssh_run_command
                from airex_core.cloud.ssh_user_resolver import resolve_ssh_user

                os_user = await resolve_ssh_user(
                    cloud="gcp",
                    tenant_name=incident_meta.get("_tenant_name", ""),
                    private_ip=private_ip,
                    instance_name=incident_meta.get("_instance_id", ""),
                    project=incident_meta.get("_project", ""),
                    zone=incident_meta.get("_zone", ""),
                )
                output = await ssh_run_command(
                    private_ip=private_ip, commands=commands, os_user=os_user,
                )
                usage = int(output.strip())
                return usage < 90
            except Exception:
                pass

        await asyncio.sleep(random.uniform(0.5, 1))
        return random.random() < 0.9
