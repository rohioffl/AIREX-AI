"""Knowledge Graph service — Phase 4 ARE.

Lightweight graph over pgvector (nodes) + pg adjacency (edges) + Redis cache.

Nodes:  infrastructure entities (services, hosts, pods, alert_types, configs)
Edges:  relationships (calls, depends_on, caused_by, resolved_by, what_worked)

Writers (call from task code):
  upsert_node()     — create/update an entity after it is observed
  add_edge()        — record a relationship (increments weight on repeat)
  record_outcome()  — write "what_worked" edge after a RESOLVED incident

Readers (called from rag_context.py):
  get_context_for_incident() — return KG context text for LLM prompt
  causal_walk()              — BFS over neighbors for debugging/audit
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.models.kg_edge import KGEdge
from airex_core.models.kg_node import KGNode

logger = structlog.get_logger(__name__)


# ── Entity ID helpers ─────────────────────────────────────────────

def make_entity_id(entity_type: str, name: str) -> str:
    """Build a canonical entity_id string, e.g. 'service:checkout-api'."""
    return f"{entity_type}:{name.strip().lower()}"


# ── KnowledgeGraph service ────────────────────────────────────────

class KnowledgeGraph:
    """Pure-DB Knowledge Graph — no I/O beyond the session passed in."""

    # ── Writers ──────────────────────────────────────────────────

    async def upsert_node(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        entity_id: str,
        entity_type: str,
        label: str,
        properties: dict[str, Any] | None = None,
    ) -> KGNode:
        """Create or update a KG node. Returns the node (not flushed)."""
        now = datetime.now(timezone.utc)
        stmt = (
            pg_insert(KGNode)
            .values(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                entity_id=entity_id,
                entity_type=entity_type,
                label=label,
                properties=properties or {},
                last_seen_at=now,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_kg_node_entity",
                set_={
                    "label": label,
                    "properties": properties or {},
                    "last_seen_at": now,
                    "updated_at": now,
                },
            )
            .returning(KGNode)
        )
        result = await session.execute(stmt)
        node = result.scalars().one()
        logger.debug(
            "kg_node_upserted",
            tenant_id=str(tenant_id),
            entity_id=entity_id,
            entity_type=entity_type,
        )
        return node

    async def add_edge(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        src_entity_id: str,
        relation: str,
        dst_entity_id: str,
        meta: dict[str, Any] | None = None,
    ) -> KGEdge:
        """Insert edge or increment weight if it already exists."""
        now = datetime.now(timezone.utc)
        stmt = (
            pg_insert(KGEdge)
            .values(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                src_entity_id=src_entity_id,
                relation=relation,
                dst_entity_id=dst_entity_id,
                weight=1.0,
                meta=meta or {},
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_kg_edge_triple",
                set_={
                    "weight": KGEdge.weight + 1.0,
                    "meta": meta or {},
                    "updated_at": now,
                },
            )
            .returning(KGEdge)
        )
        result = await session.execute(stmt)
        edge = result.scalars().one()
        logger.debug(
            "kg_edge_added",
            tenant_id=str(tenant_id),
            src=src_entity_id,
            rel=relation,
            dst=dst_entity_id,
            weight=edge.weight,
        )
        return edge

    async def record_outcome(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        incident_id: uuid.UUID,
        alert_type: str,
        action_type: str,
        success: bool,
        service_name: str | None = None,
    ) -> None:
        """Write 'what_worked' edge after a resolved incident.

        Upserts nodes for alert_type and action_type, then adds a
        weighted edge: alert_type -[what_worked]-> action_type.
        If a service_name is known, also links service -> action_type.
        """
        if not success:
            return

        alert_node_id = make_entity_id("alert_type", alert_type)
        action_node_id = make_entity_id("action", action_type)
        incident_node_id = make_entity_id("incident", str(incident_id))

        await self.upsert_node(
            session, tenant_id, alert_node_id, "alert_type", alert_type
        )
        await self.upsert_node(
            session, tenant_id, action_node_id, "action", action_type
        )
        await self.upsert_node(
            session,
            tenant_id,
            incident_node_id,
            "incident",
            str(incident_id),
            properties={"resolved_by": action_type},
        )

        # alert_type -[what_worked]-> action_type (weight increases on repeat)
        await self.add_edge(
            session,
            tenant_id,
            alert_node_id,
            "what_worked",
            action_node_id,
            meta={"incident_id": str(incident_id)},
        )

        # incident -[resolved_by]-> action_type
        await self.add_edge(
            session,
            tenant_id,
            incident_node_id,
            "resolved_by",
            action_node_id,
        )

        if service_name:
            svc_node_id = make_entity_id("service", service_name)
            await self.upsert_node(
                session, tenant_id, svc_node_id, "service", service_name
            )
            await self.add_edge(
                session,
                tenant_id,
                svc_node_id,
                "what_worked",
                action_node_id,
                meta={"incident_id": str(incident_id), "alert_type": alert_type},
            )

        logger.info(
            "kg_outcome_recorded",
            tenant_id=str(tenant_id),
            incident_id=str(incident_id),
            alert_type=alert_type,
            action_type=action_type,
            service_name=service_name,
        )

    async def upsert_alert_entities(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        incident_id: uuid.UUID,
        alert_type: str,
        host: str | None = None,
        service_name: str | None = None,
        extra_properties: dict[str, Any] | None = None,
    ) -> None:
        """Upsert entity nodes extracted from an investigation.

        Called by investigation_service after evidence is stored.
        Does NOT write outcome edges — those come from record_outcome().
        """
        alert_node_id = make_entity_id("alert_type", alert_type)
        await self.upsert_node(
            session, tenant_id, alert_node_id, "alert_type", alert_type
        )

        if host:
            host_node_id = make_entity_id("host", host)
            await self.upsert_node(
                session,
                tenant_id,
                host_node_id,
                "host",
                host,
                properties=extra_properties,
            )
            # host -[has_alert]-> alert_type
            await self.add_edge(
                session,
                tenant_id,
                host_node_id,
                "has_alert",
                alert_node_id,
                meta={"incident_id": str(incident_id)},
            )

        if service_name:
            svc_node_id = make_entity_id("service", service_name)
            await self.upsert_node(
                session,
                tenant_id,
                svc_node_id,
                "service",
                service_name,
                properties=extra_properties,
            )
            await self.add_edge(
                session,
                tenant_id,
                svc_node_id,
                "has_alert",
                alert_node_id,
                meta={"incident_id": str(incident_id)},
            )

        logger.debug(
            "kg_alert_entities_upserted",
            tenant_id=str(tenant_id),
            incident_id=str(incident_id),
            alert_type=alert_type,
            host=host,
            service_name=service_name,
        )

    # ── Readers ──────────────────────────────────────────────────

    async def causal_walk(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        start_entity_id: str,
        depth: int = 3,
    ) -> list[KGNode]:
        """BFS over outgoing edges from start_entity_id up to `depth` hops.

        Returns all reachable nodes (excluding the start node itself).
        """
        visited: set[str] = {start_entity_id}
        frontier: list[str] = [start_entity_id]
        results: list[KGNode] = []

        for _ in range(depth):
            if not frontier:
                break
            edge_stmt = (
                select(KGEdge.dst_entity_id)
                .where(
                    KGEdge.tenant_id == tenant_id,
                    KGEdge.src_entity_id.in_(frontier),
                )
            )
            edge_rows = await session.execute(edge_stmt)
            next_ids = [r for (r,) in edge_rows if r not in visited]

            if not next_ids:
                break

            node_stmt = select(KGNode).where(
                KGNode.tenant_id == tenant_id,
                KGNode.entity_id.in_(next_ids),
            )
            node_rows = await session.execute(node_stmt)
            nodes = list(node_rows.scalars())
            results.extend(nodes)
            for node in nodes:
                visited.add(node.entity_id)
            frontier = [node.entity_id for node in nodes]

        return results

    async def get_context_for_incident(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        alert_type: str,
        service_name: str | None = None,
    ) -> str | None:
        """Return a KG context text block for the LLM recommendation prompt.

        Queries 'what_worked' edges for the alert_type (and service if known),
        ordered by weight descending. Returns None when no history exists.
        """
        alert_node_id = make_entity_id("alert_type", alert_type)

        candidate_srcs = [alert_node_id]
        if service_name:
            candidate_srcs.append(make_entity_id("service", service_name))

        stmt = (
            select(KGEdge.dst_entity_id, KGEdge.weight, KGEdge.src_entity_id)
            .where(
                KGEdge.tenant_id == tenant_id,
                KGEdge.src_entity_id.in_(candidate_srcs),
                KGEdge.relation == "what_worked",
            )
            .order_by(KGEdge.weight.desc())
            .limit(5)
        )
        rows = await session.execute(stmt)
        edges = list(rows)

        if not edges:
            return None

        lines = ["Knowledge Graph — Historical Resolutions:"]
        for dst, weight, src in edges:
            # dst looks like "action:restart_service" — strip prefix for readability
            action_name = dst.split(":", 1)[-1] if ":" in dst else dst
            src_name = src.split(":", 1)[-1] if ":" in src else src
            count = int(weight)
            lines.append(
                f"  - '{action_name}' resolved '{src_name}' {count}x in the past"
            )

        return "\n".join(lines)


# Module-level singleton — import this in services
knowledge_graph = KnowledgeGraph()

__all__ = ["KnowledgeGraph", "knowledge_graph", "make_entity_id"]
