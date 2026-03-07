"""
Redis-backed sliding window rate limiter.

Applied as a FastAPI dependency to protect webhook and approval endpoints.
"""

import time
from inspect import isawaitable
from collections.abc import Awaitable, Callable

import structlog
from fastapi import HTTPException, Request, status
from redis.exceptions import RedisError

logger = structlog.get_logger()

DEFAULT_LIMIT = 60
DEFAULT_WINDOW = 60


def _get_correlation_id(request: Request) -> str | None:
    """Return correlation id from request headers when present."""
    return request.headers.get("x-correlation-id")


async def rate_limit(
    request: Request,
    limit: int = DEFAULT_LIMIT,
    window: int = DEFAULT_WINDOW,
) -> None:
    """
    Sliding window rate limit.

    key = IP + path prefix (e.g. "rl:1.2.3.4:/api/v1/webhooks")
    """
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        return

    client_ip = request.client.host if request.client else "unknown"
    path_prefix = "/".join(request.url.path.split("/")[:4])
    key = f"rl:{client_ip}:{path_prefix}"
    correlation_id = _get_correlation_id(request)

    now = time.time()
    try:
        pipe = redis.pipeline()
        if isawaitable(pipe):
            pipe = await pipe
        zrem_result = pipe.zremrangebyscore(key, 0, now - window)
        if isawaitable(zrem_result):
            await zrem_result

        zadd_result = pipe.zadd(key, {str(now): now})
        if isawaitable(zadd_result):
            await zadd_result

        zcard_result = pipe.zcard(key)
        if isawaitable(zcard_result):
            await zcard_result

        expire_result = pipe.expire(key, window + 1)
        if isawaitable(expire_result):
            await expire_result

        results = await pipe.execute()
    except RedisError as exc:
        logger.warning(
            "rate_limit_redis_unavailable",
            correlation_id=correlation_id,
            path=path_prefix,
            error_type=type(exc).__name__,
        )
        return

    count = int(results[2])
    if count > limit:
        logger.warning(
            "rate_limit_exceeded",
            correlation_id=correlation_id,
            client_ip=client_ip,
            path=path_prefix,
            count=count,
            limit=limit,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {limit} requests per {window}s",
            headers={"Retry-After": str(window)},
        )


def create_rate_limiter(
    limit: int = DEFAULT_LIMIT,
    window: int = DEFAULT_WINDOW,
) -> Callable[[Request], Awaitable[None]]:
    """Factory for FastAPI Depends() with custom limits."""

    async def _limiter(request: Request) -> None:
        await rate_limit(request, limit=limit, window=window)

    return _limiter


webhook_rate_limit = create_rate_limiter(limit=30, window=60)
approval_rate_limit = create_rate_limiter(limit=10, window=60)
auth_rate_limit = create_rate_limiter(limit=5, window=60)
