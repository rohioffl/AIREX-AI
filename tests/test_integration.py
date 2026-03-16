"""
Integration tests for AIREX API routes.

Uses httpx AsyncClient against the FastAPI app.
Tests webhook ingestion, incident listing, detail retrieval,
metrics endpoint, and health check.

NOTE: These tests run without a real database/Redis. They mock
the DB session and Redis dependencies. For full E2E tests, use
docker-compose with the seed script.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


pytestmark = pytest.mark.asyncio


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


@pytest_asyncio.fixture
async def client(mock_redis, mock_session):
    """httpx AsyncClient with mocked dependencies."""
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
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


class TestHealthCheck:
    async def test_health_returns_ok(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "airex-backend"


class TestMetrics:
    async def test_metrics_returns_prometheus_format(self, client):
        response = await client.get("/metrics")
        assert response.status_code == 200
        assert "airex_" in response.text
        assert "http_request_duration" in response.text or "incident" in response.text


class TestIncidentList:
    async def test_list_incidents_empty(self, client, mock_session):
        # First call is the COUNT query, second is the SELECT query
        mock_count_result = MagicMock()
        mock_count_result.scalar_one = MagicMock(return_value=0)

        mock_items_result = MagicMock()
        mock_items_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_items_result])

        response = await client.get("/api/v1/incidents/")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["has_more"] is False
        assert data["total"] == 0


class TestIncidentDetail:
    async def test_get_nonexistent_incident_returns_404(self, client, mock_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/incidents/{fake_id}")
        assert response.status_code == 404


class TestWebhookGeneric:
    async def test_generic_webhook_validation_error(self, client):
        response = await client.post("/api/v1/webhooks/generic", json={})
        assert response.status_code == 422

    async def test_generic_webhook_requires_fields(self, client):
        """Ensures required fields are validated."""
        response = await client.post(
            "/api/v1/webhooks/generic",
            json={"alert_type": "cpu_high"},
        )
        assert response.status_code == 422

    async def test_site24x7_webhook_rejects_non_json(self, client):
        """Non-JSON body should be rejected."""
        response = await client.post(
            "/api/v1/webhooks/site24x7",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400


class TestApproval:
    async def test_approve_nonexistent_incident(self, client, mock_session, mock_redis):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_id = str(uuid.uuid4())
        response = await client.post(
            f"/api/v1/incidents/{fake_id}/approve",
            json={"action": "restart_service", "idempotency_key": "test-key-123"},
        )
        assert response.status_code == 404
