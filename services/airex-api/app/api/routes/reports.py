"""
Report template CRUD endpoints.
"""

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.dependencies import (
    CurrentUser,
    RequireAdmin,
    RequireOperator,
    TenantId,
    TenantSession,
    require_permission,
)
from airex_core.models.enums import Permission
from airex_core.models.report_template import ReportTemplate

logger = structlog.get_logger()

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────


class ReportTemplateCreateRequest(BaseModel):
    name: str
    description: str | None = None
    schedule_type: str  # "daily", "weekly", "monthly", "manual"
    schedule_config: dict | None = None
    filters: dict | None = None
    format: str = "json"  # "json", "csv", "pdf"
    recipients: list[str] | None = None


class ReportTemplateUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    schedule_type: str | None = None
    schedule_config: dict | None = None
    filters: dict | None = None
    format: str | None = None
    recipients: list[str] | None = None
    is_active: bool | None = None


class ReportTemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    schedule_type: str
    schedule_config: dict | None
    filters: dict | None
    format: str
    recipients: list[str] | None
    is_active: bool
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


# ── List Report Templates ────────────────────────────────────────────────


@router.get("/", response_model=list[ReportTemplateResponse])
async def list_report_templates(
    tenant_id: TenantId,
    session: TenantSession,
    active_only: bool = False,
) -> list[ReportTemplateResponse]:
    """List all report templates for the tenant."""
    filters = [ReportTemplate.tenant_id == tenant_id]
    if active_only:
        filters.append(ReportTemplate.is_active == True)

    result = await session.execute(
        select(ReportTemplate).where(*filters).order_by(ReportTemplate.created_at.desc())
    )
    templates = result.scalars().all()

    return [
        ReportTemplateResponse(
            id=t.id,
            name=t.name,
            description=t.description,
            schedule_type=t.schedule_type,
            schedule_config=t.schedule_config,
            filters=t.filters,
            format=t.format,
            recipients=t.recipients,
            is_active=t.is_active,
            created_by=t.created_by,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in templates
    ]


# ── Get Report Template ──────────────────────────────────────────────────


@router.get("/{template_id}", response_model=ReportTemplateResponse)
async def get_report_template(
    template_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
) -> ReportTemplateResponse:
    """Get a specific report template."""
    result = await session.execute(
        select(ReportTemplate).where(
            ReportTemplate.tenant_id == tenant_id,
            ReportTemplate.id == template_id,
        )
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report template not found",
        )

    return ReportTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        schedule_type=template.schedule_type,
        schedule_config=template.schedule_config,
        filters=template.filters,
        format=template.format,
        recipients=template.recipients,
        is_active=template.is_active,
        created_by=template.created_by,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


# ── Create Report Template ────────────────────────────────────────────────


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ReportTemplateResponse)
async def create_report_template(
    body: ReportTemplateCreateRequest,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    _role: RequireAdmin = None,
) -> ReportTemplateResponse:
    """Create a new report template."""
    template = ReportTemplate(
        tenant_id=tenant_id,
        name=body.name,
        description=body.description,
        schedule_type=body.schedule_type,
        schedule_config=body.schedule_config,
        filters=body.filters,
        format=body.format,
        recipients=body.recipients,
        created_by=current_user.user_id if current_user else None,
    )
    session.add(template)
    await session.flush()
    await session.refresh(template)

    logger.info(
        "report_template_created",
        tenant_id=str(tenant_id),
        template_id=str(template.id),
        name=template.name,
    )

    return ReportTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        schedule_type=template.schedule_type,
        schedule_config=template.schedule_config,
        filters=template.filters,
        format=template.format,
        recipients=template.recipients,
        is_active=template.is_active,
        created_by=template.created_by,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


# ── Update Report Template ────────────────────────────────────────────────


@router.put("/{template_id}", response_model=ReportTemplateResponse)
async def update_report_template(
    template_id: uuid.UUID,
    body: ReportTemplateUpdateRequest,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    _role: RequireAdmin = None,
) -> ReportTemplateResponse:
    """Update a report template."""
    result = await session.execute(
        select(ReportTemplate).where(
            ReportTemplate.tenant_id == tenant_id,
            ReportTemplate.id == template_id,
        )
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report template not found",
        )

    if body.name is not None:
        template.name = body.name
    if body.description is not None:
        template.description = body.description
    if body.schedule_type is not None:
        template.schedule_type = body.schedule_type
    if body.schedule_config is not None:
        template.schedule_config = body.schedule_config
    if body.filters is not None:
        template.filters = body.filters
    if body.format is not None:
        template.format = body.format
    if body.recipients is not None:
        template.recipients = body.recipients
    if body.is_active is not None:
        template.is_active = body.is_active

    template.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(template)

    logger.info(
        "report_template_updated",
        tenant_id=str(tenant_id),
        template_id=str(template.id),
    )

    return ReportTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        schedule_type=template.schedule_type,
        schedule_config=template.schedule_config,
        filters=template.filters,
        format=template.format,
        recipients=template.recipients,
        is_active=template.is_active,
        created_by=template.created_by,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


# ── Delete Report Template ────────────────────────────────────────────────


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report_template(
    template_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    _role: RequireAdmin = None,
) -> None:
    """Delete a report template."""
    result = await session.execute(
        select(ReportTemplate).where(
            ReportTemplate.tenant_id == tenant_id,
            ReportTemplate.id == template_id,
        )
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report template not found",
        )

    await session.delete(template)
    await session.commit()

    logger.info(
        "report_template_deleted",
        tenant_id=str(tenant_id),
        template_id=str(template_id),
    )


# ── Generate Report ──────────────────────────────────────────────────────


@router.post("/{template_id}/generate", status_code=status.HTTP_200_OK)
async def generate_report(
    template_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    _role: RequireOperator = None,
):
    """
    Manually generate a report from a template.
    
    This endpoint generates a report on-demand using the template's filters.
    For scheduled reports, use a background job scheduler.
    """
    from airex_core.services.report_service import generate_report_from_template

    result = await session.execute(
        select(ReportTemplate).where(
            ReportTemplate.tenant_id == tenant_id,
            ReportTemplate.id == template_id,
            ReportTemplate.is_active == True,
        )
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report template not found or inactive",
        )

    # Generate report
    report_data = await generate_report_from_template(session, tenant_id, template)

    logger.info(
        "report_generated",
        tenant_id=str(tenant_id),
        template_id=str(template_id),
        user_id=str(current_user.user_id),
    )

    return {
        "template_id": str(template_id),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data": report_data,
    }
