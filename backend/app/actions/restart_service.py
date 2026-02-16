"""
Restart service action.

Simulates sending a restart command via SSM/OS Login.
In production, replace simulation with actual cloud API calls.
"""

import asyncio
import random

from app.actions.base import ActionResult, BaseAction


class RestartServiceAction(BaseAction):
    """Restart a system service via SSM RunCommand."""

    action_type = "restart_service"

    async def execute(self, incident_meta: dict) -> ActionResult:
        service_name = incident_meta.get("service_name", "application")
        host = incident_meta.get("host") or incident_meta.get("monitor_name", "unknown-host")

        # Simulate execution time
        await asyncio.sleep(random.uniform(1, 3))

        logs_lines = [
            f"[SSM] Connecting to {host}...",
            f"[SSM] Session established (instance: {host})",
            f"[SSM] Running: systemctl restart {service_name}",
            f"[SSM] Waiting for service to start...",
            f"[SSM] Service '{service_name}' restarted successfully",
            f"[SSM] Active: active (running) since Mon 2026-02-16 10:45:01 UTC",
            f"[SSM] PID: {random.randint(10000, 50000)}",
            f"[SSM] Memory: {random.randint(200, 800)}MB",
            f"[SSM] Session closed",
        ]

        return ActionResult(
            success=True,
            logs="\n".join(logs_lines),
            exit_code=0,
        )

    async def verify(self, incident_meta: dict) -> bool:
        """Check if the service is healthy after restart."""
        # Simulate a health check
        await asyncio.sleep(random.uniform(0.5, 1.5))

        # 90% success rate in simulation
        return random.random() < 0.9
