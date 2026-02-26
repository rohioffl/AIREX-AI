"""
Site24x7 monitoring probe.

Queries the Site24x7 REST API for monitor details, current status,
performance data, and outage history. Only runs when:
  1. SITE24X7_ENABLED is True
  2. incident.meta._source == "site24x7"
  3. monitor_id exists in incident meta (from MONITORID webhook field)

This probe runs as a secondary/correlation probe alongside the primary
investigation plugin — it enriches the evidence with monitoring context.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.core.config import settings
from app.investigations.base import (
    BaseInvestigation,
    ProbeCategory,
    ProbeResult,
)

logger = structlog.get_logger()


def should_run_site24x7_probe(incident_meta: dict) -> bool:
    """Check if the Site24x7 probe should run for this incident."""
    if not settings.SITE24X7_ENABLED:
        return False
    if not settings.SITE24X7_CLIENT_ID or not settings.SITE24X7_REFRESH_TOKEN:
        return False
    source = (incident_meta.get("_source") or "").lower()
    monitor_id = incident_meta.get("MONITORID") or incident_meta.get("monitor_id")
    return source == "site24x7" and bool(monitor_id)


class Site24x7Probe(BaseInvestigation):
    """Query Site24x7 API for monitor details, status, and performance."""

    alert_type = "site24x7_enrichment"

    async def investigate(self, incident_meta: dict) -> ProbeResult:
        monitor_id = (
            incident_meta.get("MONITORID") or incident_meta.get("monitor_id") or ""
        )
        monitor_name = (
            incident_meta.get("MONITORNAME")
            or incident_meta.get("monitor_name")
            or "unknown"
        )

        log = logger.bind(monitor_id=monitor_id, monitor_name=monitor_name)

        if not should_run_site24x7_probe(incident_meta):
            return ProbeResult(
                tool_name="site24x7_probe",
                raw_output="Site24x7 probe skipped: not enabled or missing config",
                category=ProbeCategory.MONITORING,
                probe_type="secondary",
                metrics={"skipped": True, "reason": "not_enabled"},
            )

        try:
            from app.monitoring.site24x7_client import Site24x7Client
            from app.core.events import get_redis

            redis = get_redis()
            client = Site24x7Client(redis=redis)

            sections: list[str] = [
                f"=== Site24x7 Monitor Enrichment: {monitor_name} ===",
                f"Monitor ID: {monitor_id}",
                "",
            ]
            metrics: dict[str, Any] = {
                "monitor_id": monitor_id,
                "monitor_name": monitor_name,
            }

            # 1. Current status
            try:
                status_data = await client.get_current_status(monitor_id)
                status = _extract_status(status_data)
                sections.append("--- Current Status ---")
                for key, val in status.items():
                    sections.append(f"  {key}: {val}")
                metrics.update(status)
            except Exception as exc:
                log.warning("site24x7_status_failed", error=str(exc))
                sections.append(f"Current Status: ERROR ({exc})")

            sections.append("")

            # 2. Monitor details
            try:
                monitor_data = await client.get_monitor(monitor_id)
                details = _extract_monitor_details(monitor_data)
                sections.append("--- Monitor Configuration ---")
                for key, val in details.items():
                    sections.append(f"  {key}: {val}")
                metrics.update(details)
            except Exception as exc:
                log.warning("site24x7_monitor_failed", error=str(exc))
                sections.append(f"Monitor Details: ERROR ({exc})")

            sections.append("")

            # 3. Performance report (last 24h)
            try:
                perf_data = await client.get_performance_report(monitor_id, period=1)
                perf = _extract_performance(perf_data)
                sections.append("--- Performance (Last 24h) ---")
                for key, val in perf.items():
                    sections.append(f"  {key}: {val}")
                metrics["performance_24h"] = perf
            except Exception as exc:
                log.warning("site24x7_performance_failed", error=str(exc))
                sections.append(f"Performance: ERROR ({exc})")

            sections.append("")

            # 4. Availability summary (last 24h)
            try:
                avail_data = await client.get_availability_summary(monitor_id, period=1)
                avail = _extract_availability(avail_data)
                sections.append("--- Availability (Last 24h) ---")
                for key, val in avail.items():
                    sections.append(f"  {key}: {val}")
                metrics["availability_24h"] = avail
            except Exception as exc:
                log.warning("site24x7_availability_failed", error=str(exc))
                sections.append(f"Availability: ERROR ({exc})")

            log.info("site24x7_probe_complete", metrics_count=len(metrics))

            return ProbeResult(
                tool_name="site24x7_probe",
                raw_output="\n".join(sections),
                category=ProbeCategory.MONITORING,
                probe_type="secondary",
                metrics=metrics,
            )

        except Exception as exc:
            log.error("site24x7_probe_failed", error=str(exc))
            return ProbeResult(
                tool_name="site24x7_probe",
                raw_output=f"Site24x7 probe failed: {exc}",
                category=ProbeCategory.MONITORING,
                probe_type="secondary",
                metrics={"error": str(exc), "failed": True},
            )


def _extract_status(data: dict) -> dict[str, Any]:
    """Extract key fields from current_status response."""
    if not data:
        return {"status": "unknown"}
    # Handle both direct and nested responses
    if isinstance(data, dict) and "monitors" in data:
        monitors = data["monitors"]
        if isinstance(monitors, list) and monitors:
            data = monitors[0]
    return {
        "status": data.get("status_name") or data.get("status", "unknown"),
        "last_polled_time": data.get("last_polled_time", ""),
        "attribute_value": data.get("attribute_value", ""),
        "unit": data.get("unit", ""),
    }


def _extract_monitor_details(data: dict) -> dict[str, Any]:
    """Extract key fields from monitor details response."""
    if not data:
        return {}
    return {
        "display_name": data.get("display_name", ""),
        "type": data.get("type_name") or data.get("type", ""),
        "hostname": data.get("hostname", ""),
        "poll_interval": data.get("poll_interval", ""),
        "timeout": data.get("timeout", ""),
        "location_count": len(
            data.get("location_profile_details", {}).get("locations", [])
        ),
    }


def _extract_performance(data: dict) -> dict[str, Any]:
    """Extract key fields from performance report."""
    if not data:
        return {}
    # Performance data varies by monitor type
    result: dict[str, Any] = {}
    if isinstance(data, dict):
        result["response_time_avg"] = data.get("response_time", {}).get("average", "")
        result["response_time_max"] = data.get("response_time", {}).get("max", "")
        result["throughput"] = data.get("throughput", "")
    return result


def _extract_availability(data: dict) -> dict[str, Any]:
    """Extract key fields from availability summary."""
    if not data:
        return {}
    result: dict[str, Any] = {}
    if isinstance(data, dict):
        result["availability_percentage"] = data.get("availability_percentage", "")
        result["downtime_duration"] = data.get("downtime_duration", "")
        result["outage_count"] = data.get("no_of_outages", 0)
    return result
