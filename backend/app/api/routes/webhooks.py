"""
Webhook ingestion endpoints.

Receives external alerts, deduplicates via idempotency key,
creates incidents, and queues async investigation.
"""

import hashlib
import json as _json
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import Redis, TenantId, TenantSession
from app.core.rate_limit import webhook_rate_limit
from app.core.webhook_signature import verify_webhook_signature
from app.models.enums import IncidentState, SeverityLevel
from app.models.incident import Incident
from app.schemas.incident import IncidentCreatedResponse
from app.schemas.webhook import GenericWebhookPayload, Site24x7Payload
from app.core.events import emit_incident_created
from app.core.metrics import incident_created_total
from app.core.state_machine import transition_state
from app.cloud.tag_parser import parse_tags, merge_context_into_meta, discover_and_enrich

from sqlalchemy import select

logger = structlog.get_logger()

router = APIRouter()

# ── Severity mapping ─────────────────────────────────────────
SEVERITY_MAP: dict[str, SeverityLevel] = {
    "down": SeverityLevel.CRITICAL,
    "critical": SeverityLevel.CRITICAL,
    "trouble": SeverityLevel.HIGH,
    "high": SeverityLevel.HIGH,
    "medium": SeverityLevel.MEDIUM,
    "low": SeverityLevel.LOW,
    "up": SeverityLevel.LOW,
}

# ── Site24x7 monitor type → AIREX alert type ─────────────────
MONITOR_TYPE_MAP: dict[str, str] = {
    "url": "http_check",
    "homepage": "http_check",
    "realbrowser": "http_check",
    "restapi": "api_check",
    "server": "cpu_high",
    "agentserver": "cpu_high",
    "amazon": "cloud_check",
    "ec2instance": "cpu_high",
    "rdsinstance": "database_check",
    "applicationlog": "log_anomaly",
    "plugin": "plugin_check",
    "heartbeat": "heartbeat_check",
    "cron": "cron_check",
    "port": "port_check",
    "ping": "network_issue",
    "dns": "network_issue",
    "ssl": "ssl_check",
    "mailserver": "mail_check",
    "ftp": "ftp_check",
}


def _generate_idempotency_key(
    alert_type: str, resource_id: str, time_window: str
) -> str:
    """Deterministic key: SHA256(alert_type + resource_id + time_window)."""
    raw = f"{alert_type}:{resource_id}:{time_window}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _time_window() -> str:
    """5-minute time bucket for deduplication."""
    now = datetime.now(timezone.utc)
    bucket = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0)
    return bucket.isoformat()


def _map_site24x7_alert_type(monitor_type: str) -> str:
    """Map Site24x7 monitor type to AIREX alert type."""
    key = monitor_type.lower().replace(" ", "").replace("_", "")
    for k, v in MONITOR_TYPE_MAP.items():
        if k in key:
            return v
    return monitor_type.lower().replace(" ", "_")


async def _parse_site24x7_payload(request: Request) -> Site24x7Payload:
    """
    Parse Site24x7 webhook payload from any content type.

    Site24x7 may send data as:
      1. application/json — standard JSON body
      2. application/x-www-form-urlencoded — JSON string as form data
      3. Raw body — JSON string without proper content-type
    """
    content_type = request.headers.get("content-type", "")
    body = await request.body()

    if not body:
        raise HTTPException(status_code=400, detail="Empty request body")

    body_str = body.decode("utf-8").strip()

    # Try JSON parse first (works for application/json)
    try:
        data = _json.loads(body_str)
        if isinstance(data, dict):
            return Site24x7Payload.model_validate(data)
    except (_json.JSONDecodeError, Exception):
        pass

    # Form-urlencoded: Site24x7 sometimes sends the entire JSON as a form key
    if "=" in body_str or "application/x-www-form-urlencoded" in content_type:
        from urllib.parse import parse_qs, unquote
        parsed = parse_qs(body_str)
        # Case 1: JSON string is the first key (no =value)
        for key in parsed:
            try:
                data = _json.loads(unquote(key))
                if isinstance(data, dict):
                    return Site24x7Payload.model_validate(data)
            except (_json.JSONDecodeError, Exception):
                continue
        # Case 2: Form fields map directly
        flat = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
        if flat:
            return Site24x7Payload.model_validate(flat)

    raise HTTPException(status_code=400, detail="Could not parse Site24x7 payload")


