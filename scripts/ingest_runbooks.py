"""CLI script to chunk + embed runbooks into pgvector."""

from __future__ import annotations

import argparse
import asyncio
import uuid
from pathlib import Path

import structlog
from sqlalchemy import delete

from airex_core.core.config import settings
from airex_core.core.database import get_tenant_session
from airex_core.llm.embeddings import EmbeddingsClient
from airex_core.models.runbook_chunk import RunbookChunk
from airex_core.rag.chunker import chunk_text

logger = structlog.get_logger()


async def ingest_runbooks(directory: str, tenant_id: uuid.UUID) -> None:
    path = Path(directory)
    files = sorted(path.glob("*.md"))
    if not files:
        logger.warning("no_runbooks_found", directory=str(path))
        return

    embeddings = EmbeddingsClient()

    async with get_tenant_session(tenant_id) as session:
        for file_path in files:
            text = file_path.read_text(encoding="utf-8")
            chunks = chunk_text(text)
            if not chunks:
                logger.info("runbook_skipped_empty", file=str(file_path))
                continue

            source_id = uuid.uuid5(uuid.NAMESPACE_URL, str(file_path.resolve()))
            await session.execute(
                delete(RunbookChunk).where(
                    RunbookChunk.tenant_id == tenant_id,
                    RunbookChunk.source_id == source_id,
                )
            )

            try:
                vectors = await embeddings.embed_texts(chunks)
            except RuntimeError as exc:
                logger.error(
                    "runbook_embedding_failed", file=str(file_path), error=str(exc)
                )
                continue

            for idx, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
                session.add(
                    RunbookChunk(
                        tenant_id=tenant_id,
                        source_type="runbook",
                        source_id=source_id,
                        chunk_index=idx,
                        content=chunk,
                        meta={
                            "title": file_path.stem,
                            "path": str(file_path),
                        },
                        embedding=vector,
                    )
                )

        logger.info("runbook_ingest_completed", files=len(files))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chunk + embed runbooks")
    parser.add_argument(
        "--directory",
        default="docs/runbooks",
        help="Path containing markdown runbooks",
    )
    parser.add_argument(
        "--tenant-id",
        default=settings.DEV_TENANT_ID,
        help="Tenant UUID to tag the runbooks with",
    )
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    tenant_id = uuid.UUID(args.tenant_id)
    await ingest_runbooks(args.directory, tenant_id)


if __name__ == "__main__":
    asyncio.run(_main())
