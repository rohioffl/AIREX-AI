"""
GCP OS Login SSH connector.

Connects to GCE instances via their private IP using OS Login authentication.
Requires:
  - AIREX host is in the same VPC or has VPC peering to the target
  - Target GCE instance has OS Login enabled (metadata: enable-oslogin=TRUE)
  - AIREX service account has roles/compute.osLogin (or osAdminLogin)
  - No manual SSH key management — Google handles key lifecycle via OS Login

Authentication chain:
  1. GCP_SERVICE_ACCOUNT_KEY (explicit JSON key file)
  2. Application Default Credentials (ADC) — auto on GCE/GKE/Cloud Run
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from functools import lru_cache

import structlog

from app.core.config import settings

logger = structlog.get_logger()


def _resolve_os_login_user() -> str:
    """
    Resolve the OS Login POSIX username.

    OS Login maps service accounts to POSIX users like:
      sa_123456789012345678901  (numeric SA unique ID)
    Or you can configure a custom username in GCP IAM.
    """
    if settings.GCP_OS_LOGIN_USER:
        return settings.GCP_OS_LOGIN_USER
    return settings.SSH_USER or "ubuntu"


@lru_cache(maxsize=1)
def _get_gcp_credentials():
    """Get GCP credentials for OS Login key injection."""
    from google.auth import default
    from google.auth.transport.requests import Request

    if settings.GCP_SERVICE_ACCOUNT_KEY and os.path.exists(settings.GCP_SERVICE_ACCOUNT_KEY):
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(
            settings.GCP_SERVICE_ACCOUNT_KEY,
            scopes=[
                "https://www.googleapis.com/auth/compute",
                "https://www.googleapis.com/auth/cloud-platform",
            ],
        )
    else:
        creds, _ = default(scopes=[
            "https://www.googleapis.com/auth/compute",
            "https://www.googleapis.com/auth/cloud-platform",
        ])

    creds.refresh(Request())
    return creds


async def gcp_ssh_run_command(
    private_ip: str,
    commands: list[str],
    instance_name: str = "",
    project: str = "",
    zone: str = "",
    timeout: int = 0,
) -> str:
    """
    Execute commands on a GCE instance via SSH using OS Login.

    Uses asyncssh to connect to the private IP. Authentication uses
    a temporary SSH key injected via the OS Login API, or falls back
    to the configured SSH key.

    Args:
        private_ip: Private IP of the GCE instance
        commands: List of shell commands to execute
        instance_name: GCE instance name (for logging)
        project: GCP project ID
        zone: GCE zone
        timeout: SSH command timeout in seconds

    Returns:
        Combined stdout from the command execution.
    """
    import asyncssh

    timeout = timeout or settings.SSH_TIMEOUT
    project = project or settings.GCP_PROJECT_ID
    zone = zone or settings.GCP_ZONE
    username = _resolve_os_login_user()

    log = logger.bind(
        private_ip=private_ip,
        instance=instance_name,
        project=project,
        username=username,
    )
    log.info("gcp_ssh_connecting")

    command_str = " && ".join(commands)

    # Try OS Login key injection first, then fall back to configured SSH key
    connect_kwargs = await _build_ssh_connect_kwargs(username, private_ip, timeout)

    try:
        async with asyncssh.connect(**connect_kwargs) as conn:
            result = await asyncio.wait_for(
                conn.run(command_str, check=False),
                timeout=timeout,
            )

            output = result.stdout or ""
            if result.stderr:
                output += f"\n--- STDERR ---\n{result.stderr}"
            if result.exit_status != 0:
                output += f"\n--- EXIT CODE: {result.exit_status} ---"

            log.info("gcp_ssh_command_complete", exit_code=result.exit_status, output_length=len(output))
            return output

    except asyncio.TimeoutError:
        raise RuntimeError(f"SSH command timed out after {timeout}s on {private_ip}")
    except asyncssh.Error as exc:
        log.error("gcp_ssh_failed", error=str(exc))
        raise RuntimeError(f"SSH to {private_ip} failed: {exc}") from exc


async def _build_ssh_connect_kwargs(
    username: str, host: str, timeout: int
) -> dict:
    """
    Build asyncssh connection kwargs.

    Priority:
    1. OS Login temporary key injection (if GCP credentials available)
    2. Configured SSH key file (SSH_KEY_PATH)
    3. SSH agent (default asyncssh behavior)
    """
    kwargs: dict = {
        "host": host,
        "port": settings.SSH_PORT,
        "username": username,
        "known_hosts": None,  # Skip host key verification for private IPs
        "connect_timeout": timeout,
    }

    # Try to get SSH key via OS Login API
    try:
        key_path = await _inject_os_login_key()
        if key_path:
            kwargs["client_keys"] = [key_path]
            logger.debug("gcp_using_os_login_key", key_path=key_path)
            return kwargs
    except Exception as exc:
        logger.warning("os_login_key_injection_failed", error=str(exc))

    # Fall back to configured SSH key
    if settings.SSH_KEY_PATH and os.path.exists(settings.SSH_KEY_PATH):
        kwargs["client_keys"] = [settings.SSH_KEY_PATH]
        logger.debug("gcp_using_configured_key", key_path=settings.SSH_KEY_PATH)
    else:
        logger.debug("gcp_using_ssh_agent")

    return kwargs


async def _inject_os_login_key() -> str | None:
    """
    Inject a temporary SSH key via the GCP OS Login API.

    The OS Login API lets you push a public key that GCP automatically
    provisions as a POSIX account. Key expires after 5 minutes.
    """
    import asyncssh

    loop = asyncio.get_event_loop()

    try:
        creds = await loop.run_in_executor(None, _get_gcp_credentials)
    except Exception:
        return None

    # Generate temporary key pair
    key = asyncssh.generate_private_key("ssh-rsa", 2048)
    pub_key = key.export_public_key().decode("utf-8").strip()

    # Push public key to OS Login
    try:
        import httpx

        sa_email = getattr(creds, "service_account_email", None)
        if not sa_email:
            return None

        access_token = creds.token
        url = f"https://oslogin.googleapis.com/v1/users/{sa_email}:importSshPublicKey"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "key": pub_key,
                    "expirationTimeUsec": str(
                        (asyncio.get_event_loop().time() + 300) * 1_000_000
                    ),
                },
                params={"projectId": settings.GCP_PROJECT_ID},
            )
            resp.raise_for_status()

    except Exception as exc:
        logger.warning("os_login_import_key_failed", error=str(exc))
        return None

    # Write private key to temp file for asyncssh
    tmp = tempfile.NamedTemporaryFile(
        mode="wb", suffix=".pem", delete=False, prefix="airex_oslogin_"
    )
    tmp.write(key.export_private_key())
    tmp.close()
    os.chmod(tmp.name, 0o600)

    return tmp.name


async def gcp_resolve_private_ip(
    instance_name: str,
    project: str = "",
    zone: str = "",
) -> str | None:
    """
    Look up a GCE instance's private IP by name using the Compute API.

    Useful when Site24x7 only sends monitor name but not the IP tag.
    """
    from google.cloud import compute_v1

    project = project or settings.GCP_PROJECT_ID
    zone = zone or settings.GCP_ZONE

    if not project or not zone:
        return None

    loop = asyncio.get_event_loop()

    try:
        client = compute_v1.InstancesClient()
        instance = await loop.run_in_executor(
            None,
            lambda: client.get(project=project, zone=zone, instance=instance_name),
        )

        for iface in instance.network_interfaces:
            if iface.network_i_p:
                return iface.network_i_p
        return None

    except Exception as exc:
        logger.warning("gcp_resolve_ip_failed", instance=instance_name, error=str(exc))
        return None
