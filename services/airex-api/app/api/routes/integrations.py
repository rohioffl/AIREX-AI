"""Platform and tenant-owned monitoring integration APIs."""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    RequirePlatformAdmin,
    authorize_tenant_access,
    authorize_tenant_admin,
    get_auth_session,
    get_authenticated_user,
)
from airex_core.core.database import engine as async_engine
from airex_core.core.rbac import normalize_role_name
from airex_core.core.security import TokenData

router = APIRouter()


class IntegrationTypeResponse(BaseModel):
    id: str
    key: str
    display_name: str
    category: str
    enabled: bool
    supports_webhook: bool
    supports_polling: bool
    supports_sync: bool
    config_schema_json: dict = {}


class IntegrationTypeRequest(BaseModel):
    key: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    display_name: str = Field(..., min_length=2, max_length=255)
    category: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    enabled: bool = True
    supports_webhook: bool = True
    supports_polling: bool = False
    supports_sync: bool = True
    config_schema_json: dict = {}


class MonitoringIntegrationRequest(BaseModel):
    integration_type_id: uuid.UUID | None = None
    integration_type_key: str | None = None
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    enabled: bool = True
    config_json: dict = {}
    secret_ref: str | None = None
    webhook_token_ref: str | None = None


class MonitoringIntegrationResponse(BaseModel):
    id: str
    tenant_id: str
    integration_type_id: str
    integration_type_key: str | None = None
    webhook_path: str | None = None
    name: str
    slug: str
    enabled: bool
    config_json: dict = {}
    secret_ref: str | None = None
    webhook_token_ref: str | None = None
    status: str
    last_tested_at: str | None = None
    last_sync_at: str | None = None


class IntegrationConnectionCheck(BaseModel):
    code: str
    status: str
    detail: str


class IntegrationConnectionTestResponse(BaseModel):
    status: str
    integration_id: str
    tenant_id: str
    integration_type_key: str
    success: bool
    detail: str
    checks: list[IntegrationConnectionCheck]


class ExternalMonitorResponse(BaseModel):
    id: str
    integration_id: str
    external_monitor_id: str
    external_name: str
    monitor_type: str
    status: str
    metadata_json: dict = {}
    enabled: bool


class SyncMonitorRequest(BaseModel):
    monitors: list[dict] = []


class ProjectMonitorBindingRequest(BaseModel):
    external_monitor_id: uuid.UUID
    enabled: bool = True
    alert_type_override: str | None = None
    resource_mapping_json: dict = {}
    routing_tags_json: dict = {}


async def _resolve_integration_type(
    conn,
    *,
    integration_type_id: uuid.UUID | None,
    integration_type_key: str | None,
):
    if integration_type_id:
        return (
            await conn.execute(
                sa_text(
                    "SELECT id, key FROM integration_types WHERE id = :integration_type_id AND enabled = true"
                ),
                {"integration_type_id": str(integration_type_id)},
            )
        ).first()
    if integration_type_key:
        return (
            await conn.execute(
                sa_text(
                    "SELECT id, key FROM integration_types WHERE lower(key) = :integration_type_key AND enabled = true"
                ),
                {"integration_type_key": integration_type_key.lower()},
            )
        ).first()
    raise HTTPException(status_code=400, detail="integration_type_id or integration_type_key is required")


async def _require_tenant_access(
    session: AsyncSession,
    current_user: TokenData,
    tenant_id: uuid.UUID,
) -> None:
    if not await authorize_tenant_access(session, current_user, tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for tenant",
        )


async def _require_tenant_admin(
    session: AsyncSession,
    current_user: TokenData,
    tenant_id: uuid.UUID,
) -> None:
    if not await authorize_tenant_admin(session, current_user, tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant admin required",
        )


