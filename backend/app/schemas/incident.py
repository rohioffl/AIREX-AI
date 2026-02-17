import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

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


class RelatedIncidentItem(BaseModel):
    """Minimal incident info for same-host linking."""
    id: uuid.UUID
    alert_type: str
    state: IncidentState
    severity: SeverityLevel
    title: str
    created_at: datetime


class IncidentDetail(IncidentListItem):
    evidence: list[EvidenceResponse] = []
    state_transitions: list[StateTransitionResponse] = []
    executions: list[ExecutionResponse] = []
    recommendation: RecommendationResponse | None = None
    meta: dict | None = None
    related_incidents: list[RelatedIncidentItem] = []


# --- Request models ---


class ApproveRequest(BaseModel):
    action: str
    idempotency_key: str


# --- Minimal creation response ---


class IncidentCreatedResponse(BaseModel):
    incident_id: uuid.UUID


class PaginatedIncidents(BaseModel):
    """Cursor-based paginated response."""
    items: list[IncidentListItem]
    next_cursor: str | None = None
    has_more: bool = False
    total: int | None = None
