from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    Enum as SAEnum,
    ForeignKeyConstraint,
    Index,
    PrimaryKeyConstraint,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airex_core.models.base import Base, TenantMixin
from airex_core.models.enums import IncidentState

if TYPE_CHECKING:
    from airex_core.models.incident import Incident


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StateTransition(Base, TenantMixin):
    """
    Immutable audit log of incident state changes.

    Hash-chained: each record includes SHA256(previous_hash + payload).
    UPDATE and DELETE are revoked at the DB level.
    """

    __tablename__ = "state_transitions"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "incident_id"],
            ["incidents.tenant_id", "incidents.id"],
            ondelete="CASCADE",
        ),
        Index("idx_state_transitions_incident_fk", "tenant_id", "incident_id"),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    from_state: Mapped[IncidentState] = mapped_column(
        SAEnum(
            IncidentState,
            name="incident_state",
            create_constraint=False,
            native_enum=True,
        ),
        nullable=False,
    )
    to_state: Mapped[IncidentState] = mapped_column(
        SAEnum(
            IncidentState,
            name="incident_state",
            create_constraint=False,
            native_enum=True,
        ),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_utcnow
    )

    # Hash chain for tamper evidence
    previous_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, default="GENESIS"
    )
    hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Relationship
    incident: Mapped[Incident] = relationship(
        back_populates="state_transitions",
        foreign_keys="[StateTransition.tenant_id, StateTransition.incident_id]",
        primaryjoin=(
            "and_(StateTransition.tenant_id == Incident.tenant_id, "
            "StateTransition.incident_id == Incident.id)"
        ),
    )

    def __repr__(self) -> str:
        return (
            "StateTransition("
            f"tenant_id={self.tenant_id!s}, "
            f"id={self.id!s}, "
            f"incident_id={self.incident_id!s}, "
            f"from_state={self.from_state.value!r}, "
            f"to_state={self.to_state.value!r}"
            ")"
        )
