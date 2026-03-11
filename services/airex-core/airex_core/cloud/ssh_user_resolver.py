"""
SSH user resolver — auto-detects the correct SSH username per machine.

Resolution chain (first match wins):
  1. Per-server override in tenants.yaml (servers[].ssh_user)
  2. Per-tenant default in tenants.yaml (ssh_user / ssh.user)
  3. Cloud API auto-detection:
     - GCP: query instance metadata for OS image → map to known user
     - AWS: query AMI description/name → map to known user
  4. Global fallback from settings.SSH_USER (default: "ubuntu")

Results are cached in Redis (or in-process dict) with TTL to avoid
repeated API calls for the same instance.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import structlog

from airex_core.core.config import settings

if TYPE_CHECKING:
    from airex_core.cloud.tenant_config import AWSConfig, GCPConfig

logger = structlog.get_logger()

# ── In-process cache ─────────────────────────────────────────────
# Key: (cloud, instance_id_or_ip) → (resolved_user, timestamp)
_ssh_user_cache: dict[tuple[str, str], tuple[str, float]] = {}
_SSH_USER_CACHE_TTL = 3600.0  # 1 hour — OS image doesn't change often


# ── Known OS image → SSH user mappings ───────────────────────────

# GCP: source image family / name patterns → default SSH user
_GCP_IMAGE_USER_MAP: list[tuple[list[str], str]] = [
    (["ubuntu"], "ubuntu"),
    (["debian"], "admin"),
    (["centos"], "centos"),
    (["rhel", "red-hat"], "ec2-user"),  # GCP RHEL uses ec2-user convention
    (["rocky", "rockylinux"], "rocky"),
    (["alma", "almalinux"], "almalinux"),
    (["fedora"], "fedora"),
    (["suse", "sles", "opensuse"], "ec2-user"),
    (["cos", "container-optimized"], "chronos"),
    (["windows"], "admin"),
    (["coreos", "flatcar"], "core"),
]

# AWS: AMI name/description patterns → default SSH user
# Order matters: more specific patterns (bitnami) before generic ones (debian)
_AWS_AMI_USER_MAP: list[tuple[list[str], str]] = [
    (["bitnami"], "bitnami"),
    (["ubuntu"], "ubuntu"),
    (["debian"], "admin"),
    (["amazon", "amzn", "al2023", "al2"], "ec2-user"),
    (["centos"], "centos"),
    (["rhel", "red hat"], "ec2-user"),
    (["rocky", "rockylinux"], "rocky"),
    (["alma", "almalinux"], "ec2-user"),
    (["fedora"], "fedora"),
    (["suse", "sles"], "ec2-user"),
    (["freebsd"], "ec2-user"),
    (["coreos", "flatcar"], "core"),
    (["windows"], "Administrator"),
]


def _match_image_pattern(image_str: str, mapping: list[tuple[list[str], str]]) -> str:
    """Match an image name/family string against known patterns."""
    lower = image_str.lower()
    for patterns, user in mapping:
        if any(p in lower for p in patterns):
            return user
    return ""


def _cache_key(cloud: str, identifier: str) -> tuple[str, str]:
    """Build a cache key from cloud + instance identifier."""
    return (cloud.lower(), identifier.strip())


def _get_cached(cloud: str, identifier: str) -> str | None:
    """Return cached SSH user if still valid, else None."""
    key = _cache_key(cloud, identifier)
    entry = _ssh_user_cache.get(key)
    if entry:
        user, ts = entry
        if (time.monotonic() - ts) < _SSH_USER_CACHE_TTL:
            return user
        del _ssh_user_cache[key]
    return None


def _set_cached(cloud: str, identifier: str, user: str) -> None:
    """Store resolved SSH user in cache."""
    key = _cache_key(cloud, identifier)
    _ssh_user_cache[key] = (user, time.monotonic())
    # Evict old entries (keep cache bounded)
    now = time.monotonic()
    expired = [
        k for k, (_, ts) in _ssh_user_cache.items() if (now - ts) >= _SSH_USER_CACHE_TTL
    ]
    for k in expired:
        _ssh_user_cache.pop(k, None)


# ═══════════════════════════════════════════════════════════════════
#  GCP auto-detection
# ═══════════════════════════════════════════════════════════════════


async def _detect_gcp_ssh_user(
    instance_name: str,
    project: str,
    zone: str,
    gcp_config: "GCPConfig | None" = None,
) -> str:
    """
    Query GCP Compute API for the instance's source image and resolve SSH user.

    Checks instance metadata for 'ssh-user' label first, then inspects the
    boot disk's source image family to determine the default OS user.
    """
    if not instance_name or not project or not zone:
        return ""

    loop = asyncio.get_event_loop()

    try:
        from google.cloud import compute_v1

        # Use per-tenant SA key if available
        sa_key_path = gcp_config.service_account_key if gcp_config else ""
        if sa_key_path:
            import os

            if os.path.exists(sa_key_path):
                client = compute_v1.InstancesClient.from_service_account_file(
                    sa_key_path
                )
            else:
                client = compute_v1.InstancesClient()
        else:
            client = compute_v1.InstancesClient()

        instance = await loop.run_in_executor(
            None,
            lambda: client.get(project=project, zone=zone, instance=instance_name),
        )

        # 1. Check instance labels for explicit ssh-user
        labels = dict(instance.labels) if instance.labels else {}
        if labels.get("ssh-user") or labels.get("ssh_user"):
            user = labels.get("ssh-user") or labels.get("ssh_user", "")
            logger.info(
                "ssh_user_from_gcp_label",
                instance=instance_name,
                user=user,
            )
            return user

        # 2. Check instance metadata for ssh-user
        if instance.metadata and instance.metadata.items:
            for item in instance.metadata.items:
                if item.key in ("ssh-user", "ssh_user"):
                    logger.info(
                        "ssh_user_from_gcp_metadata",
                        instance=instance_name,
                        user=item.value,
                    )
                    return item.value

        # 3. Inspect boot disk source image
        for disk in instance.disks:
            if not disk.boot:
                continue
            source_image = disk.source or ""
            # source looks like: projects/ubuntu-os-cloud/global/images/ubuntu-2204-...
            if source_image:
                user = _match_image_pattern(source_image, _GCP_IMAGE_USER_MAP)
                if user:
                    logger.info(
                        "ssh_user_from_gcp_image",
                        instance=instance_name,
                        source_image=source_image,
                        user=user,
                    )
                    return user

            # Also check licenses which contain OS family info
            for lic in disk.licenses or []:
                user = _match_image_pattern(lic, _GCP_IMAGE_USER_MAP)
                if user:
                    logger.info(
                        "ssh_user_from_gcp_license",
                        instance=instance_name,
                        license=lic,
                        user=user,
                    )
                    return user

    except Exception as exc:
        logger.warning(
            "gcp_ssh_user_detection_failed",
            instance=instance_name,
            error=str(exc),
        )

    return ""


# ═══════════════════════════════════════════════════════════════════
#  AWS auto-detection
# ═══════════════════════════════════════════════════════════════════


async def _detect_aws_ssh_user(
    instance_id: str,
    region: str,
    aws_config: "AWSConfig | None" = None,
) -> str:
    """
    Query AWS EC2 API for the instance's AMI and resolve SSH user.

    Checks instance tags for 'ssh-user' first, then inspects the AMI
    name/description to determine the default OS user.
    """
    if not instance_id:
        return ""

    loop = asyncio.get_event_loop()

    try:
        from airex_core.cloud.aws_auth import get_aws_client

        effective_region = (
            region
            or (aws_config.region if aws_config else "")
            or settings.AWS_REGION
            or "us-east-1"
        )

        ec2 = await loop.run_in_executor(
            None,
            lambda: get_aws_client("ec2", aws_config, region=effective_region),
        )

        resp = await loop.run_in_executor(
            None,
            lambda: ec2.describe_instances(InstanceIds=[instance_id]),
        )

        for reservation in resp.get("Reservations", []):
            for inst in reservation.get("Instances", []):
                # 1. Check instance tags for explicit ssh-user
                tags = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
                for tag_key in ("ssh-user", "ssh_user", "SshUser", "SSHUser"):
                    if tags.get(tag_key):
                        logger.info(
                            "ssh_user_from_aws_tag",
                            instance_id=instance_id,
                            tag=tag_key,
                            user=tags[tag_key],
                        )
                        return tags[tag_key]

                # 2. Look up the AMI
                ami_id = inst.get("ImageId", "")
                if not ami_id:
                    continue

                # 3. Check AMI platform detail (quick win for Windows)
                platform = inst.get("PlatformDetails", "") or inst.get("Platform", "")
                if "windows" in platform.lower():
                    return "Administrator"

                try:
                    ami_resp = await loop.run_in_executor(
                        None,
                        lambda: ec2.describe_images(ImageIds=[ami_id]),
                    )
                    for image in ami_resp.get("Images", []):
                        # Combine name + description for matching
                        ami_text = " ".join(
                            [
                                image.get("Name", ""),
                                image.get("Description", ""),
                                image.get("ImageLocation", ""),
                            ]
                        )
                        user = _match_image_pattern(ami_text, _AWS_AMI_USER_MAP)
                        if user:
                            logger.info(
                                "ssh_user_from_aws_ami",
                                instance_id=instance_id,
                                ami_id=ami_id,
                                ami_text=ami_text[:100],
                                user=user,
                            )
                            return user
                except Exception as exc:
                    logger.debug(
                        "aws_ami_lookup_failed",
                        ami_id=ami_id,
                        error=str(exc),
                    )

    except Exception as exc:
        logger.warning(
            "aws_ssh_user_detection_failed",
            instance_id=instance_id,
            error=str(exc),
        )

    return ""


# ═══════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════


async def resolve_ssh_user(
    cloud: str,
    tenant_name: str = "",
    private_ip: str = "",
    instance_id: str = "",
    instance_name: str = "",
    project: str = "",
    zone: str = "",
    region: str = "",
    aws_config: "AWSConfig | None" = None,
    gcp_config: "GCPConfig | None" = None,
) -> str:
    """
    Resolve the SSH user for a target machine.

    Resolution chain (first non-empty wins):
      1. Per-server override in tenants.yaml (servers[].ssh_user)
      2. Per-tenant default in tenants.yaml (ssh_user / ssh.user)
      3. In-process cache (from prior cloud API call)
      4. Cloud API auto-detection (GCP instance image / AWS AMI)
      5. Global fallback: settings.SSH_USER (default "ubuntu")

    This function is safe to call even without cloud credentials —
    it gracefully degrades to the tenant or global default.

    Args:
        cloud: "gcp" or "aws"
        tenant_name: Tenant name for tenants.yaml lookup.
        private_ip: Target host private IP.
        instance_id: Cloud instance ID (AWS: i-xxx, GCP: instance name).
        instance_name: GCP instance name (if different from instance_id).
        project: GCP project ID.
        zone: GCP zone.
        region: AWS region.
        aws_config: Per-tenant AWS auth config.
        gcp_config: Per-tenant GCP auth config.

    Returns:
        Resolved SSH username (never empty — always falls back to settings).
    """
    cloud = cloud.lower()
    cache_id = instance_id or instance_name or private_ip

    # Step 1-2: Static config (per-server then per-tenant)
    if tenant_name:
        from airex_core.cloud.tenant_config import get_ssh_user_for_host

        static_user = get_ssh_user_for_host(
            tenant_name, host_ip=private_ip, instance_id=instance_id or instance_name
        )
        if static_user:
            logger.debug(
                "ssh_user_from_config",
                user=static_user,
                tenant=tenant_name,
                host=cache_id,
            )
            return static_user

    # Step 3: Check in-process cache
    if cache_id:
        cached = _get_cached(cloud, cache_id)
        if cached:
            logger.debug("ssh_user_from_cache", user=cached, host=cache_id)
            return cached

    # Step 4: Cloud API auto-detection
    detected = ""
    if cloud == "gcp":
        gcp_instance = instance_name or instance_id
        detected = await _detect_gcp_ssh_user(
            instance_name=gcp_instance,
            project=project,
            zone=zone,
            gcp_config=gcp_config,
        )
    elif cloud == "aws":
        detected = await _detect_aws_ssh_user(
            instance_id=instance_id,
            region=region,
            aws_config=aws_config,
        )

    if detected:
        if cache_id:
            _set_cached(cloud, cache_id, detected)
        return detected

    # Step 5: Global fallback
    fallback = settings.SSH_USER or "ubuntu"
    logger.debug(
        "ssh_user_fallback",
        user=fallback,
        cloud=cloud,
        host=cache_id,
    )
    return fallback


def clear_cache() -> None:
    """Clear the in-process SSH user cache (e.g. for testing or config reload)."""
    _ssh_user_cache.clear()
    logger.debug("ssh_user_cache_cleared")
