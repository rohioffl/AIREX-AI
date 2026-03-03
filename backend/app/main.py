"""AIREX Backend — FastAPI application entrypoint."""

import time
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from app.api.routes import (
    auth,
    chat,
    dlq,
    health_checks,
    incidents,
    metrics as metrics_router,
    sse,
    settings as settings_router,
    tenants,
    users,
    webhooks,
)
from app.core.config import settings
from app.core.events import set_redis
from app.core.logging import setup_logging
from app.core.csrf import CSRFMiddleware
from app.core.metrics import http_request_duration_seconds

# Configure structured logging on import
setup_logging(json_output=False)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle — manages Redis connection pool."""
    redis_conn = aioredis.from_url(settings.REDIS_URL, decode_responses=False)
    app.state.redis = redis_conn
    set_redis(redis_conn)
    logger.info("startup_complete", redis_url=settings.REDIS_URL)
    yield
    await redis_conn.aclose()
    set_redis(None)
    logger.info("shutdown_complete")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Autonomous Incident Resolution Engine Xecution",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# CSRF protection
app.add_middleware(CSRFMiddleware)


# Prometheus middleware
@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    path = request.url.path
    if not path.startswith("/metrics"):
        http_request_duration_seconds.labels(
            method=request.method,
            path=path,
            status_code=str(response.status_code),
        ).observe(duration)
    return response


# Correlation ID middleware
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    import uuid

    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


# Health check
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "airex-backend"}


# Prometheus metrics endpoint
@app.get("/metrics")
async def prometheus_metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


# Register routes
app.include_router(
    auth.router,
    prefix=f"{settings.API_V1_STR}/auth",
    tags=["auth"],
)
app.include_router(
    webhooks.router,
    prefix=f"{settings.API_V1_STR}/webhooks",
    tags=["webhooks"],
)
app.include_router(
    incidents.router,
    prefix=f"{settings.API_V1_STR}/incidents",
    tags=["incidents"],
)
app.include_router(
    chat.router,
    prefix=f"{settings.API_V1_STR}/incidents",
    tags=["chat"],
)
app.include_router(
    sse.router,
    prefix=f"{settings.API_V1_STR}/events",
    tags=["events"],
)
app.include_router(
    tenants.router,
    prefix=f"{settings.API_V1_STR}/tenants",
    tags=["tenants"],
)
app.include_router(
    users.router,
    prefix=f"{settings.API_V1_STR}/users",
    tags=["users"],
)
app.include_router(
    dlq.router,
    prefix=f"{settings.API_V1_STR}/dlq",
    tags=["dlq"],
)
app.include_router(
    metrics_router.router,
    prefix=f"{settings.API_V1_STR}/metrics",
    tags=["metrics"],
)
app.include_router(
    settings_router.router,
    prefix=f"{settings.API_V1_STR}/settings",
    tags=["settings"],
)
app.include_router(
    health_checks.router,
    prefix=f"{settings.API_V1_STR}/health-checks",
    tags=["health-checks"],
)
