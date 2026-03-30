"""Notification preferences model for user notification settings."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, String, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from airex_core.models.base import Base


class NotificationPreference(Base):
    """User notification preferences for Slack and Email.

    DB PK is (tenant_id, user_id) — no separate ``id`` column (not TenantMixin).
    """

    __tablename__ = "notification_preferences"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, primary_key=True
    )
    # Email preferences
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_critical_only: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )  # Only send for CRITICAL incidents
    # Slack preferences
    slack_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    slack_webhook_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    slack_critical_only: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    # State change preferences
    notify_on_received: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notify_on_investigating: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notify_on_recommendation_ready: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_on_awaiting_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_on_executing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notify_on_verifying: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notify_on_resolved: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_on_rejected: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_on_failed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # All FAILED_* states
    # Additional metadata
    notification_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"NotificationPreference(tenant_id={self.tenant_id!s}, "
            f"user_id={self.user_id!s}, "
            f"email_enabled={self.email_enabled}, "
            f"slack_enabled={self.slack_enabled})"
        )
