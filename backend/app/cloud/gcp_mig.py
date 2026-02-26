"""
GCP Managed Instance Group (MIG) status query.

Queries MIG configuration, health, and recent operations to identify
scaling issues or unhealthy instances. Used by the infra state probe.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

logger = structlog.get_logger()


async def query_mig_status(
    instance_id: str = "",
    mig_name: str = "",
    project: str = "",
    zone: str = "",
    sa_key_path: str = "",
) -> dict[str, Any]:
    """
    Query GCP Managed Instance Group status.

    Can look up by instance_id (finds the MIG containing the instance)
    or by explicit mig_name. Zone-level MIGs only (regional MIGs not
    yet supported).

    Returns a dict with:
      - mig_name: name of the MIG
      - target_size: desired instance count
      - instance_count: current number of instances
      - healthy_count / unhealthy_count: health breakdown
      - current_actions: counts of instances in each action state
      - scaling_in_progress: bool
    """
    if not project:
        return _empty_result(instance_id, "no GCP project specified")

    try:
        from google.cloud import compute_v1

        loop = asyncio.get_running_loop()

        if sa_key_path:
            mig_client = await loop.run_in_executor(
                None,
                lambda: (
                    compute_v1.InstanceGroupManagersClient.from_service_account_json(
                        sa_key_path
                    )
                ),
            )
        else:
            mig_client = await loop.run_in_executor(
                None,
                compute_v1.InstanceGroupManagersClient,
            )

        # If no MIG name, try to find it via instance
        if not mig_name and instance_id:
            mig_name = await _find_mig_for_instance(
                mig_client, project, zone, instance_id, loop
            )
            if not mig_name:
                return _empty_result(
                    instance_id, "Instance not in any Managed Instance Group"
                )

        if not mig_name:
            return _empty_result("", "No mig_name or instance_id provided")

        if not zone:
            return _empty_result(mig_name, "Zone required for MIG query")

        # Get MIG details
        mig = await loop.run_in_executor(
            None,
            lambda: mig_client.get(
                project=project,
                zone=zone,
                instance_group_manager=mig_name,
            ),
        )

        # Get managed instances for health
        instances_response = await loop.run_in_executor(
            None,
            lambda: mig_client.list_managed_instances(
                project=project,
                zone=zone,
                instance_group_manager=mig_name,
            ),
        )

        managed_instances = list(instances_response)
        healthy = [
            i
            for i in managed_instances
            if getattr(i, "instance_status", "") == "RUNNING"
            and getattr(i, "current_action", "") == "NONE"
        ]
        unhealthy = [
            i
            for i in managed_instances
            if getattr(i, "instance_status", "") != "RUNNING"
            or getattr(i, "current_action", "") != "NONE"
        ]

        # Parse current actions
        current_actions: dict[str, int] = {}
        for inst in managed_instances:
            action = getattr(inst, "current_action", "NONE")
            current_actions[action] = current_actions.get(action, 0) + 1

        scaling_in_progress = any(
            action not in ("NONE", "VERIFYING")
            for action in current_actions
            if current_actions.get(action, 0) > 0
        )

        return {
            "mig_name": mig_name,
            "target_size": getattr(mig, "target_size", 0),
            "instance_count": len(managed_instances),
            "healthy_count": len(healthy),
            "unhealthy_count": len(unhealthy),
            "current_actions": current_actions,
            "scaling_in_progress": scaling_in_progress,
            "instance_template": _extract_template_name(
                getattr(mig, "instance_template", "")
            ),
            "zone": zone,
            "project": project,
            "resource_id": instance_id or mig_name,
        }

    except ImportError:
        logger.warning("gcp_compute_not_installed")
        return _empty_result(
            instance_id or mig_name, "google-cloud-compute not installed"
        )
    except Exception as exc:
        logger.warning("mig_query_failed", error=str(exc))
        return _empty_result(instance_id or mig_name, str(exc))


async def _find_mig_for_instance(
    mig_client: Any,
    project: str,
    zone: str,
    instance_id: str,
    loop: asyncio.AbstractEventLoop,
) -> str:
    """Try to find which MIG an instance belongs to."""
    if not zone:
        return ""

    try:
        migs_response = await loop.run_in_executor(
            None,
            lambda: mig_client.list(project=project, zone=zone),
        )

        for mig in migs_response:
            try:
                instances = await loop.run_in_executor(
                    None,
                    lambda: mig_client.list_managed_instances(
                        project=project,
                        zone=zone,
                        instance_group_manager=mig.name,
                    ),
                )
                for inst in instances:
                    inst_url = getattr(inst, "instance", "")
                    if instance_id in inst_url:
                        return mig.name
            except Exception:
                continue
    except Exception:
        pass

    return ""


def _extract_template_name(template_url: str) -> str:
    """Extract template name from full resource URL."""
    if not template_url:
        return ""
    parts = template_url.split("/")
    return parts[-1] if parts else ""


def _empty_result(resource_id: str, error: str = "") -> dict[str, Any]:
    return {
        "mig_name": "",
        "target_size": 0,
        "instance_count": 0,
        "healthy_count": 0,
        "unhealthy_count": 0,
        "current_actions": {},
        "scaling_in_progress": False,
        "instance_template": "",
        "zone": "",
        "project": "",
        "resource_id": resource_id,
        "error": error,
    }
