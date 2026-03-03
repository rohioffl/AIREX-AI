"""Pydantic schemas for health check API (Phase 6 ARE — Proactive Monitoring)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HealthCheckResponse(BaseModel):
    """Single health check result."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    target_type: str
    target_id: str
    target_name: str
    status: str
    metrics: dict | None = None
    anomalies: list | None = None
    incident_created: bool = False
    incident_id: uuid.UUID | None = None
    checked_at: datetime
    duration_ms: float | None = None
    error: str | None = None


class HealthCheckSummary(BaseModel):
    """Aggregated health check dashboard summary."""

    total_targets: int = 0
    healthy: int = 0
    degraded: int = 0
    down: int = 0
    unknown: int = 0
    error: int = 0
    last_run_at: datetime | None = None
    incidents_created_24h: int = 0


class TargetStatus(BaseModel):
    """Latest status for a single monitored target."""

    target_type: str
    target_id: str
    target_name: str
    status: str
    last_checked: datetime | None = None
    anomaly_count: int = 0
    latest_metrics: dict | None = None
    incident_id: uuid.UUID | None = None


class HealthCheckListResponse(BaseModel):
    """Paginated health check results."""

    items: list[HealthCheckResponse] = Field(default_factory=list)
    total: int = 0
    has_more: bool = False


class HealthCheckDashboard(BaseModel):
    """Full dashboard payload: summary + per-target status."""

    summary: HealthCheckSummary
    targets: list[TargetStatus] = Field(default_factory=list)
    recent_checks: list[HealthCheckResponse] = Field(default_factory=list)
