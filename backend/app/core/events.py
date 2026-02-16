"""
SSE event publisher — single import for all services.

Services call emit_* functions which publish to the tenant's Redis pub/sub channel.
The SSE endpoint in api/routes/sse.py subscribes and forwards to the browser.
"""

import json

import structlog

logger = structlog.get_logger()

_redis = None


def set_redis(redis_instance) -> None:
    """Set the shared Redis instance (called at app startup)."""
    global _redis
    _redis = redis_instance


def get_redis():
    """Get the shared Redis instance."""
    return _redis


async def _publish(tenant_id: str, event_type: str, payload: dict) -> None:
    """Low-level publish to Redis pub/sub."""
    redis = get_redis()
    if redis is None:
        logger.warning("sse_publish_skipped_no_redis", event=event_type)
        return
    channel = f"tenant:{tenant_id}:events"
    message = json.dumps({"event": event_type, "payload": payload})
    await redis.publish(channel, message)


async def emit_incident_created(tenant_id: str, incident_id: str, title: str, state: str, severity: str, alert_type: str) -> None:
    await _publish(tenant_id, "incident_created", {
        "incident_id": incident_id,
        "title": title,
        "state": state,
        "severity": severity,
        "alert_type": alert_type,
    })


async def emit_state_changed(tenant_id: str, incident_id: str, from_state: str, to_state: str, reason: str) -> None:
    await _publish(tenant_id, "state_changed", {
        "incident_id": incident_id,
        "from_state": from_state,
        "to_state": to_state,
        "reason": reason,
    })


async def emit_evidence_added(tenant_id: str, incident_id: str, tool_name: str, evidence_id: str) -> None:
    await _publish(tenant_id, "evidence_added", {
        "incident_id": incident_id,
        "tool_name": tool_name,
        "evidence_id": evidence_id,
    })


async def emit_execution_started(tenant_id: str, incident_id: str, action_type: str, execution_id: str) -> None:
    await _publish(tenant_id, "execution_started", {
        "incident_id": incident_id,
        "action_type": action_type,
        "execution_id": execution_id,
    })


async def emit_execution_log(tenant_id: str, incident_id: str, log_line: str) -> None:
    await _publish(tenant_id, "execution_log", {
        "incident_id": incident_id,
        "log": log_line,
    })


async def emit_execution_completed(tenant_id: str, incident_id: str, action_type: str, status: str, duration: float | None = None) -> None:
    await _publish(tenant_id, "execution_completed", {
        "incident_id": incident_id,
        "action_type": action_type,
        "status": status,
        "duration_seconds": duration,
    })


async def emit_verification_result(tenant_id: str, incident_id: str, result: str) -> None:
    await _publish(tenant_id, "verification_result", {
        "incident_id": incident_id,
        "result": result,
    })


async def emit_recommendation_ready(tenant_id: str, incident_id: str, recommendation: dict) -> None:
    await _publish(tenant_id, "recommendation_ready", {
        "incident_id": incident_id,
        "recommendation": recommendation,
    })
