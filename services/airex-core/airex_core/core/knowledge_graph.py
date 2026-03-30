"""Knowledge Graph service — Phase 4 ARE.

Lightweight graph over pgvector (nodes) + pg adjacency (edges) with temporal
state tracking for safer retrieval and feedback.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.models.kg_edge import KGEdge
from airex_core.models.kg_node import KGNode

logger = structlog.get_logger(__name__)


def make_entity_id(entity_type: str, name: str) -> str:
    """Build a canonical entity_id string, e.g. 'service:checkout-api'."""
    return f"{entity_type}:{name.strip().lower()}"


def make_versioned_entity_id(entity_type: str, name: str, state_hash: str) -> str:
    """Build a deterministic versioned entity id for hashed state snapshots."""
    return f"{entity_type}:{name.strip().lower()}:{state_hash[:12]}"


def build_state_hash(payload: dict[str, Any] | None) -> str:
    """Hash a state payload into a stable short identifier."""
    normalized = json.dumps(payload or {}, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeGraph:
    """Pure-DB Knowledge Graph — no I/O beyond the session passed in."""

    async def upsert_node(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        entity_id: str,
        entity_type: str,
        label: str,
        properties: dict[str, Any] | None = None,
        *,
        observed_at: datetime | None = None,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        state_hash: str | None = None,
    ) -> KGNode:
        """Create or update a KG node with temporal state metadata."""
        now = _utcnow()
        observed_ts = observed_at or now
        valid_from_ts = valid_from or observed_ts
        node_state_hash = state_hash or build_state_hash(properties)
        stmt = (
            pg_insert(KGNode)
            .values(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                entity_id=entity_id,
                entity_type=entity_type,
                label=label,
                properties=properties or {},
                observed_at=observed_ts,
                valid_from=valid_from_ts,
                valid_to=valid_to,
                state_hash=node_state_hash,
                last_seen_at=observed_ts,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_kg_node_entity",
                set_={
                    "label": label,
                    "properties": properties or {},
                    "observed_at": observed_ts,
                    "valid_from": valid_from_ts,
                    "valid_to": valid_to,
                    "state_hash": node_state_hash,
                    "last_seen_at": observed_ts,
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
            state_hash=node_state_hash,
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
        *,
        observed_at: datetime | None = None,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        causal_confidence: float | None = None,
    ) -> KGEdge:
        """Insert edge or increment weight if it already exists."""
        now = _utcnow()
        observed_ts = observed_at or now
        valid_from_ts = valid_from or observed_ts
        confidence = max(0.0, min(1.0, causal_confidence if causal_confidence is not None else 0.5))
        stmt = (
            pg_insert(KGEdge)
            .values(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                src_entity_id=src_entity_id,
                relation=relation,
                dst_entity_id=dst_entity_id,
                weight=1.0,
                causal_confidence=confidence,
                meta=meta or {},
                observed_at=observed_ts,
                valid_from=valid_from_ts,
                valid_to=valid_to,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_kg_edge_triple",
                set_={
                    "weight": KGEdge.weight + 1.0,
                    "causal_confidence": func.greatest(KGEdge.causal_confidence, confidence),
                    "meta": meta or {},
                    "observed_at": observed_ts,
                    "valid_from": valid_from_ts,
                    "valid_to": valid_to,
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
            causal_confidence=confidence,
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
        *,
        observed_at: datetime | None = None,
        resolution_seconds: int | None = None,
    ) -> None:
        """Write 'what_worked' edges after a resolved incident."""
        if not success:
            return

        observed_ts = observed_at or _utcnow()
        alert_node_id = make_entity_id("alert_type", alert_type)
        action_node_id = make_entity_id("action", action_type)
        incident_node_id = make_entity_id("incident", str(incident_id))

        await self.upsert_node(
            session,
            tenant_id,
            alert_node_id,
            "alert_type",
            alert_type,
            properties={"latest_resolution_seconds": resolution_seconds},
            observed_at=observed_ts,
        )
        await self.upsert_node(
            session,
            tenant_id,
            action_node_id,
            "action",
            action_type,
            observed_at=observed_ts,
        )
        await self.upsert_node(
            session,
            tenant_id,
            incident_node_id,
            "incident",
            str(incident_id),
            properties={
                "resolved_by": action_type,
                "resolved_at": observed_ts.isoformat(),
                "resolution_seconds": resolution_seconds,
            },
            observed_at=observed_ts,
        )

        outcome_meta = {
            "incident_id": str(incident_id),
            "observed_at": observed_ts.isoformat(),
            "resolution_seconds": resolution_seconds,
        }
        await self.add_edge(
            session,
            tenant_id,
            alert_node_id,
            "what_worked",
            action_node_id,
            meta=outcome_meta,
            observed_at=observed_ts,
            causal_confidence=0.8,
        )
        await self.add_edge(
            session,
            tenant_id,
            incident_node_id,
            "resolved_by",
            action_node_id,
            meta=outcome_meta,
            observed_at=observed_ts,
            causal_confidence=0.9,
        )

        if service_name:
            svc_node_id = make_entity_id("service", service_name)
            await self.upsert_node(
                session,
                tenant_id,
                svc_node_id,
                "service",
                service_name,
                properties={"latest_resolution_seconds": resolution_seconds},
                observed_at=observed_ts,
            )
            await self.add_edge(
                session,
                tenant_id,
                svc_node_id,
                "what_worked",
                action_node_id,
                meta={**outcome_meta, "alert_type": alert_type},
                observed_at=observed_ts,
                causal_confidence=0.82,
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
        *,
        observed_at: datetime | None = None,
    ) -> None:
        """Upsert entity nodes extracted from an investigation."""
        observed_ts = observed_at or _utcnow()
        alert_node_id = make_entity_id("alert_type", alert_type)
        incident_node_id = make_entity_id("incident", str(incident_id))
        await self.upsert_node(
            session,
            tenant_id,
            alert_node_id,
            "alert_type",
            alert_type,
            properties={
                "last_incident_id": str(incident_id),
                "last_alert_type": alert_type,
            },
            observed_at=observed_ts,
        )
        await self.upsert_node(
            session,
            tenant_id,
            incident_node_id,
            "incident",
            str(incident_id),
            properties={"alert_type": alert_type, "observed_at": observed_ts.isoformat()},
            observed_at=observed_ts,
        )
        await self.add_edge(
            session,
            tenant_id,
            incident_node_id,
            "observed_alert",
            alert_node_id,
            meta={"incident_id": str(incident_id), "alert_type": alert_type},
            observed_at=observed_ts,
            causal_confidence=0.65,
        )

        if host:
            host_node_id = make_entity_id("host", host)
            host_props = dict(extra_properties or {})
            host_props.update(
                {
                    "last_incident_id": str(incident_id),
                    "last_alert_type": alert_type,
                }
            )
            await self.upsert_node(
                session,
                tenant_id,
                host_node_id,
                "host",
                host,
                properties=host_props,
                observed_at=observed_ts,
            )
            await self.add_edge(
                session,
                tenant_id,
                host_node_id,
                "has_alert",
                alert_node_id,
                meta={"incident_id": str(incident_id)},
                observed_at=observed_ts,
                causal_confidence=0.6,
            )
            await self.add_edge(
                session,
                tenant_id,
                incident_node_id,
                "observed_entity",
                host_node_id,
                meta={"incident_id": str(incident_id), "entity_type": "host"},
                observed_at=observed_ts,
                causal_confidence=0.7,
            )

        if service_name:
            svc_node_id = make_entity_id("service", service_name)
            svc_props = dict(extra_properties or {})
            svc_props.update(
                {
                    "last_incident_id": str(incident_id),
                    "last_alert_type": alert_type,
                }
            )
            await self.upsert_node(
                session,
                tenant_id,
                svc_node_id,
                "service",
                service_name,
                properties=svc_props,
                observed_at=observed_ts,
            )
            await self.add_edge(
                session,
                tenant_id,
                svc_node_id,
                "has_alert",
                alert_node_id,
                meta={"incident_id": str(incident_id)},
                observed_at=observed_ts,
                causal_confidence=0.7,
            )
            await self.add_edge(
                session,
                tenant_id,
                incident_node_id,
                "observed_entity",
                svc_node_id,
                meta={"incident_id": str(incident_id), "entity_type": "service"},
                observed_at=observed_ts,
                causal_confidence=0.75,
            )

        logger.debug(
            "kg_alert_entities_upserted",
            tenant_id=str(tenant_id),
            incident_id=str(incident_id),
            alert_type=alert_type,
            host=host,
            service_name=service_name,
        )

    async def record_incident_timeline(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        incident_id: uuid.UUID,
        alert_type: str,
        *,
        service_name: str | None = None,
        host: str | None = None,
        observations: list[str] | None = None,
        metrics: dict[str, Any] | None = None,
        observed_at: datetime | None = None,
        config_name: str | None = None,
        config_snapshot: dict[str, Any] | None = None,
    ) -> None:
        """Record a time-indexed incident metric/config snapshot in the KG."""
        observed_ts = observed_at or _utcnow()
        incident_node_id = make_entity_id("incident", str(incident_id))
        await self.upsert_node(
            session,
            tenant_id,
            incident_node_id,
            "incident",
            str(incident_id),
            properties={"alert_type": alert_type, "observed_at": observed_ts.isoformat()},
            observed_at=observed_ts,
        )

        snapshot_payload = {
            "alert_type": alert_type,
            "service_name": service_name,
            "host": host,
            "observations": observations or [],
            "metrics": metrics or {},
        }
        state_hash = build_state_hash(snapshot_payload)
        metric_node_id = make_versioned_entity_id("metric_snapshot", str(incident_id), state_hash)
        await self.upsert_node(
            session,
            tenant_id,
            metric_node_id,
            "metric_snapshot",
            f"{alert_type} snapshot",
            properties=snapshot_payload,
            observed_at=observed_ts,
            state_hash=state_hash,
        )
        timeline_meta = {
            "incident_id": str(incident_id),
            "alert_type": alert_type,
            "service_name": service_name,
            "host": host,
            "state_hash": state_hash,
            "observed_at": observed_ts.isoformat(),
        }
        await self.add_edge(
            session,
            tenant_id,
            incident_node_id,
            "observed_metric",
            metric_node_id,
            meta=timeline_meta,
            observed_at=observed_ts,
            causal_confidence=self._estimate_causal_confidence(
                observations=observations,
                metrics=metrics,
            ),
        )

        if service_name:
            service_node_id = make_entity_id("service", service_name)
            service_props = {
                "last_state_hash": state_hash,
                "last_observation": (observations or [""])[0] if observations else "",
                "latest_incident_id": str(incident_id),
            }
            await self.upsert_node(
                session,
                tenant_id,
                service_node_id,
                "service",
                service_name,
                properties=service_props,
                observed_at=observed_ts,
                state_hash=state_hash,
            )

        if config_name and config_snapshot:
            config_hash = build_state_hash(config_snapshot)
            config_root_id = make_entity_id("config", config_name)
            config_version_id = make_versioned_entity_id("config", config_name, config_hash)
            await self.upsert_node(
                session,
                tenant_id,
                config_root_id,
                "config",
                config_name,
                properties={
                    "latest_config_state_hash": config_hash,
                    "latest_incident_id": str(incident_id),
                },
                observed_at=observed_ts,
                state_hash=config_hash,
            )
            await self.upsert_node(
                session,
                tenant_id,
                config_version_id,
                "config_version",
                config_name,
                properties=config_snapshot,
                observed_at=observed_ts,
                state_hash=config_hash,
            )
            config_meta = {
                "incident_id": str(incident_id),
                "config_name": config_name,
                "config_hash": config_hash,
                "observed_at": observed_ts.isoformat(),
            }
            await self.add_edge(
                session,
                tenant_id,
                config_root_id,
                "versioned_as",
                config_version_id,
                meta=config_meta,
                observed_at=observed_ts,
                causal_confidence=0.8,
            )
            await self.add_edge(
                session,
                tenant_id,
                incident_node_id,
                "observed_config",
                config_version_id,
                meta=config_meta,
                observed_at=observed_ts,
                causal_confidence=0.75,
            )

    async def causal_walk(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        start_entity_id: str,
        depth: int = 3,
    ) -> list[KGNode]:
        """BFS over outgoing edges from start_entity_id up to `depth` hops."""
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
        """Return KG context text including current state and historical outcomes."""
        alert_node_id = make_entity_id("alert_type", alert_type)
        candidate_srcs = [alert_node_id]
        if service_name:
            candidate_srcs.append(make_entity_id("service", service_name))

        state_stmt = (
            select(
                KGNode.entity_id,
                KGNode.label,
                KGNode.valid_from,
                KGNode.last_seen_at,
                KGNode.state_hash,
                KGNode.properties,
            )
            .where(
                KGNode.tenant_id == tenant_id,
                KGNode.entity_id.in_(candidate_srcs),
                KGNode.valid_to.is_(None),
            )
            .order_by(KGNode.last_seen_at.desc())
            .limit(3)
        )
        state_rows = list(await session.execute(state_stmt))

        history_stmt = (
            select(
                KGEdge.dst_entity_id,
                KGEdge.weight,
                KGEdge.src_entity_id,
                KGEdge.causal_confidence,
                KGEdge.observed_at,
            )
            .where(
                KGEdge.tenant_id == tenant_id,
                KGEdge.src_entity_id.in_(candidate_srcs),
                KGEdge.relation == "what_worked",
                KGEdge.valid_to.is_(None),
            )
            .order_by(KGEdge.weight.desc(), KGEdge.observed_at.desc())
            .limit(5)
        )
        history_rows = list(await session.execute(history_stmt))

        if not state_rows and not history_rows:
            return None

        lines: list[str] = []
        if state_rows:
            lines.append("Knowledge Graph — Current State:")
            for entity_id, label, valid_from, last_seen_at, state_hash, properties in state_rows:
                entity_name = entity_id.split(":", 1)[-1] if ":" in entity_id else entity_id
                last_observation = ""
                if isinstance(properties, dict):
                    candidate = properties.get("last_observation") or properties.get("last_alert_type")
                    if candidate:
                        last_observation = f"; last={candidate}"
                lines.append(
                    "  - "
                    f"'{entity_name}' current since {self._format_dt(valid_from)} "
                    f"(last seen {self._format_dt(last_seen_at)}, state={str(state_hash)[:8]}{last_observation})"
                )

        if history_rows:
            lines.append("Knowledge Graph — Historical Resolutions:")
            for dst, weight, src, causal_confidence, observed_at in history_rows:
                action_name = dst.split(":", 1)[-1] if ":" in dst else dst
                src_name = src.split(":", 1)[-1] if ":" in src else src
                count = int(weight)
                confidence = float(causal_confidence or 0.0)
                lines.append(
                    "  - "
                    f"'{action_name}' resolved '{src_name}' {count}x in the past "
                    f"(causal_confidence={confidence:.2f}, last_seen={self._format_dt(observed_at)})"
                )

        return "\n".join(lines)

    def _estimate_causal_confidence(
        self,
        *,
        observations: list[str] | None,
        metrics: dict[str, Any] | None,
    ) -> float:
        observation_count = len([item for item in (observations or []) if str(item).strip()])
        metric_count = len(metrics or {})
        return max(0.4, min(0.9, round(0.45 + (observation_count * 0.05) + (metric_count * 0.03), 2)))

    def _format_dt(self, value: datetime | None) -> str:
        if not isinstance(value, datetime):
            return "unknown"
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


knowledge_graph = KnowledgeGraph()

__all__ = [
    "KnowledgeGraph",
    "build_state_hash",
    "knowledge_graph",
    "make_entity_id",
    "make_versioned_entity_id",
]
