"""Internal tool server for AIREX forensic investigations."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_auth_session, require_internal_tool_access
from airex_core.investigations import INVESTIGATION_REGISTRY
from airex_core.investigations.base import ProbeResult
from airex_core.investigations.change_detection_probe import ChangeDetectionProbe
from airex_core.investigations.cloud_investigation import CloudInvestigation
from airex_core.investigations.infra_state_probe import InfraStateProbe
from airex_core.investigations.k8s_probe import K8sStatusProbe
from airex_core.investigations.log_analysis_probe import LogAnalysisProbe
from airex_core.models.incident import Incident
from airex_core.schemas.evidence import EvidenceContract
from airex_core.services.investigation_service import persist_investigation_evidence
from airex_core.services.rag_context import build_structured_context


router = APIRouter(dependencies=[Depends(require_internal_tool_access)])
logger = structlog.get_logger()


class InternalToolRequest(BaseModel):
    """Base request passed from external tool integrations into AIREX."""

    tenant_id: uuid.UUID
    incident_meta: dict[str, Any] = Field(default_factory=dict)

    def build_meta(self) -> dict[str, Any]:
        meta = dict(self.incident_meta)
        meta.setdefault("_tenant_id", str(self.tenant_id))
        return meta


class HostDiagnosticsRequest(InternalToolRequest):
    """Request payload for read-only host/cloud diagnostics."""

    alert_type: str
    cloud: str | None = None
    instance_id: str | None = None
    private_ip: str | None = None

    def build_meta(self) -> dict[str, Any]:
        meta = super().build_meta()
        meta["alert_type"] = self.alert_type
        if self.cloud:
            meta["_cloud"] = self.cloud
        if self.instance_id:
            meta["_instance_id"] = self.instance_id
            meta["_resource_id"] = meta.get("_resource_id") or self.instance_id
            meta["_has_cloud_target"] = True
        if self.private_ip:
            meta["_private_ip"] = self.private_ip
            meta["_has_cloud_target"] = True
        return meta


class IncidentContextRequest(BaseModel):
    """Request payload for incident-context reads."""

    tenant_id: uuid.UUID
    incident_id: uuid.UUID


class IncidentContextResponse(BaseModel):
    """Incident context returned to the caller."""

    incident_id: uuid.UUID
    alert_type: str
    title: str
    severity: str
    state: str
    meta: dict[str, Any] = Field(default_factory=dict)
    prior_similar_incidents: list[dict[str, Any]] = Field(default_factory=list)
    pattern_context: str = ""
    pattern_analysis: dict[str, Any] | None = None
    kg_context: str | None = None


class WriteEvidenceRequest(BaseModel):
    """Request payload for persisting normalized investigation evidence."""

    tenant_id: uuid.UUID
    incident_id: uuid.UUID
    evidence: EvidenceContract


class WriteEvidenceResponse(BaseModel):
    """Confirmation payload for persisted investigation evidence."""

    ok: bool
    evidence_id: uuid.UUID


def _validate_probe_result(result: Any, *, detail: str) -> ProbeResult:
    if isinstance(result, ProbeResult):
        return result
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=detail,
    )


@router.post(
    "/run_host_diagnostics",
    response_model=ProbeResult,
    summary="Run read-only host or cloud diagnostics",
)
async def run_host_diagnostics(request: HostDiagnosticsRequest) -> ProbeResult:
    meta = request.build_meta()
    cloud = str(meta.get("_cloud") or "").lower()
    has_cloud_target = bool(meta.get("_instance_id") or meta.get("_private_ip"))

    if cloud in ("aws", "gcp") and has_cloud_target:
        result = await CloudInvestigation().investigate(meta)
        return _validate_probe_result(
            result,
            detail="Cloud investigation did not return a probe result",
        )

    probe_cls = INVESTIGATION_REGISTRY.get(request.alert_type)
    if probe_cls is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No investigation probe registered for alert_type '{request.alert_type}'",
        )

    result = await probe_cls().investigate(meta)
    return _validate_probe_result(
        result,
        detail="Host diagnostics probe did not return a probe result",
    )


@router.post(
    "/fetch_log_analysis",
    response_model=ProbeResult,
    summary="Run read-only log analysis",
)
async def fetch_log_analysis(request: InternalToolRequest) -> ProbeResult:
    result = await LogAnalysisProbe().investigate(request.build_meta())
    return _validate_probe_result(
        result,
        detail="Log analysis probe did not return a probe result",
    )


@router.post(
    "/fetch_change_context",
    response_model=ProbeResult,
    summary="Fetch read-only recent change context",
)
async def fetch_change_context(request: InternalToolRequest) -> ProbeResult:
    result = await ChangeDetectionProbe().investigate(request.build_meta())
    return _validate_probe_result(
        result,
        detail="Change detection probe did not return a probe result",
    )


@router.post(
    "/fetch_infra_state",
    response_model=ProbeResult,
    summary="Fetch read-only infrastructure state",
)
async def fetch_infra_state(request: InternalToolRequest) -> ProbeResult:
    result = await InfraStateProbe().investigate(request.build_meta())
    return _validate_probe_result(
        result,
        detail="Infrastructure state probe did not return a probe result",
    )


@router.post(
    "/fetch_k8s_status",
    response_model=ProbeResult,
    summary="Fetch Kubernetes deployment and pod status",
)
async def fetch_k8s_status(request: InternalToolRequest) -> ProbeResult:
    result = await K8sStatusProbe().investigate(request.build_meta())
    return _validate_probe_result(
        result,
        detail="Kubernetes status probe did not return a probe result",
    )


async def _load_incident_for_tool(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    incident_id: uuid.UUID,
) -> Incident:
    result = await session.execute(
        select(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.id == incident_id,
        )
    )
    incident = result.scalar_one_or_none()
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )
    return incident


@router.post(
    "/read_incident_context",
    response_model=IncidentContextResponse,
    summary="Read normalized incident context for investigation",
)
async def read_incident_context(
    request: IncidentContextRequest,
    session: AsyncSession = Depends(get_auth_session),
) -> IncidentContextResponse:
    incident = await _load_incident_for_tool(
        session,
        tenant_id=request.tenant_id,
        incident_id=request.incident_id,
    )

    evidence_text = "\n---\n".join(
        f"[{e.tool_name}] {e.raw_output}" for e in incident.evidence
    )

    structured_context: dict[str, Any] | None = None
    try:
        structured_context = await build_structured_context(
            session=session,
            incident=incident,
            evidence_text=evidence_text,
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "internal_tool_read_incident_context_failed",
            tenant_id=str(request.tenant_id),
            incident_id=str(request.incident_id),
            error=str(exc),
        )

    return IncidentContextResponse(
        incident_id=incident.id,
        alert_type=incident.alert_type,
        title=incident.title,
        severity=getattr(incident.severity, "value", str(incident.severity)),
        state=getattr(incident.state, "value", str(incident.state)),
        meta=incident.meta or {},
        prior_similar_incidents=(structured_context or {}).get("similar_incidents", []),
        pattern_context=(structured_context or {}).get("text", ""),
        pattern_analysis=(structured_context or {}).get("pattern_analysis"),
        kg_context=(structured_context or {}).get("kg_context"),
    )


@router.post(
    "/write_evidence_contract",
    response_model=WriteEvidenceResponse,
    summary="Persist normalized investigation evidence onto an incident",
)
async def write_evidence_contract(
    request: WriteEvidenceRequest,
    session: AsyncSession = Depends(get_auth_session),
) -> WriteEvidenceResponse:
    incident = await _load_incident_for_tool(
        session,
        tenant_id=request.tenant_id,
        incident_id=request.incident_id,
    )

    evidence = await persist_investigation_evidence(
        session=session,
        incident=incident,
        contract=request.evidence,
    )

    return WriteEvidenceResponse(ok=True, evidence_id=evidence.id)
