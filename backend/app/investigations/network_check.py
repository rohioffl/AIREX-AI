"""
Investigation plugin for network connectivity issues.

Generates deterministic, problem-consistent evidence for network incidents.
All metrics ALWAYS indicate a network problem since this only runs when
an alert has already been triggered.
"""

from app.investigations.base import (
    BaseInvestigation,
    InvestigationResult,
    _make_seeded_rng,
)


class NetworkCheckInvestigation(BaseInvestigation):
    """Checks network connectivity, latency, and DNS resolution."""

    alert_type = "network_issue"

    async def investigate(self, incident_meta: dict) -> InvestigationResult:
        host = incident_meta.get("host") or incident_meta.get(
            "monitor_name", "unknown-host"
        )
        target = incident_meta.get("target_host", "api.example.com")
        rng = _make_seeded_rng(incident_meta)

        # Primary metrics: MUST show a network problem (this IS a network_issue alert)
        # Packet loss must be significant (15-45%), not 0-30% which could show healthy
        packet_loss = rng.uniform(15, 45)
        # Latency must be high (150-600ms), not 1-500ms which could show 2ms
        avg_latency = rng.uniform(150, 600)

        # Packets received must be consistent with loss percentage
        transmitted = 10
        received = max(transmitted - int(packet_loss / 10), 5)

        # DNS should be slow (consistent with network issues)
        dns_resolution_time = rng.uniform(25, 120)

        # Generate a consistent IP for the target (seeded, not random)
        dns_ip = f"{rng.randint(10, 172)}.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"

        # Ports should show problems (at least one TIMEOUT for a network issue)
        port_443_status = "TIMEOUT" if rng.random() > 0.4 else "OPEN"
        port_80_status = "TIMEOUT" if rng.random() > 0.5 else "OPEN"
        # Ensure at least one port is timing out (this IS a network alert)
        if port_443_status == "OPEN" and port_80_status == "OPEN":
            port_443_status = "TIMEOUT"

        # Traceroute should show a clear bottleneck
        total_hops = rng.randint(8, 15)
        bottleneck_hop = rng.randint(4, min(total_hops - 1, 9))
        bottleneck_latency = rng.uniform(200, 500)

        lines = [
            f"=== Network Investigation: {host} → {target} ===",
            f"",
            f"Ping Results ({transmitted} packets):",
            f"  Transmitted: {transmitted}  Received: {received}  Loss: {packet_loss:.1f}%",
            f"  RTT min/avg/max: {avg_latency * 0.5:.1f}/{avg_latency:.1f}/{avg_latency * 1.5:.1f} ms",
            f"",
            f"DNS Resolution:",
            f"  {target} → {dns_ip}",
            f"  Resolution time: {dns_resolution_time:.1f}ms",
            f"",
            f"TCP Connectivity:",
            f"  Port 443: {port_443_status}",
            f"  Port 80:  {port_80_status}",
            f"",
            f"Traceroute ({total_hops} hops):",
            f"  Bottleneck at hop {bottleneck_hop}: {bottleneck_latency:.1f}ms",
            f"",
            f"Diagnosis: High packet loss ({packet_loss:.1f}%) and elevated latency ({avg_latency:.0f}ms avg).",
            f"Recommendation: Check network ACLs, firewall rules, or contact NOC.",
        ]

        return InvestigationResult(
            tool_name="network_diagnostics",
            raw_output="\n".join(lines),
        )
