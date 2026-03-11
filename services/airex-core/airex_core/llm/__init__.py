"""LLM utilities: central LiteLLM configuration helpers."""

from __future__ import annotations

import litellm
import structlog

from airex_core.core.config import settings

logger = structlog.get_logger()

_configured = False


def configure_litellm() -> None:
    """Apply shared LiteLLM configuration once per process."""

    global _configured
    if _configured:
        return

    if settings.LLM_API_KEY:
        litellm.api_key = settings.LLM_API_KEY
    if settings.LLM_BASE_URL:
        litellm.api_base = settings.LLM_BASE_URL
    if settings.LLM_API_VERSION:
        litellm.api_version = settings.LLM_API_VERSION

    logger.info(
        "litellm_configured",
        api_base=settings.LLM_BASE_URL,
        embedding_model=settings.LLM_EMBEDDING_MODEL,
    )
    _configured = True


def build_llm_headers() -> dict[str, str]:
    """Attach correlation ID header for downstream tracing."""

    from structlog.contextvars import get_contextvars

    headers: dict[str, str] = {}
    correlation_id = get_contextvars().get("correlation_id")
    if correlation_id:
        headers[settings.LLM_CORRELATION_HEADER] = str(correlation_id)
    return headers


__all__ = ["configure_litellm", "build_llm_headers"]
