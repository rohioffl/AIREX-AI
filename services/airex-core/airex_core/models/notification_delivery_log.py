"""Notification delivery log model for audit trail of sent notifications."""

import uuid
from datetime import datetime

from sqlalchemy import PrimaryKeyConstraint, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from airex_core.models.base import Base, TenantMixin


class NotificationDeliveryLog(Base, TenantMixin):
    """Audit record for every notification dispatch attempt."""

    __tablename__ = "notification_delivery_log"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "id"),
    )

    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)  # email | slack
    state_transition: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # sent | failed
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    delivered_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    def __repr__(self) -> str:
        return (
            f"NotificationDeliveryLog(tenant_id={self.tenant_id!s}, "
            f"id={self.id!s}, channel={self.channel!r}, status={self.status!r})"
        )
