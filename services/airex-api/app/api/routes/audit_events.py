"""Audit Events API — read-only access to org audit trail."""

from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_auth_session, get_authenticated_user
from airex_core.core.security import TokenData
from airex_core.models.audit_event import AuditEvent

from .organizations import _require_org_access

logger = structlog.get_logger()
router = APIRouter()


class AuditEventResponse(BaseModel):
    id: str
    action: str
    actor_id: str | None
    actor_email: str | None
    actor_role: str | None
    entity_type: str | None
    entity_id: str | None
    before_state: dict | None
    after_state: dict | None
    ip_address: str | None
    created_at: str


@router.get(
    "/organizations/{org_id}/audit-events",
    response_model=list[AuditEventResponse],
)
async def list_audit_events(
    org_id: uuid.UUID,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None),
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> list[AuditEventResponse]:
    """List audit events for an organization."""
    await _require_org_access(session, current_user, org_id)

    stmt = (
        select(AuditEvent)
        .where(AuditEvent.organization_id == org_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if action:
        stmt = stmt.where(AuditEvent.action == action)

    events = (await session.execute(stmt)).scalars().all()

    return [
        AuditEventResponse(
            id=str(e.id),
            action=e.action,
            actor_id=str(e.actor_id) if e.actor_id else None,
            actor_email=e.actor_email,
            actor_role=e.actor_role,
            entity_type=e.entity_type,
            entity_id=e.entity_id,
            before_state=e.before_state,
            after_state=e.after_state,
            ip_address=e.ip_address,
            created_at=e.created_at.isoformat(),
        )
        for e in events
    ]