@router.post(
    "/site24x7",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IncidentCreatedResponse,
    dependencies=[Depends(webhook_rate_limit), Depends(verify_webhook_signature)],
)
async def ingest_site24x7(
    request: Request,
    tenant_id: TenantId,
    session: TenantSession,
    redis: Redis,
) -> IncidentCreatedResponse:
    """
    Ingest a Site24x7 alert webhook.

    Accepts both JSON and form-urlencoded payloads.

    Configure in Site24x7:
      Admin → IT Automation → Webhooks
      URL: https://<your-domain>/api/v1/webhooks/site24x7
      Method: POST
      Headers: X-Tenant-Id: <your-tenant-uuid>
    """
    payload = await _parse_site24x7_payload(request)
    monitor_name = payload.get_monitor_name()
    status_str = payload.get_status()
    monitor_type = payload.get_monitor_type()
    monitor_id = payload.get_monitor_id()
    incident_reason = payload.get_incident_reason()

    # Skip "UP" status alerts — these are recovery notifications
    if status_str.lower() == "up":
        logger.info(
            "site24x7_recovery_received",
            tenant_id=str(tenant_id),
            monitor_name=monitor_name,
        )
        # Find active incident for this monitor and resolve it
        result = await session.execute(
            select(Incident).where(
                Incident.tenant_id == tenant_id,
                Incident.state.notin_([
                    IncidentState.RESOLVED,
                    IncidentState.ESCALATED,
                ]),
                Incident.deleted_at.is_(None),
            ).order_by(Incident.created_at.desc()).limit(1)
        )
        active = result.scalar_one_or_none()
        if active:
            try:
                await transition_state(
                    session, active, IncidentState.RESOLVED,
                    reason=f"Site24x7 recovery: {monitor_name} is UP",
                    actor="site24x7_webhook",
                )
            except Exception:
                pass
            return IncidentCreatedResponse(incident_id=active.id)

        # No active incident to resolve — return a dummy response
        import uuid as _uuid
        return IncidentCreatedResponse(
            incident_id=_uuid.UUID("00000000-0000-0000-0000-000000000000")
        )

    alert_type = _map_site24x7_alert_type(monitor_type)
    severity = SEVERITY_MAP.get(status_str.lower(), SeverityLevel.MEDIUM)

    # Idempotency: reject duplicate alerts within same 5-min window
    idem_key = _generate_idempotency_key(alert_type, monitor_id, _time_window())
    existing = await redis.get(f"idem:{tenant_id}:{idem_key}")
    if existing:
        logger.info(
            "duplicate_webhook_rejected",
            tenant_id=str(tenant_id),
            idempotency_key=idem_key,
        )
        return IncidentCreatedResponse(
            incident_id=existing.decode() if isinstance(existing, bytes) else existing
        )

    # Check for active incident on same monitor (use first() — there may be multiples)
    result = await session.execute(
        select(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.alert_type == alert_type,
            Incident.state.notin_([
                IncidentState.RESOLVED,
                IncidentState.ESCALATED,
                IncidentState.FAILED_ANALYSIS,
                IncidentState.FAILED_EXECUTION,
                IncidentState.FAILED_VERIFICATION,
            ]),
            Incident.deleted_at.is_(None),
        ).order_by(Incident.created_at.desc()).limit(1)
    )
    active = result.scalar_one_or_none()
    if active:
        logger.info(
            "active_incident_exists",
            tenant_id=str(tenant_id),
            incident_id=str(active.id),
        )
        return IncidentCreatedResponse(incident_id=active.id)

    # Build rich meta from Site24x7 payload
    meta = payload.model_dump(exclude_none=True)
    meta["_source"] = "site24x7"
    meta["monitor_name"] = monitor_name
    meta["host"] = monitor_name

    # Parse cloud tags (cloud:gcp, tenant:name, ip:10.x.x.x, etc.)
    # Site24x7 sends TAGS as either a comma-string or a JSON array
    raw_tags = payload.TAGS or payload.MONITOR_TAGS or ""
    if isinstance(raw_tags, list):
        raw_tags = ",".join(str(t) for t in raw_tags)
    cloud_ctx = parse_tags(raw_tags)

    # Auto-fill IP from payload fields if not in tags
    if not cloud_ctx.private_ip:
        payload_ip = payload.get_ip_address()
        if payload_ip:
            cloud_ctx.private_ip = payload_ip
            logger.info("ip_extracted_from_payload", ip=payload_ip)

    # Auto-discover instance details (zone, name, region) from cloud APIs
    # Uses the private IP from tags + project from tenant config
    try:
        cloud_ctx = await discover_and_enrich(cloud_ctx, redis=redis)
    except Exception as exc:
        logger.warning("auto_discovery_skipped", error=str(exc))

    # Override host with instance/IP from tags if available
    if cloud_ctx.instance_id:
        meta["host"] = cloud_ctx.instance_id
    elif cloud_ctx.private_ip:
        meta["host"] = cloud_ctx.private_ip

    # Inject structured cloud context into meta for investigation plugins
    merge_context_into_meta(meta, cloud_ctx)

    logger.info(
        "site24x7_cloud_context",
        cloud=cloud_ctx.cloud,
        tenant_tag=cloud_ctx.tenant,
        private_ip=cloud_ctx.private_ip,
        instance_id=cloud_ctx.instance_id,
        zone=cloud_ctx.zone,
        region=cloud_ctx.region,
        has_target=cloud_ctx.has_target,
    )

    # Host key links related incidents (same server: CPU + memory alerts)
    host_key = (
        meta.get("_private_ip")
        or meta.get("_instance_id")
        or meta.get("host")
        or None
    )
    if host_key and not isinstance(host_key, str):
        host_key = str(host_key)
    if host_key and len(host_key) > 512:
        host_key = host_key[:512]

    # Create incident
    title = f"[{status_str.upper()}] {monitor_name}"
    if incident_reason:
        title += f" — {incident_reason[:100]}"

    incident = Incident(
        tenant_id=tenant_id,
        alert_type=alert_type,
        severity=severity,
        title=title,
        meta=meta,
        host_key=host_key or None,
    )
    session.add(incident)
    await session.flush()

    await transition_state(
        session, incident, IncidentState.INVESTIGATING,
        reason=f"Site24x7 webhook: {monitor_name} - {status_str}",
        actor="site24x7_webhook",
    )

    # Cache idempotency key (TTL = 10 minutes)
    await redis.set(
        f"idem:{tenant_id}:{idem_key}",
        str(incident.id),
        ex=600,
    )

    # Metrics + SSE
    incident_created_total.labels(
        tenant_id=str(tenant_id),
        severity=severity.value,
        alert_type=alert_type,
    ).inc()

    try:
        await emit_incident_created(
            tenant_id=str(tenant_id),
            incident_id=str(incident.id),
            title=incident.title,
            state=incident.state.value,
            severity=severity.value,
            alert_type=alert_type,
        )
    except Exception:
        pass

    logger.info(
        "site24x7_incident_created",
        tenant_id=str(tenant_id),
        incident_id=str(incident.id),
        alert_type=alert_type,
        severity=severity.value,
        monitor_name=monitor_name,
        monitor_type=monitor_type,
    )

    # Enqueue async investigation task via ARQ worker
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        from app.core.config import settings as app_settings

        pool = await create_pool(RedisSettings.from_dsn(app_settings.REDIS_URL))
        await pool.enqueue_job(
            "investigate_incident",
            str(tenant_id),
            str(incident.id),
        )
        await pool.aclose()
        logger.info("investigation_task_enqueued", incident_id=str(incident.id))
    except Exception as exc:
        logger.error("investigation_enqueue_failed", error=str(exc))

    return IncidentCreatedResponse(incident_id=incident.id)


