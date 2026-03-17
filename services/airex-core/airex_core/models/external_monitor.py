"""External monitor inventory for a tenant integration."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from airex_core.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ExternalMonitor(Base):
    """Discovered external monitor from a provider sync."""

    __tablename__ = "external_monitors"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("monitoring_integrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_monitor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_name: Mapped[str] = mapped_column(String(255), nullable=False)
    monitor_type: Mapped[str] = mapped_column(String(64), nullable=False, default="generic")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=_utcnow,
    )
