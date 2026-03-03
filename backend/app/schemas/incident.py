import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ExecutionStatus, IncidentState, RiskLevel, SeverityLevel


# --- Response sub-models ---


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tool_name: str
    raw_output: str
    timestamp: datetime


class StateTransitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_state: IncidentState
    to_state: IncidentState
    reason: str | None
    actor: str
    created_at: datetime


class ExecutionResponse(BaseModel):
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
    root_cause: str
    proposed_action: str
    risk_level: RiskLevel
    confidence: float


# --- Incident list / detail ---


class IncidentListItem(BaseModel):
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
    meta: dict | None = None
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
    host_keys: list[str] = []
    states: dict[str, int] = {}
    severities: dict[str, int] = {}
    first_seen: str | None = None
    last_seen: str | None = None
    span_seconds: int = 0


class IncidentDetail(IncidentListItem):
    evidence: list[EvidenceResponse] = []
    state_transitions: list[StateTransitionResponse] = []
    executions: list[ExecutionResponse] = []
    recommendation: RecommendationResponse | None = None
    related_incidents: list[RelatedIncidentItem] = []
    rag_context: str | None = None
    host_key: str | None = None
    # Correlation grouping
    correlation_group_id: str | None = None
    correlated_incidents: list[CorrelatedIncidentItem] = []
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
    action: str
    idempotency_key: str


class RejectRequest(BaseModel):
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Operator-provided note explaining why the incident was rejected",
    )


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
    incident_id: uuid.UUID
    feedback_score: int
    feedback_note: str | None = None


# --- Minimal creation response ---


class IncidentCreatedResponse(BaseModel):
    incident_id: uuid.UUID


class PaginatedIncidents(BaseModel):
    """Cursor-based paginated response."""

    items: list[IncidentListItem]
    next_cursor: str | None = None
    has_more: bool = False
    total: int | None = None
