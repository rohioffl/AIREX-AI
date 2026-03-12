"""
Knowledge base CRUD endpoints.
"""

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, or_, func

from app.api.dependencies import (
    CurrentUser,
    RequireAdmin,
    TenantId,
    TenantSession,
    require_permission,
)
from airex_core.models.enums import Permission
from airex_core.models.knowledge_base import KnowledgeBase

logger = structlog.get_logger()

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────


class KnowledgeBaseCreateRequest(BaseModel):
    incident_id: uuid.UUID | None = None
    title: str
    summary: str
    root_cause: str | None = None
    resolution_steps: str | None = None
    alert_type: str
    category: str | None = None
    tags: list[str] | None = None


class KnowledgeBaseUpdateRequest(BaseModel):
    title: str | None = None
    summary: str | None = None
    root_cause: str | None = None
    resolution_steps: str | None = None
    category: str | None = None
    tags: list[str] | None = None


class KnowledgeBaseResponse(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID | None
    title: str
    summary: str
    root_cause: str | None
    resolution_steps: str | None
    alert_type: str
    category: str | None
    tags: list[str] | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


# ── List Knowledge Base Entries ──────────────────────────────────────────


@router.get("/", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_base(
    tenant_id: TenantId,
    session: TenantSession,
    alert_type: str | None = Query(None),
    category: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(100, le=1000),
) -> list[KnowledgeBaseResponse]:
    """List knowledge base entries with optional filtering."""
    filters = [KnowledgeBase.tenant_id == tenant_id]
    
    if alert_type:
        filters.append(KnowledgeBase.alert_type == alert_type)
    if category:
        filters.append(KnowledgeBase.category == category)
    if search:
        search_filter = or_(
            KnowledgeBase.title.ilike(f"%{search}%"),
            KnowledgeBase.summary.ilike(f"%{search}%"),
            KnowledgeBase.root_cause.ilike(f"%{search}%"),
        )
        filters.append(search_filter)

    result = await session.execute(
        select(KnowledgeBase)
        .where(*filters)
        .order_by(KnowledgeBase.created_at.desc())
        .limit(limit)
    )
    entries = result.scalars().all()

    return [
        KnowledgeBaseResponse(
            id=e.id,
            incident_id=e.incident_id,
            title=e.title,
            summary=e.summary,
            root_cause=e.root_cause,
            resolution_steps=e.resolution_steps,
            alert_type=e.alert_type,
            category=e.category,
            tags=e.tags,
            created_by=e.created_by,
            created_at=e.created_at,
            updated_at=e.updated_at,
        )
        for e in entries
    ]


# ── Get Knowledge Base Entry ────────────────────────────────────────────


@router.get("/{entry_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base_entry(
    entry_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
) -> KnowledgeBaseResponse:
    """Get a specific knowledge base entry."""
    result = await session.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.tenant_id == tenant_id,
            KnowledgeBase.id == entry_id,
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base entry not found",
        )

    return KnowledgeBaseResponse(
        id=entry.id,
        incident_id=entry.incident_id,
        title=entry.title,
        summary=entry.summary,
        root_cause=entry.root_cause,
        resolution_steps=entry.resolution_steps,
        alert_type=entry.alert_type,
        category=entry.category,
        tags=entry.tags,
        created_by=entry.created_by,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


# ── Create Knowledge Base Entry ──────────────────────────────────────────


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=KnowledgeBaseResponse)
async def create_knowledge_base_entry(
    body: KnowledgeBaseCreateRequest,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
) -> KnowledgeBaseResponse:
    """Create a new knowledge base entry."""
    entry = KnowledgeBase(
        tenant_id=tenant_id,
        incident_id=body.incident_id,
        title=body.title,
        summary=body.summary,
        root_cause=body.root_cause,
        resolution_steps=body.resolution_steps,
        alert_type=body.alert_type,
        category=body.category,
        tags=body.tags,
        created_by=current_user.user_id if current_user else None,
    )
    session.add(entry)
    await session.flush()
    await session.refresh(entry)

    logger.info(
        "knowledge_base_entry_created",
        tenant_id=str(tenant_id),
        entry_id=str(entry.id),
        alert_type=entry.alert_type,
    )

    return KnowledgeBaseResponse(
        id=entry.id,
        incident_id=entry.incident_id,
        title=entry.title,
        summary=entry.summary,
        root_cause=entry.root_cause,
        resolution_steps=entry.resolution_steps,
        alert_type=entry.alert_type,
        category=entry.category,
        tags=entry.tags,
        created_by=entry.created_by,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


# ── Update Knowledge Base Entry ──────────────────────────────────────────


@router.put("/{entry_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge_base_entry(
    entry_id: uuid.UUID,
    body: KnowledgeBaseUpdateRequest,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
) -> KnowledgeBaseResponse:
    """Update a knowledge base entry."""
    result = await session.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.tenant_id == tenant_id,
            KnowledgeBase.id == entry_id,
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base entry not found",
        )

    if body.title is not None:
        entry.title = body.title
    if body.summary is not None:
        entry.summary = body.summary
    if body.root_cause is not None:
        entry.root_cause = body.root_cause
    if body.resolution_steps is not None:
        entry.resolution_steps = body.resolution_steps
    if body.category is not None:
        entry.category = body.category
    if body.tags is not None:
        entry.tags = body.tags

    entry.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(entry)

    logger.info(
        "knowledge_base_entry_updated",
        tenant_id=str(tenant_id),
        entry_id=str(entry_id),
    )

    return KnowledgeBaseResponse(
        id=entry.id,
        incident_id=entry.incident_id,
        title=entry.title,
        summary=entry.summary,
        root_cause=entry.root_cause,
        resolution_steps=entry.resolution_steps,
        alert_type=entry.alert_type,
        category=entry.category,
        tags=entry.tags,
        created_by=entry.created_by,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


# ── Delete Knowledge Base Entry ──────────────────────────────────────────


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base_entry(
    entry_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    _role: RequireAdmin = None,
) -> None:
    """Delete a knowledge base entry."""
    result = await session.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.tenant_id == tenant_id,
            KnowledgeBase.id == entry_id,
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base entry not found",
        )

    await session.delete(entry)
    await session.commit()

    logger.info(
        "knowledge_base_entry_deleted",
        tenant_id=str(tenant_id),
        entry_id=str(entry_id),
    )
