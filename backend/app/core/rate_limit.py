"""
Redis-backed sliding window rate limiter.

Applied as a FastAPI dependency to protect webhook and approval endpoints.
"""

import time

import structlog
from fastapi import HTTPException, Request, status

logger = structlog.get_logger()

DEFAULT_LIMIT = 60
DEFAULT_WINDOW = 60


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

    now = time.time()
    try:
        pipe = redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window + 1)
        results = await pipe.execute()
    except Exception:
        return

    count = results[2]
    if count > limit:
        logger.warning(
            "rate_limit_exceeded",
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


def create_rate_limiter(limit: int = DEFAULT_LIMIT, window: int = DEFAULT_WINDOW):
    """Factory for FastAPI Depends() with custom limits."""
    async def _limiter(request: Request):
        await rate_limit(request, limit=limit, window=window)
    return _limiter


webhook_rate_limit = create_rate_limiter(limit=30, window=60)
approval_rate_limit = create_rate_limiter(limit=10, window=60)
auth_rate_limit = create_rate_limiter(limit=5, window=60)
