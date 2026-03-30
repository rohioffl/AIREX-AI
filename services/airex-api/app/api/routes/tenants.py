"""
Tenant configuration API — full CRUD.

Provides:
  - GET  /tenants/              — list all active tenants
  - GET  /tenants/{name}        — tenant detail (with credential status)
  - POST /tenants/              — create tenant (admin)
  - PUT  /tenants/{name}        — update tenant (admin)
  - DELETE /tenants/{name}      — soft-delete tenant (admin)
  - POST /tenants/reload        — force-refresh config cache (admin)
  - GET  /tenants/{name}/servers/{srv} — server lookup (unchanged)

Reads/writes go to the ``tenants`` PostgreSQL table.  The runtime config
layer (``tenant_config.py``) is notified on every write so the 60-second
cache is always fresh.
"""

import json
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, column, false, func, or_, select, table, text as sa_text, update
from sqlalchemy.dialects.postgresql import JSONB

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    RequirePlatformAdmin,
    authorize_org_admin,
    get_auth_session,
    get_authenticated_user,
    get_home_organization_id,
    require_role,
)
from airex_core.cloud import tenant_config
from airex_core.core.database import engine as async_engine
from airex_core.core.rbac import normalize_role_name
from airex_core.core.security import TokenData
from airex_core.models.organization_membership import OrganizationMembership
from airex_core.models.tenant import Tenant
from airex_core.models.tenant_membership import TenantMembership

logger = structlog.get_logger()
router = APIRouter()
TENANTS_TABLE = table(
    "tenants",
    column("name"),
    column("display_name"),
    column("cloud"),
    column("organization_id"),
    column("is_active"),
    column("escalation_email"),
    column("slack_channel"),
    column("ssh_user"),
    column("aws_config"),
    column("gcp_config"),
    column("servers"),
    column("updated_at"),
)


# ═══════════════════════════════════════════════════════════════════
#  Schemas
# ═══════════════════════════════════════════════════════════════════


class TenantSummary(BaseModel):
    id: str | None = None
    name: str
    display_name: str
    cloud: str
    organization_id: str | None = None
    server_count: int
    escalation_email: str
    is_active: bool = True
    credential_status: str = "unknown"  # "configured" | "missing" | "unknown"


class TenantDetailResponse(BaseModel):
    id: str
    name: str
    display_name: str
    cloud: str
    organization_id: str | None = None
    is_active: bool
    escalation_email: str
    slack_channel: str
    ssh_user: str
    aws_config: dict = {}
    gcp_config: dict = {}
    servers: list = []
    credential_status: str = "unknown"
    config_source: str = "db"


class TenantCreateRequest(BaseModel):
    organization_id: str | None = None
    name: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    display_name: str = Field(..., min_length=2, max_length=255)
    cloud: str = Field(..., pattern=r"^(aws|gcp)$")
    escalation_email: str = ""
    slack_channel: str = ""
    ssh_user: str = "ubuntu"
    aws_config: dict = {}
    gcp_config: dict = {}
    servers: list = []


class TenantUpdateRequest(BaseModel):
    organization_id: str | None = None
    display_name: str | None = None
    cloud: str | None = Field(None, pattern=r"^(aws|gcp)$")
    escalation_email: str | None = None
    slack_channel: str | None = None
    ssh_user: str | None = None
    aws_config: dict | None = None
    gcp_config: dict | None = None
    servers: list | None = None
    is_active: bool | None = None


class AccessibleTenantEntry(BaseModel):
    id: str
    name: str
    display_name: str
    cloud: str
    organization_id: str | None = None
    is_active: bool
    role: str  # effective role in this tenant


# ═══════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════


