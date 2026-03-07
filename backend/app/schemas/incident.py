"""Incident request/response schemas for API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ExecutionStatus, IncidentState, RiskLevel, SeverityLevel


# --- Response sub-models ---


class EvidenceResponse(BaseModel):
    """Evidence artifact collected during incident investigation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tool_name: str
    raw_output: str
    timestamp: datetime


class StateTransitionResponse(BaseModel):
    """Audit record of an incident state transition."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_state: IncidentState
    to_state: IncidentState
    reason: str | None
    actor: str
    created_at: datetime


class ExecutionResponse(BaseModel):
    """Execution attempt metadata for remediation actions."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action_type: str
    attempt: int
    status: ExecutionStatus
    logs: str | None
    started_at: datetime
    completed_at: datetime | None
    duration_seconds: float | None


class RecommendationResponse(BaseModel):
    """Normalized recommendation details returned in incident payloads."""

    root_cause: str
    proposed_action: str
    risk_level: RiskLevel
    confidence: float


# --- Incident list / detail ---


class IncidentListItem(BaseModel):
    """Compact incident representation used by list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    alert_type: str
    state: IncidentState
    severity: SeverityLevel
    title: str
    investigation_retry_count: int
    execution_retry_count: int
    verification_retry_count: int
    created_at: datetime
    updated_at: datetime
    meta: dict[str, Any] | None = None
    host_key: str | None = None
    correlation_group_id: str | None = None
    # Resolution tracking
    resolution_type: str | None = None
    resolution_duration_seconds: float | None = None
    feedback_score: int | None = None


class RelatedIncidentItem(BaseModel):
    """Minimal incident info for same-host linking."""

    id: uuid.UUID
    alert_type: str
    state: IncidentState
    severity: SeverityLevel
    title: str
    created_at: datetime


class CorrelatedIncidentItem(BaseModel):
    """Minimal incident info for cross-host correlation groups."""

    id: uuid.UUID
    alert_type: str
    state: IncidentState
    severity: SeverityLevel
    title: str
    host_key: str | None = None
    created_at: datetime


class CorrelationGroupSummary(BaseModel):
    """Summary of a cross-host correlation group."""

    group_id: str
    alert_type: str
    incident_count: int
    affected_hosts: int
    host_keys: list[str] = Field(default_factory=list)
    states: dict[str, int] = Field(default_factory=dict)
    severities: dict[str, int] = Field(default_factory=dict)
    first_seen: str | None = None
    last_seen: str | None = None
    span_seconds: int = 0


class IncidentDetail(IncidentListItem):
    """Expanded incident payload with linked investigation and resolution data."""

    evidence: list[EvidenceResponse] = Field(default_factory=list)
    state_transitions: list[StateTransitionResponse] = Field(default_factory=list)
    executions: list[ExecutionResponse] = Field(default_factory=list)
    recommendation: RecommendationResponse | None = None
    related_incidents: list[RelatedIncidentItem] = Field(default_factory=list)
    rag_context: str | None = None
    host_key: str | None = None
    # Correlation grouping
    correlation_group_id: str | None = None
    correlated_incidents: list[CorrelatedIncidentItem] = Field(default_factory=list)
    correlation_summary: CorrelationGroupSummary | None = None
    # Resolution tracking
    resolution_type: str | None = None
    resolution_summary: str | None = None
    resolution_duration_seconds: float | None = None
    feedback_score: int | None = None
    feedback_note: str | None = None
    resolved_at: datetime | None = None


# --- Request models ---


class ApproveRequest(BaseModel):
    """Operator approval payload to trigger deterministic execution."""

    action: str
    idempotency_key: str

    @field_validator("action", "idempotency_key", mode="before")
    @classmethod
    def normalize_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class RejectRequest(BaseModel):
    """Operator rejection payload for incidents requiring manual handling."""

    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Operator-provided note explaining why the incident was rejected",
    )

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> object:
        if isinstance(value, str):
            stripped_value = value.strip()
            return stripped_value or None
        return value


class FeedbackRequest(BaseModel):
    """Operator feedback on a resolved/rejected incident."""

    score: int = Field(
        ...,
        ge=-1,
        le=5,
        description="Rating: -1=harmful, 0=ineffective, 1-5 quality scale",
    )
    note: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional text feedback explaining the rating",
    )


class FeedbackResponse(BaseModel):
    """Server acknowledgment payload for stored incident feedback."""

    incident_id: uuid.UUID
    feedback_score: int
    feedback_note: str | None = None


# --- Minimal creation response ---


class IncidentCreatedResponse(BaseModel):
    """Minimal response returned immediately after incident creation."""

    incident_id: uuid.UUID


class PaginatedIncidents(BaseModel):
    """Cursor-based paginated response."""

    items: list[IncidentListItem]
    next_cursor: str | None = None
    has_more: bool = False
    total: int | None = None
