"""Webhook event log model for inbound webhook audit and replay."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, PrimaryKeyConstraint, String, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from airex_core.models.base import Base, TenantMixin


class WebhookEvent(Base, TenantMixin):
    """Persisted record of every inbound webhook payload for audit and replay."""

    __tablename__ = "webhook_events"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "id"),
    )

    integration_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # site24x7 | generic | ...
    event_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    headers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # sanitized
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="received"
    )  # received | processed | failed | replayed
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    dedup_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_replay: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    original_event_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    received_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"WebhookEvent(tenant_id={self.tenant_id!s}, "
            f"id={self.id!s}, source={self.source!r}, status={self.status!r})"
        )
