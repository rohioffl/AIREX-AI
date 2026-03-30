"""Deterministic safety checks for approval and execution."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.core.context_resolver import ExecutionContext, resolve_execution_context
from airex_core.models.cloud_account_binding import CloudAccountBinding
from airex_core.models.enums import RiskLevel
from airex_core.schemas.recommendation_contract import ExecutionGuard, ImpactEstimate

logger = structlog.get_logger()

_LEVEL_ORDER = {"low": 0, "medium": 1, "high": 2}


def estimate_action_impact(
    action_type: str,
    params: dict[str, Any] | None,
    *,
    risk_level: RiskLevel | str | None = None,
    blast_radius: str = "",
) -> ImpactEstimate:
    """Return a deterministic side-effect estimate for an action."""
    payload = dict(params or {})
    normalized_risk = _normalize_risk(risk_level)
    cost_delta = "low"
    dependency_pressure = "low"
    resource_limit_risk = "low"
    scale_delta: int | None = None
    notes: list[str] = []

    if action_type == "scale_instances":
        desired = _coerce_int(
            payload.get("replicas")
            or payload.get("desired_replicas")
            or payload.get("instance_count")
        )
        current = _coerce_int(
            payload.get("current_replicas") or payload.get("current_instances")
        )
        if desired is not None:
            scale_delta = desired - current if current is not None else desired
            if desired >= 10 or (scale_delta is not None and scale_delta >= 5):
                cost_delta = "high"
                dependency_pressure = "high"
                resource_limit_risk = "high"
            elif desired >= 4 or (scale_delta is not None and scale_delta >= 2):
                cost_delta = "medium"
                dependency_pressure = "medium"
                resource_limit_risk = "medium"
            notes.append(
                f"Scale target {desired} replica(s)"
                + (f" from {current}" if current is not None else "")
            )
    elif action_type in {"rollback_deployment", "drain_node", "block_ip"}:
        dependency_pressure = "high"
        resource_limit_risk = "medium"
        notes.append("High-impact control-plane or traffic-routing change")
    elif action_type in {"restart_service", "restart_container", "kill_process"}:
        dependency_pressure = "medium"
        resource_limit_risk = "medium"
        notes.append("Service interruption risk while workloads restart")
    elif action_type in {"resize_disk", "rotate_credentials"}:
        cost_delta = "medium"
        dependency_pressure = "medium"
        resource_limit_risk = "medium"
        notes.append("Infrastructure state change may affect dependent workloads")
    elif action_type in {"flush_cache", "clear_logs", "toggle_feature_flag"}:
        dependency_pressure = "low"
        resource_limit_risk = "low"

    if normalized_risk == RiskLevel.HIGH:
        cost_delta = _max_level(cost_delta, "medium")
        dependency_pressure = _max_level(dependency_pressure, "medium")
        resource_limit_risk = _max_level(resource_limit_risk, "medium")
    elif normalized_risk == RiskLevel.MED:
        dependency_pressure = _max_level(dependency_pressure, "low")

    summary = blast_radius.strip() if isinstance(blast_radius, str) else ""
    if not summary:
        summary = _default_blast_radius_summary(action_type, payload)

    return ImpactEstimate(
        cost_delta=cost_delta,
        dependency_pressure=dependency_pressure,
        resource_limit_risk=resource_limit_risk,
        blast_radius_summary=summary,
        scale_delta=scale_delta,
        notes=notes,
    )


async def evaluate_execution_guard(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    action_type: str,
    params: dict[str, Any] | None,
    *,
    exec_ctx: ExecutionContext | None = None,
) -> ExecutionGuard:
    """Validate tenant, credential, and ownership scope before approval/execution."""
    payload = dict(params or {})
    resolved_ctx = exec_ctx or resolve_execution_context(payload)
    binding_id = _resolve_binding_id(payload)
    target_scope = _build_target_scope(
        tenant_id=tenant_id,
        action_type=action_type,
        params=payload,
        exec_ctx=resolved_ctx,
        binding_id=binding_id,
    )
    guard = ExecutionGuard(
        valid=True,
        reason="Execution scope validated.",
        enforcement_mode="strict" if binding_id else "legacy",
        binding_id=binding_id or "",
        target_scope=target_scope,
    )

    explicit_tenant = _resolve_uuid(payload.get("_tenant_id") or payload.get("tenant_id"))
    if explicit_tenant and explicit_tenant != tenant_id:
        return guard.model_copy(
            update={
                "valid": False,
                "reason": "Cross-tenant execution denied: payload tenant does not match incident tenant.",
                "cross_tenant_denied": True,
                "credential_scope_valid": False,
                "enforcement_mode": "strict",
            }
        )

    cluster_owner = _resolve_uuid(
        payload.get("_cluster_tenant_id") or payload.get("cluster_tenant_id")
    )
    if cluster_owner and cluster_owner != tenant_id:
        return guard.model_copy(
            update={
                "valid": False,
                "reason": "Cluster ownership verification failed for this tenant.",
                "cluster_ownership_valid": False,
                "cross_tenant_denied": True,
                "enforcement_mode": "strict",
            }
        )

    namespace_owner = _resolve_uuid(
        payload.get("_namespace_tenant_id") or payload.get("namespace_tenant_id")
    )
    if namespace_owner and namespace_owner != tenant_id:
        return guard.model_copy(
            update={
                "valid": False,
                "reason": "Namespace ownership verification failed for this tenant.",
                "namespace_scope_valid": False,
                "cross_tenant_denied": True,
                "enforcement_mode": "strict",
            }
        )

    if not binding_id:
        guard.reason = (
            "No explicit tenant-scoped binding supplied; legacy execution path allowed."
        )
        return guard

    binding_uuid = _resolve_uuid(binding_id)
    if binding_uuid is None:
        return guard.model_copy(
            update={
                "valid": False,
                "reason": "Execution binding id is invalid.",
                "credential_scope_valid": False,
            }
        )

    result = await session.execute(
        select(CloudAccountBinding).where(CloudAccountBinding.id == binding_uuid)
    )
    binding = result.scalar_one_or_none()
    if binding is None:
        return guard.model_copy(
            update={
                "valid": False,
                "reason": "Referenced cloud account binding was not found.",
                "credential_scope_valid": False,
                "enforcement_mode": "strict",
            }
        )

    if binding.tenant_id != tenant_id:
        return guard.model_copy(
            update={
                "valid": False,
                "reason": "Cross-tenant execution denied: binding belongs to another tenant.",
                "cross_tenant_denied": True,
                "credential_scope_valid": False,
                "enforcement_mode": "strict",
            }
        )

    if resolved_ctx.cloud not in {"", "unknown"} and binding.provider != resolved_ctx.cloud:
        return guard.model_copy(
            update={
                "valid": False,
                "reason": "Execution binding provider does not match target cloud scope.",
                "credential_scope_valid": False,
                "enforcement_mode": "strict",
            }
        )

    expected_external = str(
        payload.get("_external_account_id")
        or payload.get("external_account_id")
        or ""
    ).strip()
    if expected_external and binding.external_account_id != expected_external:
        return guard.model_copy(
            update={
                "valid": False,
                "reason": "Execution binding account does not match target account scope.",
                "credential_scope_valid": False,
                "enforcement_mode": "strict",
            }
        )

    guard.reason = "Execution scope validated against tenant-owned credential binding."
    guard.enforcement_mode = "strict"
    return guard


def _build_target_scope(
    *,
    tenant_id: uuid.UUID,
    action_type: str,
    params: dict[str, Any],
    exec_ctx: ExecutionContext,
    binding_id: str | None,
) -> dict[str, str]:
    scope = {
        "tenant_id": str(tenant_id),
        "action_type": action_type,
        "cloud": exec_ctx.cloud,
        "environment": exec_ctx.environment,
        "cluster": exec_ctx.cluster,
        "namespace": exec_ctx.namespace,
        "instance_id": exec_ctx.instance_id,
        "service_name": exec_ctx.service_name,
    }
    if binding_id:
        scope["binding_id"] = binding_id
    target_resource = str(
        params.get("target")
        or params.get("service_name")
        or params.get("_instance_id")
        or params.get("_cluster")
        or ""
    ).strip()
    if target_resource:
        scope["target_resource"] = target_resource
    return {key: value for key, value in scope.items() if value}


def _default_blast_radius_summary(action_type: str, params: dict[str, Any]) -> str:
    target = str(
        params.get("service_name")
        or params.get("_instance_id")
        or params.get("_cluster")
        or params.get("_namespace")
        or "target workload"
    ).strip()
    return f"{action_type} will affect {target}."


def _normalize_risk(risk_level: RiskLevel | str | None) -> RiskLevel:
    if isinstance(risk_level, RiskLevel):
        return risk_level
    candidate = str(risk_level or RiskLevel.MED.value).upper().strip()
    try:
        return RiskLevel(candidate)
    except ValueError:
        return RiskLevel.MED


def _max_level(current: str, candidate: str) -> str:
    return current if _LEVEL_ORDER[current] >= _LEVEL_ORDER[candidate] else candidate


def _resolve_binding_id(params: dict[str, Any]) -> str | None:
    for key in (
        "_cloud_account_binding_id",
        "cloud_account_binding_id",
        "_cloud_account_id",
        "cloud_account_id",
        "binding_id",
    ):
        value = params.get(key)
        if value:
            return str(value).strip()
    return None


def _resolve_uuid(value: Any) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if value in (None, ""):
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = ["estimate_action_impact", "evaluate_execution_guard"]
