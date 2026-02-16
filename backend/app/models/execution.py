from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    Computed,
    Enum as SAEnum,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin
from app.models.enums import ExecutionStatus

if TYPE_CHECKING:
    from app.models.incident import Incident


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Execution(Base, TenantMixin):
    __tablename__ = "executions"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "incident_id"],
            ["incidents.tenant_id", "incidents.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "tenant_id",
            "incident_id",
            "action_type",
            "attempt",
            name="uq_executions_idempotency",
        ),
        Index("idx_executions_incident_fk", "tenant_id", "incident_id"),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(255), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[ExecutionStatus] = mapped_column(
        SAEnum(
            ExecutionStatus,
            name="execution_status",
            create_constraint=False,
            native_enum=True,
        ),
        nullable=False,
        default=ExecutionStatus.PENDING,
    )
    logs: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    duration_seconds: Mapped[float | None] = mapped_column(
        Numeric,
        Computed("EXTRACT(EPOCH FROM (completed_at - started_at))"),
        nullable=True,
    )

    # Relationship
    incident: Mapped[Incident] = relationship(
        back_populates="executions",
        foreign_keys="[Execution.tenant_id, Execution.incident_id]",
        primaryjoin=(
            "and_(Execution.tenant_id == Incident.tenant_id, "
            "Execution.incident_id == Incident.id)"
        ),
    )
