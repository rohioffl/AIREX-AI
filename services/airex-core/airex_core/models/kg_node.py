from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from airex_core.core.config import settings
from airex_core.models.base import Base, TenantMixin


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KGNode(Base, TenantMixin):
    """Infrastructure entity node in the Knowledge Graph.

    entity_id is a stable, human-readable key scoped to the tenant:
      "service:checkout-api", "host:10.0.1.5", "pod:checkout-api-xyz",
      "ip:10.0.1.5", "config:nginx.conf", "alert_type:high_cpu"

    entity_type is one of: service | host | pod | ip | config |
                           alert_type | incident | runbook
    """

    __tablename__ = "kg_nodes"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "entity_id", name="uq_kg_node_entity"),
        Index("idx_kg_nodes_tenant_entity", "tenant_id", "entity_id"),
        Index("idx_kg_nodes_tenant_type", "tenant_id", "entity_type"),
    )

    entity_id: Mapped[str] = mapped_column(nullable=False)
    entity_type: Mapped[str] = mapped_column(nullable=False)
    label: Mapped[str] = mapped_column(nullable=False)
    properties: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.LLM_EMBEDDING_DIMENSION), nullable=True
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_utcnow
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:
        return (
            "KGNode("
            f"tenant_id={self.tenant_id!s}, "
            f"entity_id={self.entity_id!r}, "
            f"entity_type={self.entity_type!r}"
            ")"
        )


__all__ = ["KGNode"]
