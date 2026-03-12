"""
API endpoints for root cause correlation analysis.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query

from app.api.dependencies import CurrentUser, TenantId, TenantSession, require_permission
from airex_core.core.rbac import Permission
from airex_core.services.root_cause_correlation_service import (
    find_common_root_causes,
    get_root_cause_graph,
)

logger = structlog.get_logger()
router = APIRouter()


@router.get("/common")
async def list_common_root_causes(
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    days: int = Query(90, ge=7, le=365),
    min_occurrences: int = Query(2, ge=1, le=100),
    _perm: None = Depends(require_permission(Permission.INCIDENT_VIEW)),
):
    """Find common root causes across incident types."""
    causes = await find_common_root_causes(
        session, tenant_id, days=days, min_occurrences=min_occurrences
    )
    return {"root_causes": causes, "total": len(causes)}


@router.get("/graph")
async def get_root_cause_dependency_graph(
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    days: int = Query(90, ge=7, le=365),
    _perm: None = Depends(require_permission(Permission.INCIDENT_VIEW)),
):
    """Get root cause dependency graph for visualization."""
    return await get_root_cause_graph(session, tenant_id, days=days)
