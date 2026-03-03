"""
Webhook ingestion endpoints.

Receives external alerts, deduplicates via idempotency key,
creates incidents, and queues async investigation.
"""

import asyncio
import hashlib
import json as _json
import re
import uuid
from datetime import datetime, timedelta, timezone

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
from app.cloud.tag_parser import (
    parse_tags,
    merge_context_into_meta,
    discover_and_enrich,
)

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

logger = structlog.get_logger()

router = APIRouter()

# ── Repeated alert handling ───────────────────────────────────
# Keep the 5-minute idempotency bucket, but instead of skipping duplicates,
# enrich the existing incident with alert_count/last_seen/metrics.
_IDEM_TTL_SECONDS = 600
_COOLDOWN_SILENCE_SECONDS = 30 * 60

# Track last few UP/DOWN states to detect flapping.
_FLAP_HISTORY_SIZE = 5
_FLAP_TTL_SECONDS = 60 * 60

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

GENERIC_MONITOR_TYPES = {
    "healthcheck",
    "http_check",
    "heartbeat_check",
    "network_issue",
    "cloud_check",
    "api_check",
}

_KEYWORD_ALERT_OVERRIDES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(cpu|processor|load average|load)\b", re.IGNORECASE), "cpu_high"),
    (re.compile(r"\b(memory|ram|oom)\b", re.IGNORECASE), "memory_high"),
    (re.compile(r"\b(disk|filesystem|storage|inode)\b", re.IGNORECASE), "disk_full"),
    (
        re.compile(r"\b(latency|packet|ping|network|throughput)\b", re.IGNORECASE),
        "network_check",
    ),
]


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


def _refine_alert_type(
    base_type: str,
    monitor_type: str,
    incident_reason: str | None,
    cloud_ctx,
) -> tuple[str, dict | None]:
    """Use heuristics (reason text, tags) to override generic alert types."""
    override_info = None
    if base_type not in GENERIC_MONITOR_TYPES:
        return base_type, override_info

    text_blobs = [monitor_type or "", incident_reason or ""]
    if getattr(cloud_ctx, "extra_tags", None):
        text_blobs.extend(
            f"{k}:{v}" if v else k for k, v in cloud_ctx.extra_tags.items()
        )
    haystack = " ".join(text_blobs).lower()

    for pattern, mapped_type in _KEYWORD_ALERT_OVERRIDES:
        if pattern.search(haystack):
            override_info = {
                "from": base_type,
                "match": pattern.pattern,
                "source": "keywords",
            }
            return mapped_type, override_info

    return base_type, override_info


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().isoformat()


def _parse_iso_dt(value: str) -> datetime | None:
    if not value:
        return None
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _is_flapping(last_states: list[str]) -> bool:
    if len(last_states) < _FLAP_HISTORY_SIZE:
        return False
    window = [s.upper() for s in last_states[-_FLAP_HISTORY_SIZE:]]
    return window == ["DOWN", "UP", "DOWN", "UP", "DOWN"]


async def _track_flap(
    redis, tenant_id: uuid.UUID, monitor_id: str, status_str: str
) -> dict:
    """Store status history in Redis and return flap summary."""
    key = f"flap:{tenant_id}:{monitor_id}"
    raw = await redis.get(key)
    history: list[dict] = []
    if raw:
        try:
            decoded = raw.decode() if isinstance(raw, (bytes, bytearray)) else raw
            history = _json.loads(decoded) or []
        except Exception:
            history = []

    history.append({"s": status_str.upper(), "t": _utcnow_iso()})
    if len(history) > _FLAP_HISTORY_SIZE:
        history = history[-_FLAP_HISTORY_SIZE:]

    await redis.set(key, _json.dumps(history), ex=_FLAP_TTL_SECONDS)
    last_states = [h.get("s", "") for h in history if isinstance(h, dict)]
    return {
        "last_states": last_states,
        "transition_count": len(last_states),
        "is_flapping": _is_flapping(last_states),
    }


