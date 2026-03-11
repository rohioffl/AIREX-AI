"""Runbook model for visual runbook editor."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Integer, PrimaryKeyConstraint, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from airex_core.models.base import Base, TenantMixin


class Runbook(Base, TenantMixin):
    """Structured runbook with ordered steps for incident response."""

    __tablename__ = "runbooks"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "id"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    alert_type: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Steps stored as ordered JSON array
    # Each step: {order, title, description, action_type, action_config, timeout_seconds, on_failure}
    steps: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Metadata
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    tags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"Runbook(tenant_id={self.tenant_id!s}, "
            f"id={self.id!s}, name={self.name!r}, alert_type={self.alert_type!r})"
        )
