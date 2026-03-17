"""Static catalog of supported monitoring integration types."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, String, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from airex_core.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IntegrationType(Base):
    """Platform-owned catalog entry for a monitoring provider."""

    __tablename__ = "integration_types"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="monitoring")
    supports_webhook: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    supports_polling: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supports_sync: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config_schema_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
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
