"""AWS Secrets Manager resolver with in-process TTL cache.

Fetch JSON secrets at runtime so sensitive material never lives in PostgreSQL
or environment variables.  The cache is thread-safe and works from both async
and sync call paths (the underlying boto3 call is blocking but fast).

Secrets Manager is **never** called from external clients — only
``airex-api`` and ``airex-worker`` use this module via the ECS task IAM role.

Usage::

    from airex_core.cloud.secret_resolver import get_secret_json, SecretResolverError

    try:
        payload = get_secret_json(binding.credentials_secret_arn, tenant_id=tenant_id)
        access_key = payload["static"]["access_key_id"]
    except SecretResolverError as exc:
        logger.error("secret_fetch_failed", error=str(exc))
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import structlog
from structlog.contextvars import get_contextvars

logger = structlog.get_logger()

# ── In-process cache ──────────────────────────────────────────────────────────
# key: secret ARN (full or name)
# value: (parsed_dict, monotonic_timestamp_of_fetch)
_cache: dict[str, tuple[dict, float]] = {}
_CACHE_LOCK = threading.Lock()
_DEFAULT_TTL = 60  # seconds — overridden by settings.TENANT_SECRET_CACHE_TTL_SECONDS


# ── Public exception ─────────────────────────────────────────────────────────


class SecretResolverError(Exception):
    """Raised when a secret cannot be fetched, is missing, or is not valid JSON."""


# ── Internal helpers ─────────────────────────────────────────────────────────


def _get_ttl() -> int:
    """Read TTL from settings; fall back to default if settings are unavailable."""
    try:
        from airex_core.core.config import settings  # noqa: PLC0415

        return settings.TENANT_SECRET_CACHE_TTL_SECONDS
    except Exception:
        return _DEFAULT_TTL


def _arn_suffix(arn: str) -> str:
    """Return last 6 characters of the ARN for log output (safe to log)."""
    return f"...{arn[-6:]}" if len(arn) >= 6 else arn


def _fetch_from_aws(arn: str) -> dict:
    """Call AWS Secrets Manager synchronously and parse the JSON secret string.

    Raises:
        SecretResolverError: On API error, missing SecretString, or invalid JSON.
    """
    try:
        import boto3  # type: ignore[import-not-found]
        from botocore.exceptions import ClientError  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise SecretResolverError("boto3 is not installed") from exc

    client = boto3.client("secretsmanager")
    try:
        response = client.get_secret_value(SecretId=arn)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        raise SecretResolverError(
            f"Secrets Manager [{code}] for {_arn_suffix(arn)}"
        ) from exc

    raw: str = response.get("SecretString") or ""
    if not raw:
        raise SecretResolverError(
            f"Secret {_arn_suffix(arn)} has no SecretString (binary secrets not supported)"
        )

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SecretResolverError(
            f"Secret {_arn_suffix(arn)} is not valid JSON"
        ) from exc


# ── Public API ────────────────────────────────────────────────────────────────


def get_secret_json(
    arn: str,
    tenant_id: str = "",
    correlation_id: str = "",
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Fetch a JSON secret from AWS Secrets Manager with in-process TTL cache.

    Results are cached by ARN for ``TENANT_SECRET_CACHE_TTL_SECONDS`` (default 60s).
    ``force_refresh=True`` bypasses the cache (e.g. after rotation).

    Security contract:
    - The returned dict is **never logged** — only the ARN suffix appears in logs.
    - Callers must not pass the returned dict to browser clients or
      any external system.

    Args:
        arn: Full ARN or secret name in AWS Secrets Manager.
        tenant_id: Used only for structured log context — not appended to the ARN.
        correlation_id: Request correlation ID for log tracing.
        force_refresh: Bypass cache and re-fetch unconditionally.

    Returns:
        Parsed dict from the secret's SecretString.

    Raises:
        ValueError: If ``arn`` is empty.
        SecretResolverError: If the secret cannot be fetched or is not valid JSON.
    """
    if not arn:
        raise ValueError("Secret ARN must not be empty")

    _cid = correlation_id or str(get_contextvars().get("correlation_id", ""))
    _tid = tenant_id or str(get_contextvars().get("tenant_id", ""))
    ttl = _get_ttl()

    if not force_refresh:
        with _CACHE_LOCK:
            entry = _cache.get(arn)
            if entry is not None and (time.monotonic() - entry[1]) < ttl:
                logger.debug(
                    "secret_resolver_cache_hit",
                    arn_suffix=_arn_suffix(arn),
                    tenant_id=_tid,
                    correlation_id=_cid,
                )
                return entry[0]

    logger.info(
        "secret_resolver_fetch",
        arn_suffix=_arn_suffix(arn),
        tenant_id=_tid,
        correlation_id=_cid,
        force_refresh=force_refresh,
    )

    payload = _fetch_from_aws(arn)

    with _CACHE_LOCK:
        _cache[arn] = (payload, time.monotonic())

    return payload


def invalidate(arn: str) -> None:
    """Remove a single entry from the cache (call after secret rotation)."""
    with _CACHE_LOCK:
        _cache.pop(arn, None)
    logger.info("secret_resolver_cache_invalidated", arn_suffix=_arn_suffix(arn))


def invalidate_all() -> None:
    """Clear the entire secret cache (call on admin reload or tenant offboarding)."""
    with _CACHE_LOCK:
        _cache.clear()
    logger.info("secret_resolver_cache_cleared")
