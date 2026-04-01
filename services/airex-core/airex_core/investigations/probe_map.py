"""
Probe correlation map.

Maps each primary alert type to a list of secondary probe types that
should run in parallel to gather correlated evidence. This enables
the investigation service to run 3-4 probes per incident instead of 1.

Example: a cpu_high alert also runs memory and disk checks, because
CPU saturation often correlates with memory pressure or swap thrashing.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# CORRELATION_MAP: alert_type → list of secondary probe alert_types
#
# Rules:
#   - Primary probe always runs first (from INVESTIGATION_REGISTRY)
#   - Secondary probes run in parallel with each other
#   - Max 3 secondary probes per alert to stay within 10-15s budget
#   - Correlation must be technically justified (not random)
# ---------------------------------------------------------------------------

CORRELATION_MAP: dict[str, list[str]] = {
    # System alerts — cross-check related system resources
    "cpu_high": ["memory_high", "disk_full"],
    "memory_high": ["cpu_high", "disk_full"],
    "disk_full": ["memory_high", "cpu_high"],
    # Network alerts — check application health and ports
    "network_issue": ["http_check", "port_check"],
    # Application alerts — check underlying system resources
    "healthcheck": ["cpu_high", "memory_high", "network_issue"],
    "http_check": ["network_issue", "cpu_high"],
    "api_check": ["http_check", "database_check", "cpu_high"],
    # Infrastructure alerts — check system resources on instance
    "cloud_check": ["cpu_high", "memory_high", "disk_full"],
    # Database alerts — check system resources (disk/CPU often root cause)
    "database_check": ["disk_full", "cpu_high", "memory_high"],
    # Log alerts — check app and system state
    "log_anomaly": ["cpu_high", "memory_high", "http_check"],
    # Plugin alerts — check system resources
    "plugin_check": ["cpu_high", "memory_high"],
    # Heartbeat — check network and system
    "heartbeat_check": ["network_issue", "cpu_high"],
    # Cron — check system resources
    "cron_check": ["cpu_high", "disk_full"],
    # Port — check network
    "port_check": ["network_issue"],
    # Security alerts — check application health
    "ssl_check": ["http_check"],
    # Mail/FTP — check network
    "mail_check": ["network_issue", "port_check"],
    "ftp_check": ["network_issue", "port_check"],
    # Service/agent down — check if host is reachable and system resources
    "service_down": ["network_issue", "cpu_high", "memory_high"],
    "server_check": ["network_issue", "cpu_high", "memory_high"],
}


def get_secondary_probes(alert_type: str) -> list[str]:
    """
    Return the list of secondary probe alert_types for a given primary alert.

    Returns empty list if no correlations defined.
    """
    return CORRELATION_MAP.get(alert_type, [])


def get_all_probe_types(alert_type: str) -> list[str]:
    """
    Return the full list of probes to run: [primary, *secondaries].

    The primary is always the alert_type itself, followed by
    any correlated secondary probes.
    """
    return [alert_type] + get_secondary_probes(alert_type)
