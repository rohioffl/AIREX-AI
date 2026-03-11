"""
Parse Site24x7 monitor tags into structured cloud metadata.

Site24x7 tags arrive as comma-separated key:value strings, e.g.:
  "cloud:gcp,tenant:acme-corp,ip:10.128.0.15,instance:vm-prod-01,project:my-gcp-project"
  "cloud:aws,tenant:beta-inc,ip:172.31.5.42,instance:i-0abc123def,region:ap-south-1"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger()


@dataclass
class CloudContext:
    """Structured cloud context extracted from monitor tags."""

    cloud: str = ""                    # "gcp" | "aws" | ""
    tenant: str = ""                   # tenant name from tag
    private_ip: str = ""               # private IP of the target host
    instance_id: str = ""              # GCE instance name or EC2 instance-id
    project: str = ""                  # GCP project ID
    zone: str = ""                     # GCP zone (e.g. "us-central1-a")
    region: str = ""                   # AWS region (e.g. "ap-south-1")
    service_account: str = ""          # GCP service account email
    role: str = ""                     # AWS IAM role
    vpc: str = ""                      # VPC name/id
    environment: str = ""              # prod/staging/dev
    extra_tags: dict[str, str] = field(default_factory=dict)

    @property
    def is_gcp(self) -> bool:
        return self.cloud.lower() == "gcp"

    @property
    def is_aws(self) -> bool:
        return self.cloud.lower() == "aws"

    @property
    def has_target(self) -> bool:
        """True if we have enough info to reach the host."""
        return bool(self.private_ip or self.instance_id)


# Known tag keys and which CloudContext field they map to
_TAG_FIELD_MAP: dict[str, str] = {
    "cloud": "cloud",
    "tenant": "tenant",
    "ip": "private_ip",
    "private_ip": "private_ip",
    "privateip": "private_ip",
    "instance": "instance_id",
    "instance_id": "instance_id",
    "instanceid": "instance_id",
    "instance-id": "instance_id",
    "project": "project",
    "project_id": "project",
    "projectid": "project",
    "zone": "zone",
    "region": "region",
    "service_account": "service_account",
    "sa": "service_account",
    "role": "role",
    "iam_role": "role",
    "vpc": "vpc",
    "env": "environment",
    "environment": "environment",
}

# Regex for private IPs (RFC 1918)
_PRIVATE_IP_RE = re.compile(
    r"^(10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3})$"
)

# Regex for EC2 instance IDs
_EC2_INSTANCE_RE = re.compile(r"^i-[0-9a-f]{8,17}$")


def parse_tags(raw_tags: str | None) -> CloudContext:
    """
    Parse a comma-separated tag string into a CloudContext.

    Handles formats:
      - "cloud:gcp,tenant:acme,ip:10.128.0.15"
      - "cloud:gcp, tenant:acme, ip:10.128.0.15"   (spaces)
      - "production,web,cloud:aws"                   (mixed plain + kv)
    """
    ctx = CloudContext()
    if not raw_tags:
        return ctx

    parts = [p.strip() for p in raw_tags.split(",") if p.strip()]

    for part in parts:
        if ":" in part:
            key, _, value = part.partition(":")
            key = key.strip().lower().replace("-", "_").replace(" ", "_")
            value = value.strip()

            mapped_field = _TAG_FIELD_MAP.get(key)
            if mapped_field and hasattr(ctx, mapped_field):
                setattr(ctx, mapped_field, value)
            else:
                ctx.extra_tags[key] = value
        else:
            # Plain tag — check if it looks like a cloud provider
            lower = part.lower()
            if lower in ("gcp", "aws", "azure"):
                ctx.cloud = lower
            elif lower in ("prod", "production", "staging", "dev", "development"):
                ctx.environment = lower
            elif _PRIVATE_IP_RE.match(part):
                ctx.private_ip = part
            elif _EC2_INSTANCE_RE.match(part):
                ctx.instance_id = part
            else:
                ctx.extra_tags[lower] = ""

    # Enrich from tenant config file if tenant tag is present
    if ctx.tenant:
        ctx = _enrich_from_tenant_config(ctx)

    logger.debug(
        "tags_parsed",
        cloud=ctx.cloud,
        tenant=ctx.tenant,
        private_ip=ctx.private_ip,
        instance_id=ctx.instance_id,
        has_target=ctx.has_target,
    )

    return ctx


def _enrich_from_tenant_config(ctx: CloudContext) -> CloudContext:
    """
    Fill in missing CloudContext fields from config/tenants.yaml.

    Only fills cloud + project/region from config.
    Zone, instance name, etc. are auto-discovered later via cloud APIs.
    Webhook tags always take priority.
    """
    try:
        from airex_core.cloud.tenant_config import get_tenant_config

        config = get_tenant_config(ctx.tenant)
        if config is None:
            return ctx

        # Fill cloud provider if not set in tags
        if not ctx.cloud and config.cloud:
            ctx.cloud = config.cloud

        # Fill GCP project
        if ctx.is_gcp:
            if not ctx.project and config.gcp.project_id:
                ctx.project = config.gcp.project_id

        # Fill AWS region
        if ctx.is_aws:
            if not ctx.region and config.aws.region:
                ctx.region = config.aws.region

        logger.debug(
            "enriched_from_tenant_config",
            tenant=ctx.tenant,
            cloud=ctx.cloud,
            project=ctx.project,
            region=ctx.region,
        )

    except Exception as exc:
        logger.warning("tenant_config_enrichment_failed", error=str(exc))

    return ctx


async def discover_and_enrich(ctx: CloudContext, redis=None) -> CloudContext:
    """
    Auto-discover instance details from cloud APIs using the private IP.

    Called after parse_tags() when we have cloud + IP but missing
    zone/instance/region. Queries GCP Compute or AWS EC2 APIs.

    Results are cached in Redis (1 hour TTL).
    """
    if not ctx.has_target or not ctx.cloud:
        return ctx

    # Skip if we already have zone + instance (nothing to discover)
    if ctx.zone and ctx.instance_id:
        return ctx

    if not ctx.private_ip:
        return ctx

    try:
        from airex_core.cloud.discovery import discover_instance_cached
        from airex_core.cloud.tenant_config import get_tenant_config

        # Get per-tenant credentials
        sa_key = ""
        aws_config = None
        config = get_tenant_config(ctx.tenant) if ctx.tenant else None
        if config:
            sa_key = config.gcp.service_account_key
            aws_config = config.aws

        discovered = await discover_instance_cached(
            private_ip=ctx.private_ip,
            cloud=ctx.cloud,
            project_id=ctx.project,
            region=ctx.region,
            sa_key_path=sa_key,
            aws_config=aws_config,
            redis=redis,
        )

        if discovered:
            if not ctx.instance_id:
                ctx.instance_id = discovered.instance_id
            if not ctx.zone:
                ctx.zone = discovered.zone
            if not ctx.region:
                ctx.region = discovered.region
            if not ctx.service_account:
                ctx.service_account = discovered.service_account

            logger.info(
                "instance_auto_discovered",
                cloud=ctx.cloud,
                ip=ctx.private_ip,
                instance=discovered.instance_name,
                zone=discovered.zone,
                region=discovered.region,
                machine_type=discovered.machine_type,
            )
        else:
            logger.warning(
                "instance_discovery_failed",
                cloud=ctx.cloud,
                ip=ctx.private_ip,
                project=ctx.project,
            )

    except Exception as exc:
        logger.warning("auto_discovery_error", error=str(exc))

    return ctx


def merge_context_into_meta(meta: dict, ctx: CloudContext) -> dict:
    """Merge parsed cloud context back into incident meta for plugins to use."""
    meta["_cloud"] = ctx.cloud
    meta["_tenant_name"] = ctx.tenant
    meta["_private_ip"] = ctx.private_ip
    meta["_instance_id"] = ctx.instance_id
    meta["_project"] = ctx.project
    meta["_zone"] = ctx.zone
    meta["_region"] = ctx.region
    meta["_service_account"] = ctx.service_account
    meta["_environment"] = ctx.environment
    meta["_has_cloud_target"] = ctx.has_target
    if ctx.extra_tags:
        meta["_extra_tags"] = ctx.extra_tags

    # Add escalation email from tenant config for UI acknowledge feature
    if ctx.tenant:
        try:
            from airex_core.cloud.tenant_config import get_tenant_config
            config = get_tenant_config(ctx.tenant)
            if config and config.escalation_email:
                meta["_escalation_email"] = config.escalation_email
        except Exception:
            pass

    return meta
