"""
API endpoints for anomaly detection.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query

from app.api.dependencies import CurrentUser, TenantId, TenantSession, require_permission
from airex_core.core.rbac import Permission
from airex_core.services.anomaly_detection_service import detect_anomalies

logger = structlog.get_logger()
router = APIRouter()


@router.get("/")
async def list_anomalies(
    tenant_id: TenantId,
    session: TenantSession,
    baseline_days: int = Query(30, ge=7, le=365),
    detection_window_hours: int = Query(24, ge=1, le=168),
    current_user: CurrentUser = Depends(require_permission(Permission.INCIDENT_VIEW)),
):
    """Detect anomalies in incident patterns."""
    return await detect_anomalies(
        session,
        tenant_id,
        baseline_days=baseline_days,
        detection_window_hours=detection_window_hours,
    )
