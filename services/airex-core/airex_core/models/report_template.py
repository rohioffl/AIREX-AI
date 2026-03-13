"""Report template model for scheduled reports."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from airex_core.models.base import Base, TenantMixin


class ReportTemplate(Base, TenantMixin):
    """Template for generating scheduled reports."""

    __tablename__ = "report_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, primary_key=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    schedule_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "daily", "weekly", "monthly", "manual"
    schedule_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # e.g., {"day_of_week": 1, "time": "09:00"}
    filters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # Incident filters for the report
    format: Mapped[str] = mapped_column(String(20), nullable=False, default="json")  # "json", "csv", "pdf"
    recipients: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)  # List of email addresses
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
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
            f"ReportTemplate(tenant_id={self.tenant_id!s}, "
            f"id={self.id!s}, name={self.name!r}, schedule_type={self.schedule_type!r})"
        )
