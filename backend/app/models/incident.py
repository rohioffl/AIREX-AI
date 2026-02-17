from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Enum as SAEnum,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin
from app.models.enums import IncidentState, SeverityLevel

if TYPE_CHECKING:
    from app.models.evidence import Evidence
    from app.models.execution import Execution
    from app.models.state_transition import StateTransition


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Incident(Base, TenantMixin):
    __tablename__ = "incidents"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "id"),
        CheckConstraint(
            "deleted_at IS NULL OR state IN "
            "('RESOLVED', 'ESCALATED', 'FAILED_EXECUTION', 'FAILED_VERIFICATION')",
            name="ck_incidents_soft_delete",
        ),
        CheckConstraint(
            "investigation_retry_count >= 0 AND investigation_retry_count <= 3",
            name="ck_incidents_investigation_retry",
        ),
        CheckConstraint(
            "execution_retry_count >= 0 AND execution_retry_count <= 3",
            name="ck_incidents_execution_retry",
        ),
        CheckConstraint(
            "verification_retry_count >= 0 AND verification_retry_count <= 3",
            name="ck_incidents_verification_retry",
        ),
        Index("idx_incidents_tenant_state", "tenant_id", "state"),
        Index(
            "idx_incidents_active",
            "tenant_id",
            text("created_at DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "idx_incidents_awaiting_approval",
            "tenant_id",
            text("created_at DESC"),
            postgresql_where=text(
                "state = 'AWAITING_APPROVAL' AND deleted_at IS NULL"
            ),
        ),
    )

    # Core fields
    alert_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    state: Mapped[IncidentState] = mapped_column(
        SAEnum(
            IncidentState,
            name="incident_state",
            create_constraint=False,
            native_enum=True,
        ),
        nullable=False,
        default=IncidentState.RECEIVED,
    )
    severity: Mapped[SeverityLevel] = mapped_column(
        SAEnum(
            SeverityLevel,
            name="severity_level",
            create_constraint=False,
            native_enum=True,
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Retry counters — split by phase (single retry_count is BANNED)
    investigation_retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    execution_retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    verification_retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    # Host key for linking related incidents (same server: e.g. private_ip or instance_id)
    host_key: Mapped[str | None] = mapped_column(String(512), nullable=True, index=False)

    # Flexible metadata
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    evidence: Mapped[list[Evidence]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="[Evidence.tenant_id, Evidence.incident_id]",
        primaryjoin=(
            "and_(Incident.tenant_id == Evidence.tenant_id, "
            "Incident.id == Evidence.incident_id)"
        ),
    )
    state_transitions: Mapped[list[StateTransition]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="StateTransition.created_at",
        foreign_keys="[StateTransition.tenant_id, StateTransition.incident_id]",
        primaryjoin=(
            "and_(Incident.tenant_id == StateTransition.tenant_id, "
            "Incident.id == StateTransition.incident_id)"
        ),
    )
    executions: Mapped[list[Execution]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="[Execution.tenant_id, Execution.incident_id]",
        primaryjoin=(
            "and_(Incident.tenant_id == Execution.tenant_id, "
            "Incident.id == Execution.incident_id)"
        ),
    )
