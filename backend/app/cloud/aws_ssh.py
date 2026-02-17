"""
AWS EC2 Instance Connect SSH — no stored keys.

Like GCP's gcloud compute ssh / OS Login: use IAM to push a temporary SSH key
to the instance via the EC2 Instance Connect API. Key lives 60 seconds.
No SSH keys are stored anywhere.

We cache the last pushed key per (instance_id, os_user) for 55 seconds and
reuse it for repeat connections. That avoids repeatedly calling SendSSHPublicKey
(which could otherwise accumulate keys or hit rate limits).
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from typing import TYPE_CHECKING

import structlog

from app.core.config import settings

if TYPE_CHECKING:
    from app.cloud.tenant_config import AWSConfig

logger = structlog.get_logger()

# Key valid 60s per AWS; we reuse for 55s to avoid pushing a new key every time.
_EC2_CONNECT_KEY_REUSE_SEC = 55

# In-process cache: (instance_id, os_user) -> (pushed_at, priv_pem, pub_key). Locked.
_ec2_connect_key_cache: dict[tuple[str, str], tuple[float, bytes, str]] = {}
_ec2_connect_cache_lock = asyncio.Lock()


async def get_instance_availability_zone(
    instance_id: str,
    region: str,
    aws_config: "AWSConfig | None" = None,
) -> str:
    """Resolve EC2 instance ID to its Availability Zone (e.g. ap-south-1a)."""
    from app.cloud.aws_auth import get_aws_client

    loop = asyncio.get_event_loop()
    try:
        client = await loop.run_in_executor(
            None,
            lambda: get_aws_client("ec2", aws_config, region=region),
        )
        resp = await loop.run_in_executor(
            None,
            lambda: client.describe_instances(
                InstanceIds=[instance_id],
            ),
        )
        for r in resp.get("Reservations", []):
            for inst in r.get("Instances", []):
                az = inst.get("Placement", {}).get("AvailabilityZone", "")
                if az:
                    return az
    except Exception as exc:
        logger.debug("aws_get_az_failed", instance_id=instance_id, error=str(exc))
    return ""


async def aws_ec2_connect_run_command(
    private_ip: str,
    instance_id: str,
    zone: str,
    commands: list[str],
    region: str = "",
    aws_config: "AWSConfig | None" = None,
    os_user: str = "",
    timeout: int = 0,
) -> str:
    """
    Run commands on an EC2 instance via EC2 Instance Connect (no stored keys).

    Pushes a one-time SSH public key via the AWS API, connects with the matching
    private key, runs commands, disconnects. Key is discarded.

    Args:
        private_ip: Instance private IP (to open SSH connection).
        instance_id: EC2 instance ID (e.g. i-0abc123).
        zone: Availability zone (e.g. ap-south-1a) — required by SendSSHPublicKey.
        commands: Shell commands to run.
        region: AWS region (default from config).
        aws_config: Per-tenant AWS config for auth.
        os_user: OS user (e.g. ubuntu, ec2-user). Default from tenant or ubuntu.
        timeout: SSH connect/command timeout in seconds.

    Returns:
        Combined stdout/stderr from the commands.

    Raises:
        RuntimeError: If key push or SSH fails.
    """
    import asyncssh

    from app.cloud.aws_auth import get_aws_client

    timeout = timeout or settings.SSH_TIMEOUT
    os_user = os_user or settings.SSH_USER or "ubuntu"
    effective_region = region or (aws_config.region if aws_config else "") or settings.AWS_REGION or "us-east-1"

    log = logger.bind(
        instance_id=instance_id,
        private_ip=private_ip,
        zone=zone,
        os_user=os_user,
    )

    loop = asyncio.get_event_loop()
    now = time.monotonic()
    cache_key = (instance_id, os_user)
    priv_pem: bytes
    pub_key: str

    async with _ec2_connect_cache_lock:
        entry = _ec2_connect_key_cache.get(cache_key)
        if entry:
            pushed_at, cached_priv, cached_pub = entry
            if (now - pushed_at) < _EC2_CONNECT_KEY_REUSE_SEC:
                priv_pem, pub_key = cached_priv, cached_pub
                log.info("aws_ec2_connect_reusing_key", age_sec=round(now - pushed_at, 1))
            else:
                entry = None  # expired
        if not entry:
            # Evict expired entries for this cache key
            _ec2_connect_key_cache.pop(cache_key, None)
            # Generate new key and push
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.backends import default_backend

            key = rsa.generate_private_key(
                public_exponent=65537, key_size=2048, backend=default_backend()
            )
            priv_pem = key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
            pub_key = (
                key.public_key()
                .public_bytes(
                    encoding=serialization.Encoding.OpenSSH,
                    format=serialization.PublicFormat.OpenSSH,
                )
                .decode("utf-8")
                .strip()
            )

            log.info("aws_ec2_connect_starting")
            try:
                client = await loop.run_in_executor(
                    None,
                    lambda: get_aws_client("ec2-instance-connect", aws_config, region=effective_region),
                )
                await loop.run_in_executor(
                    None,
                    lambda: client.send_ssh_public_key(
                        InstanceId=instance_id,
                        InstanceOSUser=os_user,
                        SSHPublicKey=pub_key,
                        AvailabilityZone=zone,
                    ),
                )
                _ec2_connect_key_cache[cache_key] = (now, priv_pem, pub_key)
                # Evict any expired entries so cache does not grow unbounded
                for k in list(_ec2_connect_key_cache):
                    if (now - _ec2_connect_key_cache[k][0]) >= _EC2_CONNECT_KEY_REUSE_SEC:
                        del _ec2_connect_key_cache[k]
            except Exception as exc:
                log.error("aws_ec2_connect_send_key_failed", error=str(exc))
                raise RuntimeError(f"EC2 Instance Connect send key failed: {exc}") from exc

    # Write private key to temp file for asyncssh (deleted after use)
    tmp_key_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".pem", delete=False, prefix="airex_ec2_connect_"
        ) as f:
            f.write(priv_pem)
            tmp_key_path = f.name
        os.chmod(tmp_key_path, 0o600)

        command_str = " && ".join(commands)

        async with asyncssh.connect(
            host=private_ip,
            port=settings.SSH_PORT,
            username=os_user,
            client_keys=[tmp_key_path],
            known_hosts=None,
            connect_timeout=timeout,
        ) as conn:
            result = await asyncio.wait_for(
                conn.run(command_str, check=False),
                timeout=timeout,
            )
            output = result.stdout or ""
            if result.stderr:
                output += f"\n--- STDERR ---\n{result.stderr}"
            if result.exit_status != 0:
                output += f"\n--- EXIT CODE: {result.exit_status} ---"
            log.info("aws_ec2_connect_complete", exit_code=result.exit_status)
            return output

    except asyncio.TimeoutError:
        raise RuntimeError(f"SSH timed out after {timeout}s on {private_ip}")
    except asyncssh.Error as exc:
        log.error("aws_ec2_connect_ssh_failed", error=str(exc))
        raise RuntimeError(f"SSH to {private_ip} failed: {exc}") from exc
    finally:
        if tmp_key_path and os.path.exists(tmp_key_path):
            try:
                os.unlink(tmp_key_path)
            except OSError:
                pass
