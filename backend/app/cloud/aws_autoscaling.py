"""
AWS Auto Scaling Group status query.

Queries ASG configuration, health, and recent scaling activities
for resources associated with an incident. Used by the infra state
probe to detect scaling issues, unhealthy instances, or capacity problems.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.cloud.tenant_config import AWSConfig

logger = structlog.get_logger()


async def query_asg_status(
    instance_id: str = "",
    asg_name: str = "",
    region: str = "",
    aws_config: "AWSConfig | None" = None,
    lookback_minutes: int = 60,
) -> dict[str, Any]:
    """
    Query AWS Auto Scaling Group status and recent activities.

    Can look up by instance_id (finds the ASG containing the instance)
    or by explicit asg_name.

    Returns a dict with:
      - asg_name: name of the ASG
      - desired_capacity, min_size, max_size: capacity settings
      - instance_count: current number of instances
      - healthy_count / unhealthy_count: health breakdown
      - recent_activities: list of recent scaling activities
      - scaling_in_progress: bool
    """
    try:
        from app.cloud.aws_auth import get_aws_client

        loop = asyncio.get_running_loop()

        client = await loop.run_in_executor(
            None,
            lambda: get_aws_client("autoscaling", aws_config, region=region),
        )

        # Find the ASG — by name or by instance
        if asg_name:
            response = await loop.run_in_executor(
                None,
                lambda: client.describe_auto_scaling_groups(
                    AutoScalingGroupNames=[asg_name],
                    MaxRecords=1,
                ),
            )
        elif instance_id:
            # Look up which ASG this instance belongs to
            inst_response = await loop.run_in_executor(
                None,
                lambda: client.describe_auto_scaling_instances(
                    InstanceIds=[instance_id],
                ),
            )
            instances = inst_response.get("AutoScalingInstances", [])
            if not instances:
                return _empty_result(
                    instance_id, "Instance not in any Auto Scaling Group"
                )
            asg_name = instances[0].get("AutoScalingGroupName", "")
            if not asg_name:
                return _empty_result(instance_id, "ASG name not found for instance")

            response = await loop.run_in_executor(
                None,
                lambda: client.describe_auto_scaling_groups(
                    AutoScalingGroupNames=[asg_name],
                    MaxRecords=1,
                ),
            )
        else:
            return _empty_result("", "No instance_id or asg_name provided")

        asgs = response.get("AutoScalingGroups", [])
        if not asgs:
            return _empty_result(
                instance_id or asg_name, "Auto Scaling Group not found"
            )

        asg = asgs[0]

        # Parse instance health
        asg_instances = asg.get("Instances", [])
        healthy = [i for i in asg_instances if i.get("HealthStatus") == "Healthy"]
        unhealthy = [i for i in asg_instances if i.get("HealthStatus") != "Healthy"]

        # Get recent scaling activities
        activities = await _get_recent_activities(
            client, asg["AutoScalingGroupName"], lookback_minutes, loop
        )

        scaling_in_progress = any(a.get("status") == "InProgress" for a in activities)

        return {
            "asg_name": asg["AutoScalingGroupName"],
            "desired_capacity": asg.get("DesiredCapacity", 0),
            "min_size": asg.get("MinSize", 0),
            "max_size": asg.get("MaxSize", 0),
            "instance_count": len(asg_instances),
            "healthy_count": len(healthy),
            "unhealthy_count": len(unhealthy),
            "unhealthy_instances": [
                {
                    "instance_id": i.get("InstanceId", ""),
                    "health_status": i.get("HealthStatus", ""),
                    "lifecycle_state": i.get("LifecycleState", ""),
                }
                for i in unhealthy
            ],
            "recent_activities": activities,
            "scaling_in_progress": scaling_in_progress,
            "launch_template": asg.get("LaunchTemplate", {}).get(
                "LaunchTemplateName", ""
            ),
            "availability_zones": asg.get("AvailabilityZones", []),
            "resource_id": instance_id or asg_name,
        }

    except ImportError:
        logger.warning("asg_boto3_not_installed")
        return _empty_result(instance_id or asg_name, "boto3 not installed")
    except Exception as exc:
        logger.warning("asg_query_failed", error=str(exc))
        return _empty_result(instance_id or asg_name, str(exc))


async def _get_recent_activities(
    client: Any,
    asg_name: str,
    lookback_minutes: int,
    loop: asyncio.AbstractEventLoop,
) -> list[dict[str, Any]]:
    """Fetch recent scaling activities for an ASG."""
    try:
        response = await loop.run_in_executor(
            None,
            lambda: client.describe_scaling_activities(
                AutoScalingGroupName=asg_name,
                MaxRecords=10,
            ),
        )

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
        activities = []

        for activity in response.get("Activities", []):
            start_time = activity.get("StartTime")
            if start_time and start_time.replace(tzinfo=timezone.utc) < cutoff:
                continue

            activities.append(
                {
                    "description": activity.get("Description", ""),
                    "cause": activity.get("Cause", ""),
                    "status": activity.get("StatusCode", ""),
                    "start_time": str(start_time) if start_time else "",
                    "end_time": str(activity.get("EndTime", "")),
                    "progress": activity.get("Progress", 0),
                }
            )

        return activities

    except Exception as exc:
        logger.warning("asg_activities_failed", error=str(exc))
        return []


def _empty_result(resource_id: str, error: str = "") -> dict[str, Any]:
    return {
        "asg_name": "",
        "desired_capacity": 0,
        "min_size": 0,
        "max_size": 0,
        "instance_count": 0,
        "healthy_count": 0,
        "unhealthy_count": 0,
        "unhealthy_instances": [],
        "recent_activities": [],
        "scaling_in_progress": False,
        "launch_template": "",
        "availability_zones": [],
        "resource_id": resource_id,
        "error": error,
    }
