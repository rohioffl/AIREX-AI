"""
Investigation plugin for high memory alerts.

Generates deterministic, problem-consistent evidence for memory-high incidents.
RSS values are derived from the memory percentage to ensure consistency.
"""

from airex_core.investigations.base import (
    BaseInvestigation,
    ProbeCategory,
    ProbeResult,
    _make_seeded_rng,
)


class MemoryHighInvestigation(BaseInvestigation):
    """Gathers memory metrics and top memory consumers."""

    alert_type = "memory_high"

    async def investigate(self, incident_meta: dict) -> ProbeResult:
        host = incident_meta.get("host") or incident_meta.get(
            "monitor_name", "unknown-host"
        )
        rng = _make_seeded_rng(incident_meta)

        # Primary metric: Memory MUST be high (this IS a memory_high alert)
        mem_pct = incident_meta.get("memory_percent") or rng.randint(87, 97)

        total_mb = 8192
        used_mb = int(total_mb * mem_pct / 100)
        free_mb = total_mb - used_mb

        # Top process must consume most of the memory to be consistent
        primary_rss = rng.randint(
            max(int(used_mb * 0.5), 3500), max(int(used_mb * 0.7), 5500)
        )
        secondary_rss = rng.randint(150, 500)
        tertiary_rss = rng.randint(80, 300)

        # Use consistent PIDs (seeded, not random)
        top_procs = [
            {
                "pid": 2000 + rng.randint(0, 999),
                "user": "app",
                "rss": f"{primary_rss}M",
                "cmd": "java -Xmx4g -jar service.jar",
            },
            {
                "pid": 3000 + rng.randint(0, 999),
                "user": "root",
                "rss": f"{secondary_rss}M",
                "cmd": "postgres: writer process",
            },
            {
                "pid": 4000 + rng.randint(0, 999),
                "user": "app",
                "rss": f"{tertiary_rss}M",
                "cmd": "node /app/worker.js",
            },
        ]

        # Swap should be elevated when memory is high
        swap_used_mb = rng.randint(300, 900)

        # OOM kills should be present (this is a memory problem)
        oom_kills = rng.randint(1, 4)

        lines = [
            f"=== Memory Investigation: {host} ===",
            "",
            f"Total: {total_mb}MB  Used: {used_mb}MB  Free: {free_mb}MB  Usage: {mem_pct}%",
            f"Swap:  2048MB  Used: {swap_used_mb}MB",
            "",
            "Top Memory Consumers:",
            f"{'PID':>8} {'USER':<10} {'RSS':>8} COMMAND",
        ]
        for p in top_procs:
            lines.append(f"{p['pid']:>8} {p['user']:<10} {p['rss']:>8} {p['cmd']}")

        lines += [
            "",
            f"OOM Kills (24h): {oom_kills}",
            "",
            f"Diagnosis: Memory at {mem_pct}% — primary consumer is Java service.",
            "Recommendation: Restart service or increase heap limits.",
        ]

        return ProbeResult(
            tool_name="memory_diagnostics",
            raw_output="\n".join(lines),
            category=ProbeCategory.SYSTEM,
            probe_type="primary",
            metrics={
                "memory_percent": int(mem_pct),
                "total_mb": total_mb,
                "used_mb": used_mb,
                "free_mb": free_mb,
                "swap_used_mb": swap_used_mb,
                "swap_total_mb": 2048,
                "oom_kills_24h": oom_kills,
                "top_process_name": "java -Xmx4g -jar service.jar",
                "top_process_rss_mb": primary_rss,
                "top_process_pid": top_procs[0]["pid"],
            },
        )
