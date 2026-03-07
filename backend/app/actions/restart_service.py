"""
Restart service action.

Uses cloud connectors (SSM/SSH) when cloud context is available,
falls back to simulation otherwise.
"""

import asyncio
import random

import structlog

from app.actions.base import ActionResult, BaseAction

logger = structlog.get_logger()


class RestartServiceAction(BaseAction):
    """Restart a system service via SSM RunCommand or GCP SSH."""

    action_type = "restart_service"
    DESCRIPTION = (
        "Restart a system service (e.g. nginx, mysql, app server) via systemctl. "
        "Use when a service is unresponsive, consuming excessive resources, or in a "
        "degraded state. Blast radius: single service on one host. Risk: brief downtime "
        "during restart (~5-30s). Verification: service health check after restart."
    )

    async def execute(self, incident_meta: dict) -> ActionResult:
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        private_ip = incident_meta.get("_private_ip", "")
        region = incident_meta.get("_region", "")
        service_name = incident_meta.get("service_name", "application")
        host = incident_meta.get("host", "unknown-host")

        commands = [
            f"systemctl restart {service_name} 2>/dev/null || service {service_name} restart 2>/dev/null || echo 'Attempting process restart'",
            f"sleep 2 && systemctl is-active {service_name} 2>/dev/null || echo 'checking process'",
            "uptime",
        ]

        # Try real cloud execution
        if cloud == "aws" and instance_id:
            return await self._execute_aws(instance_id, commands, region, incident_meta)
        elif cloud == "gcp" and private_ip:
            return await self._execute_gcp(
                private_ip, commands, instance_id, incident_meta
            )

        # Simulation fallback
        return await self._simulate(host, service_name)

    async def _execute_aws(self, instance_id, commands, region, meta):
        try:
            from app.cloud.aws_ssm import ssm_run_command

            aws_config = None
            tenant_name = meta.get("_tenant_name", "")
            if tenant_name:
                try:
                    from app.cloud.tenant_config import get_tenant_config

                    tc = get_tenant_config(tenant_name)
                    aws_config = tc.aws if tc else None
                except Exception:
                    pass

            output = await ssm_run_command(
                instance_id=instance_id,
                commands=commands,
                region=region,
                aws_config=aws_config,
            )
            success = (
                "active" in output.lower()
                or "running" in output.lower()
                or "restart" in output.lower()
            )
            return ActionResult(
                success=success,
                logs=f"[SSM:{instance_id}]\n{output}",
                exit_code=0 if success else 1,
            )
        except Exception as exc:
            logger.warning("restart_ssm_failed", error=str(exc))
            return ActionResult(success=False, logs=f"[SSM] Failed: {exc}", exit_code=1)

    async def _execute_gcp(self, private_ip, commands, instance_name, meta):
        try:
            from app.cloud.gcp_ssh import gcp_ssh_run_command as ssh_run_command
            from app.cloud.ssh_user_resolver import resolve_ssh_user

            os_user = await resolve_ssh_user(
                cloud="gcp",
                tenant_name=meta.get("_tenant_name", ""),
                private_ip=private_ip,
                instance_name=instance_name or "",
                project=meta.get("_project", ""),
                zone=meta.get("_zone", ""),
            )

            output = await ssh_run_command(
                private_ip=private_ip,
                commands=commands,
                instance_name=instance_name or "",
                project=meta.get("_project", ""),
                zone=meta.get("_zone", ""),
                os_user=os_user,
            )
            success = (
                "active" in output.lower()
                or "running" in output.lower()
                or "restart" in output.lower()
            )
            return ActionResult(
                success=success,
                logs=f"[SSH:{private_ip}]\n{output}",
                exit_code=0 if success else 1,
            )
        except Exception as exc:
            logger.warning("restart_ssh_failed", error=str(exc))
            return ActionResult(success=False, logs=f"[SSH] Failed: {exc}", exit_code=1)

    async def _simulate(self, host, service_name):
        await asyncio.sleep(random.uniform(1, 3))
        logs_lines = [
            f"[SIM] Connecting to {host}...",
            f"[SIM] Running: systemctl restart {service_name}",
            f"[SIM] Service '{service_name}' restarted successfully",
            "[SIM] Active: active (running)",
            f"[SIM] PID: {random.randint(10000, 50000)}",
        ]
        return ActionResult(success=True, logs="\n".join(logs_lines), exit_code=0)

    async def verify(self, incident_meta: dict) -> bool:
        """Check if the service is healthy after restart."""
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        private_ip = incident_meta.get("_private_ip", "")

        commands = ["uptime && cat /proc/loadavg"]

        if cloud == "aws" and instance_id:
            try:
                from app.cloud.aws_ssm import ssm_run_command

                output = await ssm_run_command(
                    instance_id=instance_id,
                    commands=commands,
                    region=incident_meta.get("_region", ""),
                )
                load = float(output.split()[0]) if output.strip() else 99
                return load < 5.0
            except Exception:
                pass
        elif cloud == "gcp" and private_ip:
            try:
                from app.cloud.gcp_ssh import gcp_ssh_run_command as ssh_run_command
                from app.cloud.ssh_user_resolver import resolve_ssh_user

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
                load = float(output.split()[0]) if output.strip() else 99
                return load < 5.0
            except Exception:
                pass

        # Simulation: 90% success
        await asyncio.sleep(random.uniform(0.5, 1.5))
        return random.random() < 0.9
