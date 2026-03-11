"""
GCP VPC Flow Logs query.

Queries Cloud Logging for VPC Flow Log entries related to an instance,
looking for denied traffic, unusual patterns, or traffic anomalies.
Used by the infra state probe for network-level diagnostics.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any

import structlog

logger = structlog.get_logger()


async def query_gcp_vpc_flow_logs(
    project: str,
    instance_id: str = "",
    private_ip: str = "",
    zone: str = "",
    sa_key_path: str = "",
    lookback_minutes: int = 15,
    max_results: int = 100,
) -> dict[str, Any]:
    """
    Query GCP VPC Flow Logs from Cloud Logging.

    Filters by instance name or private IP. Returns traffic summary
    including connection counts, top reporters, and bytes transferred.

    Returns a dict with:
      - total_records: number of flow records found
      - connections: list of parsed flow records
      - top_dest_ports: most common destination ports
      - top_sources: most frequent source IPs
      - bytes_total: total bytes transferred
      - denied_count: number of firewall-denied flows
    """
    if not project:
        return _empty_result("", "no GCP project specified")

    if not instance_id and not private_ip:
        return _empty_result("", "no instance_id or private_ip provided")

    try:
        from google.cloud import logging as gcp_logging

        if sa_key_path:
            client = gcp_logging.Client.from_service_account_json(
                sa_key_path, project=project
            )
        else:
            client = gcp_logging.Client(project=project)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=lookback_minutes)

        # Build filter for VPC flow logs
        time_filter = (
            f'timestamp >= "{start_time.isoformat()}" '
            f'AND timestamp <= "{end_time.isoformat()}"'
        )

        # VPC flow logs use the resource type "gce_subnetwork"
        resource_filter = 'resource.type="gce_subnetwork"'
        log_filter = 'logName:"compute.googleapis.com%2Fvpc_flows"'

        # Filter by instance
        instance_filter = ""
        if instance_id:
            instance_filter = (
                f' AND (jsonPayload.src_instance.vm_name="{instance_id}"'
                f' OR jsonPayload.dest_instance.vm_name="{instance_id}")'
            )
        elif private_ip:
            instance_filter = (
                f' AND (jsonPayload.connection.src_ip="{private_ip}"'
                f' OR jsonPayload.connection.dest_ip="{private_ip}")'
            )

        full_filter = (
            f"{resource_filter} AND {log_filter} AND {time_filter}{instance_filter}"
        )

        loop = asyncio.get_running_loop()
        entries = await loop.run_in_executor(
            None,
            lambda: list(
                client.list_entries(
                    filter_=full_filter,
                    order_by=gcp_logging.DESCENDING,
                    max_results=max_results,
                    resource_names=[f"projects/{project}"],
                )
            ),
        )

        records = _parse_flow_entries(entries)
        resource_id = instance_id or private_ip

        # Compute summary
        dest_ports: dict[int, int] = {}
        src_counts: dict[str, int] = {}
        bytes_total = 0
        denied_count = 0

        for r in records:
            port = r.get("dest_port", 0)
            if port:
                dest_ports[port] = dest_ports.get(port, 0) + 1

            src = r.get("src_ip", "")
            if src and src != private_ip:
                src_counts[src] = src_counts.get(src, 0) + 1

            bytes_total += r.get("bytes_sent", 0)

            if r.get("disposition") == "DENIED":
                denied_count += 1

        top_dest_ports = sorted(dest_ports.items(), key=lambda x: x[1], reverse=True)[
            :10
        ]
        top_sources = sorted(src_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "total_records": len(records),
            "top_dest_ports": [{"port": p, "count": c} for p, c in top_dest_ports],
            "top_sources": [{"ip": ip, "count": c} for ip, c in top_sources],
            "bytes_total": bytes_total,
            "denied_count": denied_count,
            "lookback_minutes": lookback_minutes,
            "resource_id": resource_id,
            "project": project,
        }

    except ImportError:
        logger.warning("gcp_logging_not_installed")
        return _empty_result(
            instance_id or private_ip,
            "google-cloud-logging not installed",
        )
    except Exception as exc:
        logger.warning("gcp_vpc_flow_query_failed", error=str(exc))
        return _empty_result(instance_id or private_ip, str(exc))


def _parse_flow_entries(entries: list) -> list[dict[str, Any]]:
    """Parse GCP VPC Flow Log entries into simplified dicts."""
    records = []
    for entry in entries:
        payload = entry.payload if hasattr(entry, "payload") else {}
        if not isinstance(payload, dict):
            continue

        connection = payload.get("connection", {})
        src_instance = payload.get("src_instance", {})
        dest_instance = payload.get("dest_instance", {})

        record: dict[str, Any] = {
            "src_ip": connection.get("src_ip", ""),
            "dest_ip": connection.get("dest_ip", ""),
            "src_port": connection.get("src_port", 0),
            "dest_port": connection.get("dest_port", 0),
            "protocol": connection.get("protocol", 0),
            "bytes_sent": payload.get("bytes_sent", 0),
            "packets_sent": payload.get("packets_sent", 0),
            "src_instance": src_instance.get("vm_name", ""),
            "dest_instance": dest_instance.get("vm_name", ""),
            "disposition": payload.get("reporter", ""),
        }
        records.append(record)

    return records


def _empty_result(resource_id: str, error: str = "") -> dict[str, Any]:
    return {
        "total_records": 0,
        "top_dest_ports": [],
        "top_sources": [],
        "bytes_total": 0,
        "denied_count": 0,
        "lookback_minutes": 0,
        "resource_id": resource_id,
        "project": "",
        "error": error,
    }
