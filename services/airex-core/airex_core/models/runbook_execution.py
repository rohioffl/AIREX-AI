"""Runbook execution models: version snapshots, executions, and step executions."""

import uuid
from datetime import datetime

from sqlalchemy import Integer, PrimaryKeyConstraint, String, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from airex_core.models.base import Base, TenantMixin


class RunbookVersion(Base, TenantMixin):
    """Immutable snapshot of runbook steps taken before each update.

    No FK to runbooks — survives runbook deletion for audit continuity.
    """

    __tablename__ = "runbook_versions"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "id"),
    )

    runbook_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    steps: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    def __repr__(self) -> str:
        return (
            f"RunbookVersion(tenant_id={self.tenant_id!s}, "
            f"runbook_id={self.runbook_id!s}, version={self.version})"
        )


class RunbookExecution(Base, TenantMixin):
    """Tracks the execution of a runbook against a specific incident."""

    __tablename__ = "runbook_executions"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "id"),
    )

    runbook_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    runbook_version: Mapped[int] = mapped_column(Integer, nullable=False)
    runbook_steps_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="in_progress"
    )  # in_progress | completed | abandoned
    started_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"RunbookExecution(tenant_id={self.tenant_id!s}, "
            f"id={self.id!s}, incident_id={self.incident_id!s}, status={self.status!r})"
        )


class RunbookStepExecution(Base, TenantMixin):
    """Tracks the execution status of a single step within a RunbookExecution."""

    __tablename__ = "runbook_step_executions"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "id"),
    )

    execution_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    step_action_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending | in_progress | completed | skipped | failed
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"RunbookStepExecution(tenant_id={self.tenant_id!s}, "
            f"id={self.id!s}, execution_id={self.execution_id!s}, "
            f"step_order={self.step_order}, status={self.status!r})"
        )
