"""Cloud provider integrations (AWS SSM, GCP OS Login, Log Explorer, Auto-Discovery)."""

from airex_core.cloud.tag_parser import CloudContext, parse_tags, merge_context_into_meta, discover_and_enrich
from airex_core.cloud.tenant_config import (
    get_tenant_config,
    get_server_by_name,
    get_server_by_ip,
    list_tenants,
    reload_config,
    TenantConfig,
)
from airex_core.cloud.discovery import discover_instance_cached, DiscoveredInstance
from airex_core.cloud.aws_auth import get_aws_session, get_aws_client

__all__ = [
    "CloudContext",
    "parse_tags",
    "merge_context_into_meta",
    "discover_and_enrich",
    "get_tenant_config",
    "get_server_by_name",
    "get_server_by_ip",
    "list_tenants",
    "reload_config",
    "TenantConfig",
    "discover_instance_cached",
    "DiscoveredInstance",
    "get_aws_session",
    "get_aws_client",
]
