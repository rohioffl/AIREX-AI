"""
Incident template CRUD endpoints.
"""

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.dependencies import (
    CurrentUser,
    RequireAdmin,
    TenantId,
    TenantSession,
    require_permission,
)
from airex_core.models.enums import Permission
from airex_core.models.incident_template import IncidentTemplate

logger = structlog.get_logger()

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────


class TemplateCreateRequest(BaseModel):
    name: str
    description: str | None = None
    alert_type: str
    severity: str
    default_title: str | None = None
    default_meta: dict | None = None


class TemplateUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    alert_type: str | None = None
    severity: str | None = None
    default_title: str | None = None
    default_meta: dict | None = None
    is_active: bool | None = None


class TemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    alert_type: str
    severity: str
    default_title: str | None
    default_meta: dict | None
    is_active: bool
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


# ── List Templates ───────────────────────────────────────────────────────


@router.get("/", response_model=list[TemplateResponse])
async def list_templates(
    tenant_id: TenantId,
    session: TenantSession,
    active_only: bool = False,
) -> list[TemplateResponse]:
    """List all incident templates for the tenant."""
    filters = [IncidentTemplate.tenant_id == tenant_id]
    if active_only:
        filters.append(IncidentTemplate.is_active == True)

    result = await session.execute(
        select(IncidentTemplate).where(*filters).order_by(IncidentTemplate.created_at.desc())
    )
    templates = result.scalars().all()

    return [
        TemplateResponse(
            id=t.id,
            name=t.name,
            description=t.description,
            alert_type=t.alert_type,
            severity=t.severity,
            default_title=t.default_title,
            default_meta=t.default_meta,
            is_active=t.is_active,
            created_by=t.created_by,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in templates
    ]


# ── Get Template ────────────────────────────────────────────────────────


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
) -> TemplateResponse:
    """Get a specific incident template."""
    result = await session.execute(
        select(IncidentTemplate).where(
            IncidentTemplate.tenant_id == tenant_id,
            IncidentTemplate.id == template_id,
        )
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        alert_type=template.alert_type,
        severity=template.severity,
        default_title=template.default_title,
        default_meta=template.default_meta,
        is_active=template.is_active,
        created_by=template.created_by,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


# ── Create Template ──────────────────────────────────────────────────────


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=TemplateResponse)
async def create_template(
    body: TemplateCreateRequest,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    _role: RequireAdmin = None,
) -> TemplateResponse:
    """Create a new incident template."""
    template = IncidentTemplate(
        tenant_id=tenant_id,
        name=body.name,
        description=body.description,
        alert_type=body.alert_type,
        severity=body.severity,
        default_title=body.default_title,
        default_meta=body.default_meta,
        created_by=current_user.user_id if current_user else None,
    )
    session.add(template)
    await session.flush()
    await session.refresh(template)

    logger.info(
        "template_created",
        tenant_id=str(tenant_id),
        template_id=str(template.id),
        name=template.name,
    )

    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        alert_type=template.alert_type,
        severity=template.severity,
        default_title=template.default_title,
        default_meta=template.default_meta,
        is_active=template.is_active,
        created_by=template.created_by,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


# ── Update Template ──────────────────────────────────────────────────────


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: uuid.UUID,
    body: TemplateUpdateRequest,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    _role: RequireAdmin = None,
) -> TemplateResponse:
    """Update an incident template."""
    result = await session.execute(
        select(IncidentTemplate).where(
            IncidentTemplate.tenant_id == tenant_id,
            IncidentTemplate.id == template_id,
        )
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    if body.name is not None:
        template.name = body.name
    if body.description is not None:
        template.description = body.description
    if body.alert_type is not None:
        template.alert_type = body.alert_type
    if body.severity is not None:
        template.severity = body.severity
    if body.default_title is not None:
        template.default_title = body.default_title
    if body.default_meta is not None:
        template.default_meta = body.default_meta
    if body.is_active is not None:
        template.is_active = body.is_active

    template.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(template)

    logger.info(
        "template_updated",
        tenant_id=str(tenant_id),
        template_id=str(template.id),
    )

    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        alert_type=template.alert_type,
        severity=template.severity,
        default_title=template.default_title,
        default_meta=template.default_meta,
        is_active=template.is_active,
        created_by=template.created_by,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


# ── Delete Template ──────────────────────────────────────────────────────


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    _role: RequireAdmin = None,
) -> None:
    """Delete an incident template."""
    result = await session.execute(
        select(IncidentTemplate).where(
            IncidentTemplate.tenant_id == tenant_id,
            IncidentTemplate.id == template_id,
        )
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    await session.delete(template)
    await session.commit()

    logger.info(
        "template_deleted",
        tenant_id=str(tenant_id),
        template_id=str(template_id),
    )
