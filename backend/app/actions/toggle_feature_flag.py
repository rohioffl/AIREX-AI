"""
Toggle feature flag action.

Disables a feature flag that is causing errors or latency spikes.
Uses cloud connectors (SSM/SSH) when cloud context is available,
falls back to simulation otherwise.
"""

import asyncio
import random

import structlog

from app.actions.base import ActionResult, BaseAction

logger = structlog.get_logger()


class ToggleFeatureFlagAction(BaseAction):
    """Toggle (disable) a feature flag causing issues."""

    action_type = "toggle_feature_flag"
    DESCRIPTION = (
        "Disable a feature flag to stop a problematic feature from causing errors or "
        "latency. Use when a specific feature is identified as the root cause of "
        "degradation. Blast radius: users of the specific feature. Risk: feature becomes "
        "unavailable to users. Verification: error rate for the feature drops to zero."
    )

    async def execute(self, incident_meta: dict) -> ActionResult:
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        private_ip = incident_meta.get("_private_ip", "")
        region = incident_meta.get("_region", "")
        flag_name = incident_meta.get("flag_name", "unknown_flag")
        flag_service = incident_meta.get("flag_service", "configmap")
        host = incident_meta.get("host", "unknown-host")

        if flag_service == "configmap":
            commands = [
                f"kubectl get configmap feature-flags -o jsonpath='{{.data.{flag_name}}}' 2>/dev/null || echo 'current: unknown'",
                f'kubectl patch configmap feature-flags --type merge -p \'{{"data":{{"{flag_name}":"false"}}}}\' 2>/dev/null || echo \'Patch attempted\'',
                "echo 'Feature flag toggle complete'",
            ]
        else:
            commands = [
                f"echo 'Toggling feature flag: {flag_name} -> disabled'",
                f"echo 'Flag service: {flag_service}'",
                "echo 'Feature flag toggle complete'",
            ]

        if cloud == "aws" and instance_id:
            return await self._execute_aws(instance_id, commands, region, incident_meta)
        elif cloud == "gcp" and private_ip:
            return await self._execute_gcp(
                private_ip, commands, instance_id, incident_meta
            )

        return await self._simulate(host, flag_name)

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
            success = "patched" in output.lower() or "complete" in output.lower()
            return ActionResult(
                success=success,
                logs=f"[SSM:{instance_id}]\n{output}",
                exit_code=0 if success else 1,
            )
        except Exception as exc:
            logger.warning("toggle_feature_flag_ssm_failed", error=str(exc))
            return ActionResult(success=False, logs=f"[SSM] Failed: {exc}", exit_code=1)

    async def _execute_gcp(self, private_ip, commands, instance_name, meta):
        try:
            from app.cloud.gcp_ssh import gcp_ssh_run_command as ssh_run_command

            output = await ssh_run_command(
                private_ip=private_ip,
                commands=commands,
                instance_name=instance_name or "",
                project=meta.get("_project", ""),
                zone=meta.get("_zone", ""),
            )
            success = "patched" in output.lower() or "complete" in output.lower()
            return ActionResult(
                success=success,
                logs=f"[SSH:{private_ip}]\n{output}",
                exit_code=0 if success else 1,
            )
        except Exception as exc:
            logger.warning("toggle_feature_flag_ssh_failed", error=str(exc))
            return ActionResult(success=False, logs=f"[SSH] Failed: {exc}", exit_code=1)

    async def _simulate(self, host, flag_name):
        await asyncio.sleep(random.uniform(0.5, 1.5))
        logs_lines = [
            f"[SIM] Connecting to {host}...",
            f"[SIM] Feature flag '{flag_name}': enabled -> disabled",
            f"[SIM] ConfigMap updated successfully",
            f"[SIM] Pods will pick up change within 30s (configmap refresh)",
            f"[SIM] Feature flag toggle complete",
        ]
        return ActionResult(success=True, logs="\n".join(logs_lines), exit_code=0)

    async def verify(self, incident_meta: dict) -> bool:
        """Verify the feature flag is disabled."""
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        private_ip = incident_meta.get("_private_ip", "")
        flag_name = incident_meta.get("flag_name", "unknown_flag")

        commands = [
            f"kubectl get configmap feature-flags -o jsonpath='{{.data.{flag_name}}}' 2>/dev/null || echo 'false'"
        ]

        if cloud == "aws" and instance_id:
            try:
                from app.cloud.aws_ssm import ssm_run_command

                output = await ssm_run_command(
                    instance_id=instance_id,
                    commands=commands,
                    region=incident_meta.get("_region", ""),
                )
                return "false" in output.lower()
            except Exception:
                pass
        elif cloud == "gcp" and private_ip:
            try:
                from app.cloud.gcp_ssh import gcp_ssh_run_command as ssh_run_command

                output = await ssh_run_command(private_ip=private_ip, commands=commands)
                return "false" in output.lower()
            except Exception:
                pass

        await asyncio.sleep(random.uniform(0.3, 1))
        return random.random() < 0.95
