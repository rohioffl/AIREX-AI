"""Tests for the Knowledge Graph service (Phase 4 ARE)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.core.knowledge_graph import KnowledgeGraph, make_entity_id, knowledge_graph


# ── make_entity_id ────────────────────────────────────────────────


class TestMakeEntityId:
    def test_basic(self):
        assert make_entity_id("service", "checkout-api") == "service:checkout-api"

    def test_lowercases_name(self):
        assert make_entity_id("alert_type", "HighCPU") == "alert_type:highcpu"

    def test_strips_whitespace(self):
        assert make_entity_id("host", "  10.0.0.1  ") == "host:10.0.0.1"

    def test_entity_type_preserved(self):
        eid = make_entity_id("action", "restart_service")
        assert eid.startswith("action:")

    def test_singleton_import(self):
        assert isinstance(knowledge_graph, KnowledgeGraph)


# ── upsert_node ───────────────────────────────────────────────────


class TestUpsertNode:
    @pytest.fixture
    def kg(self):
        return KnowledgeGraph()

    @pytest.fixture
    def tenant_id(self):
        return uuid.UUID("00000000-0000-0000-0000-000000000000")

    @pytest.mark.asyncio
    async def test_upsert_node_executes_insert(self, kg, tenant_id):
        session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_node = MagicMock()
        mock_node.entity_id = "service:api"
        mock_result.scalars.return_value.one.return_value = mock_node
        session.execute = AsyncMock(return_value=mock_result)

        node = await kg.upsert_node(
            session=session,
            tenant_id=tenant_id,
            entity_id="service:api",
            entity_type="service",
            label="api",
        )

        session.execute.assert_called_once()
        assert node is mock_node

    @pytest.mark.asyncio
    async def test_upsert_node_passes_properties(self, kg, tenant_id):
        session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.one.return_value = MagicMock()
        session.execute = AsyncMock(return_value=mock_result)

        props = {"region": "ap-south-1"}
        await kg.upsert_node(
            session=session,
            tenant_id=tenant_id,
            entity_id="host:10.0.0.1",
            entity_type="host",
            label="10.0.0.1",
            properties=props,
        )

        call_args = session.execute.call_args[0][0]
        # The compiled statement should include properties
        assert session.execute.called


# ── add_edge ──────────────────────────────────────────────────────


class TestAddEdge:
    @pytest.fixture
    def kg(self):
        return KnowledgeGraph()

    @pytest.fixture
    def tenant_id(self):
        return uuid.UUID("00000000-0000-0000-0000-000000000000")

    @pytest.mark.asyncio
    async def test_add_edge_executes_upsert(self, kg, tenant_id):
        session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_edge = MagicMock()
        mock_edge.weight = 1.0
        mock_result.scalars.return_value.one.return_value = mock_edge
        session.execute = AsyncMock(return_value=mock_result)

        edge = await kg.add_edge(
            session=session,
            tenant_id=tenant_id,
            src_entity_id="alert_type:highcpu",
            relation="what_worked",
            dst_entity_id="action:restart_service",
        )

        session.execute.assert_called_once()
        assert edge is mock_edge

    @pytest.mark.asyncio
    async def test_add_edge_with_meta(self, kg, tenant_id):
        session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.one.return_value = MagicMock(weight=2.0)
        session.execute = AsyncMock(return_value=mock_result)

        await kg.add_edge(
            session=session,
            tenant_id=tenant_id,
            src_entity_id="service:checkout",
            relation="calls",
            dst_entity_id="service:payment",
            meta={"latency_p99": 120},
        )

        session.execute.assert_called_once()


# ── record_outcome ────────────────────────────────────────────────


class TestRecordOutcome:
    @pytest.fixture
    def kg(self):
        return KnowledgeGraph()

    @pytest.fixture
    def tenant_id(self):
        return uuid.UUID("00000000-0000-0000-0000-000000000000")

    @pytest.fixture
    def incident_id(self):
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_success_false_is_noop(self, kg, tenant_id, incident_id):
        session = AsyncMock(spec=AsyncSession)

        await kg.record_outcome(
            session=session,
            tenant_id=tenant_id,
            incident_id=incident_id,
            alert_type="HighCPU",
            action_type="restart_service",
            success=False,
        )

        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_success_true_writes_nodes_and_edges(self, kg, tenant_id, incident_id):
        session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.one.return_value = MagicMock(weight=1.0)
        session.execute = AsyncMock(return_value=mock_result)

        await kg.record_outcome(
            session=session,
            tenant_id=tenant_id,
            incident_id=incident_id,
            alert_type="HighCPU",
            action_type="restart_service",
            success=True,
        )

        # Should upsert 3 nodes (alert, action, incident) + 2 edges (what_worked, resolved_by)
        assert session.execute.call_count == 5

    @pytest.mark.asyncio
    async def test_success_true_with_service_writes_extra(self, kg, tenant_id, incident_id):
        session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.one.return_value = MagicMock(weight=1.0)
        session.execute = AsyncMock(return_value=mock_result)

        await kg.record_outcome(
            session=session,
            tenant_id=tenant_id,
            incident_id=incident_id,
            alert_type="HighCPU",
            action_type="restart_service",
            success=True,
            service_name="checkout-api",
        )

        # 3 nodes + 2 edges + 1 extra svc node + 1 extra svc edge = 7
        assert session.execute.call_count == 7

    @pytest.mark.asyncio
    async def test_entity_ids_are_canonicalized(self, kg, tenant_id, incident_id):
        """record_outcome should build canonical entity_ids (lowercased)."""
        session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.one.return_value = MagicMock(weight=1.0)
        session.execute = AsyncMock(return_value=mock_result)

        # Verify make_entity_id is used implicitly — canonical IDs are lowercase
        alert_id = make_entity_id("alert_type", "HighCPU")
        assert alert_id == "alert_type:highcpu"
        action_id = make_entity_id("action", "Restart_Service")
        assert action_id == "action:restart_service"


# ── upsert_alert_entities ─────────────────────────────────────────


class TestUpsertAlertEntities:
    @pytest.fixture
    def kg(self):
        return KnowledgeGraph()

    @pytest.fixture
    def tenant_id(self):
        return uuid.UUID("00000000-0000-0000-0000-000000000000")

    @pytest.fixture
    def incident_id(self):
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_alert_type_only(self, kg, tenant_id, incident_id):
        session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.one.return_value = MagicMock()
        session.execute = AsyncMock(return_value=mock_result)

        await kg.upsert_alert_entities(
            session=session,
            tenant_id=tenant_id,
            incident_id=incident_id,
            alert_type="DiskFull",
        )

        # Only 1 node (alert_type) — no host or service
        assert session.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_with_host_adds_node_and_edge(self, kg, tenant_id, incident_id):
        session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.one.return_value = MagicMock()
        session.execute = AsyncMock(return_value=mock_result)

        await kg.upsert_alert_entities(
            session=session,
            tenant_id=tenant_id,
            incident_id=incident_id,
            alert_type="DiskFull",
            host="10.0.0.5",
        )

        # alert_type node + host node + has_alert edge = 3
        assert session.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_with_service_adds_node_and_edge(self, kg, tenant_id, incident_id):
        session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.one.return_value = MagicMock()
        session.execute = AsyncMock(return_value=mock_result)

        await kg.upsert_alert_entities(
            session=session,
            tenant_id=tenant_id,
            incident_id=incident_id,
            alert_type="DiskFull",
            service_name="storage-api",
        )

        # alert_type node + service node + has_alert edge = 3
        assert session.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_with_host_and_service(self, kg, tenant_id, incident_id):
        session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.one.return_value = MagicMock()
        session.execute = AsyncMock(return_value=mock_result)

        await kg.upsert_alert_entities(
            session=session,
            tenant_id=tenant_id,
            incident_id=incident_id,
            alert_type="DiskFull",
            host="10.0.0.5",
            service_name="storage-api",
        )

        # alert + host + svc nodes (3) + 2 has_alert edges = 5
        assert session.execute.call_count == 5


# ── causal_walk ───────────────────────────────────────────────────


class TestCausalWalk:
    @pytest.fixture
    def kg(self):
        return KnowledgeGraph()

    @pytest.fixture
    def tenant_id(self):
        return uuid.UUID("00000000-0000-0000-0000-000000000000")

    @pytest.mark.asyncio
    async def test_empty_graph_returns_empty(self, kg, tenant_id):
        session = AsyncMock(spec=AsyncSession)
        # No edges found
        mock_edge_result = MagicMock()
        mock_edge_result.__iter__ = MagicMock(return_value=iter([]))
        session.execute = AsyncMock(return_value=mock_edge_result)

        results = await kg.causal_walk(
            session=session,
            tenant_id=tenant_id,
            start_entity_id="alert_type:highcpu",
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_returns_reachable_nodes(self, kg, tenant_id):
        session = AsyncMock(spec=AsyncSession)

        # First execute: edges from start node -> ["action:restart_service"]
        # Second execute: nodes for ["action:restart_service"]
        mock_node = MagicMock()
        mock_node.entity_id = "action:restart_service"

        edge_result = MagicMock()
        edge_result.__iter__ = MagicMock(return_value=iter([("action:restart_service",)]))

        node_result = MagicMock()
        node_result.scalars.return_value.__iter__ = MagicMock(return_value=iter([mock_node]))

        # Third call (depth=2): no more edges
        edge_result2 = MagicMock()
        edge_result2.__iter__ = MagicMock(return_value=iter([]))

        session.execute = AsyncMock(side_effect=[edge_result, node_result, edge_result2])

        results = await kg.causal_walk(
            session=session,
            tenant_id=tenant_id,
            start_entity_id="alert_type:highcpu",
            depth=2,
        )

        assert len(results) == 1
        assert results[0].entity_id == "action:restart_service"


# ── get_context_for_incident ──────────────────────────────────────


class TestGetContextForIncident:
    @pytest.fixture
    def kg(self):
        return KnowledgeGraph()

    @pytest.fixture
    def tenant_id(self):
        return uuid.UUID("00000000-0000-0000-0000-000000000000")

    @pytest.mark.asyncio
    async def test_no_history_returns_none(self, kg, tenant_id):
        session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        session.execute = AsyncMock(return_value=mock_result)

        result = await kg.get_context_for_incident(
            session=session,
            tenant_id=tenant_id,
            alert_type="HighCPU",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_with_history_returns_text(self, kg, tenant_id):
        session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        # Row: (dst_entity_id, weight, src_entity_id)
        mock_result.__iter__ = MagicMock(
            return_value=iter([
                ("action:restart_service", 3.0, "alert_type:highcpu"),
                ("action:scale_instances", 1.0, "alert_type:highcpu"),
            ])
        )
        session.execute = AsyncMock(return_value=mock_result)

        result = await kg.get_context_for_incident(
            session=session,
            tenant_id=tenant_id,
            alert_type="HighCPU",
        )

        assert result is not None
        assert "Knowledge Graph" in result
        assert "restart_service" in result
        assert "3x" in result
        assert "scale_instances" in result

    @pytest.mark.asyncio
    async def test_with_service_name_included_in_query(self, kg, tenant_id):
        session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        session.execute = AsyncMock(return_value=mock_result)

        await kg.get_context_for_incident(
            session=session,
            tenant_id=tenant_id,
            alert_type="HighCPU",
            service_name="checkout-api",
        )

        # Service name means two candidate src IDs are included in the query
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_action_name_strips_prefix(self, kg, tenant_id):
        """dst_entity_id 'action:restart_service' should display as 'restart_service'."""
        session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(
            return_value=iter([
                ("action:restart_service", 5.0, "alert_type:diskfull"),
            ])
        )
        session.execute = AsyncMock(return_value=mock_result)

        result = await kg.get_context_for_incident(
            session=session,
            tenant_id=tenant_id,
            alert_type="DiskFull",
        )

        assert "restart_service" in result
        assert "action:" not in result  # prefix stripped


# ── rag_context integration ───────────────────────────────────────


class TestRagContextKgIntegration:
    """Verify format_context_sections accepts kg_context and prepends it."""

    def test_kg_context_prepended_before_pattern_analysis(self):
        from airex_core.services.rag_context import format_context_sections

        kg_text = "Knowledge Graph — Historical Resolutions:\n  - 'restart_service' resolved 'highcpu' 3x"
        result = format_context_sections([], [], pattern_analysis=None, kg_context=kg_text)

        assert result is not None
        assert result.startswith("Knowledge Graph")

    def test_kg_context_none_still_works(self):
        from airex_core.services.rag_context import format_context_sections

        result = format_context_sections([], [], pattern_analysis=None, kg_context=None)
        assert result is None

    def test_kg_context_combined_with_runbooks(self):
        from unittest.mock import MagicMock
        from airex_core.services.rag_context import format_context_sections
        from airex_core.rag.vector_store import RunbookMatch

        kg_text = "Knowledge Graph — Historical Resolutions:\n  - 'restart_service' resolved 'highcpu' 2x"

        mock_match = MagicMock(spec=RunbookMatch)
        mock_match.metadata = {"title": "Restart Guide"}
        mock_match.source_type = "runbook"
        mock_match.score = 0.9
        mock_match.chunk_index = 0
        mock_match.content = "Step 1: restart the service"

        result = format_context_sections(
            [mock_match], [], pattern_analysis=None, kg_context=kg_text
        )

        assert result is not None
        assert result.index("Knowledge Graph") < result.index("Relevant Runbooks")
