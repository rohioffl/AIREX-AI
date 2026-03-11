"""Utilities for splitting long runbooks / evidence into overlapping chunks."""

from __future__ import annotations

from typing import Iterable


def chunk_text(
    text: str,
    *,
    chunk_size: int = 800,
    overlap: int = 120,
) -> list[str]:
    """Return overlapping chunks of ``text`` for embeddings.

    Args:
        text: Raw runbook / document text.
        chunk_size: Max characters per chunk.
        overlap: Characters to repeat between consecutive chunks.
    """

    cleaned = text.strip()
    if not cleaned:
        return []

    chunks: list[str] = []
    start = 0
    length = len(cleaned)
    overlap = max(0, min(overlap, chunk_size // 2))

    while start < length:
        end = min(start + chunk_size, length)
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start = max(0, end - overlap)

    return chunks


def iter_chunks(
    text: str, *, chunk_size: int = 800, overlap: int = 120
) -> Iterable[str]:
    """Generator variant mainly for testing / streaming."""

    for chunk in chunk_text(text, chunk_size=chunk_size, overlap=overlap):
        yield chunk


__all__ = ["chunk_text", "iter_chunks"]
