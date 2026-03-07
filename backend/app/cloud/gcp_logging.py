"""
GCP Cloud Logging (Log Explorer) connector.

Queries recent logs for a specific resource (instance, project)
to collect evidence during incident investigation.

Authentication:
  1. GCP_SERVICE_ACCOUNT_KEY (explicit JSON key file)
  2. Application Default Credentials (ADC) — auto on GCE/GKE
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone, timedelta

import structlog

from app.core.config import settings

logger = structlog.get_logger()


async def query_gcp_logs(
    project: str = "",
    instance_id: str = "",
    private_ip: str = "",
    log_filter: str = "",
    severity: str = "ERROR",
    lookback_minutes: int = 30,
    max_entries: int = 50,
    sa_key_path: str = "",
) -> str:
    """
    Query GCP Cloud Logging for recent log entries.

    Args:
        project: GCP project ID
        instance_id: GCE instance name (used in resource filter)
        private_ip: Private IP (used in log text filter)
        log_filter: Additional Cloud Logging filter expression
        severity: Minimum severity (DEFAULT, DEBUG, INFO, WARNING, ERROR, CRITICAL)
        lookback_minutes: How far back to search
        max_entries: Maximum log entries to return

    Returns:
        Formatted log output string.
    """
    project = project or settings.GCP_PROJECT_ID
    if not project:
        return "ERROR: GCP_PROJECT_ID not configured. Cannot query logs."

    log = logger.bind(project=project, instance=instance_id)
    log.info("gcp_logs_querying", severity=severity, lookback_minutes=lookback_minutes)

    loop = asyncio.get_event_loop()

    try:
        # Build client
        client = await loop.run_in_executor(
            None, lambda: _create_logging_client(project, sa_key_path)
        )

        # Build filter
        filter_str = _build_filter(
            instance_id=instance_id,
            private_ip=private_ip,
            extra_filter=log_filter,
            severity=severity,
            lookback_minutes=lookback_minutes,
        )

        log.debug("gcp_logs_filter", filter=filter_str)

        # Execute query
        entries = await loop.run_in_executor(
            None,
            lambda: list(
                client.list_entries(
                    filter_=filter_str,
                    order_by="timestamp desc",
                    max_results=max_entries,
                    page_size=max_entries,
                )
            ),
        )

        log.info("gcp_logs_retrieved", count=len(entries))

        # Format output
        return _format_log_entries(entries, project, instance_id)

    except Exception as exc:
        log.error("gcp_logs_query_failed", error=str(exc))
        return f"ERROR querying GCP logs: {exc}"


def _create_logging_client(project: str, sa_key_path: str = ""):
    """Create a Cloud Logging client with proper credentials."""
    from google.cloud import logging as cloud_logging

    # Priority: explicit key path > global setting > ADC
    key_path = sa_key_path or settings.GCP_SERVICE_ACCOUNT_KEY or ""
    if key_path and os.path.exists(key_path):
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_file(key_path)
        logger.info("gcp_logging_auth_explicit_key", key_path=key_path)
        return cloud_logging.Client(project=project, credentials=creds)

    logger.info("gcp_logging_auth_adc")
    return cloud_logging.Client(project=project)


def _build_filter(
    instance_id: str = "",
    private_ip: str = "",
    extra_filter: str = "",
    severity: str = "ERROR",
    lookback_minutes: int = 30,
) -> str:
    """Build a Cloud Logging filter expression."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(minutes=lookback_minutes)
    time_filter = f'timestamp >= "{since.isoformat()}"'

    parts = [time_filter]

    if severity:
        parts.append(f'severity >= "{severity.upper()}"')

    if instance_id:
        parts.append(
            f'(resource.labels.instance_id="{instance_id}" '
            f'OR labels.instance_name="{instance_id}" '
            f'OR textPayload:"{instance_id}")'
        )

    if private_ip:
        parts.append(f'textPayload:"{private_ip}"')

    if extra_filter:
        parts.append(f"({extra_filter})")

    return "\n".join(parts)


def _format_log_entries(entries: list, project: str, instance_id: str) -> str:
    """Format Cloud Logging entries into a readable report."""
    if not entries:
        return (
            f"=== GCP Log Explorer: {project}/{instance_id or 'all'} ===\n\n"
            f"No log entries found matching the filter criteria.\n"
            f"This may indicate the instance is not emitting logs to Cloud Logging."
        )

    lines = [
        f"=== GCP Log Explorer: {project}/{instance_id or 'all'} ===",
        f"Entries found: {len(entries)}",
        "",
    ]

    severity_counts: dict[str, int] = {}

    for entry in entries:
        sev = str(getattr(entry, "severity", "DEFAULT"))
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

        ts = getattr(entry, "timestamp", "")
        if hasattr(ts, "strftime"):
            ts = ts.strftime("%Y-%m-%d %H:%M:%S UTC")

        resource = getattr(entry, "resource", None)
        resource_str = ""
        if resource:
            resource_str = f"[{resource.type}]"

        payload = getattr(entry, "payload", None) or getattr(entry, "text_payload", "")
        if isinstance(payload, dict):
            message = payload.get("message", "") or payload.get(
                "textPayload", str(payload)
            )
        else:
            message = str(payload)

        # Truncate long messages
        if len(message) > 500:
            message = message[:500] + "..."

        log_name = getattr(entry, "log_name", "")
        short_log = log_name.split("/")[-1] if log_name else ""

        lines.append(f"[{ts}] {sev:>8} {resource_str} {short_log}")
        lines.append(f"  {message}")
        lines.append("")

    # Summary
    lines.insert(2, f"Severity breakdown: {severity_counts}")
    lines.append("--- End of Log Explorer results ---")

    return "\n".join(lines)


async def query_gcp_serial_port_output(
    instance_name: str,
    project: str = "",
    zone: str = "",
    port: int = 1,
) -> str:
    """
    Get serial port output from a GCE instance.

    Useful for boot diagnostics, kernel panics, etc. even when
    SSH is not available.
    """
    from google.cloud import compute_v1

    project = project or settings.GCP_PROJECT_ID
    zone = zone or settings.GCP_ZONE

    if not project or not zone:
        return "ERROR: GCP_PROJECT_ID and GCP_ZONE required for serial port output."

    loop = asyncio.get_event_loop()

    try:
        client = compute_v1.InstancesClient()
        request = compute_v1.GetSerialPortOutputInstanceRequest(
            instance=instance_name,
            project=project,
            zone=zone,
            port=port,
        )
        response = await loop.run_in_executor(
            None,
            lambda: client.get_serial_port_output(request=request),
        )
        output = response.contents or ""
        # Return last 200 lines
        lines = output.strip().split("\n")
        if len(lines) > 200:
            lines = lines[-200:]
        return (
            f"=== Serial Port Output: {instance_name} (last {len(lines)} lines) ===\n"
            + "\n".join(lines)
        )

    except Exception as exc:
        logger.warning("gcp_serial_port_failed", instance=instance_name, error=str(exc))
        return f"ERROR getting serial port output: {exc}"
