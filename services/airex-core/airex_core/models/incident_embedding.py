from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ForeignKeyConstraint,
    Index,
    PrimaryKeyConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from airex_core.core.config import settings
from airex_core.models.base import Base, TenantMixin


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IncidentEmbedding(Base, TenantMixin):
    """Vectorized incident summaries used for similarity retrieval."""

    __tablename__ = "incident_embeddings"
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
            name="uq_incident_embedding_incident",
        ),
        Index("idx_incident_embeddings_incident_fk", "tenant_id", "incident_id"),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    summary: Mapped[str] = mapped_column(nullable=False)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(settings.LLM_EMBEDDING_DIMENSION),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_utcnow
    )

    def __repr__(self) -> str:
        return (
            "IncidentEmbedding("
            f"tenant_id={self.tenant_id!s}, "
            f"id={self.id!s}, "
            f"incident_id={self.incident_id!s}"
            ")"
        )
