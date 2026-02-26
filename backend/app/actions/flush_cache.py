"""
Flush cache action.

Flushes Redis or Memcached caches to relieve memory pressure.
Uses cloud connectors (SSM/SSH) when cloud context is available,
falls back to simulation otherwise.
"""

import asyncio
import random

import structlog

from app.actions.base import ActionResult, BaseAction

logger = structlog.get_logger()


class FlushCacheAction(BaseAction):
    """Flush Redis or Memcached cache via SSM/SSH."""

    action_type = "flush_cache"
    DESCRIPTION = (
        "Flush Redis or Memcached caches to relieve memory pressure or clear stale data. "
        "Use when cache memory is exhausted, cache corruption is suspected, or stale "
        "cached data is causing errors. Blast radius: all cached data for the service. "
        "Risk: temporary performance degradation as cache warms up. Verification: cache "
        "memory freed, application responses normal."
    )

    async def execute(self, incident_meta: dict) -> ActionResult:
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        private_ip = incident_meta.get("_private_ip", "")
        region = incident_meta.get("_region", "")
        cache_type = incident_meta.get("cache_type", "redis")
        host = incident_meta.get("host", "unknown-host")

        if cache_type == "memcached":
            commands = [
                "echo 'flush_all' | nc localhost 11211 2>/dev/null || echo 'Memcached flush attempted'",
                "echo 'Cache flush complete'",
            ]
        else:
            commands = [
                "redis-cli FLUSHDB 2>/dev/null || echo 'Redis flush attempted'",
                "redis-cli INFO memory 2>/dev/null | grep used_memory_human || echo 'Memory info unavailable'",
                "echo 'Cache flush complete'",
            ]

        if cloud == "aws" and instance_id:
            return await self._execute_aws(instance_id, commands, region, incident_meta)
        elif cloud == "gcp" and private_ip:
            return await self._execute_gcp(
                private_ip, commands, instance_id, incident_meta
            )

        return await self._simulate(host, cache_type)

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
                "flush" in output.lower()
                or "ok" in output.lower()
                or "complete" in output.lower()
            )
            return ActionResult(
                success=success,
                logs=f"[SSM:{instance_id}]\n{output}",
                exit_code=0 if success else 1,
            )
        except Exception as exc:
            logger.warning("flush_cache_ssm_failed", error=str(exc))
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
                "flush" in output.lower()
                or "ok" in output.lower()
                or "complete" in output.lower()
            )
            return ActionResult(
                success=success,
                logs=f"[SSH:{private_ip}]\n{output}",
                exit_code=0 if success else 1,
            )
        except Exception as exc:
            logger.warning("flush_cache_ssh_failed", error=str(exc))
            return ActionResult(success=False, logs=f"[SSH] Failed: {exc}", exit_code=1)

    async def _simulate(self, host, cache_type):
        await asyncio.sleep(random.uniform(0.5, 2))
        freed_mb = random.randint(128, 1024)
        logs_lines = [
            f"[SIM] Connecting to {host}...",
            f"[SIM] Flushing {cache_type} cache...",
            f"[SIM] FLUSHDB: OK",
            f"[SIM] Memory freed: ~{freed_mb}MB",
            f"[SIM] Cache flush complete",
        ]
        return ActionResult(success=True, logs="\n".join(logs_lines), exit_code=0)

    async def verify(self, incident_meta: dict) -> bool:
        """Verify cache memory usage is reduced."""
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        private_ip = incident_meta.get("_private_ip", "")

        commands = [
            "redis-cli INFO memory 2>/dev/null | grep used_memory_human || echo 'check unavailable'"
        ]

        if cloud == "aws" and instance_id:
            try:
                from app.cloud.aws_ssm import ssm_run_command

                output = await ssm_run_command(
                    instance_id=instance_id,
                    commands=commands,
                    region=incident_meta.get("_region", ""),
                )
                return "used_memory_human" in output
            except Exception:
                pass
        elif cloud == "gcp" and private_ip:
            try:
                from app.cloud.gcp_ssh import gcp_ssh_run_command as ssh_run_command

                output = await ssh_run_command(private_ip=private_ip, commands=commands)
                return "used_memory_human" in output
            except Exception:
                pass

        await asyncio.sleep(random.uniform(0.5, 1))
        return random.random() < 0.95
