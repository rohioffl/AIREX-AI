"""LiteLLM-powered embeddings helper with metrics + timeouts."""

from __future__ import annotations

import asyncio
from typing import Sequence

import litellm
import structlog

from airex_core.core.config import settings
from airex_core.core.metrics import ai_failure_total, ai_request_total
from airex_core.llm import build_llm_headers, configure_litellm

logger = structlog.get_logger()


class EmbeddingsClient:
    """Thin wrapper for litellm embeddings with instrumentation."""

    def __init__(self) -> None:
        configure_litellm()
        self._model = settings.LLM_EMBEDDING_MODEL
        self._timeout = settings.LLM_EMBEDDING_TIMEOUT
        self._dimensions = settings.LLM_EMBEDDING_DIMENSION

    async def embed_text(self, text: str) -> list[float]:
        if not text.strip():
            raise RuntimeError("Cannot embed empty text")

        vectors = await self.embed_texts([text])
        return vectors[0]

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        payload = [t.strip() for t in texts]
        if not any(payload):
            raise RuntimeError("No non-empty inputs provided for embeddings")

        for item in payload:
            if not item:
                raise RuntimeError(
                    "All embedding inputs must be non-empty after stripping"
                )

        ai_request_total.labels(model=self._model).inc()

        # When routing through a LiteLLM proxy, use the openai/
        # prefix so the local litellm SDK treats it as an
        # OpenAI-compatible endpoint and forwards to the proxy.
        effective_model = self._model
        if settings.LLM_BASE_URL:
            if not self._model.startswith("openai/"):
                effective_model = f"openai/{self._model}"

        kwargs: dict[str, object] = {
            "model": effective_model,
            "input": payload,
        }
        # Skip dimensions when routing through a proxy — the litellm SDK
        # rejects it for openai/-prefixed models, and the proxy config
        # already passes dimensions to the upstream provider.
        if self._dimensions and not settings.LLM_BASE_URL:
            kwargs["dimensions"] = self._dimensions

        # Pass proxy base URL and API key when configured
        if settings.LLM_BASE_URL:
            kwargs["api_base"] = settings.LLM_BASE_URL
        if settings.LLM_API_KEY:
            kwargs["api_key"] = settings.LLM_API_KEY

        headers = build_llm_headers()
        if headers:
            kwargs["extra_headers"] = headers

        try:
            response = await asyncio.wait_for(
                litellm.aembedding(**kwargs),
                timeout=self._timeout,
            )
            vectors = [record["embedding"] for record in response["data"]]
            if len(vectors) != len(payload):
                raise RuntimeError("Embedding response size mismatch")
            # Map back to original ordering (skipping empty strings)
            return vectors
        except asyncio.TimeoutError as exc:
            logger.warning("embedding_timeout", timeout=self._timeout)
            ai_failure_total.labels(
                model=self._model,
                error_type="embedding_timeout",
            ).inc()
            raise RuntimeError("Embedding request timed out") from exc
        except Exception as exc:  # pragma: no cover - network errors
            logger.warning("embedding_failed", error=str(exc))
            ai_failure_total.labels(
                model=self._model,
                error_type="embedding_failure",
            ).inc()
            raise RuntimeError("Embedding request failed") from exc


__all__ = ["EmbeddingsClient"]
