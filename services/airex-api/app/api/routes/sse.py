"""
Server-Sent Events endpoint for real-time incident updates.

Subscribes to Redis pub/sub channel scoped to tenant_id.
Supports JWT authentication via query param (for EventSource which can't set headers).
"""

import asyncio
import json
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sse_starlette.sse import EventSourceResponse

from app.api.dependencies import Redis, get_auth_session, resolve_active_tenant_id
from airex_core.core.config import settings
from airex_core.core.security import decode_access_token
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

router = APIRouter()

AUTH_ERROR_DETAIL = "Invalid or expired token"


async def _resolve_tenant(
    session: AsyncSession,
    *,
    token: str | None = None,
    active_tenant_id: str | None = None,
) -> uuid.UUID:
    """Resolve the tenant channel for SSE subscriptions.

    If a JWT is provided, use the same tenant-switch logic as the REST API.
    In dev mode without auth, fall back to the explicit active tenant query
    param or the configured DEV tenant.
    """
    current_user = None
    if token:
        try:
            current_user = decode_access_token(token)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=AUTH_ERROR_DETAIL,
            ) from exc

    return await resolve_active_tenant_id(
        session=session,
        current_user=current_user,
        active_tenant_id=active_tenant_id,
    )


@router.get("/stream")
async def event_stream(
    request: Request,
    redis: Redis,
    token: str | None = Query(None),
    active_tenant_id: str | None = Query(None),
    session: AsyncSession = Depends(get_auth_session),
) -> EventSourceResponse:
    """
    SSE stream for a tenant. Emits events:
    - incident_created
    - state_changed
    - evidence_added
    - execution_started
    - execution_log
    - execution_completed
    - verification_result

    Auth: pass `token` query param with JWT. If the user switched tenants in
    the UI, also pass `active_tenant_id` so SSE subscribes to the same tenant
    channel as the REST API.
    """
    tenant_id = await _resolve_tenant(
        session,
        token=token,
        active_tenant_id=active_tenant_id,
    )

    async def generate():
        channel = f"tenant:{tenant_id}:events"
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)

        try:
            while True:
                if await request.is_disconnected():
                    break

                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=0.5
                )
                if message and message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")

                    try:
                        event_data = json.loads(data)
                        event_type = event_data.get("event", "message")
                        yield {
                            "event": event_type,
                            "data": json.dumps(event_data.get("payload", {})),
                        }
                    except json.JSONDecodeError:
                        yield {"event": "message", "data": data}
                else:
                    yield {"event": "heartbeat", "data": ""}
                    await asyncio.sleep(1)

        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    # ping=15 sends a keepalive comment every 15s so proxies/LBs don't close the stream
    return EventSourceResponse(
        generate(),
        ping=15,
        send_timeout=2.0,
    )


async def publish_event(
    redis,
    tenant_id: str,
    event_type: str,
    payload: dict,
) -> None:
    """Publish an event to the tenant's SSE channel."""
    channel = f"tenant:{tenant_id}:events"
    message = json.dumps({"event": event_type, "payload": payload})
    await redis.publish(channel, message)
