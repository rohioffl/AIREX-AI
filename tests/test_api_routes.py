"""Focused API route tests for critical HTTP surfaces."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from airex_core.core.security import create_access_token


TENANT_ID = "00000000-0000-0000-0000-000000000000"
HEADERS = {"X-Tenant-Id": TENANT_ID}


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
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest_asyncio.fixture
async def client(mock_redis, mock_session):
    from app.api.dependencies import get_db_session, get_redis

    app.dependency_overrides[get_redis] = lambda: mock_redis

    async def override_session():
        yield mock_session

    app.dependency_overrides[get_db_session] = override_session
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
    response = await client.post("/api/v1/webhooks/generic", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_generic_webhook_requires_fields(client):
    response = await client.post(
        "/api/v1/webhooks/generic",
        json={"alert_type": "cpu_high"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_site24x7_webhook_rejects_non_json(client):
    response = await client.post(
        "/api/v1/webhooks/site24x7",
        content=b"not json",
        headers={**HEADERS, "Content-Type": "application/json"},
    )
    assert response.status_code == 400


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
async def test_reject_nonexistent_incident_returns_404(client, mock_session):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=mock_result)

    response = await client.post(
        f"/api/v1/incidents/{uuid.uuid4()}/reject",
        json={"reason": "unsafe remediation"},
    )
    assert response.status_code == 404


class _FakeExecuteResult:
    def __init__(self, first_row=None, rowcount=1):
        self._first_row = first_row
        self.rowcount = rowcount

    def first(self):
        return self._first_row


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
