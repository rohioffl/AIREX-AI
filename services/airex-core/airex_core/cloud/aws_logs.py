"""
AWS CloudWatch Logs connector.

Queries recent logs from CloudWatch Log Groups for incident investigation.
Supports per-tenant authentication via AWSConfig (role assumption, static keys, etc.).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

import structlog

from airex_core.core.config import settings

if TYPE_CHECKING:
    from airex_core.cloud.tenant_config import AWSConfig

logger = structlog.get_logger()


async def query_cloudwatch_logs(
    instance_id: str = "",
    log_group: str = "",
    filter_pattern: str = "",
    region: str = "",
    lookback_minutes: int = 30,
    max_events: int = 50,
    aws_config: "AWSConfig | None" = None,
) -> str:
    """
    Query CloudWatch Logs for recent events matching the filter.

    If log_group is not specified, attempts common patterns:
      /var/log/messages, /var/log/syslog, /aws/ec2/{instance_id}
    """
    from airex_core.cloud.aws_auth import get_aws_client

    region = region or (aws_config.region if aws_config else "") or settings.AWS_REGION
    log = logger.bind(instance_id=instance_id, region=region)
    log.info("cloudwatch_querying", lookback=lookback_minutes)

    loop = asyncio.get_event_loop()

    try:
        client = await loop.run_in_executor(
            None,
            lambda: get_aws_client("logs", aws_config, region=region),
        )

        now = datetime.now(timezone.utc)
        start_time = int((now - timedelta(minutes=lookback_minutes)).timestamp() * 1000)
        end_time = int(now.timestamp() * 1000)

        # Try specified log group or discover groups
        groups = []
        if log_group:
            groups = [log_group]
        else:
            groups = await _discover_log_groups(client, instance_id, loop)

        if not groups:
            return (
                f"=== CloudWatch Logs: {instance_id} ===\n\n"
                f"No log groups found for instance {instance_id}.\n"
                f"Ensure CloudWatch Agent is installed and configured."
            )

        all_events: list[dict] = []
        for group in groups[:3]:  # Max 3 log groups
            try:
                filter_kwargs: dict = {
                    "logGroupName": group,
                    "startTime": start_time,
                    "endTime": end_time,
                    "limit": max_events,
                    "interleaved": True,
                }
                if filter_pattern:
                    filter_kwargs["filterPattern"] = filter_pattern
                elif instance_id:
                    filter_kwargs["filterPattern"] = f'"{instance_id}"'

                response = await loop.run_in_executor(
                    None,
                    lambda: client.filter_log_events(**filter_kwargs),
                )
                for event in response.get("events", []):
                    event["_log_group"] = group
                    all_events.append(event)
            except Exception as exc:
                log.warning("cloudwatch_group_query_failed", group=group, error=str(exc))

        return _format_cloudwatch_events(all_events, instance_id, groups)

    except Exception as exc:
        log.error("cloudwatch_query_failed", error=str(exc))
        return f"ERROR querying CloudWatch Logs: {exc}"


async def _discover_log_groups(client, instance_id: str, loop) -> list[str]:
    """Try to discover relevant log groups for an EC2 instance."""
    candidate_prefixes = [
        f"/aws/ec2/{instance_id}",
        "/var/log",
        "/aws/ec2",
        "syslog",
    ]

    found = []
    for prefix in candidate_prefixes:
        try:
            response = await loop.run_in_executor(
                None,
                lambda: client.describe_log_groups(
                    logGroupNamePrefix=prefix, limit=5
                ),
            )
            for group in response.get("logGroups", []):
                found.append(group["logGroupName"])
        except Exception:
            pass

    return found[:5]


def _format_cloudwatch_events(
    events: list[dict], instance_id: str, groups: list[str]
) -> str:
    """Format CloudWatch log events into a readable report."""
    if not events:
        return (
            f"=== CloudWatch Logs: {instance_id} ===\n"
            f"Searched groups: {', '.join(groups)}\n\n"
            f"No matching log events found in the lookback window."
        )

    events.sort(key=lambda e: e.get("timestamp", 0), reverse=True)

    lines = [
        f"=== CloudWatch Logs: {instance_id} ===",
        f"Searched groups: {', '.join(groups)}",
        f"Events found: {len(events)}",
        "",
    ]

    for event in events[:50]:
        ts = event.get("timestamp", 0)
        if ts:
            ts_str = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            )
        else:
            ts_str = "unknown"

        group = event.get("_log_group", "")
        short_group = group.split("/")[-1] if group else ""
        message = event.get("message", "").strip()

        if len(message) > 500:
            message = message[:500] + "..."

        lines.append(f"[{ts_str}] [{short_group}] {message}")

    lines.append("")
    lines.append("--- End of CloudWatch results ---")
    return "\n".join(lines)
