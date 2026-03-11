"""Related incidents model for explicit parent/child relationships."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKeyConstraint, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from airex_core.models.base import Base, TenantMixin


class RelatedIncident(Base, TenantMixin):
    """Many-to-many relationship between incidents for explicit linking."""

    __tablename__ = "related_incidents"

    # Primary incident (the one we're viewing)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, primary_key=True
    )
    # Related incident (linked to the primary)
    related_incident_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, primary_key=True
    )
    # Relationship type (e.g., "parent", "child", "duplicate", "related")
    relationship_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="related"
    )
    # Optional note about why they're related
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Who created the link
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    # Foreign keys
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "incident_id"],
            ["incidents.tenant_id", "incidents.id"],
            ondelete="CASCADE",
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "related_incident_id"],
            ["incidents.tenant_id", "incidents.id"],
            ondelete="CASCADE",
            deferrable=True,
            initially="DEFERRED",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"RelatedIncident(tenant_id={self.tenant_id!s}, "
            f"incident_id={self.incident_id!s}, "
            f"related_incident_id={self.related_incident_id!s}, "
            f"relationship_type={self.relationship_type!r})"
        )