def _credential_status(cloud: str, aws_config: dict, gcp_config: dict) -> str:
    """Determine whether credentials are configured for the tenant."""
    if cloud == "aws":
        c = aws_config or {}
        has_role = bool(c.get("account_id") and c.get("role_name")) or bool(c.get("role_arn"))
        has_keys = bool(c.get("access_key_id") and c.get("secret_access_key"))
        has_file = bool(c.get("credentials_file"))
        return "configured" if (has_role or has_keys or has_file) else "missing"
    elif cloud == "gcp":
        c = gcp_config or {}
        has_key = bool(c.get("service_account_key"))
        has_project = bool(c.get("project_id"))
        return "configured" if (has_key or has_project) else "missing"
    return "unknown"


def _invalidate_cache() -> None:
    """Force tenant_config.py to reload from DB on next access."""
    try:
        tenant_config.reload_config()
    except Exception as exc:
        logger.warning("cache_invalidation_failed", error=str(exc))


async def _get_visible_org_ids(
    session: AsyncSession,
    current_user: TokenData,
) -> set[uuid.UUID]:
    org_ids: set[uuid.UUID] = set()
    home_org_id = await get_home_organization_id(session, current_user)
    if home_org_id is not None:
        org_ids.add(home_org_id)

    membership_result = await session.execute(
        select(OrganizationMembership.organization_id).where(
            OrganizationMembership.user_id == current_user.user_id
        )
    )
    org_ids.update(membership_result.scalars().all())
    return org_ids


async def _get_visible_tenant_ids(
    session: AsyncSession,
    current_user: TokenData,
) -> set[uuid.UUID]:
    tenant_ids = {current_user.tenant_id}
    membership_result = await session.execute(
        select(TenantMembership.tenant_id).where(
            TenantMembership.user_id == current_user.user_id
        )
    )
    tenant_ids.update(membership_result.scalars().all())
    return tenant_ids


async def _get_tenant_organization_id(
    tenant_name: str,
) -> uuid.UUID:
    async with async_engine.connect() as conn:
        result = await conn.execute(
            select(Tenant.organization_id).where(
                func.lower(Tenant.name) == tenant_name.lower().strip()
            )
        )
        organization_id = result.scalar_one_or_none()
    if organization_id is None:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_name}' not found")
    return organization_id


# ═══════════════════════════════════════════════════════════════════
#  Routes
# ═══════════════════════════════════════════════════════════════════


@router.get(
    "/",
    response_model=list[TenantSummary],
    dependencies=[Depends(require_role("viewer", "operator", "admin", "platform_admin"))],
)
async def list_all_tenants(
    current_user: TokenData = Depends(get_authenticated_user),
    auth_session: AsyncSession = Depends(get_auth_session),
) -> list[TenantSummary]:
    """List active tenants visible to the current user."""
    is_platform_admin = normalize_role_name(current_user.role) == "platform_admin"

    result: list[TenantSummary] = []
    async with async_engine.connect() as conn:
        if is_platform_admin:
            rows = await conn.execute(
                select(Tenant)
                .where(Tenant.is_active.is_(True))
                .order_by(Tenant.name.asc())
            )
            tenants = rows.scalars().all()
        else:
            visible_org_ids = await _get_visible_org_ids(auth_session, current_user)
            visible_tenant_ids = await _get_visible_tenant_ids(auth_session, current_user)

            if not visible_org_ids and not visible_tenant_ids:
                return []

            rows = await conn.execute(
                select(Tenant)
                .where(
                    Tenant.is_active.is_(True),
                    or_(
                        Tenant.organization_id.in_(list(visible_org_ids))
                        if visible_org_ids
                        else false(),
                        Tenant.id.in_(list(visible_tenant_ids))
                        if visible_tenant_ids
                        else false(),
                    ),
                )
                .order_by(Tenant.name.asc())
            )
            tenants = rows.scalars().all()

        for tenant in tenants:
            result.append(
                TenantSummary(
                    id=str(tenant.id),
                    name=tenant.name,
                    display_name=tenant.display_name,
                    cloud=tenant.cloud,
                    organization_id=str(tenant.organization_id) if tenant.organization_id else None,
                    server_count=len(tenant.servers) if isinstance(tenant.servers, list) else 0,
                    escalation_email=tenant.escalation_email or "",
                    is_active=tenant.is_active,
                    credential_status=_credential_status(
                        tenant.cloud,
                        tenant.aws_config or {},
                        tenant.gcp_config or {},
                    ),
                )
            )
    return result


