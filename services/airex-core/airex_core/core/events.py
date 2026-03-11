"""
SSE event publisher — single import for all services.

Services call emit_* functions which publish to the tenant's Redis pub/sub channel.
The SSE endpoint in api/routes/sse.py subscribes and forwards to the browser.
"""

import json
import uuid
from collections.abc import Awaitable
from typing import Any, Protocol

import structlog

logger = structlog.get_logger()

_redis = None


class RedisPublisher(Protocol):
    """Protocol for the Redis publish API used by this module."""

    def publish(self, channel: str, message: str) -> Awaitable[Any]:
        """Publish a message to a channel."""
        ...


def set_redis(redis_instance: RedisPublisher | None) -> None:
    """Set the shared Redis instance (called at app startup)."""
    global _redis
    _redis = redis_instance


def get_redis() -> RedisPublisher | None:
    """Get the shared Redis instance."""
    return _redis


async def _publish(
    tenant_id: str,
    event_type: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
) -> None:
    """Low-level publish to Redis pub/sub."""
    effective_correlation_id = correlation_id or str(uuid.uuid4())
    bound_logger = logger.bind(
        correlation_id=effective_correlation_id,
        tenant_id=tenant_id,
        event=event_type,
    )

    redis = get_redis()
    if redis is None:
        bound_logger.warning("sse_publish_skipped_no_redis")
        return

    channel = f"tenant:{tenant_id}:events"
    try:
        message = json.dumps({"event": event_type, "payload": payload})
    except (TypeError, ValueError) as exc:
        bound_logger.warning(
            "sse_publish_payload_encoding_failed",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return

    try:
        await redis.publish(channel, message)
    except (ConnectionError, TimeoutError, OSError, RuntimeError, ValueError) as exc:
        bound_logger.warning(
            "sse_publish_failed",
            error=str(exc),
            error_type=type(exc).__name__,
            channel=channel,
        )


async def emit_incident_created(
    tenant_id: str,
    incident_id: str,
    title: str,
    state: str,
    severity: str,
    alert_type: str,
    correlation_id: str | None = None,
) -> None:
    """Emit incident_created event for a newly created incident."""
    await _publish(
        tenant_id,
        "incident_created",
        {
            "incident_id": incident_id,
            "title": title,
            "state": state,
            "severity": severity,
            "alert_type": alert_type,
        },
        correlation_id=correlation_id,
    )


async def emit_state_changed(
    tenant_id: str,
    incident_id: str,
    from_state: str,
    to_state: str,
    reason: str,
    correlation_id: str | None = None,
) -> None:
    """Emit state_changed event after a valid state transition."""
    await _publish(
        tenant_id,
        "state_changed",
        {
            "incident_id": incident_id,
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason,
        },
        correlation_id=correlation_id,
    )


async def emit_evidence_added(
    tenant_id: str,
    incident_id: str,
    tool_name: str,
    evidence_id: str,
    correlation_id: str | None = None,
) -> None:
    """Emit evidence_added event when a probe stores new evidence."""
    await _publish(
        tenant_id,
        "evidence_added",
        {
            "incident_id": incident_id,
            "tool_name": tool_name,
            "evidence_id": evidence_id,
        },
        correlation_id=correlation_id,
    )


async def emit_execution_started(
    tenant_id: str,
    incident_id: str,
    action_type: str,
    execution_id: str,
    correlation_id: str | None = None,
) -> None:
    """Emit execution_started event for an approved action."""
    await _publish(
        tenant_id,
        "execution_started",
        {
            "incident_id": incident_id,
            "action_type": action_type,
            "execution_id": execution_id,
        },
        correlation_id=correlation_id,
    )


async def emit_execution_log(
    tenant_id: str,
    incident_id: str,
    log_line: str,
    correlation_id: str | None = None,
) -> None:
    """Emit execution_log event for live command output streaming."""
    await _publish(
        tenant_id,
        "execution_log",
        {
            "incident_id": incident_id,
            "log": log_line,
        },
        correlation_id=correlation_id,
    )


async def emit_execution_completed(
    tenant_id: str,
    incident_id: str,
    action_type: str,
    status: str,
    duration: float | None = None,
    correlation_id: str | None = None,
) -> None:
    """Emit execution_completed event for action completion status."""
    await _publish(
        tenant_id,
        "execution_completed",
        {
            "incident_id": incident_id,
            "action_type": action_type,
            "status": status,
            "duration_seconds": duration,
        },
        correlation_id=correlation_id,
    )


async def emit_verification_result(
    tenant_id: str,
    incident_id: str,
    result: str,
    correlation_id: str | None = None,
) -> None:
    """Emit verification_result event after post-action checks."""
    await _publish(
        tenant_id,
        "verification_result",
        {
            "incident_id": incident_id,
            "result": result,
        },
        correlation_id=correlation_id,
    )


async def emit_recommendation_ready(
    tenant_id: str,
    incident_id: str,
    recommendation: dict[str, Any],
    correlation_id: str | None = None,
) -> None:
    """Emit recommendation_ready event with AI recommendation payload."""
    await _publish(
        tenant_id,
        "recommendation_ready",
        {
            "incident_id": incident_id,
            "recommendation": recommendation,
        },
        correlation_id=correlation_id,
    )


async def emit_investigation_progress(
    tenant_id: str,
    incident_id: str,
    probe_name: str,
    status: str,
    step: int,
    total_steps: int,
    category: str = "",
    duration_ms: float = 0.0,
    anomaly_count: int = 0,
    correlation_id: str | None = None,
) -> None:
    """Emit a live investigation progress event for frontend timeline.

    Args:
        status: One of "started", "completed", "failed", "anomalies_detected"
        step: Current probe step number (1-indexed)
        total_steps: Total number of probes being run
    """
    await _publish(
        tenant_id,
        "investigation_progress",
        {
            "incident_id": incident_id,
            "probe_name": probe_name,
            "status": status,
            "step": step,
            "total_steps": total_steps,
            "category": category,
            "duration_ms": duration_ms,
            "anomaly_count": anomaly_count,
        },
        correlation_id=correlation_id,
    )
