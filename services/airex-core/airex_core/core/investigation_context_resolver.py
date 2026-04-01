"""Pre-investigation context resolution.

Enriches incident metadata with cloud target information before probes run.
Extracts cloud provider, instance ID, and private IP from incident meta,
then optionally auto-discovers the full instance details via cloud APIs.

This module has no side-effects on the database — it only reads incident
metadata and cloud APIs, returning an enriched copy of the meta dict.
"""

from __future__ import annotations

import structlog
from typing import Any

logger = structlog.get_logger()


async def resolve_investigation_context(meta: dict[str, Any]) -> dict[str, Any]:
    """Multi-strategy context resolution for investigation targeting.

    Strategy order:
      1. Extract from incident.meta (_cloud, _instance_id, _private_ip)
      2. Auto-discover cloud instance if private_ip is available
      3. Enrich with discovery results (tags, region, zone)

    Returns a *copy* of ``meta`` with ``_has_cloud_target`` set.
    """
    enriched = dict(meta)

    cloud = (enriched.get("_cloud") or "").lower()
    instance_id = (enriched.get("_instance_id") or "").strip()
    private_ip = (enriched.get("_private_ip") or "").strip()

    # Strategy 1: already has explicit cloud target
    if cloud in ("gcp", "aws") and (instance_id or private_ip):
        enriched["_has_cloud_target"] = True
        logger.info(
            "context_resolved_from_meta",
            cloud=cloud,
            instance_id=instance_id or "(none)",
            private_ip=private_ip or "(none)",
        )
        return enriched

    # Strategy 2: auto-discover via cloud APIs if we have a private IP
    if private_ip and not instance_id:
        discovered = await _try_cloud_discovery(enriched, private_ip)
        if discovered:
            return discovered

    # Strategy 3: fall back — no cloud target available
    enriched.setdefault("_has_cloud_target", False)
    return enriched


async def _try_cloud_discovery(
    meta: dict[str, Any],
    private_ip: str,
) -> dict[str, Any] | None:
    """Attempt auto-discovery via cloud APIs. Returns enriched meta or None."""
    try:
        from airex_core.cloud.discovery import discover_instance

        discovered = await discover_instance(private_ip)
        if discovered and discovered.cloud:
            enriched = dict(meta)
            enriched["_cloud"] = discovered.cloud
            enriched["_instance_id"] = discovered.instance_id
            enriched["_private_ip"] = discovered.private_ip or private_ip
            enriched["_has_cloud_target"] = True
            if discovered.zone:
                enriched["_zone"] = discovered.zone
            if discovered.region:
                enriched["_region"] = discovered.region
            if discovered.tags:
                enriched["_discovery_tags"] = discovered.tags
            logger.info(
                "context_resolved_via_discovery",
                cloud=discovered.cloud,
                instance_id=discovered.instance_id,
                private_ip=private_ip,
            )
            return enriched
    except Exception as exc:
        logger.debug("cloud_discovery_skipped", error=str(exc))

    return None
