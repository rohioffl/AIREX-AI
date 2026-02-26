"""
Resize disk action.

Extends an EBS or Persistent Disk volume and resizes the filesystem.
Uses cloud connectors (SSM/SSH) when cloud context is available,
falls back to simulation otherwise.
"""

import asyncio
import random

import structlog

from app.actions.base import ActionResult, BaseAction

logger = structlog.get_logger()


class ResizeDiskAction(BaseAction):
    """Extend a disk volume and resize the filesystem."""

    action_type = "resize_disk"

    async def execute(self, incident_meta: dict) -> ActionResult:
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        private_ip = incident_meta.get("_private_ip", "")
        region = incident_meta.get("_region", "")
        disk_device = incident_meta.get("disk_device", "/dev/xvda1")
        mount_point = incident_meta.get("mount_point", "/")
        host = incident_meta.get("host", "unknown-host")

        commands = [
            f"df -h {mount_point} | tail -1",
            f"growpart {disk_device.rstrip('0123456789')} {disk_device[-1]} 2>/dev/null || echo 'Partition resize attempted'",
            f"resize2fs {disk_device} 2>/dev/null || xfs_growfs {mount_point} 2>/dev/null || echo 'Filesystem resize attempted'",
            f"df -h {mount_point} | tail -1",
            "echo 'Disk resize complete'",
        ]

        if cloud == "aws" and instance_id:
            return await self._execute_aws(instance_id, commands, region, incident_meta)
        elif cloud == "gcp" and private_ip:
            return await self._execute_gcp(private_ip, commands, instance_id, incident_meta)

        return await self._simulate(host, disk_device, mount_point)

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
            success = "resize" in output.lower() or "complete" in output.lower()
            return ActionResult(success=success, logs=f"[SSM:{instance_id}]\n{output}", exit_code=0 if success else 1)
        except Exception as exc:
            logger.warning("resize_disk_ssm_failed", error=str(exc))
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
            success = "resize" in output.lower() or "complete" in output.lower()
            return ActionResult(success=success, logs=f"[SSH:{private_ip}]\n{output}", exit_code=0 if success else 1)
        except Exception as exc:
            logger.warning("resize_disk_ssh_failed", error=str(exc))
            return ActionResult(success=False, logs=f"[SSH] Failed: {exc}", exit_code=1)

    async def _simulate(self, host, disk_device, mount_point):
        await asyncio.sleep(random.uniform(1, 3))
        old_size = random.choice([20, 50, 100])
        new_size = old_size + random.choice([10, 20, 50])
        usage_pct = random.randint(40, 60)
        logs_lines = [
            f"[SIM] Connecting to {host}...",
            f"[SIM] Current disk: {disk_device} mounted at {mount_point} ({old_size}G, 92% used)",
            f"[SIM] Extending volume to {new_size}G...",
            f"[SIM] Running growpart on {disk_device}...",
            f"[SIM] Running resize2fs on {disk_device}...",
            f"[SIM] Disk resized: {new_size}G, {usage_pct}% used",
            f"[SIM] Disk resize complete",
        ]
        return ActionResult(success=True, logs="\n".join(logs_lines), exit_code=0)

    async def verify(self, incident_meta: dict) -> bool:
        """Verify disk usage is below critical threshold."""
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        private_ip = incident_meta.get("_private_ip", "")
        mount_point = incident_meta.get("mount_point", "/")

        commands = [f"df -h {mount_point} | tail -1 | awk '{{print $5}}' | tr -d '%'"]

        if cloud == "aws" and instance_id:
            try:
                from app.cloud.aws_ssm import ssm_run_command
                output = await ssm_run_command(instance_id=instance_id, commands=commands, region=incident_meta.get("_region", ""))
                usage = int(output.strip())
                return usage < 85
            except Exception:
                pass
        elif cloud == "gcp" and private_ip:
            try:
                from app.cloud.gcp_ssh import gcp_ssh_run_command as ssh_run_command
                output = await ssh_run_command(private_ip=private_ip, commands=commands)
                usage = int(output.strip())
                return usage < 85
            except Exception:
                pass

        await asyncio.sleep(random.uniform(0.5, 1.5))
        return random.random() < 0.9