def _extract_metric_sample(
    alert_type: str, incident_reason: str | None
) -> tuple[str, float] | None:
    """Best-effort numeric extraction from Site24x7 incident_reason."""
    if not incident_reason:
        return None

    percents = [
        float(x) for x in re.findall(r"(\d{1,3}(?:\.\d+)?)\s*%", incident_reason)
    ]
    if not percents:
        return None

    sample = max(percents)
    if alert_type == "cpu_high":
        return ("cpu_percent", sample)
    if alert_type in {"memory_high"}:
        return ("memory_percent", sample)
    if alert_type in {"disk_full"}:
        return ("disk_percent", sample)
    return ("percent", sample)


def _enrich_meta_for_repeat(
    meta: dict | None,
    *,
    status_str: str,
    flap: dict,
    alert_type: str,
    incident_reason: str | None,
) -> dict:
    now = _utcnow()
    m: dict = dict(meta) if meta else {}

    first_seen = _parse_iso_dt(str(m.get("_alert_first_seen_at", "")))
    if not first_seen:
        first_seen = now
        m["_alert_first_seen_at"] = first_seen.isoformat()

    m["_alert_last_seen_at"] = now.isoformat()
    m["_alert_last_status"] = status_str.upper()

    try:
        m["_alert_count"] = int(m.get("_alert_count", 0)) + 1
    except Exception:
        m["_alert_count"] = 1

    m["_alert_duration_seconds"] = int((now - first_seen).total_seconds())

    # Flap metadata (does NOT change incident.state)
    m["_flap_last_5_states"] = flap.get("last_states", [])
    m["_flap_transition_count"] = int(flap.get("transition_count", 0) or 0)
    m["_unstable"] = bool(flap.get("is_flapping"))

    # Metric enrichment (optional)
    sample = _extract_metric_sample(alert_type, incident_reason)
    if sample:
        metric_name, value = sample
        stats = m.setdefault("_alert_stats", {})
        ms = stats.setdefault(metric_name, {"count": 0, "sum": 0.0, "peak": None})
        ms["count"] = int(ms.get("count", 0)) + 1
        ms["sum"] = float(ms.get("sum", 0.0)) + float(value)
        prev_peak = ms.get("peak")
        if prev_peak is None or float(value) > float(prev_peak):
            ms["peak"] = float(value)
        ms["avg"] = float(ms["sum"]) / float(ms["count"])

    return m


