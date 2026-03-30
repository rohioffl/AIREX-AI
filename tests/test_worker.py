"""Focused worker task tests for the ARQ task entrypoints."""

from contextlib import asynccontextmanager
from pathlib import Path
import sys
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

WORKER_SERVICE_DIR = Path(__file__).resolve().parents[1] / "services/airex-worker"
CORE_SERVICE_DIR = Path(__file__).resolve().parents[1] / "services/airex-core"
worker_service_path = str(WORKER_SERVICE_DIR)
if worker_service_path in sys.path:
    sys.path.remove(worker_service_path)
sys.path.insert(0, worker_service_path)

core_service_path = str(CORE_SERVICE_DIR)
if core_service_path in sys.path:
    sys.path.remove(core_service_path)
sys.path.insert(0, core_service_path)

sys.modules.pop("app", None)

import app.core.worker as worker


def _make_incident() -> SimpleNamespace:
    return SimpleNamespace(id="incident", state="RECEIVED")


def _tenant_session_factory(session):
    @asynccontextmanager
    async def _session_scope(_tenant_id):
        yield session

    return _session_scope


@pytest.mark.asyncio
async def test_investigate_incident_runs_service(monkeypatch, tenant_id, incident_id):
    session = AsyncMock()
    incident = _make_incident()
    get_incident = AsyncMock(return_value=incident)
    run_investigation = AsyncMock()

    def fake_load_attr(module_path, attr_name):
        mapping = {
            ("airex_core.services.incident_service", "get_incident"): get_incident,
            (
                "airex_core.services.investigation_service",
                "run_investigation",
            ): run_investigation,
            ("airex_core.core.database", "get_tenant_session"): _tenant_session_factory(
                session
            ),
        }
        return mapping[(module_path, attr_name)]

    monkeypatch.setattr(worker, "_load_attr", fake_load_attr)

    await worker.investigate_incident(
        {"job_id": "job-1"}, str(tenant_id), str(incident_id)
    )

    get_incident.assert_awaited_once()
    run_investigation.assert_awaited_once_with(session, incident)


@pytest.mark.asyncio
async def test_generate_recommendation_task_passes_redis(
    monkeypatch, tenant_id, incident_id
):
    session = AsyncMock()
    incident = _make_incident()
    redis = AsyncMock()
    get_incident = AsyncMock(return_value=incident)
    generate_recommendation = AsyncMock()

    def fake_load_attr(module_path, attr_name):
        mapping = {
            ("airex_core.services.incident_service", "get_incident"): get_incident,
            (
                "airex_core.services.recommendation_service",
                "generate_recommendation",
            ): generate_recommendation,
            ("airex_core.core.database", "get_tenant_session"): _tenant_session_factory(
                session
            ),
        }
        return mapping[(module_path, attr_name)]

    monkeypatch.setattr(worker, "_load_attr", fake_load_attr)

    await worker.generate_recommendation_task(
        {"job_id": "job-2", "redis": redis},
        str(tenant_id),
        str(incident_id),
    )

    generate_recommendation.assert_awaited_once_with(session, incident, redis=redis)


@pytest.mark.asyncio
async def test_execute_action_task_creates_redis_when_missing(
    monkeypatch, tenant_id, incident_id
):
    session = AsyncMock()
    incident = _make_incident()
    created_redis = AsyncMock()
    get_incident = AsyncMock(return_value=incident)
    execute_action = AsyncMock()

    def fake_load_attr(module_path, attr_name):
        mapping = {
            ("airex_core.services.execution_service", "execute_action"): execute_action,
            ("airex_core.services.incident_service", "get_incident"): get_incident,
            ("airex_core.core.database", "get_tenant_session"): _tenant_session_factory(
                session
            ),
        }
        return mapping[(module_path, attr_name)]

    monkeypatch.setattr(worker, "_load_attr", fake_load_attr)
    monkeypatch.setattr(worker.aioredis, "from_url", lambda _url: created_redis)
    monkeypatch.setattr(
        worker,
        "_get_settings",
        lambda: SimpleNamespace(REDIS_URL="redis://localhost:6379/0"),
    )

    await worker.execute_action_task(
        {"job_id": "job-3"},
        str(tenant_id),
        str(incident_id),
        "restart_service",
    )

    execute_action.assert_awaited_once()
    args = execute_action.await_args.args
    assert args[0] is session
    assert args[1] is incident
    assert args[2] == "restart_service"
    assert args[3] is created_redis
    assert execute_action.await_args.kwargs["worker_id"] == "arq-job-3"


@pytest.mark.asyncio
async def test_verify_resolution_task_invalid_uuid_goes_to_dlq(monkeypatch):
    redis = AsyncMock()
    send_to_dlq = AsyncMock()

    monkeypatch.setattr(worker, "_send_to_dlq", send_to_dlq)

    await worker.verify_resolution_task(
        {"job_id": "job-4", "redis": redis},
        "not-a-uuid",
        "also-not-a-uuid",
    )

    send_to_dlq.assert_awaited_once()
    assert send_to_dlq.await_args.args[1] == "verify_resolution_task"


@pytest.mark.asyncio
async def test_generate_runbook_task_calls_service(monkeypatch, tenant_id, incident_id):
    session = AsyncMock()
    incident = _make_incident()
    redis = AsyncMock()
    get_incident = AsyncMock(return_value=incident)
    generate_and_store_runbook = AsyncMock(return_value="runbook-source")

    def fake_load_attr(module_path, attr_name):
        mapping = {
            ("airex_core.services.incident_service", "get_incident"): get_incident,
            (
                "airex_core.services.runbook_generator",
                "generate_and_store_runbook",
            ): generate_and_store_runbook,
            ("airex_core.core.database", "get_tenant_session"): _tenant_session_factory(
                session
            ),
        }
        return mapping[(module_path, attr_name)]

    monkeypatch.setattr(worker, "_load_attr", fake_load_attr)

    await worker.generate_runbook_task(
        {"job_id": "job-5", "redis": redis},
        str(tenant_id),
        str(incident_id),
    )

    generate_and_store_runbook.assert_awaited_once_with(session, incident, redis=redis)


@pytest.mark.asyncio
async def test_approval_sla_check_fans_out_across_active_tenants(monkeypatch):
    tenant_ids = [uuid.uuid4(), uuid.uuid4()]
    sessions = {tenant_id: AsyncMock() for tenant_id in tenant_ids}
    check_approval_slas = AsyncMock(side_effect=[2, 1])

    def fake_load_attr(module_path, attr_name):
        mapping = {
            ("airex_core.services.approval_sla_service", "check_approval_slas"): check_approval_slas,
            ("airex_core.core.database", "get_tenant_session"): _tenant_session_factory_by_tenant(sessions),
        }
        return mapping[(module_path, attr_name)]

    monkeypatch.setattr(worker, "_load_attr", fake_load_attr)
    monkeypatch.setattr(worker, "_list_active_tenant_ids", AsyncMock(return_value=tenant_ids))
    monkeypatch.setattr(worker, "_get_settings", lambda: SimpleNamespace(DEV_TENANT_ID=str(tenant_ids[0])))

    await worker.approval_sla_check({"job_id": "job-sla"})

    assert check_approval_slas.await_count == 2
    for session in sessions.values():
        session.commit.assert_awaited_once()



def _tenant_session_factory_by_tenant(sessions):
    @asynccontextmanager
    async def _session_scope(tenant_id):
        yield sessions[tenant_id]

    return _session_scope
