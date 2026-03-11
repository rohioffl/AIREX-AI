"""
Site24x7 outage history probe.

Analyzes outage patterns from Site24x7 API to detect recurring issues
and provide context for recommendations.
"""

from __future__ import annotations

from typing import Any

import structlog

from airex_core.core.config import settings
from airex_core.investigations.base import (
    BaseInvestigation,
    ProbeCategory,
    ProbeResult,
)

logger = structlog.get_logger()


def should_run_outage_probe(incident_meta: dict) -> bool:
    """Check if the outage history probe should run for this incident."""
    if not settings.SITE24X7_ENABLED:
        return False
    if not settings.SITE24X7_CLIENT_ID or not settings.SITE24X7_REFRESH_TOKEN:
        return False
    source = (incident_meta.get("_source") or "").lower()
    monitor_id = incident_meta.get("MONITORID") or incident_meta.get("monitor_id")
    return source == "site24x7" and bool(monitor_id)


class Site24x7OutageHistoryProbe(BaseInvestigation):
    """Analyze Site24x7 outage history to detect patterns."""

    alert_type = "site24x7_outage_analysis"

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

        if not should_run_outage_probe(incident_meta):
            return ProbeResult(
                tool_name="site24x7_outage_probe",
                raw_output="Site24x7 outage probe skipped: not enabled or missing config",
                category=ProbeCategory.MONITORING,
                probe_type="secondary",
                metrics={"skipped": True, "reason": "not_enabled"},
            )

        try:
            from airex_core.monitoring.site24x7_client import Site24x7Client
            from airex_core.core.events import get_redis

            redis = get_redis()
            client = Site24x7Client(redis=redis)

            sections: list[str] = [
                f"=== Site24x7 Outage History Analysis: {monitor_name} ===",
                f"Monitor ID: {monitor_id}",
                "",
            ]
            metrics: dict[str, Any] = {
                "monitor_id": monitor_id,
                "monitor_name": monitor_name,
            }

            # Get outage report for last 30 days
            try:
                outage_data = await client.get_outage_report(monitor_id, period=3)  # 30 days
                outages = _extract_outages(outage_data)
                
                sections.append("--- Outage History (Last 30 Days) ---")
                sections.append(f"Total Outages: {outages.get('total_outages', 0)}")
                sections.append(f"Total Downtime: {outages.get('total_downtime', 'N/A')}")
                sections.append(f"Average Outage Duration: {outages.get('avg_duration', 'N/A')}")
                
                if outages.get("outages"):
                    sections.append("")
                    sections.append("Recent Outages:")
                    for outage in outages["outages"][:5]:  # Show last 5
                        sections.append(
                            f"  - {outage.get('start_time', 'N/A')}: {outage.get('duration', 'N/A')}"
                        )
                
                # Pattern analysis
                total = outages.get("total_outages", 0)
                if total > 5:
                    sections.append("")
                    sections.append("⚠️ PATTERN DETECTED: This monitor has frequent outages")
                    sections.append(f"   Consider investigating root cause - {total} outages in 30 days")
                elif total > 0:
                    sections.append("")
                    sections.append("ℹ️ This monitor has had some outages recently")
                
                metrics["outage_history_30d"] = outages
            except Exception as exc:
                log.warning("site24x7_outage_failed", error=str(exc))
                sections.append(f"Outage History: ERROR ({exc})")

            log.info("site24x7_outage_probe_complete", metrics_count=len(metrics))

            return ProbeResult(
                tool_name="site24x7_outage_probe",
                raw_output="\n".join(sections),
                category=ProbeCategory.MONITORING,
                probe_type="secondary",
                metrics=metrics,
            )

        except Exception as exc:
            log.error("site24x7_outage_probe_failed", error=str(exc))
            return ProbeResult(
                tool_name="site24x7_outage_probe",
                raw_output=f"Site24x7 outage probe failed: {exc}",
                category=ProbeCategory.MONITORING,
                probe_type="secondary",
                metrics={"error": str(exc), "failed": True},
            )


def _extract_outages(data: dict) -> dict[str, Any]:
    """Extract outage information from Site24x7 outage report."""
    if not data:
        return {"total_outages": 0, "outages": []}
    
    result: dict[str, Any] = {
        "total_outages": 0,
        "total_downtime": "0s",
        "avg_duration": "0s",
        "outages": [],
    }
    
    # Site24x7 outage report structure varies, handle multiple formats
    outages_list = []
    if isinstance(data, dict):
        # Try different possible keys
        outages_list = (
            data.get("outages") or
            data.get("data", {}).get("outages") or
            data.get("outage_details") or
            []
        )
    
    if isinstance(outages_list, list):
        result["total_outages"] = len(outages_list)
        result["outages"] = [
            {
                "start_time": o.get("start_time") or o.get("downtime_start") or "N/A",
                "end_time": o.get("end_time") or o.get("downtime_end") or "N/A",
                "duration": o.get("duration") or o.get("downtime_duration") or "N/A",
            }
            for o in outages_list[:10]  # Limit to 10 most recent
        ]
    
    # Calculate total downtime if available
    if isinstance(data, dict):
        total_downtime = data.get("total_downtime") or data.get("downtime_duration")
        if total_downtime:
            result["total_downtime"] = str(total_downtime)
    
    return result
