"""
API endpoints for incident pattern detection.
"""

from __future__ import annotations

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import CurrentUser, TenantId, TenantSession, require_permission
from airex_core.core.rbac import Permission
from airex_core.services.pattern_detection_service import detect_patterns, get_pattern_summary

logger = structlog.get_logger()
router = APIRouter()


@router.get("/")
async def list_patterns(
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    _perm: None = Depends(require_permission(Permission.INCIDENT_VIEW)),
    window_days: int = Query(30, ge=1, le=365),
):
    """Detect and return incident patterns."""
    patterns = await detect_patterns(session, tenant_id, window_days=window_days)
    return {"patterns": patterns, "total": len(patterns)}


@router.get("/{pattern_id}")
async def get_pattern(
    pattern_id: str,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    _perm: None = Depends(require_permission(Permission.INCIDENT_VIEW)),
):
    """Get detailed pattern summary."""
    summary = await get_pattern_summary(session, tenant_id, pattern_id)
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pattern not found",
        )
    return summary
