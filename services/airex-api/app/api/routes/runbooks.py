"""
API endpoints for runbook CRUD.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.dependencies import CurrentUser, TenantId, TenantSession, require_permission
from airex_core.core.rbac import Permission
from airex_core.models.runbook import Runbook

logger = structlog.get_logger()
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────

class RunbookStep(BaseModel):
    order: int
    title: str
    description: str = ""
    action_type: str = "manual"  # manual, command, api_call, notification, condition
    action_config: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int | None = None
    on_failure: str = "continue"  # continue, stop, skip_to

class RunbookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    alert_type: str = Field(..., min_length=1, max_length=255)
    severity: str | None = None
    steps: list[RunbookStep] = Field(default_factory=list)
    tags: list[str] | None = None
    is_active: bool = True

class RunbookUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    alert_type: str | None = None
    severity: str | None = None
    steps: list[RunbookStep] | None = None
    tags: list[str] | None = None
    is_active: bool | None = None

class RunbookResponse(BaseModel):
    tenant_id: str
    id: str
    name: str
    description: str | None
    alert_type: str
    severity: str | None
    is_active: bool
    steps: list[dict[str, Any]]
    version: int
    tags: list[str] | None
    created_by: str | None
    updated_by: str | None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


def _to_response(rb: Runbook) -> RunbookResponse:
    steps = rb.steps if isinstance(rb.steps, list) else (rb.steps or {}).get("steps", [])
    tags = rb.tags if isinstance(rb.tags, list) else (rb.tags or {}).get("tags", [])
    return RunbookResponse(
        tenant_id=str(rb.tenant_id),
        id=str(rb.id),
        name=rb.name,
        description=rb.description,
        alert_type=rb.alert_type,
        severity=rb.severity,
        is_active=rb.is_active,
        steps=steps,
        version=rb.version,
        tags=tags,
        created_by=str(rb.created_by) if rb.created_by else None,
        updated_by=str(rb.updated_by) if rb.updated_by else None,
        created_at=rb.created_at.isoformat() if rb.created_at else "",
        updated_at=rb.updated_at.isoformat() if rb.updated_at else "",
    )


# ── Endpoints ────────────────────────────────────────────────

@router.get("/")
async def list_runbooks(
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    _perm: None = Depends(require_permission(Permission.INCIDENT_VIEW)),
    active_only: bool = Query(False),
    alert_type: str | None = Query(None),
):
    """List all runbooks, optionally filtered."""
    filters = [Runbook.tenant_id == tenant_id]
    if active_only:
        filters.append(Runbook.is_active == True)
    if alert_type:
        filters.append(Runbook.alert_type == alert_type)

    result = await session.execute(
        select(Runbook).where(*filters).order_by(Runbook.updated_at.desc())
    )
    runbooks = result.scalars().all()
    return {"runbooks": [_to_response(rb) for rb in runbooks], "total": len(list(runbooks))}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_runbook(
    body: RunbookCreate,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    _perm: None = Depends(require_permission(Permission.INCIDENT_APPROVE)),
):
    """Create a new runbook."""
    runbook = Runbook(
        tenant_id=tenant_id,
        id=uuid.uuid4(),
        name=body.name,
        description=body.description,
        alert_type=body.alert_type,
        severity=body.severity,
        is_active=body.is_active,
        steps=[s.model_dump() for s in body.steps],
        tags=body.tags or [],
        version=1,
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    session.add(runbook)
    await session.flush()
    logger.info("runbook_created", runbook_id=str(runbook.id))
    return _to_response(runbook)


@router.get("/{runbook_id}")
async def get_runbook(
    runbook_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    _perm: None = Depends(require_permission(Permission.INCIDENT_VIEW)),
):
    """Get a single runbook."""
    result = await session.execute(
        select(Runbook).where(
            Runbook.tenant_id == tenant_id,
            Runbook.id == runbook_id,
        )
    )
    runbook = result.scalar_one_or_none()
    if not runbook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Runbook not found")
    return _to_response(runbook)


@router.put("/{runbook_id}")
async def update_runbook(
    runbook_id: uuid.UUID,
    body: RunbookUpdate,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    _perm: None = Depends(require_permission(Permission.INCIDENT_APPROVE)),
):
    """Update an existing runbook."""
    result = await session.execute(
        select(Runbook).where(
            Runbook.tenant_id == tenant_id,
            Runbook.id == runbook_id,
        )
    )
    runbook = result.scalar_one_or_none()
    if not runbook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Runbook not found")

    update_data = body.model_dump(exclude_unset=True)
    if "steps" in update_data and update_data["steps"] is not None:
        update_data["steps"] = [s.model_dump() if hasattr(s, "model_dump") else s for s in body.steps]
    for field, value in update_data.items():
        setattr(runbook, field, value)

    runbook.version += 1
    runbook.updated_by = current_user.user_id
    runbook.updated_at = datetime.now(timezone.utc)

    logger.info("runbook_updated", runbook_id=str(runbook.id), version=runbook.version)
    return _to_response(runbook)


@router.delete("/{runbook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_runbook(
    runbook_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    _perm: None = Depends(require_permission(Permission.INCIDENT_DELETE)),
):
    """Delete a runbook."""
    result = await session.execute(
        select(Runbook).where(
            Runbook.tenant_id == tenant_id,
            Runbook.id == runbook_id,
        )
    )
    runbook = result.scalar_one_or_none()
    if not runbook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Runbook not found")

    await session.delete(runbook)
    logger.info("runbook_deleted", runbook_id=str(runbook_id))


@router.post("/{runbook_id}/duplicate", status_code=status.HTTP_201_CREATED)
async def duplicate_runbook(
    runbook_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    _perm: None = Depends(require_permission(Permission.INCIDENT_APPROVE)),
):
    """Duplicate an existing runbook."""
    result = await session.execute(
        select(Runbook).where(
            Runbook.tenant_id == tenant_id,
            Runbook.id == runbook_id,
        )
    )
    original = result.scalar_one_or_none()
    if not original:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Runbook not found")

    duplicate = Runbook(
        tenant_id=tenant_id,
        id=uuid.uuid4(),
        name=f"{original.name} (Copy)",
        description=original.description,
        alert_type=original.alert_type,
        severity=original.severity,
        is_active=False,
        steps=original.steps,
        tags=original.tags,
        version=1,
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    session.add(duplicate)
    await session.flush()
    logger.info("runbook_duplicated", original_id=str(runbook_id), new_id=str(duplicate.id))
    return _to_response(duplicate)
