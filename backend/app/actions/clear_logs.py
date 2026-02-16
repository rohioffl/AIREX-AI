"""
Clear logs action.

Simulates clearing old log files to free disk space.
In production, replace with actual SSM/OS Login calls.
"""

import asyncio
import random

from app.actions.base import ActionResult, BaseAction


class ClearLogsAction(BaseAction):
    """Clear old log files via SSM RunCommand."""

    action_type = "clear_logs"

    async def execute(self, incident_meta: dict) -> ActionResult:
        host = incident_meta.get("host") or incident_meta.get("monitor_name", "unknown-host")
        log_path = incident_meta.get("log_path", "/var/log")

        await asyncio.sleep(random.uniform(1, 2))

        freed_gb = random.randint(5, 25)
        files_removed = random.randint(10, 50)

        logs_lines = [
            f"[SSM] Connecting to {host}...",
            f"[SSM] Session established",
            f"[SSM] Running: find {log_path} -name '*.log.*' -mtime +7 -delete",
            f"[SSM] Removed {files_removed} rotated log files",
            f"[SSM] Running: truncate -s 0 {log_path}/app/application.log",
            f"[SSM] Truncated active log file",
            f"[SSM] Running: logrotate -f /etc/logrotate.d/app",
            f"[SSM] Log rotation forced",
            f"[SSM] Freed: {freed_gb}GB",
            f"[SSM] Current disk usage: {random.randint(40, 70)}%",
            f"[SSM] Session closed",
        ]

        return ActionResult(
            success=True,
            logs="\n".join(logs_lines),
            exit_code=0,
        )

    async def verify(self, incident_meta: dict) -> bool:
        """Verify disk usage dropped below threshold."""
        await asyncio.sleep(random.uniform(0.5, 1))
        return random.random() < 0.9
