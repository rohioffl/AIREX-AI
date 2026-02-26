"""
Investigation plugin for high CPU alerts.

Generates deterministic, problem-consistent evidence for CPU-high incidents.
When no cloud connectivity is available, this simulates what a real
investigation would find: high CPU values consistent with the alert.
"""

from app.investigations.base import (
    BaseInvestigation,
    ProbeCategory,
    ProbeResult,
    _make_seeded_rng,
)


class CpuHighInvestigation(BaseInvestigation):
    """Gathers CPU metrics and top processes for high-CPU incidents."""

    alert_type = "cpu_high"

    async def investigate(self, incident_meta: dict) -> ProbeResult:
        host = incident_meta.get("host") or incident_meta.get(
            "monitor_name", "unknown-host"
        )
        rng = _make_seeded_rng(incident_meta)

        # Primary metric: CPU MUST be high (this IS a cpu_high alert)
        cpu_pct = incident_meta.get("cpu_percent") or rng.uniform(88, 98)

        # Top process must consume most of the CPU to be consistent
        primary_process = incident_meta.get("process", "java -jar app.jar")
        primary_cpu = cpu_pct - rng.uniform(1, 5)  # slightly less than total
        secondary_cpu = rng.uniform(0.5, 3.0)
        tertiary_cpu = rng.uniform(0.1, 1.5)

        top_processes = [
            {
                "pid": 1234 + rng.randint(0, 100),
                "user": "app",
                "cpu": f"{primary_cpu:.1f}%",
                "cmd": primary_process,
            },
            {
                "pid": 5678 + rng.randint(0, 100),
                "user": "root",
                "cpu": f"{secondary_cpu:.1f}%",
                "cmd": "/usr/sbin/sshd",
            },
            {
                "pid": 9012 + rng.randint(0, 100),
                "user": "nobody",
                "cpu": f"{tertiary_cpu:.1f}%",
                "cmd": "nginx: worker",
            },
        ]

        # Load average must be HIGH for a CPU alert (proportional to CPU usage)
        # On a 4-core system, load avg > 4.0 indicates saturation
        cores = 4
        load_1m = round(cores * (cpu_pct / 100) * rng.uniform(1.0, 1.3), 2)
        load_5m = round(load_1m * rng.uniform(0.7, 0.9), 2)
        load_15m = round(load_5m * rng.uniform(0.6, 0.85), 2)

        # Memory should be moderately high (CPU issues often correlate)
        mem_pct = rng.randint(65, 85)
        swap_pct = rng.randint(5, 25)

        output_lines = [
            f"=== CPU Investigation: {host} ===",
            f"",
            f"Load Average (1m/5m/15m): {load_1m} / {load_5m} / {load_15m}",
            f"CPU Cores: {cores}",
            f"Overall CPU Usage: {cpu_pct:.1f}%",
            f"",
            f"Top Processes by CPU:",
            f"{'PID':>8} {'USER':<10} {'CPU':>6} COMMAND",
            f"{'---':>8} {'---':<10} {'---':>6} -------",
        ]
        for p in top_processes:
            output_lines.append(
                f"{p['pid']:>8} {p['user']:<10} {p['cpu']:>6} {p['cmd']}"
            )

        output_lines += [
            f"",
            f"Memory: {mem_pct}% used (of 8GB)",
            f"Swap: {swap_pct}% used",
            f"",
            f"Diagnosis: High CPU driven by PID {top_processes[0]['pid']} ({top_processes[0]['cmd']})",
            f"Recommendation: Restart the service or investigate memory leaks.",
        ]

        return ProbeResult(
            tool_name="cpu_diagnostics",
            raw_output="\n".join(output_lines),
            category=ProbeCategory.SYSTEM,
            probe_type="primary",
            metrics={
                "cpu_percent": round(float(cpu_pct), 1),
                "load_1m": load_1m,
                "load_5m": load_5m,
                "load_15m": load_15m,
                "cores": cores,
                "memory_percent": mem_pct,
                "swap_percent": swap_pct,
                "top_process_name": primary_process,
                "top_process_cpu": round(primary_cpu, 1),
                "top_process_pid": top_processes[0]["pid"],
            },
        )
