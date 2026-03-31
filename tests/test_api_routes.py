"""Focused API route tests for critical HTTP surfaces."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from airex_core.core.config import settings
from airex_core.core.security import create_access_token
from airex_core.investigations.base import ProbeCategory, ProbeResult
from airex_core.models.evidence import Evidence
from airex_core.models.incident import Incident
from airex_core.models.enums import IncidentState
from airex_core.models.enums import SeverityLevel
from airex_core.models.user import User


TENANT_ID = "00000000-0000-0000-0000-000000000000"
HEADERS = {"X-Tenant-Id": TENANT_ID}
ORG_SLUG = "ankercloud"
TENANT_SLUG = "workspace-alpha"


def _auth_headers(*, role: str, tenant_id: str = TENANT_ID, user_id: uuid.UUID | None = None) -> dict[str, str]:
    token = create_access_token(
        uuid.UUID(tenant_id),
        f"{role}@example.com",
        user_id=user_id or uuid.uuid4(),
        role=role,
    )
    return {**HEADERS, "Authorization": f"Bearer {token}"}


def test_app_import_smoke():
    assert app is not None


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock()
    redis.publish = AsyncMock()
    redis.pubsub = MagicMock()
    return redis


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    def add_instance(instance):
        if getattr(instance, "id", None) is None:
            instance.id = uuid.uuid4()

    session.add = MagicMock(side_effect=add_instance)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_platform_admin_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()

    def add_instance(instance):
        if getattr(instance, "id", None) is None:
            instance.id = uuid.uuid4()

    session.add = MagicMock(side_effect=add_instance)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest_asyncio.fixture
async def client(mock_redis, mock_session, mock_platform_admin_session):
    from airex_core.core.platform_admin_db import get_platform_admin_session
    from app.api.dependencies import get_auth_session, get_db_session, get_redis

    async def override_redis():
        return mock_redis

    async def override_session():
        yield mock_session

    async def override_platform_admin_session():
        yield mock_platform_admin_session

    app.dependency_overrides[get_redis] = override_redis
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_auth_session] = override_session
    app.dependency_overrides[get_platform_admin_session] = override_platform_admin_session
    app.state.redis = mock_redis

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=HEADERS,
    ) as async_client:
        yield async_client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_openclaw_health_returns_probe_status(client, monkeypatch):
    from app import main as app_main

    monkeypatch.setattr(
        app_main.openclaw_bridge,
        "ping",
        AsyncMock(return_value={"reachable": True, "status_code": 200, "url": "http://127.0.0.1:18789/health"}),
    )
    monkeypatch.setattr(settings, "OPENCLAW_ENABLED", True)
    monkeypatch.setattr(settings, "OPENCLAW_GATEWAY_URL", "http://127.0.0.1:18789")
    monkeypatch.setattr(settings, "OPENCLAW_GATEWAY_TOKEN", "")

    response = await client.get("/health/openclaw")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["gateway"]["enabled"] is True
    assert payload["probe"]["reachable"] is True


@pytest.mark.asyncio
async def test_internal_tools_require_token(client, monkeypatch):
    monkeypatch.setattr(settings, "OPENCLAW_TOOL_SERVER_TOKEN", "tool-secret")

    response = await client.post(
        "/api/v1/internal/tools/fetch_log_analysis",
        json={
            "tenant_id": TENANT_ID,
            "incident_meta": {"alert_type": "cpu_high"},
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid internal tool token"


@pytest.mark.asyncio
async def test_internal_host_diagnostics_uses_cloud_probe(client, monkeypatch):
    from app.api.routes import internal_tools

    monkeypatch.setattr(settings, "OPENCLAW_TOOL_SERVER_TOKEN", "tool-secret")
    probe_result = ProbeResult(
        tool_name="cloud_investigation_aws",
        raw_output="=== Cloud Investigation: i-123 ===",
        category=ProbeCategory.INFRASTRUCTURE,
        probe_type="primary",
        metrics={"instance_id": "i-123"},
    )
    monkeypatch.setattr(
        internal_tools.CloudInvestigation,
        "investigate",
        AsyncMock(return_value=probe_result),
    )

    response = await client.post(
        "/api/v1/internal/tools/run_host_diagnostics",
        headers={"X-Internal-Tool-Token": "tool-secret"},
        json={
            "tenant_id": TENANT_ID,
            "alert_type": "cpu_high",
            "cloud": "aws",
            "instance_id": "i-123",
            "private_ip": "10.0.0.5",
            "incident_meta": {"host": "api-01"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_name"] == "cloud_investigation_aws"
    assert payload["metrics"]["instance_id"] == "i-123"


@pytest.mark.asyncio
async def test_internal_host_diagnostics_uses_alert_probe(client, monkeypatch):
    from app.api.routes import internal_tools

    monkeypatch.setattr(settings, "OPENCLAW_TOOL_SERVER_TOKEN", "tool-secret")

    fake_probe = MagicMock()
    fake_probe.investigate = AsyncMock(
        return_value=ProbeResult(
            tool_name="cpu_diagnostics",
            raw_output="=== CPU Investigation: api-01 ===",
            category=ProbeCategory.SYSTEM,
            probe_type="primary",
            metrics={"cpu_percent": 95.4},
        )
    )
    monkeypatch.setitem(internal_tools.INVESTIGATION_REGISTRY, "cpu_high", lambda: fake_probe)

    response = await client.post(
        "/api/v1/internal/tools/run_host_diagnostics",
        headers={"X-Internal-Tool-Token": "tool-secret"},
        json={
            "tenant_id": TENANT_ID,
            "alert_type": "cpu_high",
            "incident_meta": {"host": "api-01"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_name"] == "cpu_diagnostics"
    assert payload["metrics"]["cpu_percent"] == 95.4


@pytest.mark.asyncio
async def test_internal_fetch_change_context_returns_probe(client, monkeypatch):
    from app.api.routes import internal_tools

    monkeypatch.setattr(settings, "OPENCLAW_TOOL_SERVER_TOKEN", "tool-secret")
    monkeypatch.setattr(
        internal_tools.ChangeDetectionProbe,
        "investigate",
        AsyncMock(
            return_value=ProbeResult(
                tool_name="change_detection_aws",
                raw_output="=== Change Detection: AWS ===",
                category=ProbeCategory.CHANGE,
                probe_type="secondary",
                metrics={"deployment_detected": True},
            )
        ),
    )

    response = await client.post(
        "/api/v1/internal/tools/fetch_change_context",
        headers={"X-Internal-Tool-Token": "tool-secret"},
        json={
            "tenant_id": TENANT_ID,
            "incident_meta": {"_cloud": "aws", "_instance_id": "i-123"},
        },
    )

    assert response.status_code == 200
    assert response.json()["metrics"]["deployment_detected"] is True


@pytest.mark.asyncio
async def test_internal_fetch_infra_state_returns_probe(client, monkeypatch):
    from app.api.routes import internal_tools

    monkeypatch.setattr(settings, "OPENCLAW_TOOL_SERVER_TOKEN", "tool-secret")
    monkeypatch.setattr(
        internal_tools.InfraStateProbe,
        "investigate",
        AsyncMock(
            return_value=ProbeResult(
                tool_name="infra_state_gcp",
                raw_output="=== Infrastructure State: GCP ===",
                category=ProbeCategory.INFRASTRUCTURE,
                probe_type="secondary",
                metrics={"unhealthy_count": 1},
            )
        ),
    )

    response = await client.post(
        "/api/v1/internal/tools/fetch_infra_state",
        headers={"X-Internal-Tool-Token": "tool-secret"},
        json={
            "tenant_id": TENANT_ID,
            "incident_meta": {"_cloud": "gcp", "_instance_id": "vm-1"},
        },
    )

    assert response.status_code == 200
    assert response.json()["metrics"]["unhealthy_count"] == 1


@pytest.mark.asyncio
async def test_internal_fetch_k8s_status_returns_probe(client, monkeypatch):
    from app.api.routes import internal_tools

    monkeypatch.setattr(settings, "OPENCLAW_TOOL_SERVER_TOKEN", "tool-secret")
    monkeypatch.setattr(
        internal_tools.K8sStatusProbe,
        "investigate",
        AsyncMock(
            return_value=ProbeResult(
                tool_name="k8s_status",
                raw_output="=== Kubernetes Status: checkout ===",
                category=ProbeCategory.INFRASTRUCTURE,
                probe_type="secondary",
                metrics={"deployment": "checkout", "restart_count": 2},
            )
        ),
    )

    response = await client.post(
        "/api/v1/internal/tools/fetch_k8s_status",
        headers={"X-Internal-Tool-Token": "tool-secret"},
        json={
            "tenant_id": TENANT_ID,
            "incident_meta": {"_platform": "k8s", "_k8s_deployment": "checkout"},
        },
    )

    assert response.status_code == 200
    assert response.json()["metrics"]["deployment"] == "checkout"


@pytest.mark.asyncio
async def test_internal_read_incident_context_returns_structured_context(
    client,
    mock_session,
    monkeypatch,
):
    from app.api.routes import internal_tools

    monkeypatch.setattr(settings, "OPENCLAW_TOOL_SERVER_TOKEN", "tool-secret")
    incident_id = uuid.uuid4()
    incident = SimpleNamespace(
        id=incident_id,
        tenant_id=uuid.UUID(TENANT_ID),
        alert_type="cpu_high",
        title="CPU saturation on web-1",
        severity=SimpleNamespace(value="high"),
        state=SimpleNamespace(value="INVESTIGATING"),
        meta={"host": "web-1"},
        evidence=[SimpleNamespace(tool_name="cpu_diagnostics", raw_output="cpu=95")],
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=incident)
    mock_session.execute = AsyncMock(return_value=mock_result)
    monkeypatch.setattr(
        internal_tools,
        "build_structured_context",
        AsyncMock(
            return_value={
                "text": "Pattern context block",
                "similar_incidents": [{"incident_id": str(uuid.uuid4()), "score": 0.1}],
                "pattern_analysis": {"historical_context": "Seen before"},
                "kg_context": "KG says restart worked",
            }
        ),
    )

    response = await client.post(
        "/api/v1/internal/tools/read_incident_context",
        headers={"X-Internal-Tool-Token": "tool-secret"},
        json={
            "tenant_id": TENANT_ID,
            "incident_id": str(incident_id),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["incident_id"] == str(incident_id)
    assert payload["prior_similar_incidents"]
    assert payload["pattern_context"] == "Pattern context block"
    assert payload["kg_context"] == "KG says restart worked"


@pytest.mark.asyncio
async def test_internal_write_evidence_contract_persists_openclaw_evidence(
    client,
    mock_session,
    monkeypatch,
):
    monkeypatch.setattr(settings, "OPENCLAW_TOOL_SERVER_TOKEN", "tool-secret")
    tenant_id = uuid.UUID(TENANT_ID)
    incident_id = uuid.uuid4()
    incident = Incident(
        id=incident_id,
        tenant_id=tenant_id,
        alert_type="cpu_high",
        severity=SeverityLevel.HIGH,
        title="CPU saturation on web-1",
        meta={},
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=incident)
    mock_session.execute = AsyncMock(return_value=mock_result)

    def add_instance(instance):
        if isinstance(instance, Evidence) and getattr(instance, "id", None) is None:
            instance.id = uuid.uuid4()

    mock_session.add = MagicMock(side_effect=add_instance)

    response = await client.post(
        "/api/v1/internal/tools/write_evidence_contract",
        headers={"X-Internal-Tool-Token": "tool-secret"},
        json={
            "tenant_id": TENANT_ID,
            "incident_id": str(incident_id),
            "evidence": {
                "summary": "CPU Investigation: web-1",
                "signals": ["cpu 95%", "java hot loop"],
                "root_cause": "High CPU driven by java",
                "affected_entities": ["host:web-1", "service:checkout"],
                "confidence": 0.82,
                "raw_refs": {"forensic_tools": ["cpu_diagnostics"]},
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["evidence_id"]
    assert incident.meta["openclaw"]["summary"] == "CPU Investigation: web-1"
    assert incident.meta["investigation_summary"] == "CPU Investigation: web-1"


@pytest.mark.asyncio
async def test_metrics_returns_prometheus_payload(client):
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "http_request_duration" in response.text or "airex_" in response.text


@pytest.mark.asyncio
async def test_list_incidents_empty(client, mock_session):
    mock_count_result = MagicMock()
    mock_count_result.scalar_one = MagicMock(return_value=0)

    mock_items_result = MagicMock()
    mock_items_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[]))
    )

    mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_items_result])

    response = await client.get("/api/v1/incidents/")
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_list_organization_incidents_requires_org_membership(client, mock_session):
    organization_id = uuid.uuid4()

    no_org_membership = MagicMock()
    no_org_membership.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=no_org_membership)

    response = await client.get(
        f"/api/v1/incidents/organizations/{organization_id}",
        headers=_auth_headers(role="operator"),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Organization-level access required"


@pytest.mark.asyncio
async def test_list_organization_incidents_returns_cross_tenant_items_for_org_user(client, mock_session):
    organization_id = uuid.uuid4()
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    incident_a = Incident(
        id=uuid.uuid4(),
        tenant_id=tenant_a,
        alert_type="cpu_high",
        state=IncidentState.RECEIVED,
        severity=SeverityLevel.HIGH,
        title="CPU high on api-1",
        investigation_retry_count=0,
        execution_retry_count=0,
        verification_retry_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        meta={},
        host_key="api-1",
    )
    incident_b = Incident(
        id=uuid.uuid4(),
        tenant_id=tenant_b,
        alert_type="disk_full",
        state=IncidentState.AWAITING_APPROVAL,
        severity=SeverityLevel.CRITICAL,
        title="Disk full on db-1",
        investigation_retry_count=0,
        execution_retry_count=0,
        verification_retry_count=0,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=3),
        meta={},
        host_key="db-1",
    )

    org_membership = MagicMock()
    org_membership.scalar_one_or_none = MagicMock(return_value="viewer")
    count_result = MagicMock()
    count_result.scalar_one = MagicMock(return_value=2)
    items_result = MagicMock()
    items_result.all = MagicMock(
        return_value=[
            (incident_a, "AWS Test Client", "aws-test-client"),
            (incident_b, "GCP Test Client", "gcp-test-client"),
        ]
    )
    mock_session.execute = AsyncMock(side_effect=[org_membership, count_result, items_result])

    response = await client.get(
        f"/api/v1/incidents/organizations/{organization_id}",
        headers=_auth_headers(role="operator"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert [item["tenant_name"] for item in payload["items"]] == [
        "AWS Test Client",
        "GCP Test Client",
    ]


@pytest.mark.asyncio
async def test_export_incidents_hits_static_route(client, mock_session):
    mock_result = MagicMock()
    mock_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[]))
    )
    mock_session.execute = AsyncMock(return_value=mock_result)

    response = await client.get("/api/v1/incidents/export")
    assert response.status_code == 200
    assert response.headers["content-disposition"] == "attachment; filename=incidents.json"
    assert response.json() == []


@pytest.mark.asyncio
async def test_bulk_approve_hits_static_route(client):
    response = await client.post(
        "/api/v1/incidents/bulk-approve",
        json={"incident_ids": [], "reason": "bulk test"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "No incident IDs provided"


@pytest.mark.asyncio
async def test_bulk_reject_hits_static_route(client):
    response = await client.post(
        "/api/v1/incidents/bulk-reject",
        json={"incident_ids": [], "reason": "bulk test"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "No incident IDs provided"


@pytest.mark.asyncio
async def test_get_nonexistent_incident_returns_404(client, mock_session):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=mock_result)

    response = await client.get(f"/api/v1/incidents/{uuid.uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_generic_webhook_validation_error(client):
    response = await client.post(f"/api/v1/webhooks/{ORG_SLUG}/{TENANT_SLUG}/generic", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_generic_webhook_requires_fields(client):
    response = await client.post(
        f"/api/v1/webhooks/{ORG_SLUG}/{TENANT_SLUG}/generic",
        json={"alert_type": "cpu_high"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_site24x7_webhook_rejects_non_json(client, monkeypatch):
    from app.api.routes import webhooks as webhook_routes

    tenant_id = uuid.UUID(TENANT_ID)
    integration_id = uuid.uuid4()

    async def fake_resolve_tenant(session, org_slug, tenant_slug):
        assert org_slug == ORG_SLUG
        assert tenant_slug == TENANT_SLUG
        return tenant_id

    async def fake_resolve_integration(session, expected_tenant_id, account_slug, integration_slug):
        assert expected_tenant_id == tenant_id
        assert account_slug == "547361935557"
        assert integration_slug == "tenant-site24x7"
        return webhook_routes.Site24x7IntegrationContext(
            integration_id=integration_id,
            tenant_id=tenant_id,
            integration_name="Tenant Site24x7",
            integration_slug="tenant-site24x7",
            integration_type_key="site24x7",
            enabled=True,
            status="configured",
        )

    monkeypatch.setattr(webhook_routes, "_resolve_tenant_by_slugs", fake_resolve_tenant)
    monkeypatch.setattr(
        webhook_routes,
        "_resolve_site24x7_integration_context",
        fake_resolve_integration,
    )

    response = await client.post(
        f"/api/v1/webhooks/{ORG_SLUG}/{TENANT_SLUG}/547361935557/tenant-site24x7",
        content=b"not json",
        headers={**HEADERS, "Content-Type": "application/json"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            f"/api/v1/webhooks/{ORG_SLUG}/{TENANT_SLUG}/prometheus",
            {"alerts": [{"labels": {"alertname": "HighCPU"}}]},
        ),
        (
            f"/api/v1/webhooks/{ORG_SLUG}/{TENANT_SLUG}/grafana",
            {"title": "Grafana alert", "severity": "warning"},
        ),
        (
            f"/api/v1/webhooks/{ORG_SLUG}/{TENANT_SLUG}/pagerduty",
            {"messages": [{"event": {"incident": {"title": "PD incident", "severity": "critical"}}}]},
        ),
    ],
)
async def test_provider_webhooks_require_signature_when_secret_enabled(client, monkeypatch, path, payload):
    monkeypatch.setattr(settings, "WEBHOOK_SECRET", "test-secret")
    response = await client.post(path, json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing webhook signature header"
    monkeypatch.setattr(settings, "WEBHOOK_SECRET", "")


@pytest.mark.asyncio
async def test_sse_resolve_tenant_uses_requested_active_tenant(mock_session):
    from app.api.routes import sse as sse_routes

    active_tenant_id = uuid.uuid4()
    token = create_access_token(
        uuid.UUID(TENANT_ID),
        "viewer@example.com",
        user_id=uuid.uuid4(),
        role="tenant_viewer",
    )

    tenant_lookup = MagicMock()
    tenant_lookup.first = MagicMock(
        return_value=SimpleNamespace(
            id=active_tenant_id,
            organization_id=uuid.uuid4(),
            is_active=True,
        )
    )
    org_membership_lookup = MagicMock()
    org_membership_lookup.scalar_one_or_none = MagicMock(return_value=None)
    tenant_membership_lookup = MagicMock()
    tenant_membership_lookup.scalar_one_or_none = MagicMock(return_value="viewer")
    mock_session.execute = AsyncMock(
        side_effect=[tenant_lookup, org_membership_lookup, tenant_membership_lookup]
    )

    resolved = await sse_routes._resolve_tenant(
        mock_session,
        token=token,
        active_tenant_id=str(active_tenant_id),
    )

    assert resolved == active_tenant_id


@pytest.mark.asyncio
async def test_approve_nonexistent_incident_returns_404(client, mock_session):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=mock_result)

    response = await client.post(
        f"/api/v1/incidents/{uuid.uuid4()}/approve",
        json={"action": "restart_service", "idempotency_key": "test-key-123"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_approve_senior_gated_incident_requires_admin_role(client, mock_session, mock_redis):
    incident = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(TENANT_ID),
        state=IncidentState.AWAITING_APPROVAL,
        meta={
            "_approval_level": "senior",
            "recommendation": {
                "proposed_action": "scale_instances",
                "action_id": "scale_instances",
                "params": {"replicas": 5},
            },
        },
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=incident)
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_redis.get = AsyncMock(return_value=None)

    response = await client.post(
        f"/api/v1/incidents/{incident.id}/approve",
        json={"action": "scale_instances", "idempotency_key": "senior-check"},
        headers=_auth_headers(role="operator"),
    )

    assert response.status_code == 403
    assert "senior" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_approve_uses_recommendation_contract_when_legacy_payload_missing(
    client, mock_session, mock_redis, monkeypatch
):
    from app.api.routes import incidents as incident_routes

    incident = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(TENANT_ID),
        state=IncidentState.AWAITING_APPROVAL,
        meta={
            "recommendation_contract": {
                "action_type": "execute_fix",
                "action_id": "restart_service",
                "target": "checkout-api",
                "params": {"service_name": "checkout-api"},
                "reason": "health checks are failing",
                "confidence": 0.84,
                "risk": "MED",
                "confidence_breakdown": {
                    "model_confidence": 0.84,
                    "evidence_strength_score": 0.72,
                    "tool_grounding_score": 0.65,
                    "kg_match_score": 0.33,
                    "hallucination_penalty": 0.0,
                    "composite_confidence": 0.738,
                    "warning": "",
                },
            },
            "confidence_breakdown": {
                "model_confidence": 0.84,
                "evidence_strength_score": 0.72,
                "tool_grounding_score": 0.65,
                "kg_match_score": 0.33,
                "hallucination_penalty": 0.0,
                "composite_confidence": 0.738,
                "warning": "",
            },
        },
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=incident)
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_redis.get = AsyncMock(return_value=None)
    monkeypatch.setattr(incident_routes, "transition_state", AsyncMock())

    response = await client.post(
        f"/api/v1/incidents/{incident.id}/approve",
        json={"action": "restart_service", "idempotency_key": "contract-only"},
        headers=_auth_headers(role="admin"),
    )

    assert response.status_code == 202
    assert incident.meta["execution_snapshot"]["params"] == {
        "service_name": "checkout-api"
    }
    assert incident.meta["execution_snapshot"]["confidence_used"] == 0.738
    assert incident.meta["execution_snapshot"]["impact_estimate"]["dependency_pressure"] == "medium"
    assert incident.meta["execution_snapshot"]["execution_guard"]["valid"] is True
    assert incident.meta["execution_snapshot"]["execution_guard"]["target_scope"]["service_name"] == "checkout-api"


@pytest.mark.asyncio
async def test_approve_rejects_cross_tenant_execution_scope(
    client, mock_session, mock_redis, monkeypatch
):
    from app.api.routes import incidents as incident_routes

    incident = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(TENANT_ID),
        state=IncidentState.AWAITING_APPROVAL,
        meta={
            "recommendation": {
                "proposed_action": "restart_service",
                "action_id": "restart_service",
                "risk_level": "MED",
                "params": {
                    "service_name": "checkout-api",
                    "tenant_id": str(uuid.uuid4()),
                },
            },
        },
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=incident)
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_redis.get = AsyncMock(return_value=None)
    transition_state = AsyncMock()
    monkeypatch.setattr(incident_routes, "transition_state", transition_state)

    response = await client.post(
        f"/api/v1/incidents/{incident.id}/approve",
        json={"action": "restart_service", "idempotency_key": "cross-tenant-check"},
        headers=_auth_headers(role="admin"),
    )

    assert response.status_code == 403
    assert "cross-tenant" in response.json()["detail"].lower()
    transition_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_reject_nonexistent_incident_returns_404(client, mock_session):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=mock_result)

    response = await client.post(
        f"/api/v1/incidents/{uuid.uuid4()}/reject",
        json={"reason": "unsafe remediation"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_auth_me_returns_memberships_and_accessible_tenants(client, mock_session):
    org_id = uuid.uuid4()
    home_tenant_id = uuid.UUID(TENANT_ID)
    sibling_tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    token = create_access_token(
        home_tenant_id,
        "org-admin@example.com",
        user_id=user_id,
        role="org_admin",
    )

    user_row = MagicMock()
    user_row.scalar_one_or_none = MagicMock(
        return_value=MagicMock(
            id=user_id,
            tenant_id=home_tenant_id,
            email="org-admin@example.com",
            display_name="Org Admin",
            role="org_admin",
            is_active=True,
        )
    )

    home_tenant_row = MagicMock()
    home_tenant_row.one_or_none = MagicMock(
        return_value=MagicMock(
            id=home_tenant_id,
            name="home-tenant",
            display_name="Home Tenant",
            organization_id=org_id,
            organization_name="Ankercloud",
            organization_slug="ankercloud",
        )
    )

    org_membership_rows = MagicMock()
    org_membership_rows.all = MagicMock(
        return_value=[
            MagicMock(
                organization_id=org_id,
                role="org_admin",
                organization_name="Ankercloud",
                organization_slug="ankercloud",
            )
        ]
    )

    tenant_membership_rows = MagicMock()
    tenant_membership_rows.all = MagicMock(return_value=[])

    org_access_rows = MagicMock()
    org_access_rows.all = MagicMock(
        return_value=[
            MagicMock(
                id=home_tenant_id,
                name="home-tenant",
                display_name="Home Tenant",
                organization_id=org_id,
                organization_name="Ankercloud",
                organization_slug="ankercloud",
            ),
            MagicMock(
                id=sibling_tenant_id,
                name="uno-secur",
                display_name="UnoSecur",
                organization_id=org_id,
                organization_name="Ankercloud",
                organization_slug="ankercloud",
            ),
        ]
    )

    active_project_rows = MagicMock()
    active_project_rows.all = MagicMock(
        return_value=[
            MagicMock(id=uuid.uuid4(), name="Project-1", slug="project-1"),
            MagicMock(id=uuid.uuid4(), name="Project-2", slug="project-2"),
        ]
    )

    mock_session.execute = AsyncMock(
        side_effect=[
            user_row,
            home_tenant_row,
            org_membership_rows,
            tenant_membership_rows,
            org_access_rows,
            active_project_rows,
        ]
    )

    response = await client.get(
        "/api/v1/auth/me",
        headers={**HEADERS, "Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["role"] == "org_admin"
    assert body["active_organization"]["slug"] == "ankercloud"
    assert body["active_tenant"]["id"] == str(home_tenant_id)
    assert {tenant["name"] for tenant in body["tenants"]} == {"home-tenant", "uno-secur"}
    assert body["projects"][0]["slug"] == "project-1"


@pytest.mark.asyncio
async def test_auth_me_scopes_active_org_to_matching_membership_only(client, mock_session):
    home_org_id = uuid.uuid4()
    active_org_id = uuid.uuid4()
    home_tenant_id = uuid.UUID(TENANT_ID)
    active_tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    token = create_access_token(
        home_tenant_id,
        "org-admin@example.com",
        user_id=user_id,
        role="org_admin",
    )

    target_tenant_lookup = MagicMock()
    target_tenant_lookup.first = MagicMock(
        return_value=SimpleNamespace(
            id=active_tenant_id,
            organization_id=active_org_id,
            is_active=True,
        )
    )
    org_membership_lookup = MagicMock()
    org_membership_lookup.scalar_one_or_none = MagicMock(return_value=None)
    tenant_membership_lookup = MagicMock()
    tenant_membership_lookup.scalar_one_or_none = MagicMock(return_value="tenant_admin")

    user_row = MagicMock()
    user_row.scalar_one_or_none = MagicMock(
        return_value=MagicMock(
            id=user_id,
            tenant_id=home_tenant_id,
            email="org-admin@example.com",
            display_name="Org Admin",
            role="org_admin",
            is_active=True,
        )
    )

    active_tenant_row = MagicMock()
    active_tenant_row.one_or_none = MagicMock(
        return_value=MagicMock(
            id=active_tenant_id,
            name="active-tenant",
            display_name="Active Tenant",
            organization_id=active_org_id,
            organization_name="Uno Org",
            organization_slug="uno-org",
        )
    )

    org_membership_rows = MagicMock()
    org_membership_rows.all = MagicMock(
        return_value=[
            MagicMock(
                organization_id=home_org_id,
                role="org_admin",
                organization_name="Home Org",
                organization_slug="home-org",
            )
        ]
    )

    tenant_membership_rows = MagicMock()
    tenant_membership_rows.all = MagicMock(
        return_value=[
            MagicMock(
                tenant_id=active_tenant_id,
                role="tenant_admin",
                name="active-tenant",
                display_name="Active Tenant",
                organization_id=active_org_id,
                organization_name="Uno Org",
                organization_slug="uno-org",
            )
        ]
    )

    accessible_tenants_rows = MagicMock()
    accessible_tenants_rows.all = MagicMock(
        return_value=[
            MagicMock(
                id=home_tenant_id,
                name="home-tenant",
                display_name="Home Tenant",
                organization_id=home_org_id,
                organization_name="Home Org",
                organization_slug="home-org",
            ),
            MagicMock(
                id=active_tenant_id,
                name="active-tenant",
                display_name="Active Tenant",
                organization_id=active_org_id,
                organization_name="Uno Org",
                organization_slug="uno-org",
            ),
        ]
    )

    active_project_rows = MagicMock()
    active_project_rows.all = MagicMock(return_value=[])

    mock_session.execute = AsyncMock(
        side_effect=[
            target_tenant_lookup,
            org_membership_lookup,
            tenant_membership_lookup,
            user_row,
            active_tenant_row,
            org_membership_rows,
            tenant_membership_rows,
            accessible_tenants_rows,
            active_project_rows,
        ]
    )

    response = await client.get(
        "/api/v1/auth/me",
        headers={
            **HEADERS,
            "Authorization": f"Bearer {token}",
            "X-Active-Tenant-Id": str(active_tenant_id),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["active_organization"]["slug"] == "uno-org"
    assert body["active_organization"]["role"] == "tenant_member"
    assert {tenant["name"] for tenant in body["tenants"]} == {"home-tenant", "active-tenant"}

    accessible_query = str(mock_session.execute.call_args_list[7].args[0])
    assert "tenant_memberships" in accessible_query.lower()


@pytest.mark.asyncio
async def test_auth_me_rejects_malformed_active_tenant_id(client):
    response = await client.get(
        "/api/v1/auth/me",
        headers={
            **_auth_headers(role="org_admin"),
            "X-Active-Tenant-Id": "not-a-uuid",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid active tenant identifier"


@pytest.mark.asyncio
async def test_list_accessible_tenants_requires_shared_admin_org(client, mock_session):
    requester_org_id = uuid.uuid4()
    target_org_id = uuid.uuid4()
    target_user_id = uuid.uuid4()
    target_home_tenant_id = uuid.uuid4()

    requester_home_org = MagicMock()
    requester_home_org.scalar_one_or_none = MagicMock(return_value=requester_org_id)
    requester_org_memberships = MagicMock()
    requester_org_memberships.all = MagicMock(return_value=[])

    target_user = MagicMock()
    target_user.one_or_none = MagicMock(
        return_value=SimpleNamespace(id=target_user_id, tenant_id=target_home_tenant_id)
    )

    target_home_tenant = MagicMock()
    target_home_tenant.scalar_one_or_none = MagicMock(
        return_value=SimpleNamespace(
            id=target_home_tenant_id,
            name="foreign-home",
            display_name="Foreign Home",
            cloud="aws",
            is_active=True,
            organization_id=target_org_id,
        )
    )

    target_org_memberships = MagicMock()
    target_org_memberships.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[]))
    )
    target_tenant_memberships = MagicMock()
    target_tenant_memberships.all = MagicMock(return_value=[])

    mock_session.execute = AsyncMock(
        side_effect=[
            requester_home_org,
            requester_org_memberships,
            target_user,
            target_home_tenant,
            target_org_memberships,
            target_tenant_memberships,
        ]
    )

    response = await client.get(
        f"/api/v1/users/{target_user_id}/accessible-tenants",
        headers=_auth_headers(role="org_admin"),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to view this user's tenant access"


@pytest.mark.asyncio
async def test_list_accessible_tenants_filters_to_requester_admin_orgs(client, mock_session):
    shared_org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    target_user_id = uuid.uuid4()
    shared_tenant_id = uuid.uuid4()
    other_tenant_id = uuid.uuid4()

    requester_home_org = MagicMock()
    requester_home_org.scalar_one_or_none = MagicMock(return_value=shared_org_id)
    requester_org_memberships = MagicMock()
    requester_org_memberships.all = MagicMock(return_value=[])

    target_user = MagicMock()
    target_user.one_or_none = MagicMock(
        return_value=SimpleNamespace(id=target_user_id, tenant_id=shared_tenant_id)
    )

    target_home_tenant = MagicMock()
    target_home_tenant.scalar_one_or_none = MagicMock(
        return_value=SimpleNamespace(
            id=shared_tenant_id,
            name="shared-home",
            display_name="Shared Home",
            cloud="aws",
            is_active=True,
            organization_id=shared_org_id,
        )
    )

    target_org_memberships = MagicMock()
    target_org_memberships.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[shared_org_id, other_org_id]))
    )

    org_tenants = MagicMock()
    org_tenants.scalars = MagicMock(
        return_value=MagicMock(
            all=MagicMock(
                return_value=[
                    SimpleNamespace(
                        id=shared_tenant_id,
                        name="shared-home",
                        display_name="Shared Home",
                        cloud="aws",
                        is_active=True,
                        organization_id=shared_org_id,
                    ),
                    SimpleNamespace(
                        id=other_tenant_id,
                        name="other-org",
                        display_name="Other Org",
                        cloud="gcp",
                        is_active=True,
                        organization_id=other_org_id,
                    ),
                ]
            )
        )
    )

    explicit_memberships = MagicMock()
    explicit_memberships.all = MagicMock(
        return_value=[SimpleNamespace(tenant_id=other_tenant_id, role="tenant_admin")]
    )

    explicit_tenants = MagicMock()
    explicit_tenants.scalars = MagicMock(
        return_value=MagicMock(
            all=MagicMock(
                return_value=[
                    SimpleNamespace(
                        id=other_tenant_id,
                        name="other-org",
                        display_name="Other Org",
                        cloud="gcp",
                        is_active=True,
                        organization_id=other_org_id,
                    )
                ]
            )
        )
    )

    mock_session.execute = AsyncMock(
        side_effect=[
            requester_home_org,
            requester_org_memberships,
            target_user,
            target_home_tenant,
            target_org_memberships,
            org_tenants,
            explicit_memberships,
            explicit_tenants,
        ]
    )

    response = await client.get(
        f"/api/v1/users/{target_user_id}/accessible-tenants",
        headers=_auth_headers(role="org_admin"),
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(shared_tenant_id),
            "name": "shared-home",
            "display_name": "Shared Home",
            "cloud": "aws",
            "is_active": True,
            "organization_id": str(shared_org_id),
            "membership_role": None,
        }
    ]


@pytest.mark.asyncio
async def test_get_org_analytics_filters_non_admin_to_visible_tenants(client, mock_session):
    organization_id = uuid.uuid4()
    explicit_tenant_id = uuid.uuid4()
    home_tenant_row = MagicMock()
    home_tenant_row.scalar_one_or_none = MagicMock(return_value=organization_id)
    no_org_admin_membership = MagicMock()
    no_org_admin_membership.scalar_one_or_none = MagicMock(return_value=None)

    visible_tenants = MagicMock()
    visible_tenants.all = MagicMock(
        return_value=[
            SimpleNamespace(id=uuid.UUID(TENANT_ID), is_active=True),
            SimpleNamespace(id=explicit_tenant_id, is_active=False),
        ]
    )
    home_members = MagicMock()
    home_members.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[uuid.uuid4(), uuid.uuid4()]))
    )
    explicit_members = MagicMock()
    shared_user_id = uuid.uuid4()
    explicit_members.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[shared_user_id]))
    )

    mock_session.execute = AsyncMock(
        side_effect=[
            home_tenant_row,
            no_org_admin_membership,
            visible_tenants,
            home_members,
            explicit_members,
        ]
    )

    response = await client.get(
        f"/api/v1/organizations/{organization_id}/analytics",
        headers=_auth_headers(role="operator"),
    )

    assert response.status_code == 200
    assert response.json() == {
        "organization_id": str(organization_id),
        "tenant_count": 2,
        "active_tenant_count": 1,
        "member_count": 3,
    }


@pytest.mark.asyncio
async def test_get_org_analytics_org_admin_sees_full_org_scope(client, mock_session):
    organization_id = uuid.uuid4()

    home_org_lookup = MagicMock()
    home_org_lookup.scalar_one_or_none = MagicMock(return_value=organization_id)
    home_org_lookup_again = MagicMock()
    home_org_lookup_again.scalar_one_or_none = MagicMock(return_value=organization_id)

    visible_tenants = MagicMock()
    visible_tenants.all = MagicMock(
        return_value=[
            SimpleNamespace(id=uuid.uuid4(), is_active=True),
            SimpleNamespace(id=uuid.uuid4(), is_active=True),
            SimpleNamespace(id=uuid.uuid4(), is_active=False),
        ]
    )
    home_members = MagicMock()
    repeated_user_id = uuid.uuid4()
    home_members.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[uuid.uuid4(), repeated_user_id]))
    )
    explicit_members = MagicMock()
    explicit_members.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[repeated_user_id, uuid.uuid4()]))
    )

    mock_session.execute = AsyncMock(
        side_effect=[
            home_org_lookup,
            home_org_lookup_again,
            visible_tenants,
            home_members,
            explicit_members,
        ]
    )

    response = await client.get(
        f"/api/v1/organizations/{organization_id}/analytics",
        headers=_auth_headers(role="org_admin"),
    )

    assert response.status_code == 200
    assert response.json() == {
        "organization_id": str(organization_id),
        "tenant_count": 3,
        "active_tenant_count": 2,
        "member_count": 3,
    }


class _FakeExecuteResult:
    def __init__(self, first_row=None, rowcount=1, rows=None, scalar_rows=None, scalar_one_or_none=None):
        self._first_row = first_row
        self.rowcount = rowcount
        self._rows = list(rows or [])
        self._scalar_rows = list(scalar_rows or [])
        self._scalar_one_or_none = scalar_one_or_none

    def first(self):
        return self._first_row

    def __iter__(self):
        return iter(self._rows)

    def scalar_one_or_none(self):
        if self._scalar_one_or_none is not None:
            return self._scalar_one_or_none
        return self._first_row

    def scalars(self):
        return MagicMock(all=MagicMock(return_value=self._scalar_rows))


class _FakeConnection:
    def __init__(self, responses):
        self._responses = list(responses)
        self.statements = []

    async def execute(self, statement, params=None):
        self.statements.append((str(statement), params))
        return self._responses.pop(0)


class _FakeAsyncContext:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def __init__(self, *, begin_conn=None, connect_conn=None):
        self._begin_conn = begin_conn
        self._connect_conn = connect_conn

    def begin(self):
        return _FakeAsyncContext(self._begin_conn)

    def connect(self):
        return _FakeAsyncContext(self._connect_conn)


@pytest.mark.asyncio
async def test_tenant_create_uses_cast_for_jsonb(client, monkeypatch):
    from app.api.routes import tenants as tenant_routes

    fake_conn = _FakeConnection(
        responses=[
            _FakeExecuteResult(first_row=None),
            _FakeExecuteResult(),
        ]
    )
    monkeypatch.setattr(
        tenant_routes,
        "async_engine",
        _FakeEngine(begin_conn=fake_conn),
    )
    monkeypatch.setattr(tenant_routes, "_invalidate_cache", lambda: None)

    response = await client.post(
        "/api/v1/tenants/",
        json={
            "organization_id": "11111111-1111-1111-1111-111111111111",
            "name": "tenant-create-test",
            "display_name": "Tenant Create Test",
            "cloud": "aws",
            "aws_config": {"account_id": "123456789012", "role_name": "AirexReadOnly"},
            "servers": [{"name": "app-1"}],
        },
    )

    assert response.status_code == 201
    insert_sql = fake_conn.statements[1][0]
    assert "CAST(:aws_config AS jsonb)" in insert_sql
    assert "CAST(:gcp_config AS jsonb)" in insert_sql
    assert "CAST(:servers AS jsonb)" in insert_sql
    assert ":organization_id" in insert_sql


@pytest.mark.asyncio
async def test_tenant_update_uses_cast_for_jsonb(client, monkeypatch):
    from app.api.routes import tenants as tenant_routes

    fake_conn = _FakeConnection(responses=[_FakeExecuteResult(rowcount=1)])
    monkeypatch.setattr(
        tenant_routes,
        "async_engine",
        _FakeEngine(begin_conn=fake_conn),
    )
    monkeypatch.setattr(tenant_routes, "_invalidate_cache", lambda: None)

    response = await client.put(
        "/api/v1/tenants/tenant-update-test",
        json={
            "display_name": "Updated Tenant",
            "aws_config": {"secret_access_key": "updated-secret"},
        },
        headers=_auth_headers(role="platform_admin"),
    )

    assert response.status_code == 200
    update_sql = fake_conn.statements[0][0]
    assert "UPDATE tenants SET" in update_sql
    assert "aws_config" in update_sql
    assert "updated_at=CURRENT_TIMESTAMP" in update_sql
    assert fake_conn.statements[0][1]["aws_config"] == {
        "secret_access_key": "updated-secret"
    }


@pytest.mark.asyncio
async def test_list_organizations_returns_tenant_counts(client, mock_session):
    org_id = uuid.uuid4()

    home_org_result = MagicMock()
    home_org_result.scalar_one_or_none = MagicMock(return_value=org_id)

    membership_result = MagicMock()
    membership_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[]))
    )

    organizations_result = MagicMock()
    organizations_result.all = MagicMock(
        return_value=[
            SimpleNamespace(
                id=org_id,
                name="Ankercloud",
                slug="ankercloud",
                status="active",
                tenant_count=3,
            ),
            SimpleNamespace(
                id=uuid.uuid4(),
                name="Beta Org",
                slug="beta-org",
                status="suspended",
                tenant_count=1,
            ),
        ]
    )

    mock_session.execute = AsyncMock(
        side_effect=[home_org_result, membership_result, organizations_result]
    )

    response = await client.get(
        "/api/v1/organizations",
        headers=_auth_headers(role="org_admin"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["slug"] == "ankercloud"
    assert body[0]["tenant_count"] == 3
    assert body[1]["status"] == "suspended"


@pytest.mark.asyncio
async def test_create_project_returns_created_project(client, mock_session):
    tenant_id = uuid.uuid4()
    duplicate_result = MagicMock()
    duplicate_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=duplicate_result)

    response = await client.post(
        f"/api/v1/tenants/{tenant_id}/projects",
        json={
            "name": "Project One",
            "slug": "project-one",
            "description": "Primary project",
        },
        headers=_auth_headers(role="tenant_admin", tenant_id=str(tenant_id)),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["tenant_id"] == str(tenant_id)
    assert body["slug"] == "project-one"
    created_project = mock_session.add.call_args.args[0]
    assert created_project.name == "Project One"
    assert created_project.slug == "project-one"


@pytest.mark.asyncio
async def test_create_organization_returns_created_org(client, mock_session):
    duplicate_result = MagicMock()
    duplicate_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=duplicate_result)

    response = await client.post(
        "/api/v1/organizations",
        json={"name": "Ankercloud", "slug": "ankercloud"},
        headers=_auth_headers(role="platform_admin"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Ankercloud"
    assert body["slug"] == "ankercloud"
    created_org = mock_session.add.call_args.args[0]
    assert created_org.name == "Ankercloud"
    assert created_org.slug == "ankercloud"


@pytest.mark.asyncio
async def test_invite_org_member_creates_pending_user_and_membership(client, mock_session, monkeypatch):
    from app.api.routes import organizations as organizations_routes

    organization_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    monkeypatch.setattr(
        organizations_routes,
        "authorize_org_admin",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        organizations_routes,
        "send_user_invitation_email",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        organizations_routes,
        "record_event",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        organizations_routes,
        "generate_invitation_token",
        lambda: "org-invite-token",
    )
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:5173")
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:5173")

    org_result = MagicMock()
    org_result.scalar_one_or_none = MagicMock(return_value=organization_id)

    tenant_result = MagicMock()
    tenant_result.first = MagicMock(return_value=SimpleNamespace(id=tenant_id))

    existing_user_result = MagicMock()
    existing_user_result.scalar_one_or_none = MagicMock(return_value=None)

    membership_result = MagicMock()
    membership_result.scalar_one_or_none = MagicMock(return_value=None)

    mock_session.execute = AsyncMock(
        side_effect=[
            org_result,
            tenant_result,
            existing_user_result,
            membership_result,
        ]
    )

    response = await client.post(
        f"/api/v1/organizations/{organization_id}/invite-user",
        json={
            "email": "new.org.member@example.com",
            "display_name": "New Org Member",
            "role": "operator",
        },
        headers=_auth_headers(role="org_admin"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.org.member@example.com"
    assert body["role"] == "operator"
    assert body["organization_id"] == str(organization_id)
    assert body["home_tenant_id"] == str(tenant_id)
    assert body["invitation_url"] == "http://localhost:5173/set-password?token=org-invite-token"

    created_user = mock_session.add.call_args_list[0].args[0]
    created_membership = mock_session.add.call_args_list[1].args[0]
    assert created_user.email == "new.org.member@example.com"
    assert created_user.tenant_id == tenant_id
    assert created_user.is_active is False
    assert created_user.invitation_token == "org-invite-token"
    assert created_membership.organization_id == organization_id
    assert created_membership.user_id == created_user.id
    assert created_membership.role == "operator"

    organizations_routes.send_user_invitation_email.assert_awaited_once()
    organizations_routes.record_event.assert_awaited_once()


@pytest.mark.asyncio
async def test_invite_org_member_allows_empty_organization_without_workspace(
    client, mock_session, monkeypatch
):
    from app.api.routes import organizations as organizations_routes

    organization_id = uuid.uuid4()

    monkeypatch.setattr(
        organizations_routes,
        "authorize_org_admin",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        organizations_routes,
        "send_user_invitation_email",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        organizations_routes,
        "record_event",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        organizations_routes,
        "generate_invitation_token",
        lambda: "org-empty-token",
    )
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:5173")

    org_result = MagicMock()
    org_result.scalar_one_or_none = MagicMock(return_value=organization_id)

    empty_tenant_result = MagicMock()
    empty_tenant_result.first = MagicMock(return_value=None)

    existing_user_result = MagicMock()
    existing_user_result.scalar_one_or_none = MagicMock(return_value=None)

    membership_result = MagicMock()
    membership_result.scalar_one_or_none = MagicMock(return_value=None)

    mock_session.execute = AsyncMock(
        side_effect=[
            org_result,
            empty_tenant_result,
            existing_user_result,
            membership_result,
        ]
    )

    response = await client.post(
        f"/api/v1/organizations/{organization_id}/invite-user",
        json={
            "email": "first.org.member@example.com",
            "display_name": "First Org Member",
            "role": "operator",
        },
        headers=_auth_headers(role="org_admin"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["home_tenant_id"] is None
    assert body["invitation_url"] == "http://localhost:5173/set-password?token=org-empty-token"

    created_user = mock_session.add.call_args_list[0].args[0]
    assert created_user.email == "first.org.member@example.com"
    assert created_user.tenant_id == uuid.UUID("00000000-0000-0000-0000-000000000000")
    assert created_user.is_active is False


@pytest.mark.asyncio
async def test_invite_org_member_returns_503_when_email_cannot_be_sent(
    client, mock_session, monkeypatch
):
    from app.api.routes import organizations as organizations_routes

    organization_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    monkeypatch.setattr(
        organizations_routes,
        "authorize_org_admin",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        organizations_routes,
        "send_user_invitation_email",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        organizations_routes,
        "record_event",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        organizations_routes,
        "generate_invitation_token",
        lambda: "org-email-fail-token",
    )
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:5173")

    org_result = MagicMock()
    org_result.scalar_one_or_none = MagicMock(return_value=organization_id)

    tenant_result = MagicMock()
    tenant_result.first = MagicMock(return_value=SimpleNamespace(id=tenant_id))

    existing_user_result = MagicMock()
    existing_user_result.scalar_one_or_none = MagicMock(return_value=None)

    mock_session.execute = AsyncMock(
        side_effect=[
            org_result,
            tenant_result,
            existing_user_result,
        ]
    )

    response = await client.post(
        f"/api/v1/organizations/{organization_id}/invite-user",
        json={
            "email": "org-mail-failure@example.com",
            "display_name": "Org Mail Failure",
            "role": "operator",
        },
        headers=_auth_headers(role="org_admin"),
    )

    assert response.status_code == 503
    assert (
        response.json()["detail"]
        == "Invitation email could not be sent. Check EMAIL_FROM and AWS SES configuration."
    )


@pytest.mark.asyncio
async def test_invite_org_member_keeps_existing_active_user_pending_until_acceptance(
    client, mock_session, monkeypatch
):
    from app.api.routes import organizations as organizations_routes

    organization_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    existing_user_id = uuid.uuid4()
    existing_user = SimpleNamespace(
        id=existing_user_id,
        email="existing.member@example.com",
        display_name="Existing Member",
        role="viewer",
        is_active=True,
        tenant_id=tenant_id,
    )

    monkeypatch.setattr(
        organizations_routes,
        "authorize_org_admin",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        organizations_routes,
        "send_existing_user_access_invitation_email",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        organizations_routes,
        "record_event",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        organizations_routes,
        "generate_invitation_token",
        lambda: "org-invite-token",
    )

    org_result = MagicMock()
    org_result.scalar_one_or_none = MagicMock(return_value=organization_id)

    tenant_result = MagicMock()
    tenant_result.first = MagicMock(return_value=SimpleNamespace(id=tenant_id))

    existing_user_result = MagicMock()
    existing_user_result.scalar_one_or_none = MagicMock(return_value=existing_user)

    membership_result = MagicMock()
    membership_result.scalar_one_or_none = MagicMock(return_value=None)

    mock_session.execute = AsyncMock(
        side_effect=[
            org_result,
            tenant_result,
            existing_user_result,
            membership_result,
        ]
    )

    response = await client.post(
        f"/api/v1/organizations/{organization_id}/invite-user",
        json={
            "email": "existing.member@example.com",
            "display_name": "Existing Member",
            "role": "admin",
        },
        headers=_auth_headers(role="org_admin"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "existing.member@example.com"
    assert body["role"] == "admin"
    assert body["organization_id"] == str(organization_id)
    assert body["home_tenant_id"] == str(tenant_id)
    assert body["status"] == "invited"
    assert body["delivery_mode"] == "accept_invitation"
    assert body["invitation_url"] == "http://localhost:5173/accept-invitation?token=org-invite-token"
    assert body["expires_at"] is not None

    created_membership = mock_session.add.call_args_list[-1].args[0]
    assert created_membership.organization_id == organization_id
    assert created_membership.user_id == existing_user_id
    assert created_membership.role == "pending_admin"
    assert existing_user.invitation_token == "org-invite-token"

    organizations_routes.send_existing_user_access_invitation_email.assert_awaited_once()
    organizations_routes.record_event.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_password_requires_workspace_for_unassigned_org_invite(
    client, mock_session
):
    invited_user = User(
        tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        email="pending.org.member@example.com",
        hashed_password=None,
        display_name="Pending Org Member",
        role="operator",
        is_active=False,
        invitation_token="pending-org-token",
        invitation_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )

    user_result = MagicMock()
    user_result.scalar_one_or_none = MagicMock(return_value=invited_user)
    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(side_effect=[user_result, tenant_result])

    response = await client.post(
        "/api/v1/auth/set-password",
        json={"invitation_token": "pending-org-token", "password": "Airex@2026!Temp"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Create a workspace in this organization before accepting this invitation"
    assert invited_user.is_active is False


@pytest.mark.asyncio
async def test_set_password_assigns_first_workspace_for_unassigned_org_invite(
    client, mock_session, monkeypatch
):
    from app.api.routes import auth as auth_routes

    tenant_id = uuid.uuid4()
    invited_user = User(
        tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        email="pending.org.member@example.com",
        hashed_password=None,
        display_name="Pending Org Member",
        role="operator",
        is_active=False,
        invitation_token="pending-org-token",
        invitation_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )

    user_result = MagicMock()
    user_result.scalar_one_or_none = MagicMock(return_value=invited_user)
    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none = MagicMock(return_value=tenant_id)
    mock_session.execute = AsyncMock(side_effect=[user_result, tenant_result])

    monkeypatch.setattr(auth_routes, "_get_org_id", AsyncMock(return_value=uuid.uuid4()))

    response = await client.post(
        "/api/v1/auth/set-password",
        json={"invitation_token": "pending-org-token", "password": "Airex@2026!Temp"},
    )

    assert response.status_code == 200
    assert invited_user.tenant_id == tenant_id
    assert invited_user.is_active is True
    assert invited_user.invitation_token is None


@pytest.mark.asyncio
async def test_set_password_rejects_existing_active_user_invite(
    client, mock_session, monkeypatch
):
    tenant_id = uuid.uuid4()
    invited_user = User(
        tenant_id=tenant_id,
        email="existing.member@example.com",
        hashed_password="existing-hash",
        display_name="Existing Member",
        role="operator",
        is_active=True,
        invitation_token="existing-org-token",
        invitation_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )

    user_result = MagicMock()
    user_result.scalar_one_or_none = MagicMock(return_value=invited_user)
    mock_session.execute = AsyncMock(side_effect=[user_result])

    response = await client.post(
        "/api/v1/auth/set-password",
        json={"invitation_token": "existing-org-token", "password": "Ignored@123"},
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "This invitation must be accepted by signing in to your existing account."
    )
    assert invited_user.hashed_password == "existing-hash"
    assert invited_user.invitation_token == "existing-org-token"


@pytest.mark.asyncio
async def test_accept_invitation_activates_pending_org_membership_for_existing_user(
    client, mock_session, monkeypatch
):
    from app.api.routes import auth as auth_routes

    tenant_id = uuid.uuid4()
    organization_id = uuid.uuid4()
    user_id = uuid.uuid4()
    invited_user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="existing.member@example.com",
        hashed_password="existing-hash",
        display_name="Existing Member",
        role="operator",
        is_active=True,
        invitation_token="existing-org-token",
        invitation_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    organization_membership = SimpleNamespace(role="pending_operator")

    user_result = MagicMock()
    user_result.scalar_one_or_none = MagicMock(return_value=invited_user)
    pending_membership_result = MagicMock()
    pending_membership_result.scalars = MagicMock(return_value=SimpleNamespace(all=lambda: [organization_membership]))
    mock_session.execute = AsyncMock(side_effect=[user_result, pending_membership_result])

    monkeypatch.setattr(auth_routes, "_get_org_id", AsyncMock(return_value=organization_id))

    access_token = create_access_token(
        tenant_id,
        "existing.member@example.com",
        user_id=user_id,
        role="operator",
        org_id=organization_id,
    )

    response = await client.post(
        "/api/v1/auth/accept-invitation",
        json={"invitation_token": "existing-org-token"},
        headers={**HEADERS, "Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert invited_user.invitation_token is None
    assert organization_membership.role == "operator"


@pytest.mark.asyncio
async def test_accept_invitation_requires_matching_signed_in_user(
    client, mock_session
):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    invited_user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="existing.member@example.com",
        hashed_password="existing-hash",
        display_name="Existing Member",
        role="operator",
        is_active=True,
        invitation_token="existing-org-token",
        invitation_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )

    user_result = MagicMock()
    user_result.scalar_one_or_none = MagicMock(return_value=invited_user)
    mock_session.execute = AsyncMock(side_effect=[user_result])

    access_token = create_access_token(
        tenant_id,
        "someone.else@example.com",
        user_id=uuid.uuid4(),
        role="operator",
    )

    response = await client.post(
        "/api/v1/auth/accept-invitation",
        json={"invitation_token": "existing-org-token"},
        headers={**HEADERS, "Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Sign in as 'existing.member@example.com' to accept this invitation."


@pytest.mark.asyncio
async def test_resend_org_invitation_uses_accept_invitation_for_existing_active_user(
    client, mock_session, monkeypatch
):
    from app.api.routes import organizations as organizations_routes

    organization_id = uuid.uuid4()
    user_id = uuid.uuid4()
    membership = SimpleNamespace(role="pending_admin")
    user = User(
        id=user_id,
        tenant_id=uuid.uuid4(),
        email="existing.member@example.com",
        hashed_password="existing-hash",
        display_name="Existing Member",
        role="operator",
        is_active=True,
        invitation_token="old-token",
        invitation_expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    row_result = MagicMock()
    row_result.one_or_none = MagicMock(return_value=(membership, user))
    mock_session.execute = AsyncMock(side_effect=[row_result])

    monkeypatch.setattr(organizations_routes, "authorize_org_admin", AsyncMock(return_value=True))
    monkeypatch.setattr(organizations_routes, "generate_invitation_token", lambda: "resent-org-token")
    monkeypatch.setattr(
        organizations_routes,
        "send_existing_user_access_invitation_email",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(organizations_routes, "record_event", AsyncMock(return_value=None))
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:5173")

    response = await client.post(
        f"/api/v1/organizations/{organization_id}/members/{user_id}/resend-invitation",
        headers=_auth_headers(role="org_admin"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "existing.member@example.com"
    assert body["delivery_mode"] == "accept_invitation"
    assert user.invitation_token == "resent-org-token"
    organizations_routes.send_existing_user_access_invitation_email.assert_awaited_once()


@pytest.mark.asyncio
async def test_resend_tenant_invitation_refreshes_pending_workspace_invite(
    client, mock_session, monkeypatch
):
    from app.api.routes import tenant_members as tenant_member_routes

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    membership = SimpleNamespace(tenant_id=tenant_id, user_id=user_id, role="viewer")
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="pending.workspace@example.com",
        hashed_password=None,
        display_name="Pending Workspace",
        role="viewer",
        is_active=False,
        invitation_token="old-workspace-token",
        invitation_expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    row_result = MagicMock()
    row_result.one_or_none = MagicMock(return_value=(membership, user))
    mock_session.execute = AsyncMock(side_effect=[row_result])

    monkeypatch.setattr(tenant_member_routes, "authorize_tenant_admin", AsyncMock(return_value=True))
    monkeypatch.setattr(tenant_member_routes, "generate_invitation_token", lambda: "resent-tenant-token")
    monkeypatch.setattr(tenant_member_routes, "send_user_invitation_email", AsyncMock(return_value=True))
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:5173")

    response = await client.post(
        f"/api/v1/tenants/{tenant_id}/members/{user_id}/resend-invitation",
        headers={
            **_auth_headers(role="admin", tenant_id=str(tenant_id)),
            "X-Tenant-Id": str(tenant_id),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "pending.workspace@example.com"
    assert user.invitation_token == "resent-tenant-token"
    tenant_member_routes.send_user_invitation_email.assert_awaited_once()


@pytest.mark.asyncio
async def test_invite_tenant_user_returns_503_when_email_cannot_be_sent(
    client, mock_session, monkeypatch
):
    from app.api.routes import tenant_members as tenant_member_routes

    tenant_id = uuid.uuid4()
    tenant = SimpleNamespace(id=tenant_id, organization_id=uuid.uuid4())

    monkeypatch.setattr(
        tenant_member_routes,
        "authorize_tenant_admin",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        tenant_member_routes,
        "send_user_invitation_email",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        tenant_member_routes,
        "generate_invitation_token",
        lambda: "tenant-email-fail-token",
    )
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:5173")

    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none = MagicMock(return_value=tenant)

    existing_user_result = MagicMock()
    existing_user_result.scalar_one_or_none = MagicMock(return_value=None)

    mock_session.execute = AsyncMock(side_effect=[tenant_result, existing_user_result])

    response = await client.post(
        f"/api/v1/tenants/{tenant_id}/invite-user",
        json={
            "email": "tenant-mail-failure@example.com",
            "display_name": "Tenant Mail Failure",
            "role": "viewer",
        },
        headers=_auth_headers(role="admin", tenant_id=str(tenant_id)),
    )

    assert response.status_code == 503
    assert (
        response.json()["detail"]
        == "Invitation email could not be sent. Check EMAIL_FROM and AWS SES configuration."
    )


@pytest.mark.asyncio
async def test_list_org_members_includes_user_status_fields(client, mock_session, monkeypatch):
    from app.api.routes import organizations as organizations_routes

    organization_id = uuid.uuid4()
    user_id = uuid.uuid4()
    created_at = datetime.now(timezone.utc)

    monkeypatch.setattr(
        organizations_routes,
        "authorize_org_admin",
        AsyncMock(return_value=True),
    )

    membership = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        organization_id=organization_id,
        role="viewer",
        created_at=created_at,
    )
    user = SimpleNamespace(
        id=user_id,
        email="pending.org.member@example.com",
        display_name="Pending Org Member",
        is_active=False,
        invitation_token="invite-token",
        invitation_expires_at=created_at + timedelta(days=7),
        hashed_password=None,
    )

    result = MagicMock()
    result.all = MagicMock(return_value=[(membership, user)])
    mock_session.execute = AsyncMock(return_value=result)

    response = await client.get(
        f"/api/v1/organizations/{organization_id}/members",
        headers=_auth_headers(role="org_admin"),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(membership.id)
    assert body[0]["user_id"] == str(user_id)
    assert body[0]["organization_id"] == str(organization_id)
    assert body[0]["role"] == "viewer"
    assert body[0]["email"] == "pending.org.member@example.com"
    assert body[0]["display_name"] == "Pending Org Member"
    assert body[0]["is_active"] is False
    assert body[0]["invitation_status"] == "pending"
    assert body[0]["created_at"].startswith(created_at.strftime("%Y-%m-%dT%H:%M:%S"))


@pytest.mark.asyncio
async def test_add_org_member_endpoint_is_removed(client):
    response = await client.post(
        f"/api/v1/organizations/{uuid.uuid4()}/members",
        json={"user_id": str(uuid.uuid4()), "role": "viewer"},
        headers=_auth_headers(role="admin"),
    )

    assert response.status_code == 405


@pytest.mark.asyncio
async def test_add_tenant_member_endpoint_is_removed(client):
    tenant_id = uuid.uuid4()
    response = await client.post(
        f"/api/v1/tenants/{tenant_id}/members",
        json={"user_id": str(uuid.uuid4()), "role": "viewer"},
        headers={
            **_auth_headers(role="admin", tenant_id=str(tenant_id)),
            "X-Tenant-Id": str(tenant_id),
        },
    )

    assert response.status_code == 405


@pytest.mark.asyncio
async def test_list_integrations_allows_org_admin_for_sibling_tenant(
    client, mock_session, monkeypatch
):
    from app.api.routes import integrations as integration_routes

    home_tenant_id = uuid.UUID(TENANT_ID)
    sibling_tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()

    tenant_lookup = MagicMock()
    tenant_lookup.first = MagicMock(
        return_value=SimpleNamespace(
            id=sibling_tenant_id,
            organization_id=org_id,
            is_active=True,
        )
    )
    org_membership = MagicMock()
    org_membership.scalar_one_or_none = MagicMock(return_value="org_admin")
    mock_session.execute = AsyncMock(side_effect=[tenant_lookup, org_membership])

    fake_conn = _FakeConnection(
        responses=[
            [
                SimpleNamespace(
                    id=uuid.uuid4(),
                    tenant_id=sibling_tenant_id,
                    integration_type_id=uuid.uuid4(),
                    integration_type_key="site24x7",
                    organization_slug=ORG_SLUG,
                    tenant_slug=TENANT_SLUG,
                    name="Primary Site24x7",
                    slug="primary-site24x7",
                    enabled=True,
                    config_json={"mode": "webhook"},
                    secret_ref="secret://site24x7",
                    webhook_token_ref="secret://site24x7-webhook",
                    status="configured",
                    last_tested_at=None,
                    last_sync_at=None,
                )
            ]
        ]
    )
    monkeypatch.setattr(
        integration_routes,
        "async_engine",
        _FakeEngine(connect_conn=fake_conn),
    )

    response = await client.get(
        f"/api/v1/tenants/{sibling_tenant_id}/integrations",
        headers=_auth_headers(role="org_admin", tenant_id=str(home_tenant_id)),
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["tenant_id"] == str(sibling_tenant_id)
    assert body[0]["integration_type_key"] == "site24x7"
    assert body[0]["webhook_path"] == f"/api/v1/webhooks/{ORG_SLUG}/{TENANT_SLUG}/default/primary-site24x7"


@pytest.mark.asyncio
async def test_list_tenant_members_allows_org_admin_for_managed_tenant(client, mock_session):
    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    membership_id = uuid.uuid4()
    created_at = datetime.now(timezone.utc)

    tenant_org_lookup = MagicMock()
    tenant_org_lookup.scalar_one_or_none = MagicMock(return_value=org_id)
    org_membership_lookup = MagicMock()
    org_membership_lookup.scalar_one_or_none = MagicMock(return_value="org_admin")
    member_rows = MagicMock()
    member_rows.all = MagicMock(
        return_value=[
            (
                SimpleNamespace(
                    id=membership_id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    role="viewer",
                    created_at=created_at,
                ),
                "workspace.user@example.com",
                "Workspace User",
                True,
            )
        ]
    )
    mock_session.execute = AsyncMock(
        side_effect=[tenant_org_lookup, org_membership_lookup, member_rows]
    )

    response = await client.get(
        f"/api/v1/tenants/{tenant_id}/members",
        headers={
            **_auth_headers(role="viewer", tenant_id=str(tenant_id)),
            "X-Tenant-Id": str(tenant_id),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["tenant_id"] == str(tenant_id)
    assert body[0]["user_id"] == str(user_id)
    assert body[0]["role"] == "viewer"
    assert body[0]["email"] == "workspace.user@example.com"
    assert body[0]["display_name"] == "Workspace User"


@pytest.mark.asyncio
async def test_create_runbook_allows_org_admin_for_active_tenant(client, mock_session):
    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()

    tenant_org_lookup = MagicMock()
    tenant_org_lookup.scalar_one_or_none = MagicMock(return_value=org_id)
    org_membership_lookup = MagicMock()
    org_membership_lookup.scalar_one_or_none = MagicMock(return_value="org_admin")
    mock_session.execute = AsyncMock(side_effect=[tenant_org_lookup, org_membership_lookup])

    response = await client.post(
        "/api/v1/runbooks/",
        json={
            "name": "CPU Recovery",
            "alert_type": "cpu_high",
            "description": "Restart the service and verify recovery.",
            "steps": [],
        },
        headers={
            **_auth_headers(role="viewer", tenant_id=str(tenant_id)),
            "X-Tenant-Id": str(tenant_id),
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["tenant_id"] == str(tenant_id)
    assert body["name"] == "CPU Recovery"
    assert body["alert_type"] == "cpu_high"


@pytest.mark.asyncio
async def test_update_org_member_rejects_self_role_change(client, monkeypatch):
    from app.api.routes import organizations as organization_routes

    user_id = uuid.uuid4()
    monkeypatch.setattr(
        organization_routes,
        "authorize_org_admin",
        AsyncMock(return_value=True),
    )

    response = await client.patch(
        f"/api/v1/organizations/{uuid.uuid4()}/members/{user_id}",
        json={"role": "viewer"},
        headers=_auth_headers(role="admin", user_id=user_id),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Use another organization admin to change your own role"


@pytest.mark.asyncio
async def test_remove_tenant_member_rejects_self_removal(client, monkeypatch):
    from app.api.routes import tenant_members as tenant_member_routes

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    monkeypatch.setattr(
        tenant_member_routes,
        "authorize_tenant_admin",
        AsyncMock(return_value=True),
    )

    response = await client.delete(
        f"/api/v1/tenants/{tenant_id}/members/{user_id}",
        headers={
            **_auth_headers(role="admin", tenant_id=str(tenant_id), user_id=user_id),
            "X-Tenant-Id": str(tenant_id),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Use another workspace admin to remove your own access"


@pytest.mark.asyncio
async def test_remove_org_member_rejects_self_removal(client, monkeypatch):
    from app.api.routes import organizations as organization_routes

    organization_id = uuid.uuid4()
    user_id = uuid.uuid4()
    monkeypatch.setattr(
        organization_routes,
        "authorize_org_admin",
        AsyncMock(return_value=True),
    )

    response = await client.delete(
        f"/api/v1/organizations/{organization_id}/members/{user_id}",
        headers=_auth_headers(role="admin", user_id=user_id),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Use another organization admin to remove your own access"


@pytest.mark.asyncio
async def test_invite_tenant_user_returns_already_has_access_for_org_member(
    client, mock_session, monkeypatch
):
    from app.api.routes import tenant_members as tenant_member_routes

    tenant_id = uuid.uuid4()
    organization_id = uuid.uuid4()
    user_id = uuid.uuid4()
    existing_user = SimpleNamespace(
        id=user_id,
        email="existing.member@example.com",
        display_name="Existing Member",
        role="viewer",
        is_active=True,
    )

    monkeypatch.setattr(
        tenant_member_routes,
        "authorize_tenant_admin",
        AsyncMock(return_value=True),
    )

    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none = MagicMock(
        return_value=SimpleNamespace(id=tenant_id, organization_id=organization_id)
    )
    existing_user_result = MagicMock()
    existing_user_result.scalar_one_or_none = MagicMock(return_value=existing_user)
    tenant_membership_result = MagicMock()
    tenant_membership_result.scalar_one_or_none = MagicMock(return_value=None)
    org_membership_result = MagicMock()
    org_membership_result.scalar_one_or_none = MagicMock(return_value=uuid.uuid4())
    mock_session.execute = AsyncMock(
        side_effect=[
            tenant_result,
            existing_user_result,
            tenant_membership_result,
            org_membership_result,
        ]
    )

    response = await client.post(
        f"/api/v1/tenants/{tenant_id}/invite-user",
        json={
            "email": "existing.member@example.com",
            "display_name": "Existing Member",
            "role": "operator",
        },
        headers={
            **_auth_headers(role="admin", tenant_id=str(tenant_id)),
            "X-Tenant-Id": str(tenant_id),
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "existing.member@example.com"
    assert body["status"] == "already_has_access"
    assert body["invitation_url"] is None
    assert body["expires_at"] is None


@pytest.mark.asyncio
async def test_update_tenant_member_rejects_self_role_change(client, monkeypatch):
    from app.api.routes import tenant_members as tenant_member_routes

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    monkeypatch.setattr(
        tenant_member_routes,
        "authorize_tenant_admin",
        AsyncMock(return_value=True),
    )

    response = await client.patch(
        f"/api/v1/tenants/{tenant_id}/members/{user_id}",
        json={"role": "viewer"},
        headers={
            **_auth_headers(role="admin", tenant_id=str(tenant_id), user_id=user_id),
            "X-Tenant-Id": str(tenant_id),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Use another workspace admin to change your own role"


@pytest.mark.asyncio
async def test_list_integrations_rejects_unrelated_tenant_access(client, mock_session):
    sibling_tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()

    tenant_lookup = MagicMock()
    tenant_lookup.first = MagicMock(
        return_value=SimpleNamespace(
            id=sibling_tenant_id,
            organization_id=org_id,
            is_active=True,
        )
    )
    org_membership = MagicMock()
    org_membership.scalar_one_or_none = MagicMock(return_value=None)
    tenant_membership = MagicMock()
    tenant_membership.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(
        side_effect=[tenant_lookup, org_membership, tenant_membership]
    )

    response = await client.get(
        f"/api/v1/tenants/{sibling_tenant_id}/integrations",
        headers=_auth_headers(role="tenant_viewer"),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized for tenant"


@pytest.mark.asyncio
async def test_tenant_list_rejects_non_viewer_role(client):
    token = create_access_token(
        uuid.UUID(TENANT_ID),
        "guest@example.com",
        user_id=uuid.uuid4(),
        role="guest",
    )

    response = await client.get(
        "/api/v1/tenants/",
        headers={**HEADERS, "Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"]


@pytest.mark.asyncio
async def test_tenant_detail_allows_viewer_role(client, monkeypatch):
    from app.api.routes import tenants as tenant_routes

    token = create_access_token(
        uuid.UUID(TENANT_ID),
        "viewer@example.com",
        user_id=uuid.uuid4(),
        role="viewer",
    )
    fake_conn = _FakeConnection(
        responses=[
            _FakeExecuteResult(
                first_row=(
                    uuid.uuid4(),
                    "viewer-visible-tenant",
                    "Viewer Visible Tenant",
                    "gcp",
                    True,
                    uuid.uuid4(),
                    "viewer@example.com",
                    "#viewer",
                    "ubuntu",
                    {},
                    {"project_id": "viewer-project"},
                    [],
                )
            )
        ]
    )
    monkeypatch.setattr(
        tenant_routes,
        "async_engine",
        _FakeEngine(connect_conn=fake_conn),
    )
    monkeypatch.setattr("airex_core.cloud.tenant_config.get_config_source", lambda: "db")

    response = await client.get(
        "/api/v1/tenants/viewer-visible-tenant",
        headers={**HEADERS, "Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "viewer-visible-tenant"


@pytest.mark.asyncio
async def test_tenant_detail_redacts_secret_access_key(client, monkeypatch):
    from app.api.routes import tenants as tenant_routes

    fake_conn = _FakeConnection(
        responses=[
            _FakeExecuteResult(
                first_row=(
                    uuid.uuid4(),
                    "aws-secret-test",
                    "AWS Secret Test",
                    "aws",
                    True,
                    uuid.uuid4(),
                    "ops@example.com",
                    "#ops",
                    "ubuntu",
                    {
                        "account_id": "123456789012",
                        "access_key_id": "AKIATEST",
                        "secret_access_key": "super-secret",
                    },
                    {},
                    [],
                )
            )
        ]
    )
    monkeypatch.setattr(
        tenant_routes,
        "async_engine",
        _FakeEngine(connect_conn=fake_conn),
    )
    monkeypatch.setattr("airex_core.cloud.tenant_config.get_config_source", lambda: "db")

    response = await client.get("/api/v1/tenants/aws-secret-test")

    assert response.status_code == 200
    assert response.json()["aws_config"]["secret_access_key"] == "••••••••"
    assert response.json()["config_source"] == "db"


@pytest.mark.asyncio
async def test_list_organizations_returns_visible_orgs(client, mock_session):
    org_id = uuid.uuid4()
    home_org_result = MagicMock()
    home_org_result.scalar_one_or_none = MagicMock(return_value=org_id)

    membership_result = MagicMock()
    membership_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[]))
    )

    org_rows = MagicMock()
    org_rows.all = MagicMock(
        return_value=[
            SimpleNamespace(
                id=org_id,
                name="Ankercloud",
                slug="ankercloud",
                status="active",
                tenant_count=3,
            )
        ]
    )
    mock_session.execute = AsyncMock(
        side_effect=[home_org_result, membership_result, org_rows]
    )

    response = await client.get(
        "/api/v1/organizations",
        headers=_auth_headers(role="org_admin"),
    )

    assert response.status_code == 200
    assert response.json()[0]["slug"] == "ankercloud"
    assert response.json()[0]["tenant_count"] == 3


@pytest.mark.asyncio
async def test_list_organization_tenants_limits_home_org_user_to_accessible_tenants(
    client, mock_session, monkeypatch
):
    from app.api.routes import organizations as organization_routes

    organization_id = uuid.uuid4()
    home_tenant_id = uuid.UUID(TENANT_ID)
    sibling_tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    monkeypatch.setattr(
        organization_routes,
        "authorize_org_access",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        organization_routes,
        "authorize_org_admin",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        organization_routes,
        "has_org_membership",
        AsyncMock(return_value=False),
    )

    tenant_membership_rows = MagicMock()
    tenant_membership_rows.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[sibling_tenant_id]))
    )
    tenant_rows = MagicMock()
    tenant_rows.scalars = MagicMock(
        return_value=MagicMock(
            all=MagicMock(
                return_value=[
                    SimpleNamespace(
                        id=home_tenant_id,
                        name="home-tenant",
                        display_name="Home Tenant",
                        cloud="aws",
                        is_active=True,
                        organization_id=organization_id,
                    ),
                    SimpleNamespace(
                        id=sibling_tenant_id,
                        name="sibling-tenant",
                        display_name="Sibling Tenant",
                        cloud="gcp",
                        is_active=True,
                        organization_id=organization_id,
                    ),
                ]
            )
        )
    )
    mock_session.execute = AsyncMock(
        side_effect=[tenant_membership_rows, tenant_rows]
    )

    response = await client.get(
        f"/api/v1/organizations/{organization_id}/tenants",
        headers=_auth_headers(
            role="tenant_viewer",
            tenant_id=str(home_tenant_id),
            user_id=user_id,
        ),
    )

    assert response.status_code == 200
    assert {tenant["id"] for tenant in response.json()} == {
        str(home_tenant_id),
        str(sibling_tenant_id),
    }


@pytest.mark.asyncio
async def test_create_tenant_under_organization_sets_organization_id(client, mock_session):
    organization_id = uuid.uuid4()
    home_org_result = MagicMock()
    home_org_result.scalar_one_or_none = MagicMock(return_value=organization_id)
    organization_result = MagicMock()
    organization_result.scalar_one_or_none = MagicMock(return_value=organization_id)
    duplicate_check = MagicMock()
    duplicate_check.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(
        side_effect=[home_org_result, organization_result, duplicate_check]
    )

    response = await client.post(
        f"/api/v1/organizations/{organization_id}/tenants",
        json={
            "name": "uno-secur",
            "display_name": "UnoSecur",
            "cloud": "aws",
            "aws_config": {"account_id": "123456789012"},
        },
        headers=_auth_headers(role="org_admin"),
    )

    assert response.status_code == 201
    created_tenant = mock_session.add.call_args.args[0]
    assert created_tenant.organization_id == organization_id
    assert created_tenant.aws_config == {"account_id": "123456789012"}


@pytest.mark.asyncio
async def test_list_projects_for_tenant_returns_projects(client, mock_session):
    tenant_uuid = uuid.UUID(TENANT_ID)
    rows = MagicMock()
    rows.scalars = MagicMock(
        return_value=MagicMock(
            all=MagicMock(
                return_value=[
                    SimpleNamespace(
                        id=uuid.uuid4(),
                        tenant_id=tenant_uuid,
                        name="Project 1",
                        slug="project-1",
                        description="Primary app",
                        is_active=True,
                    )
                ]
            )
        )
    )
    mock_session.execute = AsyncMock(return_value=rows)

    response = await client.get(
        f"/api/v1/tenants/{tenant_uuid}/projects",
        headers=_auth_headers(role="tenant_viewer", tenant_id=str(tenant_uuid)),
    )

    assert response.status_code == 200
    assert response.json()[0]["slug"] == "project-1"


@pytest.mark.asyncio
async def test_create_project_for_tenant_persists_project(client, mock_session):
    tenant_uuid = uuid.UUID(TENANT_ID)
    duplicate_check = MagicMock()
    duplicate_check.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=duplicate_check)

    response = await client.post(
        f"/api/v1/tenants/{tenant_uuid}/projects",
        json={
            "name": "Project 1",
            "slug": "project-1",
            "description": "Primary app",
            "is_active": True,
        },
        headers=_auth_headers(role="tenant_admin"),
    )

    assert response.status_code == 201
    created_project = mock_session.add.call_args.args[0]
    assert created_project.tenant_id == tenant_uuid
    assert created_project.slug == "project-1"


@pytest.mark.asyncio
async def test_create_integration_for_tenant_uses_jsonb_cast(client, mock_session, monkeypatch):
    from app.api.routes import integrations as integration_routes

    tenant_uuid = uuid.UUID(TENANT_ID)
    integration_type_row = SimpleNamespace(id=uuid.uuid4(), key="site24x7")

    fake_conn = _FakeConnection(
        responses=[
            _FakeExecuteResult(
                first_row=SimpleNamespace(
                    id=tenant_uuid,
                    organization_slug=ORG_SLUG,
                    tenant_slug=TENANT_SLUG,
                )
            ),
            _FakeExecuteResult(first_row=integration_type_row),
            _FakeExecuteResult(first_row=None),
            _FakeExecuteResult(),
        ]
    )
    monkeypatch.setattr(
        integration_routes,
        "async_engine",
        _FakeEngine(begin_conn=fake_conn),
    )

    response = await client.post(
        f"/api/v1/tenants/{tenant_uuid}/integrations",
        json={
            "integration_type_key": "site24x7",
            "name": "Tenant Site24x7",
            "slug": "site24x7-primary",
            "config_json": {"account": "tenant-a"},
        },
        headers=_auth_headers(role="tenant_admin", tenant_id=str(tenant_uuid)),
    )

    assert response.status_code == 201
    assert response.json()["webhook_path"] == (
        f"/api/v1/webhooks/{ORG_SLUG}/{TENANT_SLUG}/default/site24x7-primary"
    )
    insert_sql, insert_params = fake_conn.statements[3]
    assert "CAST(:config_json AS jsonb)" in insert_sql
    assert insert_params["tenant_id"] == str(tenant_uuid)


@pytest.mark.asyncio
async def test_create_cloud_account_uses_jsonb_cast(client, mock_session, monkeypatch):
    from app.api.routes import cloud_accounts as cloud_account_routes

    tenant_uuid = uuid.UUID(TENANT_ID)
    created_at = datetime.now(timezone.utc)
    binding_id = uuid.uuid4()
    row = {
        "id": binding_id,
        "tenant_id": tenant_uuid,
        "provider": "aws",
        "display_name": "Production AWS",
        "external_account_id": "123456789012",
        "config_json": {"region": "us-east-1"},
        "credentials_secret_arn": None,
        "is_default": False,
        "created_at": created_at,
        "updated_at": created_at,
    }
    insert_result = MagicMock()
    insert_result.mappings.return_value.one.return_value = row

    monkeypatch.setattr(
        cloud_account_routes,
        "authorize_tenant_admin",
        AsyncMock(return_value=True),
    )
    mock_session.execute = AsyncMock(return_value=insert_result)

    response = await client.post(
        "/api/v1/cloud-accounts",
        json={
            "provider": "aws",
            "display_name": "Production AWS",
            "external_account_id": "123456789012",
            "config_json": {"region": "us-east-1"},
        },
        headers=_auth_headers(role="tenant_admin", tenant_id=str(tenant_uuid)),
    )

    assert response.status_code == 201
    insert_sql = str(mock_session.execute.await_args.args[0])
    insert_params = mock_session.execute.await_args.args[1]
    assert "CAST(:config_json AS jsonb)" in insert_sql
    assert insert_params["tenant_id"] == tenant_uuid
    assert insert_params["config_json"] == json.dumps({"region": "us-east-1"})


@pytest.mark.asyncio
async def test_update_cloud_account_uses_jsonb_cast(client, mock_session, monkeypatch):
    from app.api.routes import cloud_accounts as cloud_account_routes

    tenant_uuid = uuid.UUID(TENANT_ID)
    binding_id = uuid.uuid4()
    updated_at = datetime.now(timezone.utc)

    existing_result = MagicMock()
    existing_result.mappings.return_value.one_or_none.return_value = {
        "id": binding_id,
        "provider": "aws",
    }
    update_result = MagicMock()
    update_result.mappings.return_value.one.return_value = {
        "id": binding_id,
        "tenant_id": tenant_uuid,
        "provider": "aws",
        "display_name": "Updated AWS",
        "external_account_id": "123456789012",
        "config_json": {"region": "us-west-2"},
        "credentials_secret_arn": None,
        "is_default": False,
        "created_at": updated_at,
        "updated_at": updated_at,
    }

    monkeypatch.setattr(
        cloud_account_routes,
        "authorize_tenant_admin",
        AsyncMock(return_value=True),
    )
    mock_session.execute = AsyncMock(side_effect=[existing_result, update_result])

    response = await client.put(
        f"/api/v1/cloud-accounts/{binding_id}",
        json={"display_name": "Updated AWS", "config_json": {"region": "us-west-2"}},
        headers=_auth_headers(role="tenant_admin", tenant_id=str(tenant_uuid)),
    )

    assert response.status_code == 200
    update_sql = str(mock_session.execute.await_args_list[1].args[0])
    update_params = mock_session.execute.await_args_list[1].args[1]
    assert "config_json = CAST(:p_config_json AS jsonb)" in update_sql
    assert update_params["tenant_id"] == tenant_uuid
    assert update_params["p_config_json"] == json.dumps({"region": "us-west-2"})


@pytest.mark.asyncio
async def test_create_cloud_account_returns_boto_error_detail_for_secret_provisioning(
    client, mock_session, monkeypatch
):
    import botocore.exceptions

    from app.api.routes import cloud_accounts as cloud_account_routes

    tenant_uuid = uuid.UUID(TENANT_ID)

    monkeypatch.setattr(
        cloud_account_routes,
        "authorize_tenant_admin",
        AsyncMock(return_value=True),
    )

    class _BrokenSecretsClient:
        def create_secret(self, **kwargs):
            raise botocore.exceptions.NoCredentialsError()

    class _FakeBoto3:
        @staticmethod
        def client(service_name, region_name=None):
            assert service_name == "secretsmanager"
            return _BrokenSecretsClient()

    monkeypatch.setitem(__import__("sys").modules, "boto3", _FakeBoto3())

    response = await client.post(
        "/api/v1/cloud-accounts",
        json={
            "provider": "aws",
            "display_name": "Production AWS",
            "external_account_id": "123456789012",
            "config_json": {"region": "us-east-1"},
            "aws_credentials": {
                "access_key_id": "AKIA1234567890ABCD",
                "secret_access_key": "secret-value",
            },
        },
        headers=_auth_headers(role="tenant_admin", tenant_id=str(tenant_uuid)),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "Failed to provision Secrets Manager secret: NoCredentialsError"
    )
    mock_session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_integration_rejects_malformed_integration_type_id(client):
    tenant_uuid = uuid.UUID(TENANT_ID)

    response = await client.post(
        f"/api/v1/tenants/{tenant_uuid}/integrations",
        json={
            "integration_type_id": "not-a-uuid",
            "name": "Tenant Site24x7",
            "slug": "site24x7-primary",
            "config_json": {"account": "tenant-a"},
        },
        headers=_auth_headers(role="tenant_admin", tenant_id=str(tenant_uuid)),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_site24x7_integration_webhook_uses_integration_tenant(
    client, mock_session, monkeypatch
):
    from app.api.routes import webhooks as webhook_routes
    from airex_core.schemas.incident import IncidentCreatedResponse

    integration_id = uuid.uuid4()
    integration_tenant_id = uuid.uuid4()
    captured = {}

    async def fake_resolve_tenant(session, org_slug, tenant_slug):
        assert org_slug == ORG_SLUG
        assert tenant_slug == TENANT_SLUG
        return integration_tenant_id

    async def fake_resolve(session, expected_tenant_id, account_slug, integration_slug):
        assert expected_tenant_id == integration_tenant_id
        assert account_slug == "547361935557"
        assert integration_slug == "tenant-site24x7"
        return webhook_routes.Site24x7IntegrationContext(
            integration_id=integration_id,
            tenant_id=integration_tenant_id,
            integration_name="Tenant Site24x7",
            integration_slug="tenant-site24x7",
            integration_type_key="site24x7",
            enabled=True,
            status="configured",
        )

    async def fake_ingest(request, *, tenant_id, session, redis, integration_context, tenant_slug):
        captured["tenant_id"] = tenant_id
        captured["integration_context"] = integration_context
        captured["tenant_slug"] = tenant_slug
        return IncidentCreatedResponse(incident_id=uuid.uuid4())

    monkeypatch.setattr(webhook_routes, "_resolve_tenant_by_slugs", fake_resolve_tenant)
    monkeypatch.setattr(webhook_routes, "_resolve_site24x7_integration_context", fake_resolve)
    monkeypatch.setattr(webhook_routes, "_ingest_site24x7_request", fake_ingest)

    response = await client.post(
        f"/api/v1/webhooks/{ORG_SLUG}/{TENANT_SLUG}/547361935557/tenant-site24x7",
        json={"monitor_id": "monitor-1", "monitor_name": "Web-01", "status": "down"},
    )

    assert response.status_code == 202
    assert captured["tenant_id"] == integration_tenant_id
    assert captured["integration_context"].integration_id == integration_id
    assert captured["tenant_slug"] == TENANT_SLUG


@pytest.mark.asyncio
async def test_merge_site24x7_integration_meta_adds_project_and_integration_context():
    from app.api.routes import webhooks as webhook_routes

    integration_id = uuid.uuid4()
    project_id = uuid.uuid4()

    meta = webhook_routes._merge_site24x7_integration_meta(
        {"monitor_name": "CPU Alert"},
        webhook_routes.Site24x7IntegrationContext(
            integration_id=integration_id,
            tenant_id=uuid.uuid4(),
            integration_name="Primary Site24x7",
            integration_slug="primary-site24x7",
            integration_type_key="site24x7",
            enabled=True,
        ),
        webhook_routes.Site24x7ProjectBinding(
            project_id=project_id,
            project_name="Project One",
            project_slug="project-one",
            alert_type_override="cpu_high",
        ),
    )

    assert meta["_integration_id"] == str(integration_id)
    assert meta["_integration_slug"] == "primary-site24x7"
    assert meta["project_id"] == str(project_id)
    assert meta["project_slug"] == "project-one"


def test_annotate_tenant_tag_mismatch_preserves_path_authority():
    from app.api.routes import webhooks as webhook_routes

    meta = webhook_routes._annotate_tenant_tag_mismatch(
        {"_source": "site24x7"},
        tenant_slug="workspace-alpha",
        tenant_tag="beta-workspace",
    )

    assert meta["_tenant_tag_mismatch"] == {
        "path_tenant": "workspace-alpha",
        "tag_tenant": "beta-workspace",
    }


@pytest.mark.asyncio
async def test_create_project_monitor_binding_enforces_same_tenant(client, monkeypatch):
    from app.api.routes import integrations as integration_routes

    project_id = uuid.uuid4()
    project_tenant_id = uuid.UUID(TENANT_ID)
    monitor_id = uuid.uuid4()

    from unittest.mock import MagicMock
    from app.api.dependencies import get_auth_session

    project_lookup = MagicMock()
    project_lookup.first = MagicMock(return_value=SimpleNamespace(tenant_id=project_tenant_id))
    auth_session = AsyncMock()
    auth_session.execute = AsyncMock(return_value=project_lookup)

    async def override_auth_session():
        yield auth_session

    app.dependency_overrides[get_auth_session] = override_auth_session

    fake_conn = _FakeConnection(
        responses=[
            _FakeExecuteResult(first_row=SimpleNamespace(tenant_id=project_tenant_id)),
            _FakeExecuteResult(first_row=None),
        ]
    )
    monkeypatch.setattr(
        integration_routes,
        "async_engine",
        _FakeEngine(begin_conn=fake_conn),
    )

    response = await client.post(
        f"/api/v1/projects/{project_id}/monitor-bindings",
        json={
            "external_monitor_id": str(monitor_id),
            "resource_mapping_json": {"host_key": "web-01"},
        },
        headers=_auth_headers(role="admin", tenant_id=str(project_tenant_id)),
    )

    assert response.status_code == 404
    assert "project tenant" in response.json()["detail"]
    app.dependency_overrides.pop(get_auth_session, None)


@pytest.mark.asyncio
async def test_create_project_monitor_binding_rejects_malformed_external_monitor_id(client):
    project_id = uuid.uuid4()

    response = await client.post(
        f"/api/v1/projects/{project_id}/monitor-bindings",
        json={
            "external_monitor_id": "not-a-uuid",
            "enabled": True,
        },
        headers=_auth_headers(role="tenant_admin"),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_platform_analytics_returns_platform_summary(
    client, mock_session, mock_platform_admin_session, mock_redis
):
    def count_result(value):
        result = MagicMock()
        result.scalar_one = MagicMock(return_value=value)
        return result

    mock_session.execute = AsyncMock(
        side_effect=[
            count_result(12),
            count_result(9),
            count_result(5),
            count_result(4),
            count_result(11),
            count_result(8),
            count_result(6),
            count_result(2),
            count_result(3),
            count_result(15),
        ]
    )
    mock_platform_admin_session.execute = AsyncMock(
        side_effect=[count_result(2), count_result(1)]
    )
    mock_redis.llen = AsyncMock(return_value=4)
    mock_redis.get = AsyncMock(return_value=b'{"is_open": true}')

    response = await client.get(
        "/api/v1/platform/analytics",
        headers=_auth_headers(role="platform_admin"),
    )

    assert response.status_code == 200
    assert response.json() == {
        "total_users": 12,
        "active_users": 9,
        "total_platform_admins": 2,
        "active_platform_admins": 1,
        "total_organizations": 5,
        "active_organizations": 4,
        "total_tenants": 11,
        "active_tenants": 8,
        "active_incidents": 6,
        "critical_incidents": 2,
        "failed_incidents_24h": 3,
        "total_incidents_24h": 15,
        "platform_error_rate_24h": 0.2,
        "dlq_entries": 4,
        "llm_circuit_breaker_open": True,
    }


@pytest.mark.asyncio
async def test_list_platform_admins_returns_isolated_accounts(client, mock_platform_admin_session):
    admin_id = uuid.uuid4()
    result = MagicMock()
    result.scalars = MagicMock(
        return_value=MagicMock(
            all=MagicMock(
                return_value=[
                    SimpleNamespace(
                        id=admin_id,
                        email="airex@ankercloud.com",
                        display_name="Platform Admin",
                        is_active=True,
                    )
                ]
            )
        )
    )
    mock_platform_admin_session.execute = AsyncMock(return_value=result)

    response = await client.get(
        "/api/v1/platform/admins",
        headers=_auth_headers(role="platform_admin", user_id=admin_id),
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": str(admin_id),
                "email": "airex@ankercloud.com",
                "display_name": "Platform Admin",
                "is_active": True,
                "role": "platform_admin",
            }
        ]
    }


@pytest.mark.asyncio
async def test_create_platform_admin_hashes_password(client, mock_platform_admin_session, monkeypatch):
    from app.api.routes import platform_admin as platform_admin_routes

    empty_lookup = MagicMock()
    empty_lookup.scalar_one_or_none = MagicMock(return_value=None)
    mock_platform_admin_session.execute = AsyncMock(return_value=empty_lookup)
    monkeypatch.setattr(
        platform_admin_routes,
        "hash_password",
        lambda password: f"hashed::{password}",
    )

    response = await client.post(
        "/api/v1/platform/admins",
        json={
            "email": "OPS@Example.com",
            "display_name": "Ops Admin",
            "password": "StrongPass123",
        },
        headers=_auth_headers(role="platform_admin"),
    )

    assert response.status_code == 201
    created_admin = mock_platform_admin_session.add.call_args[0][0]
    assert created_admin.email == "ops@example.com"
    assert created_admin.display_name == "Ops Admin"
    assert created_admin.hashed_password == "hashed::StrongPass123"
    assert response.json()["email"] == "ops@example.com"


@pytest.mark.asyncio
async def test_update_platform_admin_blocks_self_deactivate(client, mock_platform_admin_session):
    admin_id = uuid.uuid4()
    admin = SimpleNamespace(
        id=admin_id,
        email="airex@ankercloud.com",
        display_name="Platform Admin",
        hashed_password="hashed",
        is_active=True,
    )
    lookup = MagicMock()
    lookup.scalar_one_or_none = MagicMock(return_value=admin)
    mock_platform_admin_session.execute = AsyncMock(return_value=lookup)

    response = await client.patch(
        f"/api/v1/platform/admins/{admin_id}",
        json={"is_active": False},
        headers=_auth_headers(role="platform_admin", user_id=admin_id),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "You cannot deactivate your own platform admin account"


@pytest.mark.asyncio
async def test_settings_patch_updates_runtime_values_for_platform_admin(client, monkeypatch):
    from app.api.routes import settings as settings_routes

    calls = []
    monkeypatch.setattr(settings_routes, "_update_llm_clients", lambda: calls.append("updated"))
    monkeypatch.setattr(settings_routes.settings, "LLM_PROVIDER", "vertex_ai")
    monkeypatch.setattr(settings_routes.settings, "LLM_CIRCUIT_BREAKER_THRESHOLD", 3)
    monkeypatch.setattr(settings_routes.settings, "LOCK_TTL", 120)

    response = await client.patch(
        "/api/v1/settings/",
        json={
            "llm_provider": "openai",
            "llm_circuit_breaker_threshold": 5,
            "lock_ttl": 180,
        },
        headers=_auth_headers(role="platform_admin"),
    )

    assert response.status_code == 200
    assert response.json()["applied_updates"] == {
        "llm_provider": "openai",
        "llm_circuit_breaker_threshold": 5,
        "lock_ttl": 180,
    }
    assert settings_routes.settings.LLM_PROVIDER == "openai"
    assert settings_routes.settings.LLM_CIRCUIT_BREAKER_THRESHOLD == 5
    assert settings_routes.settings.LOCK_TTL == 180
    assert calls == ["updated"]


@pytest.mark.asyncio
async def test_create_integration_type_uses_jsonb_cast(client, monkeypatch):
    from app.api.routes import integrations as integration_routes

    fake_conn = _FakeConnection(
        responses=[
            _FakeExecuteResult(first_row=None),
            _FakeExecuteResult(),
        ]
    )
    monkeypatch.setattr(
        integration_routes,
        "async_engine",
        _FakeEngine(begin_conn=fake_conn),
    )

    response = await client.post(
        "/api/v1/integration-types",
        json={
            "key": "pingdom",
            "display_name": "Pingdom",
            "category": "monitoring",
            "supports_webhook": True,
            "supports_polling": False,
            "supports_sync": True,
            "config_schema_json": {
                "type": "object",
                "properties": {
                    "base_url": {"type": "string"},
                },
                "required": ["base_url"],
            },
        },
        headers=_auth_headers(role="platform_admin"),
    )

    assert response.status_code == 201
    insert_sql, insert_params = fake_conn.statements[1]
    assert "CAST(:config_schema_json AS jsonb)" in insert_sql
    assert insert_params["key"] == "pingdom"


@pytest.mark.asyncio
async def test_test_integration_reports_missing_required_fields(client, mock_session, monkeypatch):
    from app.api.routes import integrations as integration_routes

    integration_id = uuid.uuid4()
    tenant_id = uuid.UUID(TENANT_ID)

    monkeypatch.setattr(
        integration_routes,
        "_get_integration_tenant_id",
        AsyncMock(return_value=tenant_id),
    )
    monkeypatch.setattr(
        integration_routes,
        "_require_tenant_admin",
        AsyncMock(return_value=None),
    )

    fake_conn = _FakeConnection(
        responses=[
            _FakeExecuteResult(
                first_row=SimpleNamespace(
                    id=integration_id,
                    tenant_id=tenant_id,
                    config_json={},
                    secret_ref=None,
                    webhook_token_ref=None,
                    integration_type_key="site24x7",
                    supports_webhook=True,
                    config_schema_json={
                        "type": "object",
                        "properties": {
                            "api_key": {"type": "string"},
                        },
                        "required": ["api_key"],
                    },
                )
            ),
            _FakeExecuteResult(),
        ]
    )
    monkeypatch.setattr(
        integration_routes,
        "async_engine",
        _FakeEngine(begin_conn=fake_conn),
    )

    response = await client.post(
        f"/api/v1/integrations/{integration_id}/test",
        headers=_auth_headers(role="tenant_admin", tenant_id=str(tenant_id)),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["success"] is False
    assert "Missing required integration fields" in body["detail"]
    assert any(check["code"] == "required:api_key" and check["status"] == "failed" for check in body["checks"])


@pytest.mark.asyncio
async def test_delete_integration_hard_deletes_row(client, monkeypatch):
    from app.api.routes import integrations as integration_routes

    integration_id = uuid.uuid4()
    tenant_id = uuid.UUID(TENANT_ID)

    monkeypatch.setattr(
        integration_routes,
        "_get_integration_tenant_id",
        AsyncMock(return_value=tenant_id),
    )
    monkeypatch.setattr(
        integration_routes,
        "_require_tenant_admin",
        AsyncMock(return_value=None),
    )

    fake_conn = _FakeConnection(responses=[_FakeExecuteResult(rowcount=1)])
    monkeypatch.setattr(
        integration_routes,
        "async_engine",
        _FakeEngine(begin_conn=fake_conn),
    )

    response = await client.delete(
        f"/api/v1/integrations/{integration_id}",
        headers=_auth_headers(role="tenant_admin", tenant_id=str(tenant_id)),
    )

    assert response.status_code == 200
    assert response.json() == {"status": "deleted"}
    delete_sql, delete_params = fake_conn.statements[0]
    assert "DELETE FROM monitoring_integrations" in delete_sql
    assert "UPDATE monitoring_integrations" not in delete_sql
    assert delete_params == {"integration_id": str(integration_id)}


@pytest.mark.asyncio
async def test_create_integration_purges_legacy_disabled_slug_before_insert(client, monkeypatch):
    from app.api.routes import integrations as integration_routes

    tenant_id = uuid.UUID(TENANT_ID)
    integration_type_id = uuid.uuid4()
    binding_id = uuid.uuid4()

    monkeypatch.setattr(
        integration_routes,
        "_require_tenant_admin",
        AsyncMock(return_value=None),
    )

    fake_conn = _FakeConnection(
        responses=[
            _FakeExecuteResult(
                first_row=SimpleNamespace(
                    id=tenant_id,
                    tenant_slug="workspace-alpha",
                    organization_slug="ankercloud",
                )
            ),
            _FakeExecuteResult(
                first_row=SimpleNamespace(
                    id=integration_type_id,
                    key="site24x7",
                )
            ),
            _FakeExecuteResult(
                first_row=SimpleNamespace(
                    id=binding_id,
                    display_name="AWS Test Client",
                    external_account_id="547361935557",
                )
            ),
            _FakeExecuteResult(rowcount=1),
            _FakeExecuteResult(first_row=None),
            _FakeExecuteResult(),
        ]
    )
    monkeypatch.setattr(
        integration_routes,
        "async_engine",
        _FakeEngine(begin_conn=fake_conn),
    )

    response = await client.post(
        f"/api/v1/tenants/{tenant_id}/integrations",
        json={
            "integration_type_key": "site24x7",
            "name": "Site24x7",
            "slug": "site24x7",
            "cloud_account_binding_id": str(binding_id),
            "enabled": True,
            "config_json": {"api_key": "test"},
        },
        headers=_auth_headers(role="tenant_admin", tenant_id=str(tenant_id)),
    )

    assert response.status_code == 201
    purge_sql, purge_params = fake_conn.statements[3]
    assert "DELETE FROM monitoring_integrations" in purge_sql
    assert "enabled = false" in purge_sql
    assert purge_params == {
        "tenant_id": str(tenant_id),
        "slug": "site24x7",
        "cloud_account_binding_id": str(binding_id),
    }

    conflict_sql, conflict_params = fake_conn.statements[4]
    assert "AND enabled = true" in conflict_sql
    assert "cloud_account_binding_id = :cloud_account_binding_id" in conflict_sql
    assert conflict_params == {
        "tenant_id": str(tenant_id),
        "slug": "site24x7",
        "cloud_account_binding_id": str(binding_id),
    }


@pytest.mark.asyncio
async def test_create_integration_allows_same_slug_for_different_account(client, monkeypatch):
    from app.api.routes import integrations as integration_routes

    tenant_id = uuid.UUID(TENANT_ID)
    integration_type_id = uuid.uuid4()
    binding_id = uuid.uuid4()

    monkeypatch.setattr(
        integration_routes,
        "_require_tenant_admin",
        AsyncMock(return_value=None),
    )

    fake_conn = _FakeConnection(
        responses=[
            _FakeExecuteResult(
                first_row=SimpleNamespace(
                    id=tenant_id,
                    tenant_slug="workspace-alpha",
                    organization_slug="ankercloud",
                )
            ),
            _FakeExecuteResult(
                first_row=SimpleNamespace(
                    id=integration_type_id,
                    key="site24x7",
                )
            ),
            _FakeExecuteResult(
                first_row=SimpleNamespace(
                    id=binding_id,
                    display_name="AWS Test Client",
                    external_account_id="547361935557",
                )
            ),
            _FakeExecuteResult(rowcount=0),
            _FakeExecuteResult(first_row=None),
            _FakeExecuteResult(),
        ]
    )
    monkeypatch.setattr(
        integration_routes,
        "async_engine",
        _FakeEngine(begin_conn=fake_conn),
    )

    response = await client.post(
        f"/api/v1/tenants/{tenant_id}/integrations",
        json={
            "integration_type_key": "site24x7",
            "name": "Site24x7",
            "slug": "shared-slug",
            "cloud_account_binding_id": str(binding_id),
            "enabled": True,
            "config_json": {"api_key": "test"},
        },
        headers=_auth_headers(role="tenant_admin", tenant_id=str(tenant_id)),
    )

    assert response.status_code == 201
    assert response.json()["webhook_path"] == (
        f"/api/v1/webhooks/ankercloud/workspace-alpha/547361935557/shared-slug"
    )


@pytest.mark.asyncio
async def test_list_webhook_events_sets_tenant_context_with_set_config(client, monkeypatch):
    from app.api.routes import integrations as integration_routes

    integration_id = uuid.uuid4()
    tenant_id = uuid.UUID(TENANT_ID)
    received_at = datetime.now(timezone.utc)

    monkeypatch.setattr(
        integration_routes,
        "_get_integration_tenant_id",
        AsyncMock(return_value=tenant_id),
    )
    monkeypatch.setattr(
        integration_routes,
        "_require_tenant_access",
        AsyncMock(return_value=None),
    )

    fake_conn = _FakeConnection(
        responses=[
            _FakeExecuteResult(),
            _FakeExecuteResult(
                rows=[
                    SimpleNamespace(
                        id=uuid.uuid4(),
                        integration_id=integration_id,
                        source="site24x7",
                        event_type="alert",
                        payload={"STATUS": "DOWN"},
                        status="processed",
                        incident_id=None,
                        dedup_key=None,
                        is_replay=False,
                        original_event_id=None,
                        received_at=received_at,
                        processed_at=None,
                    )
                ]
            ),
        ]
    )
    monkeypatch.setattr(
        integration_routes,
        "async_engine",
        _FakeEngine(connect_conn=fake_conn),
    )

    response = await client.get(
        f"/api/v1/integrations/{integration_id}/webhook-events",
        headers=_auth_headers(role="tenant_admin", tenant_id=str(tenant_id)),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["source"] == "site24x7"
    set_sql, set_params = fake_conn.statements[0]
    assert "set_config('app.tenant_id', :tenant_id, true)" in set_sql
    assert set_params == {"tenant_id": str(tenant_id)}


@pytest.mark.asyncio
async def test_org_admin_cannot_access_dlq(client):
    response = await client.get(
        "/api/v1/dlq/",
        headers=_auth_headers(role="org_admin"),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Platform admin access required"


@pytest.mark.asyncio
async def test_platform_admin_can_access_dlq(client, mock_redis):
    tenant_id = uuid.UUID(TENANT_ID)
    mock_redis.lrange = AsyncMock(
        return_value=[
            json.dumps(
                {
                    "task": "reconcile_incident",
                    "tenant_id": str(tenant_id),
                    "incident_id": str(uuid.uuid4()),
                    "error": "boom",
                    "failed_at": "2026-03-18T00:00:00Z",
                }
            ).encode()
        ]
    )

    response = await client.get(
        "/api/v1/dlq/",
        headers=_auth_headers(role="platform_admin", tenant_id=str(tenant_id)),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["task"] == "reconcile_incident"


@pytest.mark.asyncio
async def test_org_admin_cannot_reload_tenant_config(client):
    response = await client.post(
        "/api/v1/tenants/reload",
        headers=_auth_headers(role="org_admin"),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Platform admin access required"


@pytest.mark.asyncio
async def test_top_level_tenant_create_requires_platform_admin(client):
    response = await client.post(
        "/api/v1/tenants/",
        json={
            "name": "org-scoped-attempt",
            "display_name": "Org Scoped Attempt",
            "cloud": "aws",
        },
        headers=_auth_headers(role="org_admin"),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Platform admin access required"


@pytest.mark.asyncio
async def test_list_all_tenants_scopes_non_platform_users(client, mock_session, monkeypatch):
    from app.api.routes import tenants as tenant_routes

    org_id = uuid.uuid4()
    explicit_tenant_id = uuid.uuid4()

    home_org_result = MagicMock()
    home_org_result.scalar_one_or_none = MagicMock(return_value=org_id)

    org_memberships_result = MagicMock()
    org_memberships_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[]))
    )

    tenant_memberships_result = MagicMock()
    tenant_memberships_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[explicit_tenant_id]))
    )

    mock_session.execute = AsyncMock(
        side_effect=[
            home_org_result,
            org_memberships_result,
            tenant_memberships_result,
        ]
    )

    fake_conn = _FakeConnection(
        responses=[
            _FakeExecuteResult(
                scalar_rows=[
                    SimpleNamespace(
                        id=uuid.UUID(TENANT_ID),
                        name="home-tenant",
                        display_name="Home Tenant",
                        cloud="aws",
                        organization_id=org_id,
                        servers=[{"name": "app-1"}],
                        escalation_email="home@example.com",
                        is_active=True,
                        aws_config={},
                        gcp_config={},
                    ),
                    SimpleNamespace(
                        id=explicit_tenant_id,
                        name="member-tenant",
                        display_name="Member Tenant",
                        cloud="gcp",
                        organization_id=uuid.uuid4(),
                        servers=[],
                        escalation_email="member@example.com",
                        is_active=True,
                        aws_config={},
                        gcp_config={"project_id": "member-project"},
                    ),
                ]
            )
        ]
    )
    monkeypatch.setattr(
        tenant_routes,
        "async_engine",
        _FakeEngine(connect_conn=fake_conn),
    )

    response = await client.get(
        "/api/v1/tenants/",
        headers=_auth_headers(role="org_admin"),
    )

    assert response.status_code == 200
    assert [tenant["name"] for tenant in response.json()] == [
        "home-tenant",
        "member-tenant",
    ]
    assert mock_session.execute.await_count == 3


@pytest.mark.asyncio
async def test_update_tenant_rejects_cross_org_admin(client, monkeypatch):
    from app.api.routes import tenants as tenant_routes

    tenant_org_id = uuid.uuid4()

    monkeypatch.setattr(
        tenant_routes,
        "authorize_org_admin",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        tenant_routes,
        "async_engine",
        _FakeEngine(
            connect_conn=_FakeConnection(
                responses=[_FakeExecuteResult(scalar_one_or_none=tenant_org_id)]
            )
        ),
    )

    response = await client.put(
        "/api/v1/tenants/cross-org-tenant",
        json={"display_name": "Blocked Update"},
        headers=_auth_headers(role="org_admin"),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Organization admin required for this tenant"


@pytest.mark.asyncio
async def test_delete_tenant_rejects_cross_org_admin(client, monkeypatch):
    from app.api.routes import tenants as tenant_routes

    tenant_org_id = uuid.uuid4()

    monkeypatch.setattr(
        tenant_routes,
        "authorize_org_admin",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        tenant_routes,
        "async_engine",
        _FakeEngine(
            connect_conn=_FakeConnection(
                responses=[_FakeExecuteResult(scalar_one_or_none=tenant_org_id)]
            )
        ),
    )

    response = await client.delete(
        "/api/v1/tenants/cross-org-tenant",
        headers=_auth_headers(role="org_admin"),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Organization admin required for this tenant"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("get", "/api/v1/users/", None),
        ("get", f"/api/v1/users/{uuid.uuid4()}", None),
        (
            "post",
            "/api/v1/users/",
            {
                "email": "new-user@example.com",
                "display_name": "New User",
                "role": "viewer",
            },
        ),
        (
            "patch",
            f"/api/v1/users/{uuid.uuid4()}",
            {
                "display_name": "Updated Name",
            },
        ),
        ("delete", f"/api/v1/users/{uuid.uuid4()}", None),
        ("post", f"/api/v1/users/{uuid.uuid4()}/resend-invitation", None),
    ],
)
async def test_user_management_routes_reject_out_of_scope_org_admin(
    client,
    monkeypatch,
    method,
    path,
    json_body,
):
    from app.api.routes import users as user_routes

    monkeypatch.setattr(
        user_routes,
        "authorize_tenant_admin",
        AsyncMock(return_value=False),
    )

    request_kwargs = {"headers": _auth_headers(role="org_admin")}
    if json_body is not None:
        request_kwargs["json"] = json_body

    response = await getattr(client, method)(path, **request_kwargs)

    assert response.status_code == 403
    assert response.json()["detail"] == "Tenant admin required"