@router.get(
    "/accessible",
    response_model=list[AccessibleTenantEntry],
)
async def list_accessible_tenants(
    current_user: TokenData = Depends(get_authenticated_user),
    auth_session: AsyncSession = Depends(get_auth_session),
) -> list[AccessibleTenantEntry]:
    """List all tenants accessible to the current user with their effective role."""
    is_platform_admin = normalize_role_name(current_user.role) == "platform_admin"
    result: list[AccessibleTenantEntry] = []

    async with async_engine.connect() as conn:
        if is_platform_admin:
            rows = await conn.execute(
                select(Tenant).where(Tenant.is_active.is_(True)).order_by(Tenant.name.asc())
            )
            for tenant in rows.all():
                result.append(
                    AccessibleTenantEntry(
                        id=str(tenant.id),
                        name=tenant.name,
                        display_name=tenant.display_name,
                        cloud=tenant.cloud,
                        organization_id=str(tenant.organization_id) if tenant.organization_id else None,
                        is_active=tenant.is_active,
                        role="platform_admin",
                    )
                )
            return result

        # Collect explicit tenant memberships
        explicit_roles: dict[uuid.UUID, str] = {}
        membership_rows = await auth_session.execute(
            select(TenantMembership.tenant_id, TenantMembership.role).where(
                TenantMembership.user_id == current_user.user_id
            )
        )
        for tid, role in membership_rows.all():
            explicit_roles[tid] = str(role)

        # Collect org memberships → inherit role for all org tenants
        org_roles: dict[uuid.UUID, str] = {}
        org_membership_rows = await auth_session.execute(
            select(OrganizationMembership.organization_id, OrganizationMembership.role).where(
                OrganizationMembership.user_id == current_user.user_id
            )
        )
        for oid, role in org_membership_rows.all():
            org_roles[oid] = str(role)

        # Home tenant (JWT) and home org
        visible_ids = set(explicit_roles.keys()) | {current_user.tenant_id}
        visible_org_ids = set(org_roles.keys())
        home_org_id = await get_home_organization_id(auth_session, current_user)
        if home_org_id:
            visible_org_ids.add(home_org_id)

        if not visible_ids and not visible_org_ids:
            return []

        rows = await conn.execute(
            select(Tenant).where(
                Tenant.is_active.is_(True),
                or_(
                    Tenant.id.in_(list(visible_ids)) if visible_ids else false(),
                    Tenant.organization_id.in_(list(visible_org_ids)) if visible_org_ids else false(),
                ),
            ).order_by(Tenant.name.asc())
        )
        for tenant in rows.all():
            if tenant.id in explicit_roles:
                eff_role = explicit_roles[tenant.id]
            elif tenant.organization_id and tenant.organization_id in org_roles:
                eff_role = org_roles[tenant.organization_id]
            else:
                eff_role = current_user.role
            result.append(
                AccessibleTenantEntry(
                    id=str(tenant.id),
                    name=tenant.name,
                    display_name=tenant.display_name,
                    cloud=tenant.cloud,
                    organization_id=str(tenant.organization_id) if tenant.organization_id else None,
                    is_active=tenant.is_active,
                    role=eff_role,
                )
            )
    return result


