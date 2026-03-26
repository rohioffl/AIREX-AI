"""AuditEvent — append-only audit trail for all org/platform actions."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from airex_core.models.base import Base


class AuditEvent(Base):
    """Immutable record of an action taken by an actor on an entity."""

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Who performed the action
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    actor_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # What org/tenant context
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )

    # The action
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # The entity affected
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Before/after snapshots (optional, for mutations)
    before_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Extra context
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"AuditEvent(id={self.id!s}, action={self.action!r}, "
            f"actor={self.actor_email!r})"
        )
