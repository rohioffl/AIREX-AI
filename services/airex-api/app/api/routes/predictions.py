"""
API endpoints for predictive analytics.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import CurrentUser, TenantId, TenantSession, require_permission
from airex_core.core.rbac import Permission
from airex_core.services.predictive_analytics_service import (
    predict_root_cause,
    get_prediction_accuracy,
)

logger = structlog.get_logger()
router = APIRouter()


@router.get("/root-cause")
async def predict(
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    alert_type: str = Query(..., description="Alert type to predict for"),
    severity: str | None = Query(None),
    host_key: str | None = Query(None),
    _perm: None = Depends(require_permission(Permission.INCIDENT_VIEW)),
):
    """Predict likely root cause for a given alert type."""
    return await predict_root_cause(
        session,
        tenant_id,
        alert_type=alert_type,
        severity=severity,
        host_key=host_key,
    )


@router.get("/accuracy")
async def prediction_accuracy(
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    days: int = Query(30, ge=1, le=365),
    _perm: None = Depends(require_permission(Permission.INCIDENT_VIEW)),
):
    """Get prediction accuracy metrics."""
    return await get_prediction_accuracy(session, tenant_id, days=days)
