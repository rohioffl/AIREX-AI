"""pgvector-backed semantic search helpers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.llm.embeddings import EmbeddingsClient
from app.models.incident_embedding import IncidentEmbedding
from app.models.runbook_chunk import RunbookChunk

logger = structlog.get_logger()


@dataclass(frozen=True, slots=True)
class RunbookMatch:
    source_type: str
    source_id: uuid.UUID
    chunk_index: int
    content: str
    metadata: dict[str, Any]
    score: float


@dataclass(frozen=True, slots=True)
class IncidentMatch:
    incident_id: uuid.UUID
    summary: str
    score: float


class VectorStore:
    """High-level RAG helper for runbooks and prior incidents."""

    def __init__(self, embeddings_client: EmbeddingsClient | None = None) -> None:
        self._embeddings = embeddings_client or EmbeddingsClient()

    async def search_runbook_chunks(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        query: str,
        *,
        limit: int | None = None,
    ) -> list[RunbookMatch]:
        if not query.strip():
            return []

        limit = limit or settings.RAG_RUNBOOK_LIMIT
        try:
            query_embedding = await self._embeddings.embed_text(query)
        except RuntimeError:
            logger.warning("rag_embedding_failed", scope="runbooks")
            return []

        distance_expr = RunbookChunk.embedding.cosine_distance(query_embedding).label(
            "distance"
        )
        stmt = (
            select(
                RunbookChunk.source_type,
                RunbookChunk.source_id,
                RunbookChunk.chunk_index,
                RunbookChunk.content,
                RunbookChunk.meta,
                distance_expr,
            )
            .where(RunbookChunk.tenant_id == tenant_id)
            .order_by(distance_expr)
            .limit(limit)
        )

        result = await session.execute(stmt)
        threshold = settings.RAG_SIMILARITY_THRESHOLD
        matches: list[RunbookMatch] = []
        for row in result:
            distance = _safe_float(row.distance)
            if distance > threshold:
                logger.debug(
                    "rag_runbook_below_threshold",
                    distance=distance,
                    threshold=threshold,
                )
                continue
            matches.append(
                RunbookMatch(
                    source_type=row.source_type,
                    source_id=row.source_id,
                    chunk_index=row.chunk_index,
                    content=row.content,
                    metadata=row.meta or {},
                    score=distance,
                )
            )
        return matches

    async def search_incident_history(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        query: str,
        *,
        limit: int | None = None,
    ) -> list[IncidentMatch]:
        if not query.strip():
            return []

        limit = limit or settings.RAG_INCIDENT_LIMIT
        try:
            query_embedding = await self._embeddings.embed_text(query)
        except RuntimeError:
            logger.warning("rag_embedding_failed", scope="incidents")
            return []

        distance_expr = IncidentEmbedding.embedding.cosine_distance(
            query_embedding
        ).label("distance")
        stmt = (
            select(
                IncidentEmbedding.incident_id,
                IncidentEmbedding.summary,
                distance_expr,
            )
            .where(IncidentEmbedding.tenant_id == tenant_id)
            .order_by(distance_expr)
            .limit(limit)
        )

        result = await session.execute(stmt)
        threshold = settings.RAG_SIMILARITY_THRESHOLD
        matches: list[IncidentMatch] = []
        for row in result:
            distance = _safe_float(row.distance)
            if distance > threshold:
                logger.debug(
                    "rag_incident_below_threshold",
                    distance=distance,
                    threshold=threshold,
                )
                continue
            matches.append(
                IncidentMatch(
                    incident_id=row.incident_id,
                    summary=row.summary,
                    score=distance,
                )
            )
        return matches


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return 0.0


__all__ = ["IncidentMatch", "RunbookMatch", "VectorStore"]
