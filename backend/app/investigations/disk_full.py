"""
Investigation plugin for disk full alerts.

Generates deterministic, problem-consistent evidence for disk-full incidents.
File sizes are derived from the disk usage percentage to ensure consistency.
"""

from app.investigations.base import (
    BaseInvestigation,
    ProbeCategory,
    ProbeResult,
    _make_seeded_rng,
)


class DiskFullInvestigation(BaseInvestigation):
    """Gathers disk usage metrics for disk-full incidents."""

    alert_type = "disk_full"

    async def investigate(self, incident_meta: dict) -> ProbeResult:
        host = incident_meta.get("host") or incident_meta.get(
            "monitor_name", "unknown-host"
        )
        rng = _make_seeded_rng(incident_meta)

        # Primary metric: Disk MUST be near-full (this IS a disk_full alert)
        disk_pct = incident_meta.get("disk_percent") or rng.randint(91, 98)

        total_gb = 100
        used_gb = int(total_gb * disk_pct / 100)
        avail_gb = total_gb - used_gb

        # File sizes must add up to something plausible relative to used_gb
        # Main culprit should be large (application logs)
        main_log_gb = rng.randint(
            max(int(used_gb * 0.3), 15), max(int(used_gb * 0.5), 25)
        )
        syslog_gb = rng.randint(max(int(used_gb * 0.1), 3), max(int(used_gb * 0.2), 12))
        heap_dump_gb = rng.randint(2, 8)
        nginx_log_gb = rng.randint(1, 5)

        large_files = [
            {"size": f"{main_log_gb}G", "path": "/var/log/app/application.log"},
            {"size": f"{syslog_gb}G", "path": "/var/log/syslog.1"},
            {"size": f"{heap_dump_gb}G", "path": "/tmp/heap_dump_20260215.hprof"},
            {"size": f"{nginx_log_gb}G", "path": "/var/log/nginx/access.log"},
        ]

        # Inode usage should be moderate-to-high for disk full scenarios
        inode_pct = rng.randint(35, 70)

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
            f"Inode usage: {inode_pct}%",
            f"",
            f"Diagnosis: Disk at {disk_pct}% — primary culprit is application logs.",
            f"Recommendation: Rotate/clear old log files to free space.",
        ]

        return ProbeResult(
            tool_name="disk_diagnostics",
            raw_output="\n".join(output_lines),
            category=ProbeCategory.SYSTEM,
            probe_type="primary",
            metrics={
                "disk_percent": int(disk_pct),
                "total_gb": total_gb,
                "used_gb": used_gb,
                "avail_gb": avail_gb,
                "inode_percent": inode_pct,
                "largest_file_path": "/var/log/app/application.log",
                "largest_file_gb": main_log_gb,
                "total_log_gb": main_log_gb + syslog_gb + nginx_log_gb,
            },
        )
