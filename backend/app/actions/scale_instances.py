"""
Scale instances action.

Simulates horizontal scaling via cloud API.
"""

import asyncio
import random

from app.actions.base import ActionResult, BaseAction


class ScaleInstancesAction(BaseAction):
    """Scale up/down instances in an auto-scaling group."""

    action_type = "scale_instances"

    async def execute(self, incident_meta: dict) -> ActionResult:
        service = incident_meta.get("service_name", "web-app")
        current = incident_meta.get("current_instances", random.randint(2, 4))
        target = incident_meta.get("target_instances", current + 2)

        await asyncio.sleep(random.uniform(2, 4))

        lines = [
            f"[ASG] Auto Scaling Group: {service}-asg",
            f"[ASG] Current capacity: {current}",
            f"[ASG] Desired capacity: {target}",
            f"[ASG] Updating desired capacity...",
            f"[ASG] Waiting for instances to launch...",
        ]
        for i in range(current + 1, target + 1):
            lines.append(f"[ASG] Instance {i}/{target}: i-{random.randint(10000, 99999):05x} running")

        lines += [
            f"[ASG] All {target} instances healthy",
            f"[ASG] Load balancer targets updated",
            f"[ASG] Scale operation complete",
        ]

        return ActionResult(
            success=True,
            logs="\n".join(lines),
            exit_code=0,
        )

    async def verify(self, incident_meta: dict) -> bool:
        """Verify all scaled instances are healthy."""
        await asyncio.sleep(random.uniform(1, 2))
        return random.random() < 0.85
