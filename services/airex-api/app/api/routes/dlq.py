"""
Dead Letter Queue (DLQ) inspection and replay endpoints.

Admin-only endpoints for viewing and replaying failed tasks.
"""

import json
from typing import Any, cast

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.dependencies import CurrentUser, RequireAdmin, Redis, TenantId, require_role
from airex_core.core.config import settings

DLQ_KEY = "airex:dlq"

logger = structlog.get_logger()

router = APIRouter()


class DLQEntry(BaseModel):
    task: str
    tenant_id: str
    incident_id: str
    error: str
    failed_at: str


class DLQListResponse(BaseModel):
    items: list[DLQEntry]
    total: int


@router.get("/", response_model=DLQListResponse, dependencies=[Depends(require_role("admin"))])
async def list_dlq(
    tenant_id: TenantId,
    redis: Redis,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
) -> DLQListResponse:
    """
    List all entries in the Dead Letter Queue (admin only).

    Returns failed tasks that exceeded max retries.
    """
    redis_client = cast(Any, redis)

    # Get all entries from Redis list
    all_entries = await redis_client.lrange(DLQ_KEY, 0, -1)

    # Parse and filter by tenant
    items: list[DLQEntry] = []
    for entry_bytes in all_entries:
        try:
            entry_str = (
                entry_bytes.decode()
                if isinstance(entry_bytes, bytes)
                else str(entry_bytes)
            )
            entry = json.loads(entry_str)
            # Filter by tenant if specified
            if str(entry.get("tenant_id")) == str(tenant_id):
                items.append(DLQEntry(**entry))
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.warning("dlq_entry_parse_failed", error=str(exc), entry=entry_bytes)
            continue

    # Apply pagination
    paginated_items = items[offset : offset + limit]

    return DLQListResponse(items=paginated_items, total=len(items))


@router.post("/{entry_index}/replay", dependencies=[Depends(require_role("admin"))])
async def replay_dlq_entry(
    entry_index: int,
    tenant_id: TenantId,
    redis: Redis,
    current_user: CurrentUser,
) -> dict[str, str]:
    """
    Replay a failed task from the DLQ (admin only).

    Removes the entry from DLQ and re-enqueues the task.
    """
    # Get the entry at index
    redis_client = cast(Any, redis)
    entry_bytes = await redis_client.lindex(DLQ_KEY, entry_index)
    if entry_bytes is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DLQ entry at index {entry_index} not found",
        )

    try:
        entry_str = (
            entry_bytes.decode() if isinstance(entry_bytes, bytes) else str(entry_bytes)
        )
        entry = json.loads(entry_str)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid DLQ entry format: {exc}",
        ) from exc

    # Verify tenant matches
    if str(entry.get("tenant_id")) != str(tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DLQ entry belongs to a different tenant",
        )

    task_name = entry.get("task")
    incident_id = entry.get("incident_id")

    # Remove from DLQ
    await redis_client.lrem(DLQ_KEY, 1, entry_bytes)

    # Re-enqueue the task
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        await pool.enqueue_job(
            task_name,
            entry["tenant_id"],
            incident_id,
        )
        await pool.aclose()

        logger.info(
            "dlq_entry_replayed",
            entry_index=entry_index,
            task=task_name,
            tenant_id=entry["tenant_id"],
            incident_id=incident_id,
            replayed_by=current_user.sub if current_user else "unknown",
        )

        return {
            "status": "replayed",
            "task": task_name,
            "incident_id": incident_id,
        }
    except Exception as exc:
        # Put back in DLQ if replay failed
        await redis_client.rpush(DLQ_KEY, entry_bytes)
        logger.error("dlq_replay_failed", error=str(exc), entry_index=entry_index)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to replay task: {exc}",
        ) from exc


@router.delete("/", dependencies=[Depends(require_role("admin"))])
async def clear_dlq(
    tenant_id: TenantId,
    redis: Redis,
    current_user: CurrentUser,
) -> dict[str, str | int]:
    """
    Clear all DLQ entries for the current tenant (admin only).
    """
    # Get all entries
    redis_client = cast(Any, redis)
    all_entries = await redis_client.lrange(DLQ_KEY, 0, -1)

    # Filter and remove tenant-specific entries
    removed_count = 0
    for entry_bytes in all_entries:
        try:
            entry_str = (
                entry_bytes.decode()
                if isinstance(entry_bytes, bytes)
                else str(entry_bytes)
            )
            entry = json.loads(entry_str)
            if str(entry.get("tenant_id")) == str(tenant_id):
                await redis_client.lrem(DLQ_KEY, 1, entry_bytes)
                removed_count += 1
        except (json.JSONDecodeError, ValueError):
            continue

    logger.info(
        "dlq_cleared",
        tenant_id=str(tenant_id),
        removed_count=removed_count,
        cleared_by=current_user.sub if current_user else "unknown",
    )

    return {
        "status": "cleared",
        "removed_count": removed_count,
    }
