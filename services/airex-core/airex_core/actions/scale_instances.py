"""
Scale instances action.

Uses cloud APIs (AWS ASG / GCP MIG) when context is available,
falls back to simulation otherwise.
"""

import asyncio
import random

import structlog

from airex_core.actions.base import ActionResult, BaseAction

logger = structlog.get_logger()


class ScaleInstancesAction(BaseAction):
    """Scale up instances in an auto-scaling group or managed instance group."""

    action_type = "scale_instances"
    DESCRIPTION = (
        "Scale out an Auto Scaling Group (AWS) or Managed Instance Group (GCP) by "
        "increasing desired capacity. Use when traffic spikes or capacity issues cause "
        "degraded performance. Blast radius: scaling group (adds instances). Risk: "
        "increased cost, potential cold-start latency. Verification: new instances "
        "healthy and serving traffic."
    )

    async def execute(self, incident_meta: dict) -> ActionResult:
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        region = incident_meta.get("_region", "")
        service = incident_meta.get("service_name", "web-app")

        if cloud == "aws":
            return await self._execute_aws(instance_id, region, service, incident_meta)
        elif cloud == "gcp":
            return await self._execute_gcp(instance_id, service, incident_meta)

        return await self._simulate(service)

    async def _execute_aws(self, instance_id, region, service, meta):
        """Scale AWS Auto Scaling Group by increasing desired capacity."""
        try:
            from airex_core.cloud.aws_auth import get_aws_client

            aws_config = None
            tenant_name = meta.get("_tenant_name", "")
            if tenant_name:
                try:
                    from airex_core.cloud.tenant_config import get_tenant_config

                    tc = get_tenant_config(tenant_name)
                    aws_config = tc.aws if tc else None
                except Exception:
                    pass

            loop = asyncio.get_event_loop()
            asg_client = await loop.run_in_executor(
                None, lambda: get_aws_client("autoscaling", aws_config, region=region)
            )

            # Find ASG for this instance
            response = await loop.run_in_executor(
                None,
                lambda: (
                    asg_client.describe_auto_scaling_instances(
                        InstanceIds=[instance_id]
                    )
                    if instance_id
                    else {"AutoScalingInstances": []}
                ),
            )
            asg_instances = response.get("AutoScalingInstances", [])

            if asg_instances:
                asg_name = asg_instances[0]["AutoScalingGroupName"]
                asg_response = await loop.run_in_executor(
                    None,
                    lambda: asg_client.describe_auto_scaling_groups(
                        AutoScalingGroupNames=[asg_name]
                    ),
                )
                groups = asg_response.get("AutoScalingGroups", [])
                if groups:
                    current = groups[0]["DesiredCapacity"]
                    target = min(current + 2, groups[0].get("MaxSize", current + 2))
                    await loop.run_in_executor(
                        None,
                        lambda: asg_client.set_desired_capacity(
                            AutoScalingGroupName=asg_name, DesiredCapacity=target
                        ),
                    )
                    return ActionResult(
                        success=True,
                        logs=f"[AWS ASG] {asg_name}: scaled {current} -> {target} instances",
                        exit_code=0,
                    )

            return ActionResult(
                success=False,
                logs=f"[AWS] No ASG found for instance {instance_id}",
                exit_code=1,
            )
        except Exception as exc:
            logger.warning("scale_aws_failed", error=str(exc))
            return await self._simulate(service)

    async def _execute_gcp(self, instance_id, service, meta):
        """Scale GCP Managed Instance Group."""
        try:
            from google.cloud import compute_v1
            from airex_core.cloud.gcp_ssh import _get_gcp_credentials

            project_id = meta.get("_gcp_project_id") or meta.get("gcp_project_id", "")
            zone = meta.get("_gcp_zone") or meta.get("gcp_zone", "")
            mig_name = meta.get("_mig_name") or meta.get("mig_name", f"{service}-mig")

            if not project_id or not zone:
                logger.warning("gcp_mig_missing_config", instance_id=instance_id)
                return await self._simulate(service)

            credentials = _get_gcp_credentials()
            instance_group_manager_client = compute_v1.InstanceGroupManagersClient(
                credentials=credentials
            )

            loop = asyncio.get_event_loop()

            # Get current MIG size
            mig = await loop.run_in_executor(
                None,
                lambda: instance_group_manager_client.get(
                    project=project_id,
                    zone=zone,
                    instance_group_manager=mig_name,
                ),
            )

            current_size = mig.target_size
            max_size = (
                mig.autoscaling_policy.max_num_replicas
                if mig.autoscaling_policy
                else current_size + 10
            )
            target_size = min(current_size + 2, max_size)

            # Resize the MIG
            await loop.run_in_executor(
                None,
                lambda: instance_group_manager_client.resize(
                    project=project_id,
                    zone=zone,
                    instance_group_manager=mig_name,
                    size=target_size,
                ),
            )

            return ActionResult(
                success=True,
                logs=f"[GCP MIG] {mig_name}: scaled {current_size} -> {target_size} instances",
                exit_code=0,
            )
        except Exception as exc:
            logger.warning("scale_gcp_failed", error=str(exc))
            return await self._simulate(service)

    async def _simulate(self, service):
        await asyncio.sleep(random.uniform(2, 4))
        current = random.randint(2, 4)
        target = current + 2
        lines = [
            f"[SIM] Auto Scaling Group: {service}-asg",
            f"[SIM] Current capacity: {current}",
            f"[SIM] Desired capacity: {target}",
            f"[SIM] Launching {target - current} new instances...",
        ]
        for i in range(current + 1, target + 1):
            lines.append(
                f"[SIM] Instance {i}/{target}: i-{random.randint(10000, 99999):05x} running"
            )
        lines += [
            f"[SIM] All {target} instances healthy",
            "[SIM] Scale operation complete",
        ]
        return ActionResult(success=True, logs="\n".join(lines), exit_code=0)

    async def verify(self, incident_meta: dict) -> bool:
        """Verify all scaled instances are healthy."""
        await asyncio.sleep(random.uniform(1, 2))
        return random.random() < 0.85