async def _get_integration_tenant_id(
    session: AsyncSession,
    integration_id: uuid.UUID,
) -> uuid.UUID:
    result = await session.execute(
        sa_text("SELECT tenant_id FROM monitoring_integrations WHERE id = :integration_id"),
        {"integration_id": str(integration_id)},
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return uuid.UUID(str(row.tenant_id))


async def _get_project_tenant_id(
    session: AsyncSession,
    project_id: uuid.UUID,
) -> uuid.UUID:
    result = await session.execute(
        sa_text("SELECT tenant_id FROM projects WHERE id = :project_id"),
        {"project_id": str(project_id)},
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return uuid.UUID(str(row.tenant_id))


async def _get_binding_tenant_id(
    session: AsyncSession,
    binding_id: uuid.UUID,
) -> uuid.UUID:
    result = await session.execute(
        sa_text(
            """
            SELECT p.tenant_id
            FROM project_monitor_bindings pmb
            JOIN projects p ON p.id = pmb.project_id
            WHERE pmb.id = :binding_id
            """
        ),
        {"binding_id": str(binding_id)},
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project binding not found")
    return uuid.UUID(str(row.tenant_id))


class ProjectMonitorBindingResponse(BaseModel):
    id: str
    project_id: str
    external_monitor_id: str
    enabled: bool
    alert_type_override: str | None = None
    resource_mapping_json: dict = {}
    routing_tags_json: dict = {}


def _build_webhook_path(integration_type_key: str | None, integration_id: str) -> str | None:
    if not integration_type_key:
        return None
    return f"/api/v1/webhooks/{integration_type_key}/{integration_id}"


def _serialize_integration_type(row) -> IntegrationTypeResponse:
    return IntegrationTypeResponse(
        id=str(row.id),
        key=row.key,
        display_name=row.display_name,
        category=row.category,
        enabled=row.enabled,
        supports_webhook=row.supports_webhook,
        supports_polling=row.supports_polling,
        supports_sync=row.supports_sync,
        config_schema_json=dict(row.config_schema_json or {}),
    )


def _validate_integration_configuration(row) -> tuple[bool, list[IntegrationConnectionCheck], str]:
    config = dict(row.config_json or {})
    schema = dict(row.config_schema_json or {})
    properties = schema.get("properties") or {}
    required_fields = schema.get("required") or []
    checks: list[IntegrationConnectionCheck] = []
    missing_required: list[str] = []

    for field_name in required_fields:
        field_meta = properties.get(field_name) or {}
        field_value = config.get(field_name)
        has_value = field_value not in (None, "", [], {})
        secret_backed = bool(field_meta.get("secret")) and bool(row.secret_ref)
        if has_value or secret_backed:
            checks.append(
                IntegrationConnectionCheck(
                    code=f"required:{field_name}",
                    status="passed",
                    detail=f"{field_name} is configured",
                )
            )
            continue
        missing_required.append(field_name)
        checks.append(
            IntegrationConnectionCheck(
                code=f"required:{field_name}",
                status="failed",
                detail=f"{field_name} is required by the integration schema",
            )
        )

    for field_name, value in config.items():
        if field_name.endswith("_url") or field_name == "base_url":
            valid = isinstance(value, str) and value.startswith(("http://", "https://"))
            checks.append(
                IntegrationConnectionCheck(
                    code=f"url:{field_name}",
                    status="passed" if valid else "failed",
                    detail=(
                        f"{field_name} uses a valid HTTP(S) URL"
                        if valid
                        else f"{field_name} must start with http:// or https://"
                    ),
                )
            )

    if row.supports_webhook:
        has_webhook_secret = bool(row.webhook_token_ref) or bool(config.get("webhook_secret")) or bool(config.get("hmac_secret"))
        checks.append(
            IntegrationConnectionCheck(
                code="webhook:secret",
                status="passed" if has_webhook_secret else "warning",
                detail=(
                    "Webhook secret is configured"
                    if has_webhook_secret
                    else "No webhook secret configured; webhook validation may be weaker than intended"
                ),
            )
        )

    failed_checks = [check for check in checks if check.status == "failed"]
    success = not missing_required and not failed_checks
    if success:
        detail = "Connection configuration validated for the active tenant workspace"
    elif missing_required:
        detail = f"Missing required integration fields: {', '.join(missing_required)}"
    else:
        detail = "Integration configuration failed validation checks"

    return success, checks, detail


@router.get("/integration-types", response_model=list[IntegrationTypeResponse])
async def list_integration_types(
    current_user: TokenData = Depends(get_authenticated_user),
    include_disabled: bool = Query(default=False),
) -> list[IntegrationTypeResponse]:
    async with async_engine.connect() as conn:
        if include_disabled and normalize_role_name(current_user.role) != "platform_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Platform admin required to view disabled integration types",
            )
        rows = await conn.execute(
            sa_text(
                """
                SELECT id, key, display_name, category, enabled, supports_webhook, supports_polling, supports_sync, config_schema_json
                FROM integration_types
                WHERE (:include_disabled = true OR enabled = true)
                ORDER BY display_name
                """
            ),
            {"include_disabled": include_disabled},
        )
        return [_serialize_integration_type(row) for row in rows]


@router.get("/integration-types/{integration_type_id}", response_model=IntegrationTypeResponse)
async def get_integration_type(
    integration_type_id: uuid.UUID,
    _: RequirePlatformAdmin,
    __: TokenData = Depends(get_authenticated_user),
) -> IntegrationTypeResponse:
    async with async_engine.connect() as conn:
        row = (
            await conn.execute(
                sa_text(
                    """
                    SELECT id, key, display_name, category, enabled, supports_webhook, supports_polling, supports_sync, config_schema_json
                    FROM integration_types
                    WHERE id = :integration_type_id
                    """
                ),
                {"integration_type_id": str(integration_type_id)},
            )
        ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration type not found")
    return _serialize_integration_type(row)


@router.post("/integration-types", response_model=IntegrationTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_integration_type(
    body: IntegrationTypeRequest,
    _: RequirePlatformAdmin,
    __: TokenData = Depends(get_authenticated_user),
) -> IntegrationTypeResponse:
    integration_type_id = uuid.uuid4()
    async with async_engine.begin() as conn:
        existing = (
            await conn.execute(
                sa_text("SELECT id FROM integration_types WHERE lower(key) = :key"),
                {"key": body.key.lower()},
            )
        ).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Integration type key already exists")
        await conn.execute(
            sa_text(
                """
                INSERT INTO integration_types (
                    id, key, display_name, category, enabled, supports_webhook,
                    supports_polling, supports_sync, config_schema_json
                ) VALUES (
                    :id, :key, :display_name, :category, :enabled, :supports_webhook,
                    :supports_polling, :supports_sync, CAST(:config_schema_json AS jsonb)
                )
                """
            ),
            {
                "id": str(integration_type_id),
                "key": body.key.lower(),
                "display_name": body.display_name,
                "category": body.category.lower(),
                "enabled": body.enabled,
                "supports_webhook": body.supports_webhook,
                "supports_polling": body.supports_polling,
                "supports_sync": body.supports_sync,
                "config_schema_json": json.dumps(body.config_schema_json),
            },
        )
    return IntegrationTypeResponse(
        id=str(integration_type_id),
        key=body.key.lower(),
        display_name=body.display_name,
        category=body.category.lower(),
        enabled=body.enabled,
        supports_webhook=body.supports_webhook,
        supports_polling=body.supports_polling,
        supports_sync=body.supports_sync,
        config_schema_json=body.config_schema_json,
    )


@router.put("/integration-types/{integration_type_id}", response_model=IntegrationTypeResponse)
async def update_integration_type(
    integration_type_id: uuid.UUID,
    body: IntegrationTypeRequest,
    _: RequirePlatformAdmin,
    __: TokenData = Depends(get_authenticated_user),
) -> IntegrationTypeResponse:
    async with async_engine.begin() as conn:
        existing = (
            await conn.execute(
                sa_text("SELECT id FROM integration_types WHERE id = :integration_type_id"),
                {"integration_type_id": str(integration_type_id)},
            )
        ).first()
        if existing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration type not found")
        conflict = (
            await conn.execute(
                sa_text(
                    "SELECT id FROM integration_types WHERE lower(key) = :key AND id <> :integration_type_id"
                ),
                {"key": body.key.lower(), "integration_type_id": str(integration_type_id)},
            )
        ).first()
        if conflict:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Integration type key already exists")
        await conn.execute(
            sa_text(
                """
                UPDATE integration_types
                SET key = :key,
                    display_name = :display_name,
                    category = :category,
                    enabled = :enabled,
                    supports_webhook = :supports_webhook,
                    supports_polling = :supports_polling,
                    supports_sync = :supports_sync,
                    config_schema_json = CAST(:config_schema_json AS jsonb),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :integration_type_id
                """
            ),
            {
                "integration_type_id": str(integration_type_id),
                "key": body.key.lower(),
                "display_name": body.display_name,
                "category": body.category.lower(),
                "enabled": body.enabled,
                "supports_webhook": body.supports_webhook,
                "supports_polling": body.supports_polling,
                "supports_sync": body.supports_sync,
                "config_schema_json": json.dumps(body.config_schema_json),
            },
        )
    return IntegrationTypeResponse(
        id=str(integration_type_id),
        key=body.key.lower(),
        display_name=body.display_name,
        category=body.category.lower(),
        enabled=body.enabled,
        supports_webhook=body.supports_webhook,
        supports_polling=body.supports_polling,
        supports_sync=body.supports_sync,
        config_schema_json=body.config_schema_json,
    )


@router.delete("/integration-types/{integration_type_id}")
async def delete_integration_type(
    integration_type_id: uuid.UUID,
    _: RequirePlatformAdmin,
    __: TokenData = Depends(get_authenticated_user),
) -> dict[str, str]:
    async with async_engine.begin() as conn:
        result = await conn.execute(
            sa_text(
                """
                UPDATE integration_types
                SET enabled = false, updated_at = CURRENT_TIMESTAMP
                WHERE id = :integration_type_id
                """
            ),
            {"integration_type_id": str(integration_type_id)},
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration type not found")
    return {"status": "disabled"}


@router.get("/tenants/{tenant_id}/integrations", response_model=list[MonitoringIntegrationResponse])
async def list_monitoring_integrations(
    tenant_id: uuid.UUID,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> list[MonitoringIntegrationResponse]:
    await _require_tenant_access(session, current_user, tenant_id)
    async with async_engine.connect() as conn:
        rows = await conn.execute(
            sa_text(
                """
                SELECT mi.id, mi.tenant_id, mi.integration_type_id, it.key AS integration_type_key,
                       mi.name, mi.slug, mi.enabled, mi.config_json, mi.secret_ref,
                       mi.webhook_token_ref, mi.status, mi.last_tested_at, mi.last_sync_at
                FROM monitoring_integrations mi
                JOIN integration_types it ON it.id = mi.integration_type_id
                WHERE mi.tenant_id = :tenant_id
                ORDER BY mi.name
                """
            ),
            {"tenant_id": str(tenant_id)},
        )
        return [
            MonitoringIntegrationResponse(
                id=str(row.id),
                tenant_id=str(row.tenant_id),
                integration_type_id=str(row.integration_type_id),
                integration_type_key=row.integration_type_key,
                webhook_path=_build_webhook_path(row.integration_type_key, str(row.id)),
                name=row.name,
                slug=row.slug,
                enabled=row.enabled,
                config_json=dict(row.config_json or {}),
                secret_ref=row.secret_ref,
                webhook_token_ref=row.webhook_token_ref,
                status=row.status,
                last_tested_at=str(row.last_tested_at) if row.last_tested_at else None,
                last_sync_at=str(row.last_sync_at) if row.last_sync_at else None,
            )
            for row in rows
        ]


@router.post("/tenants/{tenant_id}/integrations", response_model=MonitoringIntegrationResponse, status_code=201)
async def create_monitoring_integration(
    tenant_id: uuid.UUID,
    body: MonitoringIntegrationRequest,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> MonitoringIntegrationResponse:
    await _require_tenant_admin(session, current_user, tenant_id)
    integration_id = uuid.uuid4()
    async with async_engine.begin() as conn:
        tenant = (await conn.execute(sa_text("SELECT id FROM tenants WHERE id = :tenant_id"), {"tenant_id": str(tenant_id)})).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        integration_type = await _resolve_integration_type(
            conn,
            integration_type_id=body.integration_type_id,
            integration_type_key=body.integration_type_key,
        )
        if not integration_type:
            raise HTTPException(status_code=404, detail="Integration type not found")
        conflict = (
            await conn.execute(
                sa_text(
                    "SELECT id FROM monitoring_integrations WHERE tenant_id = :tenant_id AND lower(slug) = :slug"
                ),
                {"tenant_id": str(tenant_id), "slug": body.slug.lower()},
            )
        ).first()
        if conflict:
            raise HTTPException(status_code=409, detail="Integration slug already exists in tenant")
        await conn.execute(
            sa_text(
                """
                INSERT INTO monitoring_integrations (
                    id, tenant_id, integration_type_id, name, slug, enabled,
                    config_json, secret_ref, webhook_token_ref, status
                )
                VALUES (
                    :id, :tenant_id, :integration_type_id, :name, :slug, :enabled,
                    CAST(:config_json AS jsonb), :secret_ref, :webhook_token_ref, 'configured'
                )
                """
            ),
            {
                "id": str(integration_id),
                "tenant_id": str(tenant_id),
                "integration_type_id": str(integration_type.id),
                "name": body.name,
                "slug": body.slug.lower(),
                "enabled": body.enabled,
                "config_json": json.dumps(body.config_json),
                "secret_ref": body.secret_ref,
                "webhook_token_ref": body.webhook_token_ref,
            },
        )
    return MonitoringIntegrationResponse(
        id=str(integration_id),
        tenant_id=str(tenant_id),
        integration_type_id=str(integration_type.id),
        integration_type_key=integration_type.key,
        webhook_path=_build_webhook_path(integration_type.key, str(integration_id)),
        name=body.name,
        slug=body.slug.lower(),
        enabled=body.enabled,
        config_json=body.config_json,
        secret_ref=body.secret_ref,
        webhook_token_ref=body.webhook_token_ref,
        status="configured",
    )


@router.get("/integrations/{integration_id}", response_model=MonitoringIntegrationResponse)
async def get_monitoring_integration(
    integration_id: uuid.UUID,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> MonitoringIntegrationResponse:
    tenant_id = await _get_integration_tenant_id(session, integration_id)
    await _require_tenant_access(session, current_user, tenant_id)
    async with async_engine.connect() as conn:
        row = (
            await conn.execute(
                sa_text(
                    """
                    SELECT mi.id, mi.tenant_id, mi.integration_type_id, it.key AS integration_type_key,
                           mi.name, mi.slug, mi.enabled, mi.config_json, mi.secret_ref,
                           mi.webhook_token_ref, mi.status, mi.last_tested_at, mi.last_sync_at
                    FROM monitoring_integrations mi
                    JOIN integration_types it ON it.id = mi.integration_type_id
                    WHERE mi.id = :integration_id
                    """
                ),
                {"integration_id": str(integration_id)},
            )
        ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Integration not found")
    return MonitoringIntegrationResponse(
        id=str(row.id),
        tenant_id=str(row.tenant_id),
        integration_type_id=str(row.integration_type_id),
        integration_type_key=row.integration_type_key,
        webhook_path=_build_webhook_path(row.integration_type_key, str(row.id)),
        name=row.name,
        slug=row.slug,
        enabled=row.enabled,
        config_json=dict(row.config_json or {}),
        secret_ref=row.secret_ref,
        webhook_token_ref=row.webhook_token_ref,
        status=row.status,
        last_tested_at=str(row.last_tested_at) if row.last_tested_at else None,
        last_sync_at=str(row.last_sync_at) if row.last_sync_at else None,
    )


@router.put("/integrations/{integration_id}", response_model=MonitoringIntegrationResponse)
async def update_monitoring_integration(
    integration_id: uuid.UUID,
    body: MonitoringIntegrationRequest,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> MonitoringIntegrationResponse:
    tenant_id = await _get_integration_tenant_id(session, integration_id)
    await _require_tenant_admin(session, current_user, tenant_id)
    async with async_engine.begin() as conn:
        current = (
            await conn.execute(
                sa_text("SELECT tenant_id FROM monitoring_integrations WHERE id = :integration_id"),
                {"integration_id": str(integration_id)},
            )
        ).first()
        if not current:
            raise HTTPException(status_code=404, detail="Integration not found")
        conflict = (
            await conn.execute(
                sa_text(
                    "SELECT id FROM monitoring_integrations WHERE tenant_id = :tenant_id AND lower(slug) = :slug AND id <> :integration_id"
                ),
                {"tenant_id": str(current.tenant_id), "slug": body.slug.lower(), "integration_id": str(integration_id)},
            )
        ).first()
        if conflict:
            raise HTTPException(status_code=409, detail="Integration slug already exists in tenant")
        integration_type = await _resolve_integration_type(
            conn,
            integration_type_id=body.integration_type_id,
            integration_type_key=body.integration_type_key,
        )
        if not integration_type:
            raise HTTPException(status_code=404, detail="Integration type not found")
        await conn.execute(
            sa_text(
                """
                UPDATE monitoring_integrations
                SET integration_type_id = :integration_type_id,
                    name = :name,
                    slug = :slug,
                    enabled = :enabled,
                    config_json = CAST(:config_json AS jsonb),
                    secret_ref = :secret_ref,
                    webhook_token_ref = :webhook_token_ref,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :integration_id
                """
            ),
            {
                "integration_id": str(integration_id),
                "integration_type_id": str(integration_type.id),
                "name": body.name,
                "slug": body.slug.lower(),
                "enabled": body.enabled,
                "config_json": json.dumps(body.config_json),
                "secret_ref": body.secret_ref,
                "webhook_token_ref": body.webhook_token_ref,
            },
        )
    updated = await get_monitoring_integration(
        integration_id,
        current_user=current_user,
        session=session,
    )
    updated.integration_type_key = integration_type.key
    return updated


@router.delete("/integrations/{integration_id}")
async def delete_monitoring_integration(
    integration_id: uuid.UUID,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> dict[str, str]:
    tenant_id = await _get_integration_tenant_id(session, integration_id)
    await _require_tenant_admin(session, current_user, tenant_id)
    async with async_engine.begin() as conn:
        result = await conn.execute(
            sa_text(
                "UPDATE monitoring_integrations SET enabled = false, status = 'disabled', updated_at = CURRENT_TIMESTAMP WHERE id = :integration_id"
            ),
            {"integration_id": str(integration_id)},
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Integration not found")
    return {"status": "deleted"}


@router.post("/integrations/{integration_id}/test", response_model=IntegrationConnectionTestResponse)
async def test_monitoring_integration(
    integration_id: uuid.UUID,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> IntegrationConnectionTestResponse:
    tenant_id = await _get_integration_tenant_id(session, integration_id)
    await _require_tenant_admin(session, current_user, tenant_id)
    async with async_engine.begin() as conn:
        result = await conn.execute(
            sa_text(
                """
                SELECT mi.id, mi.tenant_id, mi.config_json, mi.secret_ref, mi.webhook_token_ref,
                       it.key AS integration_type_key, it.supports_webhook, it.config_schema_json
                FROM monitoring_integrations mi
                JOIN integration_types it ON it.id = mi.integration_type_id
                WHERE mi.id = :integration_id
                """
            ),
            {"integration_id": str(integration_id)},
        )
        row = result.first()
        if not row:
            raise HTTPException(status_code=404, detail="Integration not found")
        success, checks, detail = _validate_integration_configuration(row)
        await conn.execute(
            sa_text(
                """
                UPDATE monitoring_integrations
                SET status = :status, last_tested_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = :integration_id
                """
            ),
            {
                "status": "verified" if success else "error",
                "integration_id": str(integration_id),
            },
        )
    return IntegrationConnectionTestResponse(
        status="verified" if success else "error",
        integration_id=str(integration_id),
        tenant_id=str(row.tenant_id),
        integration_type_key=row.integration_type_key,
        success=success,
        detail=detail,
        checks=checks,
    )


@router.post("/integrations/{integration_id}/sync-monitors")
async def sync_external_monitors(
    integration_id: uuid.UUID,
    body: SyncMonitorRequest,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> dict[str, object]:
    tenant_id = await _get_integration_tenant_id(session, integration_id)
    await _require_tenant_admin(session, current_user, tenant_id)
    async with async_engine.begin() as conn:
        integration = (
            await conn.execute(
                sa_text("SELECT id FROM monitoring_integrations WHERE id = :integration_id"),
                {"integration_id": str(integration_id)},
            )
        ).first()
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")
        synced = 0
        for monitor in body.monitors:
            monitor_id = str(uuid.uuid4())
            await conn.execute(
                sa_text(
                    """
                    INSERT INTO external_monitors (
                        id, integration_id, external_monitor_id, external_name,
                        monitor_type, status, metadata_json, enabled, last_seen_at
                    )
                    VALUES (
                        :id, :integration_id, :external_monitor_id, :external_name,
                        :monitor_type, :status, CAST(:metadata_json AS jsonb), :enabled, CURRENT_TIMESTAMP
                    )
                    ON CONFLICT (integration_id, external_monitor_id)
                    DO UPDATE SET external_name = EXCLUDED.external_name,
                                  monitor_type = EXCLUDED.monitor_type,
                                  status = EXCLUDED.status,
                                  metadata_json = EXCLUDED.metadata_json,
                                  enabled = EXCLUDED.enabled,
                                  last_seen_at = CURRENT_TIMESTAMP,
                                  updated_at = CURRENT_TIMESTAMP
                    """
                ),
                {
                    "id": monitor_id,
                    "integration_id": str(integration_id),
                    "external_monitor_id": str(monitor.get("external_monitor_id") or monitor.get("id") or monitor_id),
                    "external_name": monitor.get("external_name") or monitor.get("name") or "Unnamed Monitor",
                    "monitor_type": monitor.get("monitor_type") or "generic",
                    "status": monitor.get("status") or "synced",
                    "metadata_json": json.dumps(monitor.get("metadata_json") or monitor.get("metadata") or {}),
                    "enabled": monitor.get("enabled", True),
                },
            )
            synced += 1
        await conn.execute(
            sa_text(
                "UPDATE monitoring_integrations SET status = 'synced', last_sync_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = :integration_id"
            ),
            {"integration_id": str(integration_id)},
        )
    return {"status": "synced", "integration_id": str(integration_id), "monitor_count": synced}


@router.get("/integrations/{integration_id}/external-monitors", response_model=list[ExternalMonitorResponse])
async def list_external_monitors(
    integration_id: uuid.UUID,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> list[ExternalMonitorResponse]:
    tenant_id = await _get_integration_tenant_id(session, integration_id)
    await _require_tenant_access(session, current_user, tenant_id)
    async with async_engine.connect() as conn:
        rows = await conn.execute(
            sa_text(
                """
                SELECT id, integration_id, external_monitor_id, external_name, monitor_type, status, metadata_json, enabled
                FROM external_monitors
                WHERE integration_id = :integration_id
                ORDER BY external_name
                """
            ),
            {"integration_id": str(integration_id)},
        )
        return [
            ExternalMonitorResponse(
                id=str(row.id),
                integration_id=str(row.integration_id),
                external_monitor_id=row.external_monitor_id,
                external_name=row.external_name,
                monitor_type=row.monitor_type,
                status=row.status,
                metadata_json=dict(row.metadata_json or {}),
                enabled=row.enabled,
            )
            for row in rows
        ]


@router.get("/projects/{project_id}/monitor-bindings", response_model=list[ProjectMonitorBindingResponse])
async def list_project_bindings(
    project_id: uuid.UUID,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> list[ProjectMonitorBindingResponse]:
    tenant_id = await _get_project_tenant_id(session, project_id)
    await _require_tenant_access(session, current_user, tenant_id)
    async with async_engine.connect() as conn:
        rows = await conn.execute(
            sa_text(
                """
                SELECT id, project_id, external_monitor_id, enabled, alert_type_override,
                       resource_mapping_json, routing_tags_json
                FROM project_monitor_bindings
                WHERE project_id = :project_id
                ORDER BY created_at
                """
            ),
            {"project_id": str(project_id)},
        )
        return [
            ProjectMonitorBindingResponse(
                id=str(row.id),
                project_id=str(row.project_id),
                external_monitor_id=str(row.external_monitor_id),
                enabled=row.enabled,
                alert_type_override=row.alert_type_override,
                resource_mapping_json=dict(row.resource_mapping_json or {}),
                routing_tags_json=dict(row.routing_tags_json or {}),
            )
            for row in rows
        ]


@router.post("/projects/{project_id}/monitor-bindings", response_model=ProjectMonitorBindingResponse, status_code=201)
async def create_project_binding(
    project_id: uuid.UUID,
    body: ProjectMonitorBindingRequest,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> ProjectMonitorBindingResponse:
    tenant_id = await _get_project_tenant_id(session, project_id)
    await _require_tenant_admin(session, current_user, tenant_id)
    binding_id = uuid.uuid4()
    external_monitor_id = body.external_monitor_id
    async with async_engine.begin() as conn:
        project = (
            await conn.execute(
                sa_text("SELECT tenant_id FROM projects WHERE id = :project_id"),
                {"project_id": str(project_id)},
            )
        ).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        monitor = (
            await conn.execute(
                sa_text(
                    """
                    SELECT em.id
                    FROM external_monitors em
                    JOIN monitoring_integrations mi ON mi.id = em.integration_id
                    WHERE em.id = :external_monitor_id AND mi.tenant_id = :tenant_id
                    """
                ),
                {"external_monitor_id": str(external_monitor_id), "tenant_id": str(project.tenant_id)},
            )
        ).first()
        if not monitor:
            raise HTTPException(status_code=404, detail="External monitor not found for project tenant")
        conflict = (
            await conn.execute(
                sa_text(
                    "SELECT id FROM project_monitor_bindings WHERE project_id = :project_id AND external_monitor_id = :external_monitor_id"
                ),
                {"project_id": str(project_id), "external_monitor_id": str(external_monitor_id)},
            )
        ).first()
        if conflict:
            raise HTTPException(status_code=409, detail="Project binding already exists")
        await conn.execute(
            sa_text(
                """
                INSERT INTO project_monitor_bindings (
                    id, project_id, external_monitor_id, enabled, alert_type_override,
                    resource_mapping_json, routing_tags_json
                ) VALUES (
                    :id, :project_id, :external_monitor_id, :enabled, :alert_type_override,
                    CAST(:resource_mapping_json AS jsonb), CAST(:routing_tags_json AS jsonb)
                )
                """
            ),
            {
                "id": str(binding_id),
                "project_id": str(project_id),
                "external_monitor_id": str(external_monitor_id),
                "enabled": body.enabled,
                "alert_type_override": body.alert_type_override,
                "resource_mapping_json": json.dumps(body.resource_mapping_json),
                "routing_tags_json": json.dumps(body.routing_tags_json),
            },
        )
    return ProjectMonitorBindingResponse(
        id=str(binding_id),
        project_id=str(project_id),
        external_monitor_id=str(external_monitor_id),
        enabled=body.enabled,
        alert_type_override=body.alert_type_override,
        resource_mapping_json=body.resource_mapping_json,
        routing_tags_json=body.routing_tags_json,
    )


class WebhookEventResponse(BaseModel):
    id: str
    integration_id: str
    source: str
    event_type: str | None
    payload: dict | None
    status: str
    incident_id: str | None
    dedup_key: str | None
    is_replay: bool
    original_event_id: str | None
    received_at: str
    processed_at: str | None


@router.get("/integrations/{integration_id}/webhook-events", response_model=list[WebhookEventResponse])
async def list_webhook_events(
    integration_id: uuid.UUID,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
    limit: int = 50,
) -> list[WebhookEventResponse]:
    tenant_id = await _get_integration_tenant_id(session, integration_id)
    await _require_tenant_access(session, current_user, tenant_id)
    async with async_engine.connect() as conn:
        await conn.execute(
            sa_text("SET LOCAL app.tenant_id = :tenant_id"),
            {"tenant_id": str(tenant_id)},
        )
        rows = await conn.execute(
            sa_text(
                """
                SELECT id, integration_id, source, event_type, payload, status,
                       incident_id, dedup_key, is_replay, original_event_id,
                       received_at, processed_at
                FROM webhook_events
                WHERE tenant_id = :tenant_id AND integration_id = :integration_id
                ORDER BY received_at DESC
                LIMIT :limit
                """
            ),
            {"tenant_id": str(tenant_id), "integration_id": str(integration_id), "limit": limit},
        )
        return [
            WebhookEventResponse(
                id=str(row.id),
                integration_id=str(row.integration_id),
                source=row.source,
                event_type=row.event_type,
                payload=dict(row.payload) if row.payload else None,
                status=row.status,
                incident_id=str(row.incident_id) if row.incident_id else None,
                dedup_key=row.dedup_key,
                is_replay=row.is_replay,
                original_event_id=str(row.original_event_id) if row.original_event_id else None,
                received_at=str(row.received_at),
                processed_at=str(row.processed_at) if row.processed_at else None,
            )
            for row in rows
        ]


@router.post(
    "/integrations/{integration_id}/webhook-events/{event_id}/replay",
    status_code=status.HTTP_202_ACCEPTED,
)
async def replay_webhook_event(
    integration_id: uuid.UUID,
    event_id: uuid.UUID,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> dict[str, str]:
    tenant_id = await _get_integration_tenant_id(session, integration_id)
    await _require_tenant_admin(session, current_user, tenant_id)
    new_event_id = uuid.uuid4()
    async with async_engine.begin() as conn:
        await conn.execute(
            sa_text("SET LOCAL app.tenant_id = :tenant_id"),
            {"tenant_id": str(tenant_id)},
        )
        original = (
            await conn.execute(
                sa_text(
                    """
                    SELECT id, source, event_type, payload, headers
                    FROM webhook_events
                    WHERE tenant_id = :tenant_id AND integration_id = :integration_id AND id = :event_id
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "integration_id": str(integration_id),
                    "event_id": str(event_id),
                },
            )
        ).first()
        if not original:
            raise HTTPException(status_code=404, detail="Webhook event not found")
        await conn.execute(
            sa_text(
                """
                INSERT INTO webhook_events (
                    tenant_id, id, integration_id, source, event_type, payload, headers,
                    status, is_replay, original_event_id, received_at
                )
                VALUES (
                    :tenant_id, :id, :integration_id, :source, :event_type,
                    CAST(:payload AS jsonb), CAST(:headers AS jsonb),
                    'queued', true, :original_event_id, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "id": str(new_event_id),
                "integration_id": str(integration_id),
                "source": original.source,
                "event_type": original.event_type,
                "payload": json.dumps(dict(original.payload) if original.payload else {}),
                "headers": json.dumps({}),
                "original_event_id": str(event_id),
            },
        )
    return {"status": "queued", "replay_event_id": str(new_event_id), "original_event_id": str(event_id)}


@router.post("/integrations/{integration_id}/rotate-secret")
async def rotate_integration_secret(
    integration_id: uuid.UUID,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> dict[str, str]:
    tenant_id = await _get_integration_tenant_id(session, integration_id)
    await _require_tenant_admin(session, current_user, tenant_id)
    new_token = str(uuid.uuid4())
    async with async_engine.begin() as conn:
        result = await conn.execute(
            sa_text(
                """
                UPDATE monitoring_integrations
                SET webhook_token_ref = :new_token, updated_at = CURRENT_TIMESTAMP
                WHERE id = :integration_id
                RETURNING id
                """
            ),
            {"integration_id": str(integration_id), "new_token": new_token},
        )
        if not result.first():
            raise HTTPException(status_code=404, detail="Integration not found")
    return {"status": "rotated", "webhook_token": new_token, "integration_id": str(integration_id)}


@router.delete("/project-monitor-bindings/{binding_id}")
async def delete_project_binding(
    binding_id: uuid.UUID,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> dict[str, str]:
    tenant_id = await _get_binding_tenant_id(session, binding_id)
    await _require_tenant_admin(session, current_user, tenant_id)
    async with async_engine.begin() as conn:
        result = await conn.execute(
            sa_text("DELETE FROM project_monitor_bindings WHERE id = :binding_id"),
            {"binding_id": str(binding_id)},
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Project binding not found")
    return {"status": "deleted"}
