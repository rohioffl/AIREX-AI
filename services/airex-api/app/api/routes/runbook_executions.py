"""
Runbook execution tracking endpoints.

Exposes per-execution and per-step state management:
  GET  /runbook-executions/{id}
  POST /runbook-executions/{id}/steps/{order}/complete
  POST /runbook-executions/{id}/steps/{order}/skip
  POST /runbook-executions/{id}/abandon
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUser, TenantId, TenantSession, require_permission
from airex_core.core.rbac import Permission
from airex_core.models.runbook_execution import RunbookExecution, RunbookStepExecution

logger = structlog.get_logger()
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────


class StepActionRequest(BaseModel):
    notes: str | None = None
    output: dict[str, Any] | None = None


class StepExecutionResponse(BaseModel):
    id: str
    execution_id: str
    step_order: int
    step_title: str | None
    step_action_type: str | None
    status: str
    actor_id: str | None
    notes: str | None
    output: dict[str, Any] | None
    started_at: str | None
    completed_at: str | None


class ExecutionResponse(BaseModel):
    id: str
    tenant_id: str
    runbook_id: str
    runbook_version: int
    runbook_steps_snapshot: list[dict[str, Any]]
    incident_id: str
    status: str
    started_by: str | None
    started_at: str
    completed_at: str | None
    steps: list[StepExecutionResponse]


def _step_to_response(step: RunbookStepExecution) -> StepExecutionResponse:
    return StepExecutionResponse(
        id=str(step.id),
        execution_id=str(step.execution_id),
        step_order=step.step_order,
        step_title=step.step_title,
        step_action_type=step.step_action_type,
        status=step.status,
        actor_id=str(step.actor_id) if step.actor_id else None,
        notes=step.notes,
        output=step.output,
        started_at=step.started_at.isoformat() if step.started_at else None,
        completed_at=step.completed_at.isoformat() if step.completed_at else None,
    )


def _exec_to_response(
    execution: RunbookExecution, steps: list[RunbookStepExecution]
) -> ExecutionResponse:
    snapshot = execution.runbook_steps_snapshot
    if not isinstance(snapshot, list):
        snapshot = []
    return ExecutionResponse(
        id=str(execution.id),
        tenant_id=str(execution.tenant_id),
        runbook_id=str(execution.runbook_id),
        runbook_version=execution.runbook_version,
        runbook_steps_snapshot=snapshot,
        incident_id=str(execution.incident_id),
        status=execution.status,
        started_by=str(execution.started_by) if execution.started_by else None,
        started_at=execution.started_at.isoformat() if execution.started_at else "",
        completed_at=execution.completed_at.isoformat() if execution.completed_at else None,
        steps=[_step_to_response(s) for s in sorted(steps, key=lambda x: x.step_order)],
    )


async def _load_execution(
    execution_id: uuid.UUID,
    tenant_id: uuid.UUID,
    session: AsyncSession,
) -> RunbookExecution:
    result = await session.execute(
        select(RunbookExecution).where(
            RunbookExecution.tenant_id == tenant_id,
            RunbookExecution.id == execution_id,
        )
    )
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    return execution


async def _load_steps(
    execution_id: uuid.UUID,
    tenant_id: uuid.UUID,
    session: AsyncSession,
) -> list[RunbookStepExecution]:
    result = await session.execute(
        select(RunbookStepExecution).where(
            RunbookStepExecution.tenant_id == tenant_id,
            RunbookStepExecution.execution_id == execution_id,
        )
    )
    return list(result.scalars().all())


async def _maybe_complete_execution(
    execution: RunbookExecution,
    steps: list[RunbookStepExecution],
    session: AsyncSession,
) -> None:
    """Auto-complete the execution when all steps are completed or skipped."""
    if all(s.status in ("completed", "skipped") for s in steps):
        execution.status = "completed"
        execution.completed_at = datetime.now(timezone.utc)
        logger.info(
            "runbook_execution_auto_completed",
            execution_id=str(execution.id),
            tenant_id=str(execution.tenant_id),
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/{execution_id}")
async def get_execution(
    execution_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    _perm: None = Depends(require_permission(Permission.INCIDENT_VIEW)),
) -> ExecutionResponse:
    """Get a runbook execution with all step statuses."""
    execution = await _load_execution(execution_id, tenant_id, session)
    steps = await _load_steps(execution_id, tenant_id, session)
    return _exec_to_response(execution, steps)


@router.post("/{execution_id}/steps/{step_order}/complete")
async def complete_step(
    execution_id: uuid.UUID,
    step_order: int,
    body: StepActionRequest,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    _perm: None = Depends(require_permission(Permission.INCIDENT_APPROVE)),
) -> ExecutionResponse:
    """Mark a step as completed."""
    execution = await _load_execution(execution_id, tenant_id, session)
    if execution.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Execution is {execution.status}, not in_progress",
        )

    steps = await _load_steps(execution_id, tenant_id, session)
    step = next((s for s in steps if s.step_order == step_order), None)
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found")
    if step.status not in ("pending", "in_progress"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Step is already {step.status}",
        )

    now = datetime.now(timezone.utc)
    step.status = "completed"
    step.actor_id = current_user.user_id if current_user else None
    step.notes = body.notes
    step.output = body.output
    if not step.started_at:
        step.started_at = now
    step.completed_at = now

    await _maybe_complete_execution(execution, steps, session)

    logger.info(
        "runbook_step_completed",
        execution_id=str(execution_id),
        step_order=step_order,
        tenant_id=str(tenant_id),
    )
    return _exec_to_response(execution, steps)


@router.post("/{execution_id}/steps/{step_order}/skip")
async def skip_step(
    execution_id: uuid.UUID,
    step_order: int,
    body: StepActionRequest,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    _perm: None = Depends(require_permission(Permission.INCIDENT_APPROVE)),
) -> ExecutionResponse:
    """Mark a step as skipped."""
    execution = await _load_execution(execution_id, tenant_id, session)
    if execution.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Execution is {execution.status}, not in_progress",
        )

    steps = await _load_steps(execution_id, tenant_id, session)
    step = next((s for s in steps if s.step_order == step_order), None)
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found")
    if step.status not in ("pending", "in_progress"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Step is already {step.status}",
        )

    step.status = "skipped"
    step.actor_id = current_user.user_id if current_user else None
    step.notes = body.notes
    step.completed_at = datetime.now(timezone.utc)

    await _maybe_complete_execution(execution, steps, session)

    logger.info(
        "runbook_step_skipped",
        execution_id=str(execution_id),
        step_order=step_order,
        tenant_id=str(tenant_id),
    )
    return _exec_to_response(execution, steps)


@router.post("/{execution_id}/abandon")
async def abandon_execution(
    execution_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    _perm: None = Depends(require_permission(Permission.INCIDENT_APPROVE)),
) -> ExecutionResponse:
    """Abandon a running execution."""
    execution = await _load_execution(execution_id, tenant_id, session)
    if execution.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Execution is {execution.status}, not in_progress",
        )

    execution.status = "abandoned"
    execution.completed_at = datetime.now(timezone.utc)

    steps = await _load_steps(execution_id, tenant_id, session)

    logger.info(
        "runbook_execution_abandoned",
        execution_id=str(execution_id),
        tenant_id=str(tenant_id),
    )
    return _exec_to_response(execution, steps)
