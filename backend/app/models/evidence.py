from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    ForeignKeyConstraint,
    Index,
    PrimaryKeyConstraint,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin

if TYPE_CHECKING:
    from app.models.incident import Incident


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Evidence(Base, TenantMixin):
    """Captured investigation evidence tied to a single incident."""

    __tablename__ = "evidence"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "incident_id"],
            ["incidents.tenant_id", "incidents.id"],
            ondelete="CASCADE",
        ),
        Index("idx_evidence_incident_fk", "tenant_id", "incident_id"),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_output: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_utcnow
    )

    # Relationship
    incident: Mapped[Incident] = relationship(
        back_populates="evidence",
        foreign_keys="[Evidence.tenant_id, Evidence.incident_id]",
        primaryjoin=(
            "and_(Evidence.tenant_id == Incident.tenant_id, "
            "Evidence.incident_id == Incident.id)"
        ),
    )

    def __repr__(self) -> str:
        return (
            "Evidence("
            f"tenant_id={self.tenant_id!s}, "
            f"id={self.id!s}, "
            f"incident_id={self.incident_id!s}, "
            f"tool_name={self.tool_name!r}"
            ")"
        )
