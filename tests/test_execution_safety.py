"""Tests for deterministic execution safety helpers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from airex_core.core.execution_safety import (
    estimate_action_impact,
    evaluate_execution_guard,
)
from airex_core.models.enums import RiskLevel


def test_estimate_action_impact_for_scale_instances_is_high():
    estimate = estimate_action_impact(
        "scale_instances",
        {"replicas": 12, "current_replicas": 4},
        risk_level=RiskLevel.HIGH,
        blast_radius="checkout service and background workers",
    )

    assert estimate.cost_delta == "high"
    assert estimate.dependency_pressure == "high"
    assert estimate.resource_limit_risk == "high"
    assert estimate.scale_delta == 8
    assert estimate.blast_radius_summary == "checkout service and background workers"


@pytest.mark.asyncio
async def test_execution_guard_rejects_cross_tenant_payload():
    session = AsyncMock()
    tenant_id = uuid.uuid4()
    other_tenant_id = uuid.uuid4()

    guard = await evaluate_execution_guard(
        session,
        tenant_id,
        "restart_service",
        {"service_name": "checkout", "tenant_id": str(other_tenant_id)},
    )

    assert guard.valid is False
    assert guard.cross_tenant_denied is True
    assert guard.credential_scope_valid is False
    assert "Cross-tenant" in guard.reason


@pytest.mark.asyncio
async def test_execution_guard_rejects_binding_owned_by_other_tenant():
    session = AsyncMock()
    tenant_id = uuid.uuid4()
    binding_id = uuid.uuid4()
    binding = SimpleNamespace(
        id=binding_id,
        tenant_id=uuid.uuid4(),
        provider="aws",
        external_account_id="123456789012",
    )
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=binding)
    session.execute = AsyncMock(return_value=result)

    guard = await evaluate_execution_guard(
        session,
        tenant_id,
        "restart_service",
        {
            "_cloud": "aws",
            "service_name": "checkout",
            "cloud_account_binding_id": str(binding_id),
        },
    )

    assert guard.valid is False
    assert guard.cross_tenant_denied is True
    assert guard.credential_scope_valid is False
    assert "binding belongs to another tenant" in guard.reason


@pytest.mark.asyncio
async def test_execution_guard_allows_legacy_scope_without_binding():
    session = AsyncMock()
    tenant_id = uuid.uuid4()

    guard = await evaluate_execution_guard(
        session,
        tenant_id,
        "restart_service",
        {"service_name": "checkout", "_environment": "prod"},
    )

    assert guard.valid is True
    assert guard.enforcement_mode == "legacy"
    assert guard.target_scope["tenant_id"] == str(tenant_id)
    assert guard.target_scope["service_name"] == "checkout"
    assert "legacy execution path allowed" in guard.reason
