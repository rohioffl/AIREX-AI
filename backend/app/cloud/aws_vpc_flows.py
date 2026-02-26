"""
AWS VPC Flow Logs query.

Queries CloudWatch Logs for VPC Flow Log entries related to an instance,
looking for rejected traffic, unusual patterns, or traffic spikes.
Used by the infra state probe for network-level diagnostics.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.cloud.tenant_config import AWSConfig

logger = structlog.get_logger()

# Common VPC Flow Log group name patterns
_FLOW_LOG_PREFIXES = [
    "/aws/vpc/flowlogs",
    "vpc-flow-logs",
    "VPCFlowLogs",
    "/vpc/flow",
]


async def query_vpc_flow_logs(
    instance_id: str = "",
    private_ip: str = "",
    region: str = "",
    aws_config: "AWSConfig | None" = None,
    lookback_minutes: int = 15,
    max_events: int = 100,
) -> dict[str, Any]:
    """
    Query VPC Flow Logs from CloudWatch for traffic related to an instance.

    Filters by the instance's private IP (ENI source/dest). Returns
    traffic summary including reject counts, top talkers, and port stats.

    Returns a dict with:
      - total_records: number of flow records found
      - accepted_count / rejected_count: traffic disposition
      - top_rejected_ports: ports with most rejected traffic
      - top_sources: most frequent source IPs
      - bytes_in / bytes_out: total traffic volume
      - flow_log_group: which log group was queried
    """
    if not private_ip and not instance_id:
        return _empty_result("", "No private_ip or instance_id provided")

    try:
        from app.cloud.aws_auth import get_aws_client

        loop = asyncio.get_running_loop()

        client = await loop.run_in_executor(
            None,
            lambda: get_aws_client("logs", aws_config, region=region),
        )

        # Discover flow log group
        flow_log_group = await _discover_flow_log_group(client, loop)
        if not flow_log_group:
            return _empty_result(
                private_ip or instance_id,
                "No VPC Flow Log group found in CloudWatch",
            )

        # Build filter pattern for the IP
        filter_ip = private_ip or instance_id
        filter_pattern = f'"{filter_ip}"'

        now = datetime.now(timezone.utc)
        start_time = int((now - timedelta(minutes=lookback_minutes)).timestamp() * 1000)
        end_time = int(now.timestamp() * 1000)

        response = await loop.run_in_executor(
            None,
            lambda: client.filter_log_events(
                logGroupName=flow_log_group,
                startTime=start_time,
                endTime=end_time,
                filterPattern=filter_pattern,
                limit=max_events,
                interleaved=True,
            ),
        )

        events = response.get("events", [])
        records = _parse_flow_records(events, filter_ip)

        # Compute summary
        accepted = [r for r in records if r.get("action") == "ACCEPT"]
        rejected = [r for r in records if r.get("action") == "REJECT"]

        # Top rejected destination ports
        reject_ports: dict[int, int] = {}
        for r in rejected:
            port = r.get("dstport", 0)
            reject_ports[port] = reject_ports.get(port, 0) + 1
        top_rejected_ports = sorted(
            reject_ports.items(), key=lambda x: x[1], reverse=True
        )[:10]

        # Top source IPs
        src_counts: dict[str, int] = {}
        for r in records:
            src = r.get("srcaddr", "")
            if src and src != filter_ip:
                src_counts[src] = src_counts.get(src, 0) + 1
        top_sources = sorted(src_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Traffic volume
        bytes_in = sum(
            r.get("bytes", 0) for r in records if r.get("dstaddr") == filter_ip
        )
        bytes_out = sum(
            r.get("bytes", 0) for r in records if r.get("srcaddr") == filter_ip
        )

        return {
            "total_records": len(records),
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            "top_rejected_ports": [
                {"port": p, "count": c} for p, c in top_rejected_ports
            ],
            "top_sources": [{"ip": ip, "count": c} for ip, c in top_sources],
            "bytes_in": bytes_in,
            "bytes_out": bytes_out,
            "flow_log_group": flow_log_group,
            "lookback_minutes": lookback_minutes,
            "resource_id": private_ip or instance_id,
        }

    except ImportError:
        logger.warning("vpc_flows_boto3_not_installed")
        return _empty_result(private_ip or instance_id, "boto3 not installed")
    except Exception as exc:
        logger.warning("vpc_flow_query_failed", error=str(exc))
        return _empty_result(private_ip or instance_id, str(exc))


async def _discover_flow_log_group(
    client: Any,
    loop: asyncio.AbstractEventLoop,
) -> str:
    """Try to find a VPC Flow Log group in CloudWatch."""
    for prefix in _FLOW_LOG_PREFIXES:
        try:
            response = await loop.run_in_executor(
                None,
                lambda: client.describe_log_groups(
                    logGroupNamePrefix=prefix,
                    limit=1,
                ),
            )
            groups = response.get("logGroups", [])
            if groups:
                return groups[0]["logGroupName"]
        except Exception:
            continue
    return ""


def _parse_flow_records(
    events: list[dict],
    filter_ip: str,
) -> list[dict[str, Any]]:
    """Parse VPC Flow Log records from CloudWatch events.

    VPC Flow Log format (v2):
      version account-id interface-id srcaddr dstaddr srcport dstport
      protocol packets bytes start end action log-status
    """
    records = []
    for event in events:
        message = event.get("message", "").strip()
        parts = message.split()
        if len(parts) < 14:
            continue

        try:
            record: dict[str, Any] = {
                "interface_id": parts[2],
                "srcaddr": parts[3],
                "dstaddr": parts[4],
                "srcport": int(parts[5]) if parts[5] != "-" else 0,
                "dstport": int(parts[6]) if parts[6] != "-" else 0,
                "protocol": int(parts[7]) if parts[7] != "-" else 0,
                "packets": int(parts[8]) if parts[8] != "-" else 0,
                "bytes": int(parts[9]) if parts[9] != "-" else 0,
                "action": parts[12],
            }
            records.append(record)
        except (ValueError, IndexError):
            continue

    return records


def _empty_result(resource_id: str, error: str = "") -> dict[str, Any]:
    return {
        "total_records": 0,
        "accepted_count": 0,
        "rejected_count": 0,
        "top_rejected_ports": [],
        "top_sources": [],
        "bytes_in": 0,
        "bytes_out": 0,
        "flow_log_group": "",
        "lookback_minutes": 0,
        "resource_id": resource_id,
        "error": error,
    }
