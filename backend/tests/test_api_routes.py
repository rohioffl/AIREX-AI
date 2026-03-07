"""Focused API route tests for critical HTTP surfaces."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


TENANT_ID = "00000000-0000-0000-0000-000000000000"
HEADERS = {"X-Tenant-Id": TENANT_ID}


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


@pytest.fixture
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
