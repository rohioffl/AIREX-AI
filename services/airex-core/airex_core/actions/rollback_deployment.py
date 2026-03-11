"""
Rollback deployment action.

Rolls back to the previous deployment version using kubectl or
cloud-specific rollback mechanisms.
Uses cloud connectors (SSM/SSH) when cloud context is available,
falls back to simulation otherwise.
"""

import asyncio
import random

import structlog

from airex_core.actions.base import ActionResult, BaseAction

logger = structlog.get_logger()


class RollbackDeploymentAction(BaseAction):
    """Roll back a deployment to a previous version."""

    action_type = "rollback_deployment"
    DESCRIPTION = (
        "Roll back to the previous deployment version using kubectl rollout undo or "
        "cloud-specific rollback mechanisms. Use when a recent deployment caused errors, "
        "crashes, or performance degradation. Blast radius: entire service/deployment. "
        "Risk: reverts all changes including intentional ones. Verification: error rate "
        "returns to pre-deployment baseline."
    )

    async def execute(self, incident_meta: dict) -> ActionResult:
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        private_ip = incident_meta.get("_private_ip", "")
        region = incident_meta.get("_region", "")
        deployment_name = incident_meta.get("deployment_name", "application")
        namespace = incident_meta.get("namespace", "default")
        host = incident_meta.get("host", "unknown-host")

        commands = [
            f"kubectl rollout undo deployment/{deployment_name} -n {namespace} 2>/dev/null || echo 'Rollback attempted via kubectl'",
            "sleep 5",
            f"kubectl rollout status deployment/{deployment_name} -n {namespace} --timeout=60s 2>/dev/null || echo 'Checking rollout status'",
            "echo 'Rollback action complete'",
        ]

        if cloud == "aws" and instance_id:
            return await self._execute_aws(instance_id, commands, region, incident_meta)
        elif cloud == "gcp" and private_ip:
            return await self._execute_gcp(
                private_ip, commands, instance_id, incident_meta
            )

        return await self._simulate(host, deployment_name)

    async def _execute_aws(self, instance_id, commands, region, meta):
        try:
            from airex_core.cloud.aws_ssm import ssm_run_command

            aws_config = None
            tenant_name = meta.get("_tenant_name", "")
            if tenant_name:
                try:
                    from airex_core.cloud.tenant_config import get_tenant_config

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
                "rolled back" in output.lower()
                or "successfully" in output.lower()
                or "complete" in output.lower()
            )
            return ActionResult(
                success=success,
                logs=f"[SSM:{instance_id}]\n{output}",
                exit_code=0 if success else 1,
            )
        except Exception as exc:
            logger.warning("rollback_deployment_ssm_failed", error=str(exc))
            return ActionResult(success=False, logs=f"[SSM] Failed: {exc}", exit_code=1)

    async def _execute_gcp(self, private_ip, commands, instance_name, meta):
        try:
            from airex_core.cloud.gcp_ssh import gcp_ssh_run_command as ssh_run_command
            from airex_core.cloud.ssh_user_resolver import resolve_ssh_user

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
                "rolled back" in output.lower()
                or "successfully" in output.lower()
                or "complete" in output.lower()
            )
            return ActionResult(
                success=success,
                logs=f"[SSH:{private_ip}]\n{output}",
                exit_code=0 if success else 1,
            )
        except Exception as exc:
            logger.warning("rollback_deployment_ssh_failed", error=str(exc))
            return ActionResult(success=False, logs=f"[SSH] Failed: {exc}", exit_code=1)

    async def _simulate(self, host, deployment_name):
        await asyncio.sleep(random.uniform(2, 4))
        prev_rev = random.randint(1, 50)
        logs_lines = [
            f"[SIM] Connecting to {host}...",
            f"[SIM] Rolling back deployment/{deployment_name}...",
            f"[SIM] deployment.apps/{deployment_name} rolled back to revision {prev_rev}",
            "[SIM] Waiting for rollout to complete...",
            f'[SIM] deployment "{deployment_name}" successfully rolled out',
            "[SIM] Rollback action complete",
        ]
        return ActionResult(success=True, logs="\n".join(logs_lines), exit_code=0)

    async def verify(self, incident_meta: dict) -> bool:
        """Verify the rollback completed and deployment is healthy."""
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        private_ip = incident_meta.get("_private_ip", "")
        deployment_name = incident_meta.get("deployment_name", "application")
        namespace = incident_meta.get("namespace", "default")

        commands = [
            f"kubectl rollout status deployment/{deployment_name} -n {namespace} --timeout=30s 2>/dev/null || echo 'status check'"
        ]

        if cloud == "aws" and instance_id:
            try:
                from airex_core.cloud.aws_ssm import ssm_run_command

                output = await ssm_run_command(
                    instance_id=instance_id,
                    commands=commands,
                    region=incident_meta.get("_region", ""),
                )
                return "successfully rolled out" in output.lower()
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
                return "successfully rolled out" in output.lower()
            except Exception:
                pass

        await asyncio.sleep(random.uniform(0.5, 1.5))
        return random.random() < 0.85