@router.post(
    "/generic",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IncidentCreatedResponse,
    dependencies=[Depends(webhook_rate_limit), Depends(verify_webhook_signature)],
)
async def ingest_generic(
    payload: GenericWebhookPayload,
    tenant_id: TenantId,
    session: TenantSession,
    redis: Redis,
) -> IncidentCreatedResponse:
    """Ingest a generic alert webhook."""
    severity = SEVERITY_MAP.get(payload.severity.lower(), SeverityLevel.MEDIUM)

    idem_key = _generate_idempotency_key(
        payload.alert_type, payload.resource_id, _time_window()
    )
    existing = await redis.get(f"idem:{tenant_id}:{idem_key}")
    if existing:
        return IncidentCreatedResponse(
            incident_id=existing.decode() if isinstance(existing, bytes) else existing
        )

    meta = payload.meta or {}
    host_key = (
        meta.get("_private_ip")
        or meta.get("_instance_id")
        or meta.get("host")
        or None
    )
    if host_key and not isinstance(host_key, str):
        host_key = str(host_key)
    if host_key and len(host_key) > 512:
        host_key = host_key[:512]

    incident = Incident(
        tenant_id=tenant_id,
        alert_type=payload.alert_type,
        severity=severity,
        title=payload.title,
        meta=meta,
        host_key=host_key or None,
    )
    session.add(incident)
    await session.flush()

    await transition_state(
        session, incident, IncidentState.INVESTIGATING,
        reason=f"Generic webhook: {payload.title}",
        actor="webhook_ingestion",
    )

    await redis.set(f"idem:{tenant_id}:{idem_key}", str(incident.id), ex=600)

    incident_created_total.labels(
        tenant_id=str(tenant_id),
        severity=severity.value,
        alert_type=payload.alert_type,
    ).inc()

    try:
        await emit_incident_created(
            tenant_id=str(tenant_id),
            incident_id=str(incident.id),
            title=incident.title,
            state=incident.state.value,
            severity=severity.value,
            alert_type=payload.alert_type,
        )
    except Exception:
        pass

    logger.info(
        "incident_created",
        tenant_id=str(tenant_id),
        incident_id=str(incident.id),
        alert_type=payload.alert_type,
    )

    # Enqueue async investigation task via ARQ worker
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        from app.core.config import settings as app_settings

        pool = await create_pool(RedisSettings.from_dsn(app_settings.REDIS_URL))
        await pool.enqueue_job(
            "investigate_incident",
            str(tenant_id),
            str(incident.id),
        )
        await pool.aclose()
        logger.info("investigation_task_enqueued", incident_id=str(incident.id))
    except Exception as exc:
        logger.error("investigation_enqueue_failed", error=str(exc))

    return IncidentCreatedResponse(incident_id=incident.id)
