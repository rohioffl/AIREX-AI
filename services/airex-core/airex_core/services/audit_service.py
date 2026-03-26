"""Audit service — write immutable audit trail events."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.models.audit_event import AuditEvent

logger = structlog.get_logger()


async def record_event(
    session: AsyncSession,
    *,
    action: str,
    actor_id: uuid.UUID | None = None,
    actor_email: str | None = None,
    actor_role: str | None = None,
    organization_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    extra: dict[str, Any] | None = None,
) -> AuditEvent:
    """Append an immutable audit event to the database.

    Does NOT flush/commit — caller owns the transaction.
    """
    event = AuditEvent(
        action=action,
        actor_id=actor_id,
        actor_email=actor_email,
        actor_role=actor_role,
        organization_id=organization_id,
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        before_state=before_state,
        after_state=after_state,
        ip_address=ip_address,
        user_agent=user_agent,
        extra=extra,
    )
    session.add(event)
    logger.info(
        "audit_event",
        action=action,
        actor_id=str(actor_id) if actor_id else None,
        organization_id=str(organization_id) if organization_id else None,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    return event
