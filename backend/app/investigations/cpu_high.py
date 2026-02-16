"""
Investigation plugin for high CPU alerts.

Simulates collecting real system metrics. In production, replace
the simulation with actual SSM RunCommand / GCP OS Login calls.
"""

import random

from app.investigations.base import BaseInvestigation, InvestigationResult


class CpuHighInvestigation(BaseInvestigation):
    """Gathers CPU metrics and top processes for high-CPU incidents."""

    alert_type = "cpu_high"

    async def investigate(self, incident_meta: dict) -> InvestigationResult:
        host = incident_meta.get("host") or incident_meta.get("monitor_name", "unknown-host")
        cpu_pct = incident_meta.get("cpu_percent", random.uniform(85, 99))

        top_processes = [
            {"pid": 1234, "user": "app", "cpu": f"{cpu_pct:.1f}%", "cmd": incident_meta.get("process", "java -jar app.jar")},
            {"pid": 5678, "user": "root", "cpu": f"{random.uniform(1, 5):.1f}%", "cmd": "/usr/sbin/sshd"},
            {"pid": 9012, "user": "nobody", "cpu": f"{random.uniform(0.1, 2):.1f}%", "cmd": "nginx: worker"},
        ]

        load_avg = [round(random.uniform(3, 12), 2), round(random.uniform(2, 8), 2), round(random.uniform(1, 6), 2)]

        output_lines = [
            f"=== CPU Investigation: {host} ===",
            f"",
            f"Load Average (1m/5m/15m): {load_avg[0]} / {load_avg[1]} / {load_avg[2]}",
            f"CPU Cores: 4",
            f"Overall CPU Usage: {cpu_pct:.1f}%",
            f"",
            f"Top Processes by CPU:",
            f"{'PID':>8} {'USER':<10} {'CPU':>6} COMMAND",
            f"{'---':>8} {'---':<10} {'---':>6} -------",
        ]
        for p in top_processes:
            output_lines.append(f"{p['pid']:>8} {p['user']:<10} {p['cpu']:>6} {p['cmd']}")

        output_lines += [
            f"",
            f"Memory: {random.randint(60, 90)}% used (of 8GB)",
            f"Swap: {random.randint(0, 30)}% used",
            f"",
            f"Diagnosis: High CPU driven by PID {top_processes[0]['pid']} ({top_processes[0]['cmd']})",
            f"Recommendation: Restart the service or investigate memory leaks.",
        ]

        return InvestigationResult(
            tool_name="cpu_diagnostics",
            raw_output="\n".join(output_lines),
        )
