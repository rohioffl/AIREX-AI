"""
Tenant configuration loader.

Reads tenant data from **PostgreSQL** (primary) or falls back to
``config/tenants.yaml`` when the DB is unavailable.  The public API and
dataclass contracts are identical regardless of source, so the 30+
downstream consumers (actions, probes, cloud auth, SSH resolution, etc.)
require zero changes.

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

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
import threading
from typing import Any

import structlog
import yaml  # type: ignore[import-untyped]

logger = structlog.get_logger()

# ── Config file path (YAML fallback) ─────────────────────────────
_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
if not _CONFIG_DIR.exists():
    _CONFIG_DIR = Path("/app/airex-core/config")
_DEFAULT_CONFIG_PATH = _CONFIG_DIR / "tenants.yaml"

# Unified cache — works for both DB and YAML sources
_config_cache: dict[str, Any] = {}
_cache_timestamp: float = 0.0
_CACHE_TTL = 60.0  # seconds
_SOURCE: str = "none"  # "db" or "yaml" — tracks current source
_CACHE_LOCK = threading.Lock()
_DB_CONNECT_TIMEOUT_SECONDS = 1.0
_DB_FETCH_TIMEOUT_SECONDS = 1.5


# ═══════════════════════════════════════════════════════════════════
#  Data classes  (unchanged — exact same contract for all consumers)
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
#  DB Reader — converts Tenant model rows → same dict shape as YAML
# ═══════════════════════════════════════════════════════════════════


def _run_async_sync(awaitable_factory: Any, *args: Any) -> Any:
    """Run an async callable from sync code, even if an event loop is active."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            asyncio.wait_for(
                awaitable_factory(*args),
                timeout=_DB_FETCH_TIMEOUT_SECONDS,
            )
        )

    result: dict[str, Any] = {}
    error: dict[str, BaseException] = {}

    def _runner() -> None:
        try:
            result["value"] = asyncio.run(awaitable_factory(*args))
        except BaseException as exc:  # pragma: no cover - thread handoff
            error["exc"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join(timeout=_DB_FETCH_TIMEOUT_SECONDS)

    if thread.is_alive():
        raise TimeoutError("Tenant DB fetch timed out")

    if "exc" in error:
        raise error["exc"]
    return result.get("value")


async def _fetch_active_tenants(sync_url: str) -> list[Any]:
    """Fetch active tenants using asyncpg without requiring psycopg2."""
    import asyncpg

    conn = await asyncpg.connect(
        sync_url,
        timeout=_DB_CONNECT_TIMEOUT_SECONDS,
        command_timeout=_DB_CONNECT_TIMEOUT_SECONDS,
    )
    try:
        return await conn.fetch(
            """
            SELECT id, name, display_name, cloud, is_active,
                   escalation_email, slack_channel, ssh_user,
                   aws_config, gcp_config, servers
            FROM tenants
            WHERE is_active = true
            ORDER BY name
            """
        )
    finally:
        await conn.close()


def _load_tenants_from_db() -> dict | None:
    """
    Load all active tenants from PostgreSQL synchronously.

    Returns a dict shaped like the YAML file:
        {"defaults": {}, "tenants": {"name": {...}, ...}}
    Returns None if DB is unavailable (caller falls back to YAML).
    """
    try:
        import asyncpg
        from airex_core.core.config import settings

        sync_url = settings.DATABASE_URL.replace(
            "postgresql+asyncpg://", "postgresql://"
        )
        rows = _run_async_sync(_fetch_active_tenants, sync_url)

        if not rows:
            return None

        tenants: dict[str, dict] = {}
        for row in rows:
            tenant_id = row["id"]
            name = row["name"]
            display_name = row["display_name"]
            cloud = row["cloud"]
            escalation_email = row["escalation_email"]
            slack_channel = row["slack_channel"]
            ssh_user = row["ssh_user"]
            aws_config = row["aws_config"]
            gcp_config = row["gcp_config"]
            servers_json = row["servers"]

            tenant_dict: dict[str, Any] = {
                "tenant_id": str(tenant_id),
                "display_name": display_name or name,
                "cloud": cloud or "aws",
                "escalation_email": escalation_email or "",
                "slack_channel": slack_channel or "",
                "ssh_user": ssh_user or "ubuntu",
            }

            # AWS config (JSONB → dict)
            if aws_config and isinstance(aws_config, dict):
                tenant_dict["aws"] = aws_config

            # GCP config (JSONB → dict)
            if gcp_config and isinstance(gcp_config, dict):
                tenant_dict["gcp"] = gcp_config

            # Servers (JSONB → list of dicts)
            if servers_json and isinstance(servers_json, list):
                tenant_dict["servers"] = servers_json

            tenants[name] = tenant_dict

        logger.info(
            "tenant_config_loaded_from_db",
            tenant_count=len(tenants),
        )
        return {"defaults": {}, "tenants": tenants}
    except (ImportError, ModuleNotFoundError):
        logger.exception("tenant_config_db_driver_missing")
        raise
    except (asyncpg.PostgresError, OSError, ConnectionError, TimeoutError) as exc:
        logger.warning(
            "tenant_config_db_unavailable",
            error=str(exc),
            msg="falling back to YAML",
        )
        return None


# ═══════════════════════════════════════════════════════════════════
#  YAML Loader (fallback)
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


# ═══════════════════════════════════════════════════════════════════
#  Unified Cache — tries DB first, falls back to YAML
# ═══════════════════════════════════════════════════════════════════


def _get_cached_config(config_path: str = "") -> dict:
    """Get config with TTL caching.  DB is primary, YAML is fallback."""
    global _config_cache, _cache_timestamp, _SOURCE

    now = time.monotonic()
    with _CACHE_LOCK:
        if _config_cache and (now - _cache_timestamp) < _CACHE_TTL:
            return _config_cache

    # Try DB first (unless caller forced a specific YAML path)
    source = "yaml"
    if not config_path:
        db_data = _load_tenants_from_db()
        if db_data and db_data.get("tenants"):
            source = "db"
            new_cache = db_data
        else:
            new_cache = _load_raw_config(config_path)
    else:
        new_cache = _load_raw_config(config_path)

    with _CACHE_LOCK:
        _config_cache = new_cache
        _cache_timestamp = now
        _SOURCE = source
        return _config_cache


def reload_config(config_path: str = "") -> None:
    """Force reload the config (e.g. on SIGHUP or API call)."""
    global _config_cache, _cache_timestamp, _SOURCE

    # Try DB first
    if not config_path:
        db_data = _load_tenants_from_db()
        if db_data and db_data.get("tenants"):
            with _CACHE_LOCK:
                _config_cache = db_data
                _cache_timestamp = time.monotonic()
                _SOURCE = "db"
            logger.info("tenant_config_reloaded", source="db")
            return

    # Fallback to YAML
    with _CACHE_LOCK:
        _config_cache = _load_raw_config(config_path)
        _cache_timestamp = time.monotonic()
        _SOURCE = "yaml"
    logger.info("tenant_config_reloaded", source="yaml")


def get_config_source() -> str:
    """Return current config source: 'db', 'yaml', or 'none'."""
    with _CACHE_LOCK:
        return _SOURCE


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
#  Public API  (unchanged signatures — safe for all 30+ consumers)
# ═══════════════════════════════════════════════════════════════════


def get_tenant_config(tenant_name: str, config_path: str = "") -> TenantConfig | None:
    """
    Look up a tenant by name from DB (primary) or YAML (fallback).

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
    """Return all tenant names from DB (primary) or YAML (fallback)."""
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
      1. Per-server ssh_user (from servers[] or DB)
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

    Returns the tenant_id string, or empty string if the tenant is not
    found or has no tenant_id configured.

    This enables Site24x7 webhooks to automatically resolve the correct
    database tenant without needing an X-Tenant-Id header.
    """
    config = get_tenant_config(tenant_name, config_path)
    if config and config.tenant_id:
        return config.tenant_id
    return ""