def _is_stale_for_cooldown(incident: Incident) -> bool:
    now = _utcnow()
    meta = incident.meta or {}
    last_seen = _parse_iso_dt(str(meta.get("_alert_last_seen_at", "")))
    if not last_seen:
        last_seen = incident.updated_at or incident.created_at
    return (now - last_seen) > timedelta(seconds=_COOLDOWN_SILENCE_SECONDS)


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

    Tenant identification (priority order):
      1. JWT Bearer token with tenant_id claim
      2. X-Tenant-Id HTTP header (UUID)
      3. DEV_TENANT_ID fallback (single-tenant mode)

    Configure in Site24x7:
      Admin → IT Automation → Webhooks
      URL: https://<your-domain>/api/v1/webhooks/site24x7
      Method: POST
      Tags: optional (no tenant tag required in single-tenant mode)
    """
    payload = await _parse_site24x7_payload(request)
    monitor_name = payload.get_monitor_name()
    status_str = payload.get_status()
    monitor_type = payload.get_monitor_type()
    monitor_id = payload.get_monitor_id()
    incident_reason = payload.get_incident_reason()

    # ── Parse cloud tags early to resolve tenant_id ──────────────
    # Site24x7 sends TAGS as either a comma-string or a JSON array.
    # Parsing before UP/idempotency/active-incident checks ensures
    # all DB operations use the correct tenant_id (not DEV_TENANT_ID).
    raw_tags = payload.TAGS or payload.MONITOR_TAGS or ""
    if isinstance(raw_tags, list):
        raw_tags = ",".join(str(t) for t in raw_tags)
    cloud_ctx = parse_tags(raw_tags)

    # Track status history for flapping detection (UP and DOWN)
    flap = await _track_flap(
        redis, tenant_id=tenant_id, monitor_id=monitor_id, status_str=status_str
    )

    # Skip "UP" status alerts — these are recovery notifications
    if status_str.lower() == "up":
        logger.info(
            "site24x7_recovery_received",
            tenant_id=str(tenant_id),
            monitor_name=monitor_name,
        )
        # Find active incident for this monitor and resolve it
        result = await session.execute(
            select(Incident)
            .where(
                Incident.tenant_id == tenant_id,
                Incident.state.notin_(
                    [
                        IncidentState.RESOLVED,
                    ]
                ),
                Incident.deleted_at.is_(None),
            )
            .order_by(Incident.created_at.desc())
            .limit(1)
        )
        active = result.scalar_one_or_none()
        if active:
            try:
                active.meta = _enrich_meta_for_repeat(
                    active.meta,
                    status_str=status_str,
                    flap=flap,
                    alert_type=_map_site24x7_alert_type(monitor_type),
                    incident_reason=incident_reason,
                )
                flag_modified(active, "meta")
                session.add(active)
                await transition_state(
                    session,
                    active,
                    IncidentState.RESOLVED,
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
    alert_type, override_info = _refine_alert_type(
        alert_type, monitor_type, incident_reason, cloud_ctx
    )
    if override_info:
        logger.info(
            "alert_type_overridden",
            original_alert_type=override_info["from"],
            new_alert_type=alert_type,
            monitor_type=monitor_type,
            incident_reason=incident_reason,
        )
    severity = SEVERITY_MAP.get(status_str.lower(), SeverityLevel.MEDIUM)

    # Idempotency: reject duplicate alerts within same 5-min window
    idem_key = _generate_idempotency_key(alert_type, monitor_id, _time_window())
    existing = await redis.get(f"idem:{tenant_id}:{idem_key}")
    if existing:
        decoded = (
            existing.decode()
            if isinstance(existing, (bytes, bytearray))
            else str(existing)
        )
        try:
            existing_id = uuid.UUID(decoded)
        except ValueError:
            logger.info(
                "duplicate_webhook_rejected",
                tenant_id=str(tenant_id),
                idempotency_key=idem_key,
            )
            raise HTTPException(
                status_code=500, detail="Invalid idempotency incident id"
            )

        # Enrich the existing incident instead of skipping.
        try:
            result = await session.execute(
                select(Incident).where(
                    Incident.tenant_id == tenant_id,
                    Incident.id == existing_id,
                    Incident.deleted_at.is_(None),
                )
            )
            dup_incident = result.scalar_one_or_none()
            if dup_incident:
                dup_incident.meta = _enrich_meta_for_repeat(
                    dup_incident.meta,
                    status_str=status_str,
                    flap=flap,
                    alert_type=alert_type,
                    incident_reason=incident_reason,
                )
                flag_modified(dup_incident, "meta")
                session.add(dup_incident)
                await session.flush()
        except Exception:
            logger.warning(
                "enrichment_flush_failed", incident_id=str(existing_id), exc_info=True
            )

        # Refresh TTL so rapid repeats keep enriching the same incident.
        await redis.set(
            f"idem:{tenant_id}:{idem_key}", str(existing_id), ex=_IDEM_TTL_SECONDS
        )
        logger.info(
            "duplicate_webhook_enriched",
            tenant_id=str(tenant_id),
            incident_id=str(existing_id),
            idempotency_key=idem_key,
        )
        return IncidentCreatedResponse(incident_id=existing_id)

    # Check for active incident on same monitor AND same host.
    # Without host filtering, different servers with the same alert_type
    # (e.g. two servers both with cpu_high) would collapse into one incident.
    _candidate_host_key = monitor_name or monitor_id
    _host_filter = (
        Incident.host_key == _candidate_host_key
        if _candidate_host_key
        else Incident.host_key.is_(None)
    )
    result = await session.execute(
        select(Incident)
        .where(
            Incident.tenant_id == tenant_id,
            Incident.alert_type == alert_type,
            _host_filter,
            Incident.state.notin_(
                [
                    IncidentState.RESOLVED,
                    IncidentState.FAILED_ANALYSIS,
                    IncidentState.FAILED_EXECUTION,
                    IncidentState.FAILED_VERIFICATION,
                ]
            ),
            Incident.deleted_at.is_(None),
        )
        .order_by(Incident.created_at.desc())
        .limit(1)
    )
    active = result.scalar_one_or_none()
    if active:
        # Cooldown window: if the incident has been silent long enough,
        # treat this as a new occurrence instead of keeping one incident open forever.
        if not _is_stale_for_cooldown(active):
            active.meta = _enrich_meta_for_repeat(
                active.meta,
                status_str=status_str,
                flap=flap,
                alert_type=alert_type,
                incident_reason=incident_reason,
            )
            flag_modified(active, "meta")
            session.add(active)
            await session.flush()
            logger.info(
                "active_incident_enriched",
                tenant_id=str(tenant_id),
                incident_id=str(active.id),
            )
            return IncidentCreatedResponse(incident_id=active.id)

        try:
            cooldown_meta = dict(active.meta) if active.meta else {}
            cooldown_meta["_cooldown_stale"] = True
            cooldown_meta["_cooldown_last_seen_at"] = str(
                cooldown_meta.get("_alert_last_seen_at") or ""
            )
            active.meta = cooldown_meta
            flag_modified(active, "meta")
            session.add(active)
            await session.flush()
        except Exception:
            logger.warning(
                "cooldown_meta_flush_failed", incident_id=str(active.id), exc_info=True
            )

    # Build rich meta from Site24x7 payload
    meta = payload.model_dump(exclude_none=True)
    meta["_source"] = "site24x7"
    meta["monitor_name"] = monitor_name
    meta["host"] = monitor_name
    meta["_source_monitor_type"] = monitor_type
    if override_info:
        meta["_alert_type_override"] = override_info

    # Initialize repeated-alert tracking fields for the new incident
    meta = _enrich_meta_for_repeat(
        meta,
        status_str=status_str,
        flap=flap,
        alert_type=alert_type,
        incident_reason=incident_reason,
    )

    # cloud_ctx and raw_tags already parsed above (before UP check)

    # Auto-fill IP from payload fields if not in tags
    if not cloud_ctx.private_ip:
        payload_ip = payload.get_ip_address()
        if payload_ip:
            cloud_ctx.private_ip = payload_ip
            logger.info("ip_extracted_from_payload", ip=payload_ip)

    # Auto-discover instance details (zone, name, region) from cloud APIs
    # Uses the private IP from tags + project from tenant config
    # Timeout after 3s to avoid blocking the webhook response on slow region scans
    try:
        async with asyncio.timeout(3):
            cloud_ctx = await discover_and_enrich(cloud_ctx, redis=redis)
    except (TimeoutError, Exception) as exc:
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
        meta.get("_private_ip") or meta.get("_instance_id") or meta.get("host") or None
    )
    if host_key and not isinstance(host_key, str):
        host_key = str(host_key)
    if host_key and len(host_key) > 512:
        host_key = host_key[:512]

    # Check tenant limits before creating incident
    from app.core.tenant_limits import check_concurrent_incidents

    allowed, current, max_allowed = await check_concurrent_incidents(session, tenant_id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Tenant limit exceeded: {current}/{max_allowed} concurrent incidents. Please resolve existing incidents or contact support.",
        )

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
        session,
        incident,
        IncidentState.INVESTIGATING,
        reason=f"Site24x7 webhook: {monitor_name} - {status_str}",
        actor="site24x7_webhook",
    )

    # Cache idempotency key (TTL = 10 minutes)
    await redis.set(
        f"idem:{tenant_id}:{idem_key}",
        str(incident.id),
        ex=_IDEM_TTL_SECONDS,
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

    # Cross-host correlation (Phase 4 ARE)
    try:
        from app.services.correlation_service import correlate_incident

        group_id = await correlate_incident(session, incident)
        if group_id:
            logger.info(
                "correlation_group_assigned",
                incident_id=str(incident.id),
                group_id=group_id,
            )
    except Exception as exc:
        logger.warning("correlation_failed", error=str(exc))

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
        decoded = (
            existing.decode()
            if isinstance(existing, (bytes, bytearray))
            else str(existing)
        )
        try:
            existing_id = uuid.UUID(decoded)
        except ValueError as exc:
            raise HTTPException(
                status_code=500, detail="Invalid idempotency incident id"
            ) from exc
        return IncidentCreatedResponse(incident_id=existing_id)

    meta = payload.meta or {}

    # Parse cloud tags from meta.TAGS (if present)
    raw_tags = meta.get("TAGS") or meta.get("tags") or ""
    if isinstance(raw_tags, list):
        raw_tags = ",".join(str(t) for t in raw_tags)
    cloud_ctx = parse_tags(str(raw_tags) if raw_tags else "")

    # Auto-fill IP from meta fields if not in tags
    if not cloud_ctx.private_ip:
        # Try common IP fields in meta
        for ip_field in ["ip", "ipaddress", "ip_address", "private_ip", "host"]:
            ip_value = meta.get(ip_field)
            if ip_value and isinstance(ip_value, str):
                # Check if it looks like an IP
                import re

                ip_re = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
                if ip_re.match(ip_value.strip()):
                    cloud_ctx.private_ip = ip_value.strip()
                    logger.info(
                        "ip_extracted_from_meta",
                        ip=cloud_ctx.private_ip,
                        field=ip_field,
                    )
                    break

    # Auto-discover instance details (zone, name, region) from cloud APIs
    # Timeout after 3s to avoid blocking the webhook response on slow region scans
    try:
        async with asyncio.timeout(3):
            cloud_ctx = await discover_and_enrich(cloud_ctx, redis=redis)
    except (TimeoutError, Exception) as exc:
        logger.warning("auto_discovery_skipped", error=str(exc))

    # Override host with instance/IP from tags if available
    if cloud_ctx.instance_id:
        meta["host"] = cloud_ctx.instance_id
    elif cloud_ctx.private_ip and not meta.get("host"):
        meta["host"] = cloud_ctx.private_ip

    # Inject structured cloud context into meta for investigation plugins
    merge_context_into_meta(meta, cloud_ctx)

    logger.info(
        "generic_webhook_cloud_context",
        cloud=cloud_ctx.cloud,
        tenant_tag=cloud_ctx.tenant,
        private_ip=cloud_ctx.private_ip,
        instance_id=cloud_ctx.instance_id,
        zone=cloud_ctx.zone,
        region=cloud_ctx.region,
        has_target=cloud_ctx.has_target,
    )

    host_key = (
        meta.get("_private_ip") or meta.get("_instance_id") or meta.get("host") or None
    )
    if host_key and not isinstance(host_key, str):
        host_key = str(host_key)
    if host_key and len(host_key) > 512:
        host_key = host_key[:512]

    # Check tenant limits before creating incident
    from app.core.tenant_limits import check_concurrent_incidents

    allowed, current, max_allowed = await check_concurrent_incidents(session, tenant_id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Tenant limit exceeded: {current}/{max_allowed} concurrent incidents. Please resolve existing incidents or contact support.",
        )

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
        session,
        incident,
        IncidentState.INVESTIGATING,
        reason=f"Generic webhook: {payload.title}",
        actor="webhook_ingestion",
    )

    await redis.set(
        f"idem:{tenant_id}:{idem_key}", str(incident.id), ex=_IDEM_TTL_SECONDS
    )

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

    # Cross-host correlation (Phase 4 ARE)
    try:
        from app.services.correlation_service import correlate_incident

        group_id = await correlate_incident(session, incident)
        if group_id:
            logger.info(
                "correlation_group_assigned",
                incident_id=str(incident.id),
                group_id=group_id,
            )
    except Exception as exc:
        logger.warning("correlation_failed", error=str(exc))

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