@router.get(
    "/{tenant_name}",
    response_model=TenantDetailResponse,
    dependencies=[Depends(require_role("viewer", "operator", "admin"))],
)
async def get_tenant_detail(tenant_name: str) -> TenantDetailResponse:
    """Get detailed configuration for a specific tenant."""
    async with async_engine.connect() as conn:
        row = (
            await conn.execute(
                sa_text(
                    """
                    SELECT id, name, display_name, cloud, is_active,
                           organization_id, escalation_email, slack_channel, ssh_user,
                           aws_config, gcp_config, servers
                    FROM tenants
                    WHERE lower(name) = :name
                    """
                ),
                {"name": tenant_name.lower().strip()},
            )
        ).first()

    if not row:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_name}' not found")

    tid, name, display_name, cloud, is_active, organization_id, email, slack, ssh_user, aws_cfg, gcp_cfg, servers = row

    # Redact sensitive fields for the response
    safe_aws: dict[str, Any] = dict(aws_cfg) if aws_cfg else {}
    if safe_aws.get("secret_access_key"):
        safe_aws["secret_access_key"] = "••••••••"

    return TenantDetailResponse(
        id=str(tid),
        name=name,
        display_name=display_name,
        cloud=cloud,
        organization_id=str(organization_id),
        is_active=is_active,
        escalation_email=email or "",
        slack_channel=slack or "",
        ssh_user=ssh_user or "ubuntu",
        aws_config=safe_aws,
        gcp_config=dict(gcp_cfg) if gcp_cfg else {},
        servers=list(servers) if servers else [],
        credential_status=_credential_status(cloud, aws_cfg or {}, gcp_cfg or {}),
        config_source=tenant_config.get_config_source(),
    )


@router.post("/", status_code=201)
async def create_tenant(req: TenantCreateRequest, _: RequirePlatformAdmin) -> dict:
    """Create a new tenant (admin only)."""
    tenant_id = uuid.uuid4()

    async with async_engine.begin() as conn:
        # Check for duplicate name
        existing = (
            await conn.execute(
                sa_text("SELECT 1 FROM tenants WHERE lower(name) = :name"),
                {"name": req.name.lower()},
            )
        ).first()

        if existing:
            raise HTTPException(
                status_code=409, detail=f"Tenant '{req.name}' already exists"
            )

        await conn.execute(
            sa_text(
                """
                INSERT INTO tenants (id, name, display_name, cloud,
                                     organization_id, escalation_email, slack_channel, ssh_user,
                                     aws_config, gcp_config, servers)
                VALUES (:id, :name, :display_name, :cloud, :organization_id,
                        :escalation_email, :slack_channel, :ssh_user,
                        CAST(:aws_config AS jsonb),
                        CAST(:gcp_config AS jsonb),
                        CAST(:servers AS jsonb))
                """
            ),
            {
                "id": str(tenant_id),
                "name": req.name.lower(),
                "display_name": req.display_name,
                "cloud": req.cloud,
                "organization_id": req.organization_id,
                "escalation_email": req.escalation_email,
                "slack_channel": req.slack_channel,
                "ssh_user": req.ssh_user,
                "aws_config": json.dumps(req.aws_config),
                "gcp_config": json.dumps(req.gcp_config),
                "servers": json.dumps(req.servers),
            },
        )

    _invalidate_cache()
    logger.info("tenant_created", name=req.name, id=str(tenant_id))
    return {"status": "created", "name": req.name, "id": str(tenant_id)}


