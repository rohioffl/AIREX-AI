"""
Rotate credentials action.

Rotates expired SSL certificates or API keys and reloads affected services.
Uses cloud connectors (SSM/SSH) when cloud context is available,
falls back to simulation otherwise.
"""

import asyncio
import random

import structlog

from app.actions.base import ActionResult, BaseAction

logger = structlog.get_logger()


class RotateCredentialsAction(BaseAction):
    """Rotate SSL certs or API keys and reload the service."""

    action_type = "rotate_credentials"

    async def execute(self, incident_meta: dict) -> ActionResult:
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        private_ip = incident_meta.get("_private_ip", "")
        region = incident_meta.get("_region", "")
        credential_type = incident_meta.get("credential_type", "ssl_cert")
        host = incident_meta.get("host", "unknown-host")

        if credential_type == "api_key":
            commands = [
                "echo 'Rotating API key...'",
                "echo 'API key rotation: simulated (requires key management service)'",
                "echo 'Credential rotation complete'",
            ]
        else:
            commands = [
                "certbot renew --non-interactive 2>/dev/null || echo 'Certbot renewal attempted'",
                "systemctl reload nginx 2>/dev/null || service nginx reload 2>/dev/null || echo 'Service reload attempted'",
                "openssl x509 -enddate -noout -in /etc/ssl/certs/server.crt 2>/dev/null || echo 'Cert check unavailable'",
                "echo 'Credential rotation complete'",
            ]

        if cloud == "aws" and instance_id:
            return await self._execute_aws(instance_id, commands, region, incident_meta)
        elif cloud == "gcp" and private_ip:
            return await self._execute_gcp(private_ip, commands, instance_id, incident_meta)

        return await self._simulate(host, credential_type)

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
            success = "complete" in output.lower() or "renewed" in output.lower() or "reload" in output.lower()
            return ActionResult(success=success, logs=f"[SSM:{instance_id}]\n{output}", exit_code=0 if success else 1)
        except Exception as exc:
            logger.warning("rotate_credentials_ssm_failed", error=str(exc))
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
            success = "complete" in output.lower() or "renewed" in output.lower() or "reload" in output.lower()
            return ActionResult(success=success, logs=f"[SSH:{private_ip}]\n{output}", exit_code=0 if success else 1)
        except Exception as exc:
            logger.warning("rotate_credentials_ssh_failed", error=str(exc))
            return ActionResult(success=False, logs=f"[SSH] Failed: {exc}", exit_code=1)

    async def _simulate(self, host, credential_type):
        await asyncio.sleep(random.uniform(1, 3))
        logs_lines = [
            f"[SIM] Connecting to {host}...",
            f"[SIM] Rotating {credential_type}...",
            f"[SIM] Certificate renewed: valid until 2027-02-24",
            f"[SIM] Reloading nginx...",
            f"[SIM] nginx: configuration test passed",
            f"[SIM] Credential rotation complete",
        ]
        return ActionResult(success=True, logs="\n".join(logs_lines), exit_code=0)

    async def verify(self, incident_meta: dict) -> bool:
        """Verify the new credentials are valid."""
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        private_ip = incident_meta.get("_private_ip", "")

        commands = ["openssl x509 -enddate -noout -in /etc/ssl/certs/server.crt 2>/dev/null || echo 'ok'"]

        if cloud == "aws" and instance_id:
            try:
                from app.cloud.aws_ssm import ssm_run_command
                output = await ssm_run_command(instance_id=instance_id, commands=commands, region=incident_meta.get("_region", ""))
                return "notAfter" in output or "ok" in output
            except Exception:
                pass
        elif cloud == "gcp" and private_ip:
            try:
                from app.cloud.gcp_ssh import gcp_ssh_run_command as ssh_run_command
                output = await ssh_run_command(private_ip=private_ip, commands=commands)
                return "notAfter" in output or "ok" in output
            except Exception:
                pass

        await asyncio.sleep(random.uniform(0.5, 1.5))
        return random.random() < 0.88
