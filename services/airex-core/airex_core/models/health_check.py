"""Health check result model (Phase 6 ARE — Proactive Monitoring)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Float, Index, PrimaryKeyConstraint, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from airex_core.models.base import Base, TenantMixin


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HealthCheckStatus:
    """Health check result status constants."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"
    ERROR = "error"


class TargetType:
    """Health check target type constants."""

    SITE24X7 = "site24x7_monitor"
    CLOUD_INSTANCE = "cloud_instance"
    ENDPOINT = "endpoint"


class HealthCheck(Base, TenantMixin):
    """Stores a single health check probe result against known infrastructure."""

    __tablename__ = "health_checks"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "id"),
        Index(
            "idx_health_checks_tenant_checked",
            "tenant_id",
            text("checked_at DESC"),
        ),
        Index(
            "idx_health_checks_target",
            "tenant_id",
            "target_type",
            "target_id",
        ),
        Index(
            "idx_health_checks_anomalous",
            "tenant_id",
            text("checked_at DESC"),
            postgresql_where=text("status IN ('degraded', 'down')"),
        ),
    )

    # Target identification
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False)
    target_name: Mapped[str] = mapped_column(String(500), nullable=False)

    # Result
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=HealthCheckStatus.UNKNOWN
    )
    metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    anomalies: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Incident linkage
    incident_created: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )

    # Timing
    checked_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_utcnow
    )
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Error info
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            "HealthCheck("
            f"tenant_id={self.tenant_id!s}, "
            f"id={self.id!s}, "
            f"target_type={self.target_type!r}, "
            f"target_id={self.target_id!r}, "
            f"status={self.status!r}"
            ")"
        )
