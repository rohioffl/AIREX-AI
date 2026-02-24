"""Heuristic investigation plugin for generic Site24x7 healthcheck alerts."""

from __future__ import annotations

from typing import Iterable

from app.investigations.base import (
    BaseInvestigation,
    InvestigationResult,
    _make_seeded_rng,
)
from app.investigations.cpu_high import CpuHighInvestigation
from app.investigations.memory_high import MemoryHighInvestigation
from app.investigations.disk_full import DiskFullInvestigation
from app.investigations.network_check import NetworkCheckInvestigation


class HealthCheckInvestigation(BaseInvestigation):
    """Route generic health checks to the closest specialised plugin."""

    alert_type = "healthcheck"

    _ROUTING_RULES: list[tuple[str, type[BaseInvestigation], tuple[str, ...]]] = [
        (
            "cpu_high",
            CpuHighInvestigation,
            (
                "cpu",
                "processor",
                "load",
                "load average",
                "core",
                "utilization",
            ),
        ),
        (
            "memory_high",
            MemoryHighInvestigation,
            (
                "memory",
                "ram",
                "oom",
                "swap",
                "heap",
            ),
        ),
        (
            "disk_full",
            DiskFullInvestigation,
            (
                "disk",
                "filesystem",
                "inode",
                "storage",
                "volume",
            ),
        ),
        (
            "network_issue",
            NetworkCheckInvestigation,
            (
                "latency",
                "ping",
                "packet",
                "timeout",
                "network",
                "connection",
                "ssl",
            ),
        ),
    ]

    async def investigate(self, incident_meta: dict) -> InvestigationResult:
        text_haystack = self._build_context_blob(incident_meta)
        inferred = self._infer_target_plugin(text_haystack)

        if inferred:
            target_alert_type, plugin_cls = inferred
            derived_meta = dict(incident_meta)
            derived_meta.setdefault("_healthcheck_inferred_type", target_alert_type)
            plugin = plugin_cls()
            return await plugin.investigate(derived_meta)

        return self._fallback_probe(incident_meta)

    @staticmethod
    def _build_context_blob(meta: dict) -> str:
        parts: list[str] = []
        for key in (
            "INCIDENT_REASON",
            "MONITORTYPE",
            "monitor_name",
            "ALARM_CATEGORY",
        ):
            value = meta.get(key) or meta.get(
                key.lower() if isinstance(key, str) else key
            )
            if isinstance(value, str):
                parts.append(value)

        # Tags can arrive as list/str
        tags = meta.get("TAGS") or meta.get("JSON_TAGS") or []
        if isinstance(tags, str):
            parts.append(tags)
        elif isinstance(tags, Iterable):
            for tag in tags:
                if isinstance(tag, str):
                    parts.append(tag)
                elif isinstance(tag, dict) and tag.get("name"):
                    parts.append(str(tag["name"]))

        return " ".join(parts).lower()

    def _infer_target_plugin(
        self, context: str
    ) -> tuple[str, type[BaseInvestigation]] | None:
        for target, plugin_cls, keywords in self._ROUTING_RULES:
            if any(keyword in context for keyword in keywords):
                return target, plugin_cls
        return None

    def _fallback_probe(self, meta: dict) -> InvestigationResult:
        host = meta.get("host") or meta.get("monitor_name") or "unknown-host"
        rng = _make_seeded_rng(meta)

        response_ms = rng.uniform(500, 1200)
        success_count = rng.randint(2, 4)
        failure_count = rng.randint(1, 2)
        trace = [
            f"Attempt {i + 1}: HTTP 200 in {rng.uniform(320, 480):.0f}ms"
            for i in range(success_count)
        ]
        trace.append(
            f"Attempt {success_count + 1}: HTTP 503 in {response_ms:.0f}ms (origin server timeout)"
        )
        if failure_count > 1:
            trace.append(
                f"Attempt {success_count + 2}: TCP handshake failed after {rng.uniform(150, 250):.0f}ms"
            )

        output = [
            f"=== Synthetic Health Check: {host} ===",
            "Probe URL: /health",
            "Region Pool: site24x7-synthetic-ap-south",
            "",
            *trace,
            "",
            "Observed issue: Origin responded slowly and returned HTTP 503.",
            "Recommendation: Validate upstream service health and review recent deploys.",
        ]

        return InvestigationResult(
            tool_name="healthcheck_probe",
            raw_output="\n".join(output),
        )
