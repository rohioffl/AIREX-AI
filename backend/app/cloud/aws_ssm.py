"""
AWS Systems Manager (SSM) connector.

Sends RunShellScript commands to EC2 instances via SSM.
Requires:
  - AIREX host has an IAM role with ssm:SendCommand + ssm:GetCommandInvocation
  - Target EC2 instance has SSM Agent running + IAM role with AmazonSSMManagedInstanceCore
  - No SSH keys needed — all auth is via IAM roles.

Supports per-tenant authentication via AWSConfig (role assumption, static keys, etc.).
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import structlog

from app.core.config import settings

if TYPE_CHECKING:
    from app.cloud.tenant_config import AWSConfig

logger = structlog.get_logger()


async def ssm_run_command(
    instance_id: str,
    commands: list[str],
    region: str = "",
    timeout: int = 0,
    aws_config: AWSConfig | None = None,
) -> str:
    """
    Execute shell commands on an EC2 instance via SSM RunShellScript.

    Args:
        instance_id: EC2 instance ID (e.g. "i-0abc123def456")
        commands: List of shell commands to run
        region: AWS region (defaults to settings.AWS_REGION)
        timeout: Max seconds to wait (defaults to settings.AWS_SSM_TIMEOUT)
        aws_config: Per-tenant AWS config for authentication

    Returns:
        Combined stdout from the command execution.

    Raises:
        RuntimeError: If SSM command fails or times out.
    """
    from app.cloud.aws_auth import get_aws_client

    timeout = timeout or settings.AWS_SSM_TIMEOUT
    effective_region = region or (aws_config.region if aws_config else "") or settings.AWS_REGION
    ssm_document = (aws_config.ssm_document if aws_config else "") or settings.AWS_SSM_DOCUMENT

    log = logger.bind(instance_id=instance_id, region=effective_region)
    log.info("ssm_sending_command", commands=commands[:3])

    loop = asyncio.get_event_loop()

    try:
        client = await loop.run_in_executor(
            None,
            lambda: get_aws_client("ssm", aws_config, region=effective_region),
        )

        response = await loop.run_in_executor(
            None,
            lambda: client.send_command(
                InstanceIds=[instance_id],
                DocumentName=ssm_document,
                Parameters={"commands": commands},
                TimeoutSeconds=timeout,
                Comment=f"AIREX investigation on {instance_id}",
            ),
        )

        command_id = response["Command"]["CommandId"]
        log.info("ssm_command_sent", command_id=command_id)

        output = await _wait_for_command(client, command_id, instance_id, timeout, loop)
        log.info("ssm_command_complete", output_length=len(output))
        return output

    except Exception as exc:
        log.error("ssm_command_failed", error=str(exc))
        raise RuntimeError(f"SSM command failed on {instance_id}: {exc}") from exc


async def _wait_for_command(
    client,
    command_id: str,
    instance_id: str,
    timeout: int,
    loop: asyncio.AbstractEventLoop,
) -> str:
    """Poll SSM until command completes or times out."""
    start = time.monotonic()
    poll_interval = 2.0

    while True:
        elapsed = time.monotonic() - start
        if elapsed > timeout:
            raise RuntimeError(
                f"SSM command {command_id} timed out after {timeout}s"
            )

        await asyncio.sleep(poll_interval)

        result = await loop.run_in_executor(
            None,
            lambda: client.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id,
            ),
        )

        status = result["Status"]

        if status == "Success":
            stdout = result.get("StandardOutputContent", "")
            stderr = result.get("StandardErrorContent", "")
            if stderr:
                stdout += f"\n--- STDERR ---\n{stderr}"
            return stdout

        if status in ("Failed", "Cancelled", "TimedOut"):
            error_msg = result.get("StandardErrorContent", "Unknown error")
            raise RuntimeError(
                f"SSM command {status}: {error_msg}"
            )

        # Still running — increase poll interval slightly
        poll_interval = min(poll_interval * 1.2, 5.0)


async def ssm_check_instance_managed(
    instance_id: str,
    region: str = "",
    aws_config: "AWSConfig | None" = None,
) -> bool:
    """Check if an instance is managed by SSM (has SSM agent running)."""
    from app.cloud.aws_auth import get_aws_client

    loop = asyncio.get_event_loop()
    try:
        client = await loop.run_in_executor(
            None,
            lambda: get_aws_client("ssm", aws_config, region=region),
        )
        response = await loop.run_in_executor(
            None,
            lambda: client.describe_instance_information(
                Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
            ),
        )
        instances = response.get("InstanceInformationList", [])
        return len(instances) > 0 and instances[0].get("PingStatus") == "Online"
    except Exception:
        return False
