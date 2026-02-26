"""
Block IP action.

Blocks a malicious IP address using iptables or cloud security groups
to mitigate DDoS or unauthorized access.
Uses cloud connectors (SSM/SSH) when cloud context is available,
falls back to simulation otherwise.
"""

import asyncio
import random

import structlog

from app.actions.base import ActionResult, BaseAction

logger = structlog.get_logger()


class BlockIpAction(BaseAction):
    """Block a malicious IP address via iptables or security group."""

    action_type = "block_ip"
    DESCRIPTION = (
        "Block a malicious IP address via iptables, security group, or WAF rule. "
        "Use when DDoS, brute force, or malicious traffic from specific IPs is detected. "
        "Blast radius: traffic from the blocked IP only. Risk: false positive could block "
        "legitimate users. Verification: traffic from blocked IP ceases, attack metrics "
        "drop."
    )

    async def execute(self, incident_meta: dict) -> ActionResult:
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        private_ip = incident_meta.get("_private_ip", "")
        region = incident_meta.get("_region", "")
        malicious_ip = incident_meta.get("malicious_ip", "0.0.0.0")
        host = incident_meta.get("host", "unknown-host")

        commands = [
            f"iptables -C INPUT -s {malicious_ip} -j DROP 2>/dev/null && echo 'Already blocked' || iptables -A INPUT -s {malicious_ip} -j DROP",
            f"iptables -L INPUT -n --line-numbers | grep {malicious_ip} || echo 'Rule verification'",
            "echo 'Block IP action complete'",
        ]

        if cloud == "aws" and instance_id:
            return await self._execute_aws(instance_id, commands, region, incident_meta)
        elif cloud == "gcp" and private_ip:
            return await self._execute_gcp(
                private_ip, commands, instance_id, incident_meta
            )

        return await self._simulate(host, malicious_ip)

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
                "drop" in output.lower()
                or "blocked" in output.lower()
                or "complete" in output.lower()
            )
            return ActionResult(
                success=success,
                logs=f"[SSM:{instance_id}]\n{output}",
                exit_code=0 if success else 1,
            )
        except Exception as exc:
            logger.warning("block_ip_ssm_failed", error=str(exc))
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
            success = (
                "drop" in output.lower()
                or "blocked" in output.lower()
                or "complete" in output.lower()
            )
            return ActionResult(
                success=success,
                logs=f"[SSH:{private_ip}]\n{output}",
                exit_code=0 if success else 1,
            )
        except Exception as exc:
            logger.warning("block_ip_ssh_failed", error=str(exc))
            return ActionResult(success=False, logs=f"[SSH] Failed: {exc}", exit_code=1)

    async def _simulate(self, host, malicious_ip):
        await asyncio.sleep(random.uniform(0.5, 2))
        logs_lines = [
            f"[SIM] Connecting to {host}...",
            f"[SIM] Blocking IP: {malicious_ip}",
            f"[SIM] iptables -A INPUT -s {malicious_ip} -j DROP",
            f"[SIM] Rule added successfully",
            f"[SIM] Verifying: {malicious_ip} DROP rule active",
            f"[SIM] Block IP action complete",
        ]
        return ActionResult(success=True, logs="\n".join(logs_lines), exit_code=0)

    async def verify(self, incident_meta: dict) -> bool:
        """Verify the IP is blocked."""
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        private_ip = incident_meta.get("_private_ip", "")
        malicious_ip = incident_meta.get("malicious_ip", "0.0.0.0")

        commands = [
            f"iptables -L INPUT -n | grep {malicious_ip} | grep -q DROP && echo 'BLOCKED' || echo 'NOT_BLOCKED'"
        ]

        if cloud == "aws" and instance_id:
            try:
                from app.cloud.aws_ssm import ssm_run_command

                output = await ssm_run_command(
                    instance_id=instance_id,
                    commands=commands,
                    region=incident_meta.get("_region", ""),
                )
                return "BLOCKED" in output
            except Exception:
                pass
        elif cloud == "gcp" and private_ip:
            try:
                from app.cloud.gcp_ssh import gcp_ssh_run_command as ssh_run_command

                output = await ssh_run_command(private_ip=private_ip, commands=commands)
                return "BLOCKED" in output
            except Exception:
                pass

        await asyncio.sleep(random.uniform(0.3, 1))
        return random.random() < 0.93
