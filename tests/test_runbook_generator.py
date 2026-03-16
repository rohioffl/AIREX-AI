"""
Tests for runbook auto-generation service (Phase 5 ARE).
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airex_core.models.enums import IncidentState, SeverityLevel
from airex_core.services.runbook_generator import (
    build_runbook_context,
    generate_and_store_runbook,
    generate_runbook_content,
    store_runbook,
)


TENANT = uuid.UUID("00000000-0000-0000-0000-000000000000")


def _make_incident(
    state=IncidentState.RESOLVED,
    meta=None,
    resolution_type="auto",
    resolution_duration_seconds=120.0,
):
    incident = MagicMock()
    incident.id = uuid.uuid4()
    incident.tenant_id = TENANT
    incident.state = state
    incident.severity = SeverityLevel.HIGH
    incident.title = "[DOWN] Server-A — CPU at 95%"
    incident.alert_type = "cpu_high"
    incident.host_key = "10.0.0.1"
    incident.created_at = datetime.now(timezone.utc)
    incident.updated_at = incident.created_at
    incident.resolution_type = resolution_type
    incident.resolution_duration_seconds = resolution_duration_seconds
    incident.resolution_summary = "Restarted service to resolve CPU spike"

    default_meta = {
        "recommendation": {
            "root_cause": "Memory leak causing CPU thrashing",
            "proposed_action": "restart_service",
            "confidence": 0.92,
            "risk_level": "LOW",
            "verification_criteria": [
                "CPU usage below 80%",
                "Service responding to health checks",
            ],
        },
    }
    incident.meta = meta if meta is not None else default_meta

    # Evidence
    e1 = MagicMock()
    e1.tool_name = "ssh_command"
    e1.raw_output = "top - CPU: 95% us, 3% sy"
    e2 = MagicMock()
    e2.tool_name = "cloud_metrics"
    e2.raw_output = "CPU utilization: 95.2%"
    incident.evidence = [e1, e2]

    return incident


# ── build_runbook_context ────────────────────────────────────


class TestBuildRunbookContext:
    def test_extracts_all_fields(self):
        incident = _make_incident()
        ctx = build_runbook_context(incident)

        assert ctx["alert_type"] == "cpu_high"
        assert ctx["severity"] == "HIGH"
        assert "CPU at 95%" in ctx["title"]
        assert ctx["resolution_type"] == "auto"
        assert ctx["duration"] == "2 minutes"
        assert ctx["root_cause"] == "Memory leak causing CPU thrashing"
        assert ctx["action_taken"] == "restart_service"
        assert "ssh_command" in ctx["evidence_summary"]
        assert "CPU usage below 80%" in ctx["verification"]

    def test_handles_missing_recommendation(self):
        incident = _make_incident(meta={})
        ctx = build_runbook_context(incident)

        assert ctx["root_cause"] == "Not determined"
        assert ctx["action_taken"] == "Manual resolution"

    def test_handles_short_duration(self):
        incident = _make_incident(resolution_duration_seconds=45.0)
        ctx = build_runbook_context(incident)
        assert ctx["duration"] == "45 seconds"

    def test_handles_long_duration(self):
        incident = _make_incident(resolution_duration_seconds=7200.0)
        ctx = build_runbook_context(incident)
        assert ctx["duration"] == "2h 0m"

    def test_handles_none_duration(self):
        incident = _make_incident(resolution_duration_seconds=None)
        ctx = build_runbook_context(incident)
        assert ctx["duration"] == "Unknown"

    def test_handles_no_evidence(self):
        incident = _make_incident()
        incident.evidence = []
        ctx = build_runbook_context(incident)
        assert ctx["evidence_summary"] == "No evidence recorded"


# ── generate_runbook_content ─────────────────────────────────


class TestGenerateRunbookContent:
    @pytest.mark.asyncio
    async def test_returns_content_on_success(self):
        context = build_runbook_context(_make_incident())
        mock_content = "# CPU High Runbook\n\n## Symptoms\n- High CPU usage"

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acomp:
            mock_acomp.return_value = {
                "choices": [{"message": {"content": mock_content}}]
            }

            result = await generate_runbook_content(context)

        assert result == mock_content

    @pytest.mark.asyncio
    async def test_returns_none_on_timeout(self):
        context = build_runbook_context(_make_incident())

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acomp:
            import asyncio
            mock_acomp.side_effect = asyncio.TimeoutError()

            result = await generate_runbook_content(context)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self):
        context = build_runbook_context(_make_incident())

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acomp:
            mock_acomp.side_effect = RuntimeError("LLM down")

            result = await generate_runbook_content(context)

        assert result is None


# ── store_runbook ────────────────────────────────────────────


class TestStoreRunbook:
    @pytest.mark.asyncio
    async def test_stores_chunks_with_embeddings(self):
        incident = _make_incident()
        content = "# Runbook\n\nSome content here that is long enough to chunk."
        session = AsyncMock()
        session.add = MagicMock()

        with patch("airex_core.services.runbook_generator.EmbeddingsClient") as MockEmbed:
            mock_embed_instance = MagicMock()
            mock_embed_instance.embed_texts = AsyncMock(
                return_value=[[0.1] * 1024]  # One chunk → one vector
            )
            MockEmbed.return_value = mock_embed_instance

            source_id = await store_runbook(session, incident, content)

        assert source_id is not None
        # session.add should have been called for each chunk
        assert session.add.called

    @pytest.mark.asyncio
    async def test_deterministic_source_id(self):
        incident = _make_incident()
        content = "# Runbook content"
        session = AsyncMock()
        session.add = MagicMock()

        with patch("airex_core.services.runbook_generator.EmbeddingsClient") as MockEmbed:
            mock_embed_instance = MagicMock()
            mock_embed_instance.embed_texts = AsyncMock(
                return_value=[[0.1] * 1024]
            )
            MockEmbed.return_value = mock_embed_instance

            id1 = await store_runbook(session, incident, content)
            id2 = await store_runbook(session, incident, content)

        assert id1 == id2  # Same incident → same source_id


# ── generate_and_store_runbook ───────────────────────────────


class TestGenerateAndStoreRunbook:
    @pytest.mark.asyncio
    async def test_skips_non_resolved_incidents(self):
        incident = _make_incident(state=IncidentState.REJECTED)
        session = AsyncMock()

        result = await generate_and_store_runbook(session, incident)
        assert result is None

    @pytest.mark.asyncio
    async def test_skips_incidents_without_recommendation(self):
        incident = _make_incident(meta={})
        session = AsyncMock()

        result = await generate_and_store_runbook(session, incident)
        assert result is None

    @pytest.mark.asyncio
    async def test_full_pipeline_success(self):
        incident = _make_incident()
        session = AsyncMock()

        with patch("airex_core.services.runbook_generator.generate_runbook_content",
                    new_callable=AsyncMock) as mock_gen, \
             patch("airex_core.services.runbook_generator.store_runbook",
                    new_callable=AsyncMock) as mock_store:
            mock_gen.return_value = "# Generated Runbook"
            mock_store.return_value = uuid.uuid4()

            result = await generate_and_store_runbook(session, incident)

        assert result is not None
        mock_gen.assert_called_once()
        mock_store.assert_called_once()
        assert incident.meta["_auto_runbook_source_id"] is not None

    @pytest.mark.asyncio
    async def test_returns_none_when_llm_fails(self):
        incident = _make_incident()
        session = AsyncMock()

        with patch("airex_core.services.runbook_generator.generate_runbook_content",
                    new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = None

            result = await generate_and_store_runbook(session, incident)

        assert result is None


# ── Worker task registration ─────────────────────────────────


class TestWorkerHasRunbookTask:
    def test_generate_runbook_task_in_worker(self):
        from airex_core.core.worker import WorkerSettings
        func_names = [f.__name__ for f in WorkerSettings.functions]
        assert "generate_runbook_task" in func_names
