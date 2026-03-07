"""
Incident AI Chat endpoint (Phase 7).

POST /api/v1/incidents/{incident_id}/chat
GET  /api/v1/incidents/{incident_id}/chat/history
DELETE /api/v1/incidents/{incident_id}/chat/history
"""

import uuid
from functools import lru_cache
from importlib import import_module
from typing import Any, Awaitable, Callable, cast

import structlog
from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import Redis, TenantId, TenantSession
from app.schemas.chat import ChatRequest, ChatResponse

logger = structlog.get_logger()

router = APIRouter()


@lru_cache(maxsize=1)
def _chat_service_module() -> Any:
    return import_module("app.services.chat_service")


@router.post(
    "/{incident_id}/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
async def send_chat_message(
    incident_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
    redis: Redis,
    body: ChatRequest,
) -> ChatResponse:
    """Send a chat message about an incident and receive an AI response.

    The conversation history is stored in Redis with a 24-hour TTL.
    Each incident has its own independent chat session.
    """
    chat_with_incident = cast(
        Callable[..., Awaitable[tuple[str, int]]],
        _chat_service_module().chat_with_incident,
    )
    try:
        reply, conversation_length = await chat_with_incident(
            session=session,
            incident_id=incident_id,
            tenant_id=tenant_id,
            user_message=body.message,
            redis=redis,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    return ChatResponse(
        reply=reply,
        conversation_length=conversation_length,
    )


@router.get(
    "/{incident_id}/chat/history",
    response_model=list[dict[str, str]],
    status_code=status.HTTP_200_OK,
)
async def get_chat_history(
    incident_id: uuid.UUID,
    tenant_id: TenantId,
    redis: Redis,
) -> list[dict[str, str]]:
    """Retrieve the conversation history for an incident chat session.

    Returns an empty list if no conversation exists.
    """
    get_conversation_history = cast(
        Callable[..., Awaitable[list[dict[str, str]]]],
        _chat_service_module().get_conversation_history,
    )
    history = await get_conversation_history(
        redis,
        str(tenant_id),
        str(incident_id),
    )
    return history


@router.delete(
    "/{incident_id}/chat/history",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def clear_chat_history(
    incident_id: uuid.UUID,
    tenant_id: TenantId,
    redis: Redis,
) -> None:
    """Clear the conversation history for an incident chat session."""
    save_conversation_history = cast(
        Callable[..., Awaitable[None]],
        _chat_service_module().save_conversation_history,
    )
    await save_conversation_history(
        redis,
        str(tenant_id),
        str(incident_id),
        [],
    )
    logger.info(
        "chat_history_cleared",
        tenant_id=str(tenant_id),
        incident_id=str(incident_id),
    )
