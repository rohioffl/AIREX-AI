from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Index, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from airex_core.models.base import Base, TenantMixin


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KGEdge(Base, TenantMixin):
    """Directed relationship between two Knowledge Graph nodes.

    Relations:
      calls         — service A calls service B
      depends_on    — component A depends on component B
      caused_by     — incident/alert A was caused by entity B
      resolved_by   — incident A was resolved by executing action B
      what_worked   — alert_type/service A: action B worked (weight increases each time)
    """

    __tablename__ = "kg_edges"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "id"),
        UniqueConstraint(
            "tenant_id",
            "src_entity_id",
            "relation",
            "dst_entity_id",
            name="uq_kg_edge_triple",
        ),
        Index("idx_kg_edges_tenant_src", "tenant_id", "src_entity_id"),
        Index("idx_kg_edges_tenant_dst", "tenant_id", "dst_entity_id"),
        Index("idx_kg_edges_relation", "tenant_id", "relation"),
    )

    src_entity_id: Mapped[str] = mapped_column(nullable=False)
    relation: Mapped[str] = mapped_column(nullable=False)
    dst_entity_id: Mapped[str] = mapped_column(nullable=False)
    # weight: increases each time the same (src, rel, dst) triple is observed
    weight: Mapped[float] = mapped_column(nullable=False, default=1.0)
    causal_confidence: Mapped[float] = mapped_column(nullable=False, default=0.5)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_utcnow
    )
    valid_from: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_utcnow
    )
    valid_to: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:
        return (
            "KGEdge("
            f"tenant_id={self.tenant_id!s}, "
            f"{self.src_entity_id!r} -[{self.relation}]-> {self.dst_entity_id!r}, "
            f"weight={self.weight}"
            ")"
        )


__all__ = ["KGEdge"]
