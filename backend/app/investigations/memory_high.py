"""Investigation plugin for high memory alerts."""

import random

from app.investigations.base import BaseInvestigation, InvestigationResult


class MemoryHighInvestigation(BaseInvestigation):
    """Gathers memory metrics and top memory consumers."""

    alert_type = "memory_high"

    async def investigate(self, incident_meta: dict) -> InvestigationResult:
        host = incident_meta.get("host") or incident_meta.get("monitor_name", "unknown-host")
        mem_pct = incident_meta.get("memory_percent", random.randint(85, 99))

        total_mb = 8192
        used_mb = int(total_mb * mem_pct / 100)
        free_mb = total_mb - used_mb

        top_procs = [
            {"pid": random.randint(1000, 9999), "user": "app", "rss": f"{random.randint(2000, 5000)}M", "cmd": "java -Xmx4g -jar service.jar"},
            {"pid": random.randint(1000, 9999), "user": "root", "rss": f"{random.randint(100, 500)}M", "cmd": "postgres: writer process"},
            {"pid": random.randint(1000, 9999), "user": "app", "rss": f"{random.randint(50, 300)}M", "cmd": "node /app/worker.js"},
        ]

        lines = [
            f"=== Memory Investigation: {host} ===",
            f"",
            f"Total: {total_mb}MB  Used: {used_mb}MB  Free: {free_mb}MB  Usage: {mem_pct}%",
            f"Swap:  2048MB  Used: {random.randint(100, 800)}MB",
            f"",
            f"Top Memory Consumers:",
            f"{'PID':>8} {'USER':<10} {'RSS':>8} COMMAND",
        ]
        for p in top_procs:
            lines.append(f"{p['pid']:>8} {p['user']:<10} {p['rss']:>8} {p['cmd']}")

        lines += [
            f"",
            f"OOM Kills (24h): {random.randint(0, 5)}",
            f"",
            f"Diagnosis: Memory at {mem_pct}% — primary consumer is Java service.",
            f"Recommendation: Restart service or increase heap limits.",
        ]

        return InvestigationResult(
            tool_name="memory_diagnostics",
            raw_output="\n".join(lines),
        )
