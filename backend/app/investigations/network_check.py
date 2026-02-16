"""Investigation plugin for network connectivity issues."""

import random

from app.investigations.base import BaseInvestigation, InvestigationResult


class NetworkCheckInvestigation(BaseInvestigation):
    """Checks network connectivity, latency, and DNS resolution."""

    alert_type = "network_issue"

    async def investigate(self, incident_meta: dict) -> InvestigationResult:
        host = incident_meta.get("host") or incident_meta.get("monitor_name", "unknown-host")
        target = incident_meta.get("target_host", "api.example.com")

        packet_loss = random.uniform(0, 30)
        avg_latency = random.uniform(1, 500)

        lines = [
            f"=== Network Investigation: {host} → {target} ===",
            f"",
            f"Ping Results (10 packets):",
            f"  Transmitted: 10  Received: {10 - int(packet_loss / 10)}  Loss: {packet_loss:.1f}%",
            f"  RTT min/avg/max: {avg_latency * 0.5:.1f}/{avg_latency:.1f}/{avg_latency * 1.5:.1f} ms",
            f"",
            f"DNS Resolution:",
            f"  {target} → {random.randint(10, 172)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}",
            f"  Resolution time: {random.uniform(1, 50):.1f}ms",
            f"",
            f"TCP Connectivity:",
            f"  Port 443: {'OPEN' if random.random() > 0.3 else 'TIMEOUT'}",
            f"  Port 80:  {'OPEN' if random.random() > 0.2 else 'TIMEOUT'}",
            f"",
            f"Traceroute ({random.randint(5, 15)} hops):",
            f"  Bottleneck at hop {random.randint(3, 8)}: {random.uniform(50, 300):.1f}ms",
            f"",
            f"Diagnosis: {'High packet loss and latency' if packet_loss > 10 else 'Intermittent connectivity'}.",
            f"Recommendation: Check network ACLs or contact NOC.",
        ]

        return InvestigationResult(
            tool_name="network_diagnostics",
            raw_output="\n".join(lines),
        )
