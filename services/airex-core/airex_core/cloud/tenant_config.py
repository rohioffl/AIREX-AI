"""
Tenant configuration loader.

Reads services/airex-core/config/tenants.yaml to provide per-tenant cloud credentials,
SSH keys, server inventories, and investigation preferences.

Usage:
    from airex_core.cloud.tenant_config import get_tenant_config, get_server_by_name

    config = get_tenant_config("acme-corp")
    if config:
        print(config.cloud)            # "gcp"
        print(config.gcp.project_id)   # "acme-production"

    server = get_server_by_name("acme-corp", "vm-prod-web-01")
    if server:
        print(server.private_ip)       # "10.128.0.15"
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
import yaml  # type: ignore[import-untyped]

logger = structlog.get_logger()

# ── Config file path ─────────────────────────────────────────────
# Resolve to airex-core/config: from airex_core/cloud/tenant_config.py
# go up 3 levels to reach airex-core/, then into config/
_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
# Fallback: if not found, try /app/airex-core/config (Docker container path)
if not _CONFIG_DIR.exists():
    _CONFIG_DIR = Path("/app/airex-core/config")
_DEFAULT_CONFIG_PATH = _CONFIG_DIR / "tenants.yaml"

# Cache
_config_cache: dict[str, Any] = {}
_cache_timestamp: float = 0.0
_CACHE_TTL = 60.0  # seconds


# ═══════════════════════════════════════════════════════════════════
#  Data classes
# ═══════════════════════════════════════════════════════════════════


@dataclass
class GCPConfig:
    """GCP-specific configuration for a tenant."""

    project_id: str = ""
    zone: str = ""
    service_account_key: str = ""
    os_login_user: str = ""
    log_explorer_enabled: bool = True


@dataclass
class AWSConfig:
    """AWS-specific configuration for a tenant."""

    region: str = ""  # empty = auto-discover from all regions
    profile: str = ""
    ssm_document: str = "AWS-RunShellScript"
    ssm_timeout: int = 30
    log_group_prefix: str = ""

    # ── Auth Method 1: Cross-account Role Assumption ──────────────
    account_id: str = ""  # AWS account number (e.g. "123456789012")
    role_arn: str = (
        ""  # Full role ARN — auto-built from account_id + role_name if empty
    )
    role_name: str = ""  # Role name (e.g. "AirexReadOnly") — used with account_id
    external_id: str = ""  # STS external ID for cross-account trust

    # ── Auth Method 2: Static Access Key / Secret Key ─────────────
    credentials_file: str = (
        ""  # Path to JSON/YAML with access_key_id + secret_access_key
    )
    access_key_id: str = ""  # Inline (not recommended — use credentials_file)
    secret_access_key: str = ""  # Inline (not recommended — use credentials_file)

    def get_role_arn(self) -> str:
        """Build role ARN from account_id + role_name if role_arn not set."""
        if self.role_arn:
            return self.role_arn
        if self.account_id and self.role_name:
            return f"arn:aws:iam::{self.account_id}:role/{self.role_name}"
        return ""


@dataclass
class SSHConfig:
    """SSH connection configuration."""

    user: str = "ubuntu"
    key_path: str = ""
    port: int = 22


@dataclass
class ServerEntry:
    """A known server/instance for a tenant."""

    name: str = ""
    instance_id: str = ""
    private_ip: str = ""
    cloud: str = ""  # override per-server (for multi-cloud tenants)
    role: str = ""  # web, api, database, worker, etc.
    ssh_user: str = ""  # per-machine SSH user override (e.g. "wacko", "ec2-user")


@dataclass
class TenantConfig:
    """Complete configuration for one tenant."""

    tenant_name: str = ""
    tenant_id: str = ""  # UUID for DB isolation (RLS)
    display_name: str = ""
    cloud: str = ""  # primary cloud: "gcp" | "aws"
    gcp: GCPConfig = field(default_factory=GCPConfig)
    aws: AWSConfig = field(default_factory=AWSConfig)
    ssh: SSHConfig = field(default_factory=SSHConfig)
    servers: list[ServerEntry] = field(default_factory=list)
    escalation_email: str = ""
    slack_channel: str = ""

    # Defaults (merged from global defaults)
    ssh_timeout: int = 15
    investigation_timeout: int = 60
    log_lookback_minutes: int = 30
    log_severity: str = "WARNING"
    max_log_entries: int = 50


# ═══════════════════════════════════════════════════════════════════
#  Loader
# ═══════════════════════════════════════════════════════════════════


def _load_raw_config(config_path: str | Path = "") -> dict:
    """Load and parse the YAML config file."""
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH

    if not path.exists():
        logger.warning("tenant_config_not_found", path=str(path))
        return {}

    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        logger.info(
            "tenant_config_loaded",
            path=str(path),
            tenant_count=len(data.get("tenants", {})),
        )
        return data or {}
    except Exception as exc:
        logger.error("tenant_config_load_failed", path=str(path), error=str(exc))
        return {}


def _get_cached_config(config_path: str = "") -> dict:
    """Get config with TTL caching."""
    global _config_cache, _cache_timestamp

    now = time.monotonic()
    if _config_cache and (now - _cache_timestamp) < _CACHE_TTL:
        return _config_cache

    _config_cache = _load_raw_config(config_path)
    _cache_timestamp = now
    return _config_cache


def reload_config(config_path: str = "") -> None:
    """Force reload the config (e.g. on SIGHUP or API call)."""
    global _config_cache, _cache_timestamp
    _config_cache = _load_raw_config(config_path)
    _cache_timestamp = time.monotonic()
    logger.info("tenant_config_reloaded")


def _parse_tenant(name: str, raw: dict, defaults: dict) -> TenantConfig:
    """Parse a raw tenant dict into a TenantConfig dataclass."""
    tc = TenantConfig(
        tenant_name=name,
        tenant_id=raw.get("tenant_id", ""),
        display_name=raw.get("display_name", name),
        cloud=raw.get("cloud", ""),
        escalation_email=raw.get("escalation_email", ""),
        slack_channel=raw.get("slack_channel", ""),
        ssh_timeout=raw.get("ssh_timeout", defaults.get("ssh_timeout", 15)),
        investigation_timeout=raw.get(
            "investigation_timeout", defaults.get("investigation_timeout", 60)
        ),
        log_lookback_minutes=raw.get(
            "log_lookback_minutes", defaults.get("log_lookback_minutes", 30)
        ),
        log_severity=raw.get("log_severity", defaults.get("log_severity", "WARNING")),
        max_log_entries=raw.get("max_log_entries", defaults.get("max_log_entries", 50)),
    )

    # GCP
    gcp_raw = raw.get("gcp", {})
    if gcp_raw:
        tc.gcp = GCPConfig(
            project_id=gcp_raw.get("project_id", ""),
            zone=gcp_raw.get("zone", ""),
            service_account_key=gcp_raw.get("service_account_key", ""),
            os_login_user=gcp_raw.get("os_login_user", ""),
            log_explorer_enabled=gcp_raw.get("log_explorer_enabled", True),
        )

    # AWS
    aws_raw = raw.get("aws", {})
    if aws_raw:
        tc.aws = AWSConfig(
            region=aws_raw.get("region", ""),
            profile=aws_raw.get("profile", ""),
            ssm_document=aws_raw.get("ssm_document", "AWS-RunShellScript"),
            ssm_timeout=aws_raw.get("ssm_timeout", 30),
            log_group_prefix=aws_raw.get("log_group_prefix", ""),
            account_id=str(aws_raw.get("account_id", "")),
            role_arn=aws_raw.get("role_arn", ""),
            role_name=aws_raw.get("role_name", ""),
            external_id=aws_raw.get("external_id", ""),
            credentials_file=aws_raw.get("credentials_file", ""),
            access_key_id=aws_raw.get("access_key_id", ""),
            secret_access_key=aws_raw.get("secret_access_key", ""),
        )

    # SSH — support both nested ssh: block and top-level ssh_user key
    ssh_raw = raw.get("ssh", {})
    top_level_ssh_user = raw.get("ssh_user", defaults.get("ssh_user", "ubuntu"))
    top_level_ssh_port = raw.get("ssh_port", defaults.get("ssh_port", 22))
    if ssh_raw:
        tc.ssh = SSHConfig(
            user=ssh_raw.get("user", top_level_ssh_user),
            key_path=ssh_raw.get("key_path", ""),
            port=ssh_raw.get("port", top_level_ssh_port),
        )
    else:
        tc.ssh = SSHConfig(
            user=top_level_ssh_user,
            key_path="",
            port=top_level_ssh_port,
        )

    # Servers
    for srv_raw in raw.get("servers", []):
        tc.servers.append(
            ServerEntry(
                name=srv_raw.get("name", ""),
                instance_id=srv_raw.get("instance_id", ""),
                private_ip=srv_raw.get("private_ip", ""),
                cloud=srv_raw.get("cloud", tc.cloud),
                role=srv_raw.get("role", ""),
                ssh_user=srv_raw.get("ssh_user", ""),
            )
        )

    return tc


# ═══════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════


def get_tenant_config(tenant_name: str, config_path: str = "") -> TenantConfig | None:
    """
    Look up a tenant by name from the config file.

    Returns None if the tenant is not found.
    The tenant_name is matched case-insensitively.
    """
    if not tenant_name:
        return None

    data = _get_cached_config(config_path)
    defaults = data.get("defaults", {})
    tenants = data.get("tenants", {})

    # Case-insensitive lookup
    key = tenant_name.lower().strip()
    for name, raw in tenants.items():
        if name.lower() == key:
            return _parse_tenant(name, raw, defaults)

    logger.debug("tenant_not_in_config", tenant_name=tenant_name)
    return None


def list_tenants(config_path: str = "") -> list[str]:
    """Return all tenant names from the config."""
    data = _get_cached_config(config_path)
    return list(data.get("tenants", {}).keys())


def get_server_by_name(
    tenant_name: str, server_name: str, config_path: str = ""
) -> ServerEntry | None:
    """Look up a specific server by name within a tenant."""
    config = get_tenant_config(tenant_name, config_path)
    if not config:
        return None

    key = server_name.lower().strip()
    for server in config.servers:
        if server.name.lower() == key:
            return server
        if server.instance_id.lower() == key:
            return server
    return None


def get_server_by_ip(
    tenant_name: str, ip: str, config_path: str = ""
) -> ServerEntry | None:
    """Look up a specific server by private IP within a tenant."""
    config = get_tenant_config(tenant_name, config_path)
    if not config:
        return None

    for server in config.servers:
        if server.private_ip == ip:
            return server
    return None


def get_ssh_user_for_host(
    tenant_name: str, host_ip: str = "", instance_id: str = "", config_path: str = ""
) -> str:
    """
    Resolve the SSH user for a specific host within a tenant.

    Resolution order:
      1. Per-server ssh_user (from servers[] in tenants.yaml)
      2. Per-tenant ssh_user (top-level or ssh.user)
      3. Empty string (caller should use auto-detection or global fallback)

    Args:
        tenant_name: Tenant name from config.
        host_ip: Private IP of the target host.
        instance_id: Cloud instance ID (e.g. i-0abc123, vm-prod-web-01).

    Returns:
        SSH username or empty string if no static mapping found.
    """
    config = get_tenant_config(tenant_name, config_path)
    if not config:
        return ""

    # Check per-server override first
    if host_ip:
        server = get_server_by_ip(tenant_name, host_ip, config_path)
        if server and server.ssh_user:
            return server.ssh_user

    if instance_id:
        server = get_server_by_name(tenant_name, instance_id, config_path)
        if server and server.ssh_user:
            return server.ssh_user

    # Fall back to tenant-level SSH user
    return config.ssh.user


def resolve_tenant_id_by_name(tenant_name: str, config_path: str = "") -> str:
    """
    Resolve a tenant name (from Site24x7 tags) to a database tenant_id UUID.

    Returns the tenant_id string from tenants.yaml, or empty string if
    the tenant is not found or has no tenant_id configured.

    This enables Site24x7 webhooks to automatically resolve the correct
    database tenant without needing an X-Tenant-Id header.
    """
    config = get_tenant_config(tenant_name, config_path)
    if config and config.tenant_id:
        return config.tenant_id
    return ""