@router.put("/{tenant_name}")
async def update_tenant(
    tenant_name: str,
    req: TenantUpdateRequest,
    current_user: TokenData = Depends(get_authenticated_user),
    auth_session: AsyncSession = Depends(get_auth_session),
) -> dict:
    """Update an existing tenant. Platform admin or org admin required."""
    if normalize_role_name(current_user.role) != "platform_admin":
        organization_id = await _get_tenant_organization_id(tenant_name)
        if not await authorize_org_admin(auth_session, current_user, organization_id):
            raise HTTPException(
                status_code=403,
                detail="Organization admin required for this tenant",
            )

    scalar_updates: dict[str, Any] = {}
    if req.display_name is not None:
        scalar_updates["display_name"] = req.display_name
    if req.cloud is not None:
        scalar_updates["cloud"] = req.cloud
    if req.escalation_email is not None:
        scalar_updates["escalation_email"] = req.escalation_email
    if req.slack_channel is not None:
        scalar_updates["slack_channel"] = req.slack_channel
    if req.ssh_user is not None:
        scalar_updates["ssh_user"] = req.ssh_user
    if req.is_active is not None:
        scalar_updates["is_active"] = req.is_active
    if req.organization_id is not None:
        scalar_updates["organization_id"] = req.organization_id

    jsonb_updates: dict[str, Any] = {}
    if req.aws_config is not None:
        jsonb_updates["aws_config"] = req.aws_config
    if req.gcp_config is not None:
        jsonb_updates["gcp_config"] = req.gcp_config
    if req.servers is not None:
        jsonb_updates["servers"] = req.servers

    if not scalar_updates and not jsonb_updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    params: dict[str, Any] = {"tenant_name": tenant_name.lower().strip()}
    update_values: dict[str, Any] = {"updated_at": func.current_timestamp()}
    for col, val in scalar_updates.items():
        params[col] = val
    for col, val in jsonb_updates.items():
        params[col] = val
        update_values[col] = bindparam(col, type_=JSONB)
    update_values.update(scalar_updates)
    stmt = (
        update(TENANTS_TABLE)
        .where(func.lower(TENANTS_TABLE.c.name) == bindparam("tenant_name"))
        .values(**update_values)
    )

    async with async_engine.begin() as conn:
        result = await conn.execute(stmt, params)

        if result.rowcount == 0:
            raise HTTPException(
                status_code=404, detail=f"Tenant '{tenant_name}' not found"
            )

    _invalidate_cache()
    logger.info(
        "tenant_updated",
        name=tenant_name,
        fields=list(scalar_updates.keys()) + list(jsonb_updates.keys()),
    )
    return {"status": "updated", "name": tenant_name}


@router.delete("/{tenant_name}")
async def delete_tenant(
    tenant_name: str,
    current_user: TokenData = Depends(get_authenticated_user),
    auth_session: AsyncSession = Depends(get_auth_session),
) -> dict:
    """Soft-delete a tenant. Platform admin or org admin required."""
    if normalize_role_name(current_user.role) != "platform_admin":
        organization_id = await _get_tenant_organization_id(tenant_name)
        if not await authorize_org_admin(auth_session, current_user, organization_id):
            raise HTTPException(
                status_code=403,
                detail="Organization admin required for this tenant",
            )

    async with async_engine.begin() as conn:
        result = await conn.execute(
            sa_text(
                """
                UPDATE tenants
                SET is_active = false, updated_at = CURRENT_TIMESTAMP
                WHERE lower(name) = :name AND is_active = true
                """
            ),
            {"name": tenant_name.lower().strip()},
        )

        if result.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Tenant '{tenant_name}' not found or already deleted",
            )

    _invalidate_cache()
    logger.info("tenant_deleted", name=tenant_name)
    return {"status": "deleted", "name": tenant_name}


@router.post("/reload")
async def reload_tenant_config(_: RequirePlatformAdmin) -> dict:
    """Reload tenant config cache (admin only)."""
    _invalidate_cache()
    names = tenant_config.list_tenants()

    return {
        "status": "reloaded",
        "source": tenant_config.get_config_source(),
        "tenant_count": len(names),
        "tenants": names,
    }


@router.get(
    "/{tenant_name}/servers/{server_name}",
    dependencies=[Depends(require_role("viewer", "operator", "admin"))],
)
async def get_server_detail(tenant_name: str, server_name: str) -> dict[str, str]:
    """Look up a specific server within a tenant."""

    server = tenant_config.get_server_by_name(tenant_name, server_name)
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
