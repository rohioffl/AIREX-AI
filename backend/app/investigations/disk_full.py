"""
Investigation plugin for disk full alerts.

Simulates collecting real disk metrics.
"""

import random

from app.investigations.base import BaseInvestigation, InvestigationResult


class DiskFullInvestigation(BaseInvestigation):
    """Gathers disk usage metrics for disk-full incidents."""

    alert_type = "disk_full"

    async def investigate(self, incident_meta: dict) -> InvestigationResult:
        host = incident_meta.get("host") or incident_meta.get("monitor_name", "unknown-host")
        disk_pct = incident_meta.get("disk_percent", random.randint(90, 99))

        total_gb = 100
        used_gb = int(total_gb * disk_pct / 100)
        avail_gb = total_gb - used_gb

        large_files = [
            {"size": f"{random.randint(5, 30)}G", "path": "/var/log/app/application.log"},
            {"size": f"{random.randint(2, 15)}G", "path": "/var/log/syslog.1"},
            {"size": f"{random.randint(1, 8)}G", "path": "/tmp/heap_dump_20260215.hprof"},
            {"size": f"{random.randint(1, 5)}G", "path": "/var/log/nginx/access.log"},
        ]

        output_lines = [
            f"=== Disk Investigation: {host} ===",
            f"",
            f"Filesystem      Size  Used Avail Use% Mounted on",
            f"/dev/sda1       {total_gb}G   {used_gb}G   {avail_gb}G  {disk_pct}% /",
            f"/dev/sda2       50G    2G   48G   4% /boot",
            f"",
            f"Largest files on /:",
        ]
        for f in large_files:
            output_lines.append(f"  {f['size']:>6}  {f['path']}")

        output_lines += [
            f"",
            f"Inode usage: {random.randint(20, 60)}%",
            f"",
            f"Diagnosis: Disk at {disk_pct}% — primary culprit is application logs.",
            f"Recommendation: Rotate/clear old log files to free space.",
        ]

        return InvestigationResult(
            tool_name="disk_diagnostics",
            raw_output="\n".join(output_lines),
        )
