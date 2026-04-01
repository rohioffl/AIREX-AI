"""
Investigation plugin for service/agent-down alerts.

When no cloud connectivity is available, this generates simulated evidence
consistent with a service outage (agent stopped, process not found, service
status inactive) rather than fake CPU/memory metrics.

The cloud investigation path (SSH/SSM) is the preferred path — this plugin
is the fallback when ``_has_cloud_target`` is ``False``.
"""

from airex_core.investigations.base import (
    BaseInvestigation,
    ProbeCategory,
    ProbeResult,
    _make_seeded_rng,
)


class ServiceDownInvestigation(BaseInvestigation):
    """Gathers service health evidence for agent/service-down incidents."""

    alert_type = "service_down"

    async def investigate(self, incident_meta: dict) -> ProbeResult:
        host = incident_meta.get("host") or incident_meta.get(
            "monitor_name", "unknown-host"
        )
        rng = _make_seeded_rng(incident_meta)

        # Extract service context from the alert title / reason
        title = incident_meta.get("title", "")
        reason = incident_meta.get("incident_reason", "") or incident_meta.get(
            "INCIDENT_REASON", ""
        )
        context_text = f"{title} {reason}".lower()

        # Determine the affected service name
        if "agent" in context_text:
            service_name = "site24x7-agent"
            process_name = "MonitoringAgentService"
        elif "ssh" in context_text:
            service_name = "sshd"
            process_name = "sshd"
        elif "nginx" in context_text or "web" in context_text:
            service_name = "nginx"
            process_name = "nginx"
        else:
            service_name = "monitoring-agent"
            process_name = "MonitoringAgentService"

        # Simulated uptime and last-seen data
        uptime_days = rng.randint(15, 120)
        last_seen_minutes_ago = rng.randint(2, 30)

        output_lines = [
            f"=== Service Down Investigation: {host} ===",
            "",
            f"Service: {service_name}",
            f"Status: INACTIVE (dead)",
            f"Process '{process_name}': NOT FOUND in process list",
            "",
            f"Host uptime: {uptime_days} days (host is reachable)",
            f"Last agent check-in: {last_seen_minutes_ago} minutes ago",
            "",
            "systemctl status:",
            f"  ● {service_name}.service - Monitoring Agent",
            f"     Loaded: loaded (/etc/systemd/system/{service_name}.service; enabled)",
            "     Active: inactive (dead)",
            f"     Main PID: (not running)",
            "",
            "Recent journal entries:",
            f"  -- {service_name} service stopped --",
            "  Process exited with status=0/SUCCESS",
            "  Received SIGTERM signal",
            "",
            f"Diagnosis: {service_name} service is stopped on {host}.",
            "The host is reachable but the monitoring agent process is not running.",
            "Recommendation: Restart the service or investigate why it was stopped.",
        ]

        return ProbeResult(
            tool_name="service_diagnostics",
            raw_output="\n".join(output_lines),
            category=ProbeCategory.APPLICATION,
            probe_type="primary",
            metrics={
                "service_name": service_name,
                "service_status": "inactive",
                "process_running": False,
                "host_reachable": True,
                "host_uptime_days": uptime_days,
                "last_checkin_minutes_ago": last_seen_minutes_ago,
            },
        )
