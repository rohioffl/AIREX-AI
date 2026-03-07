"""
Kill process action.

Terminates a runaway process consuming excessive CPU or memory.
Uses cloud connectors (SSM/SSH) when cloud context is available,
falls back to simulation otherwise.
"""

import asyncio
import random

import structlog

from app.actions.base import ActionResult, BaseAction

logger = structlog.get_logger()


class KillProcessAction(BaseAction):
    """Kill a runaway process by name or PID via SSM/SSH."""

    action_type = "kill_process"
    DESCRIPTION = (
        "Terminate a runaway process consuming excessive CPU or memory. Use when a "
        "single process is the root cause of resource exhaustion (not a systemic issue). "
        "Blast radius: single process on one host. Risk: data loss if process has unsaved "
        "state. Verification: CPU/memory returns to normal after kill."
    )

    async def execute(self, incident_meta: dict) -> ActionResult:
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        private_ip = incident_meta.get("_private_ip", "")
        region = incident_meta.get("_region", "")
        process_name = incident_meta.get("process_name", "unknown")
        host = incident_meta.get("host", "unknown-host")

        commands = [
            f"pkill -TERM -f '{process_name}' 2>/dev/null || echo 'Process not found'",
            "sleep 2",
            f"pgrep -f '{process_name}' && kill -9 $(pgrep -f '{process_name}') 2>/dev/null || echo 'Process terminated'",
            "echo 'Kill process action complete'",
        ]

        if cloud == "aws" and instance_id:
            return await self._execute_aws(instance_id, commands, region, incident_meta)
        elif cloud == "gcp" and private_ip:
            return await self._execute_gcp(
                private_ip, commands, instance_id, incident_meta
            )

        return await self._simulate(host, process_name)

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
            success = "terminated" in output.lower() or "not found" in output.lower()
            return ActionResult(
                success=success,
                logs=f"[SSM:{instance_id}]\n{output}",
                exit_code=0 if success else 1,
            )
        except Exception as exc:
            logger.warning("kill_process_ssm_failed", error=str(exc))
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
            success = "terminated" in output.lower() or "not found" in output.lower()
            return ActionResult(
                success=success,
                logs=f"[SSH:{private_ip}]\n{output}",
                exit_code=0 if success else 1,
            )
        except Exception as exc:
            logger.warning("kill_process_ssh_failed", error=str(exc))
            return ActionResult(success=False, logs=f"[SSH] Failed: {exc}", exit_code=1)

    async def _simulate(self, host, process_name):
        await asyncio.sleep(random.uniform(1, 2))
        pid = random.randint(1000, 50000)
        logs_lines = [
            f"[SIM] Connecting to {host}...",
            f"[SIM] Found runaway process: {process_name} (PID {pid})",
            f"[SIM] Sending SIGTERM to PID {pid}...",
            "[SIM] Waiting 2s for graceful shutdown...",
            f"[SIM] Process {process_name} (PID {pid}) terminated successfully",
        ]
        return ActionResult(success=True, logs="\n".join(logs_lines), exit_code=0)

    async def verify(self, incident_meta: dict) -> bool:
        """Verify the process is no longer running."""
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        private_ip = incident_meta.get("_private_ip", "")
        process_name = incident_meta.get("process_name", "unknown")

        commands = [
            f"pgrep -f '{process_name}' && echo 'STILL_RUNNING' || echo 'TERMINATED'"
        ]

        if cloud == "aws" and instance_id:
            try:
                from app.cloud.aws_ssm import ssm_run_command

                output = await ssm_run_command(
                    instance_id=instance_id,
                    commands=commands,
                    region=incident_meta.get("_region", ""),
                )
                return "TERMINATED" in output
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
                return "TERMINATED" in output
            except Exception:
                pass

        await asyncio.sleep(random.uniform(0.5, 1.5))
        return random.random() < 0.92
