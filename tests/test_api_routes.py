"""Focused API route tests for critical HTTP surfaces."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from airex_core.core.security import create_access_token


TENANT_ID = "00000000-0000-0000-0000-000000000000"
HEADERS = {"X-Tenant-Id": TENANT_ID}


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


@pytest_asyncio.fixture
async def client(mock_redis, mock_session):
    from app.api.dependencies import get_auth_session, get_db_session, get_redis

    async def override_redis():
        return mock_redis

    async def override_session():
        yield mock_session

    app.dependency_overrides[get_redis] = override_redis
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_auth_session] = override_session
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
        headers=_auth_headers(role="org_admin"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Ankercloud"
    assert body["slug"] == "ankercloud"
    created_org = mock_session.add.call_args.args[0]
    assert created_org.name == "Ankercloud"
    assert created_org.slug == "ankercloud"


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
    assert body[0]["webhook_path"] == f"/api/v1/webhooks/site24x7/{body[0]['id']}"


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
            _FakeExecuteResult(first_row=SimpleNamespace(id=tenant_uuid)),
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
    assert response.json()["webhook_path"] == f"/api/v1/webhooks/site24x7/{response.json()['id']}"
    insert_sql, insert_params = fake_conn.statements[3]
    assert "CAST(:config_json AS jsonb)" in insert_sql
    assert insert_params["tenant_id"] == str(tenant_uuid)


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

    async def fake_resolve(session, integration_id_arg):
        assert integration_id_arg == integration_id
        return webhook_routes.Site24x7IntegrationContext(
            integration_id=integration_id,
            tenant_id=integration_tenant_id,
            integration_name="Tenant Site24x7",
            integration_slug="tenant-site24x7",
            integration_type_key="site24x7",
            enabled=True,
        )

    async def fake_ingest(request, *, tenant_id, session, redis, integration_context):
        captured["tenant_id"] = tenant_id
        captured["integration_context"] = integration_context
        return IncidentCreatedResponse(incident_id=uuid.uuid4())

    monkeypatch.setattr(webhook_routes, "_resolve_site24x7_integration_context", fake_resolve)
    monkeypatch.setattr(webhook_routes, "_ingest_site24x7_request", fake_ingest)

    response = await client.post(
        f"/api/v1/webhooks/site24x7/{integration_id}",
        json={"monitor_id": "monitor-1", "monitor_name": "Web-01", "status": "down"},
    )

    assert response.status_code == 202
    assert captured["tenant_id"] == integration_tenant_id
    assert captured["integration_context"].integration_id == integration_id


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
