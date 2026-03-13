"""
Tenant configuration API.

Provides read access to the tenant config and a reload endpoint
for operators to refresh the config without restarting the server.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from importlib import import_module
from functools import lru_cache
from typing import Any, Callable, cast

from app.api.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter()


@lru_cache(maxsize=1)
def _tenant_config_module() -> Any:
    return import_module("airex_core.cloud.tenant_config")


class TenantSummary(BaseModel):
    name: str
    display_name: str
    cloud: str
    server_count: int
    escalation_email: str


class TenantDetailResponse(BaseModel):
    name: str
    display_name: str
    cloud: str
    gcp_project: str
    aws_region: str
    escalation_email: str
    slack_channel: str


@router.get("/", response_model=list[TenantSummary])
async def list_all_tenants() -> list[TenantSummary]:
    """List all configured tenants."""
    list_tenants = cast(Callable[[], list[str]], _tenant_config_module().list_tenants)
    get_tenant_config = cast(
        Callable[[str], Any],
        _tenant_config_module().get_tenant_config,
    )

    names = list_tenants()
    result: list[TenantSummary] = []
    for name in names:
        config = get_tenant_config(name)
        if config:
            result.append(
                TenantSummary(
                    name=config.tenant_name,
                    display_name=config.display_name,
                    cloud=config.cloud,
                    server_count=len(config.servers),
                    escalation_email=config.escalation_email,
                )
            )
    return result


@router.get("/{tenant_name}", response_model=TenantDetailResponse)
async def get_tenant_detail(tenant_name: str) -> TenantDetailResponse:
    """Get detailed configuration for a specific tenant."""
    get_tenant_config = cast(
        Callable[[str], Any],
        _tenant_config_module().get_tenant_config,
    )
    config = get_tenant_config(tenant_name)
    if config is None:
        raise HTTPException(
            status_code=404, detail=f"Tenant '{tenant_name}' not found in config"
        )

    return TenantDetailResponse(
        name=config.tenant_name,
        display_name=config.display_name,
        cloud=config.cloud,
        gcp_project=config.gcp.project_id,
        aws_region=config.aws.region,
        escalation_email=config.escalation_email,
        slack_channel=config.slack_channel,
    )


@router.post("/reload", dependencies=[Depends(require_role("admin"))])
async def reload_tenant_config() -> dict[str, int | str | list[str]]:
    """Reload tenant config from disk without restarting the server (admin only)."""
    reload_config = cast(Callable[[], None], _tenant_config_module().reload_config)
    list_tenants = cast(Callable[[], list[str]], _tenant_config_module().list_tenants)

    reload_config()
    names = list_tenants()
    logger.info("tenant_config_reloaded_via_api", count=len(names))
    return {"status": "reloaded", "tenant_count": len(names), "tenants": names}


@router.get("/{tenant_name}/servers/{server_name}")
async def get_server_detail(
    tenant_name: str,
    server_name: str,
) -> dict[str, str]:
    """Look up a specific server within a tenant."""
    get_server_by_name = cast(
        Callable[[str, str], Any],
        _tenant_config_module().get_server_by_name,
    )
    server = get_server_by_name(tenant_name, server_name)
    if server is None:
        raise HTTPException(
            status_code=404,
            detail=f"Server '{server_name}' not found for tenant '{tenant_name}'",
        )
    return {
        "name": server.name,
        "instance_id": server.instance_id,
        "private_ip": server.private_ip,
        "cloud": server.cloud,
        "role": server.role,
    }
