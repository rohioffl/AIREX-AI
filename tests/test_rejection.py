import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from airex_core.models.enums import IncidentState
from airex_core.models.incident import Incident

TENANT_ID = "00000000-0000-0000-0000-000000000000"
HEADERS = {"X-Tenant-Id": TENANT_ID}


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock()
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
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_reject_incident_success(client, mock_session):
    # Setup mock incident
    incident_id = uuid.uuid4()
    mock_incident = Incident(
        id=incident_id,
        tenant_id=uuid.UUID(TENANT_ID),
        state=IncidentState.INVESTIGATING,
        alert_type="cpu_high",
        title="CPU High",
        severity="MEDIUM",
    )
    mock_incident.meta = {}

    # Mock DB response
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_incident)
    # Return previous transition for hash chain (None is fine for test)
    mock_prev_transition = MagicMock()
    mock_prev_transition.scalar_one_or_none = MagicMock(return_value=None)

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_result,  # fetch incident
            mock_prev_transition,  # fetch prev transition
        ]
    )

    note = "False alarm; handled manually"
    response = await client.post(
        f"/api/v1/incidents/{incident_id}/reject",
        json={"reason": note},
    )

    assert response.status_code == 202
    assert response.json()["incident_id"] == str(incident_id)
    assert mock_incident.state == IncidentState.REJECTED
    assert mock_incident.meta is not None
    meta = mock_incident.meta
    assert isinstance(meta, dict)
    assert meta["_manual_review_reason"] == note
    assert meta["_manual_review_required"] is True

    # Verify state transition was added
    assert mock_session.add.called
    transition = mock_session.add.call_args[0][0]
    assert transition.to_state == IncidentState.REJECTED
    assert transition.reason == note


@pytest.mark.asyncio
async def test_reject_nonexistent_incident(client, mock_session):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=mock_result)

    fake_id = uuid.uuid4()
    response = await client.post(f"/api/v1/incidents/{fake_id}/reject", json={})

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reject_incident_without_note_uses_default(client, mock_session):
    incident_id = uuid.uuid4()
    mock_incident = Incident(
        id=incident_id,
        tenant_id=uuid.UUID(TENANT_ID),
        state=IncidentState.AWAITING_APPROVAL,
        alert_type="cpu_high",
        title="CPU High",
        severity="HIGH",
    )
    mock_incident.meta = {}

    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_incident)
    mock_prev_transition = MagicMock()
    mock_prev_transition.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(side_effect=[mock_result, mock_prev_transition])

    response = await client.post(f"/api/v1/incidents/{incident_id}/reject", json={})

    assert response.status_code == 202
    assert mock_incident.meta is not None
    meta = mock_incident.meta
    assert isinstance(meta, dict)
    assert meta["_manual_review_reason"] == "Manually rejected by operator"
