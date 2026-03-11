from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, Index, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from airex_core.core.config import settings
from airex_core.models.base import Base, TenantMixin


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RunbookChunk(Base, TenantMixin):
    """Embedded runbook/document chunks used for retrieval-augmented guidance."""

    __tablename__ = "runbook_chunks"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "id"),
        UniqueConstraint(
            "tenant_id",
            "source_type",
            "source_id",
            "chunk_index",
            name="uq_runbook_chunk_source",
        ),
        Index(
            "idx_runbook_chunks_tenant_source", "tenant_id", "source_type", "source_id"
        ),
        CheckConstraint("chunk_index >= 0", name="ck_runbook_chunk_index_non_negative"),
    )

    source_type: Mapped[str] = mapped_column(nullable=False, index=False)
    source_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(nullable=False)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(settings.LLM_EMBEDDING_DIMENSION),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_utcnow
    )

    def __repr__(self) -> str:
        return (
            "RunbookChunk("
            f"tenant_id={self.tenant_id!s}, "
            f"id={self.id!s}, "
            f"source_type={self.source_type!r}, "
            f"source_id={self.source_id!s}, "
            f"chunk_index={self.chunk_index}"
            ")"
        )
