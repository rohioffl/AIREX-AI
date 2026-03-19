"""Dynamic probe chainer — Phase 5 Dynamic Investigation.

Examines completed primary probe results and generates additional
follow-up probe types based on what signals were actually found,
rather than firing secondary probes unconditionally based on alert type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from airex_core.investigations.base import ProbeCategory, ProbeResult


@dataclass(frozen=True)
class ChainRule:
    """A rule that triggers a follow-up probe when a metric threshold is crossed."""

    trigger_category: ProbeCategory
    trigger_metric: str
    trigger_threshold: float
    follow_up_probe: str
    reason: str


# Chain rules: (category, metric, threshold) → follow-up probe type
CHAIN_RULES: list[ChainRule] = [
    ChainRule(
        trigger_category=ProbeCategory.SYSTEM,
        trigger_metric="cpu_percent",
        trigger_threshold=80.0,
        follow_up_probe="change_detection",
        reason="High CPU — checking for recent deployments",
    ),
    ChainRule(
        trigger_category=ProbeCategory.SYSTEM,
        trigger_metric="memory_percent",
        trigger_threshold=85.0,
        follow_up_probe="log_analysis",
        reason="High memory — scanning logs for OOM/leak signals",
    ),
    ChainRule(
        trigger_category=ProbeCategory.APPLICATION,
        trigger_metric="error_rate",
        trigger_threshold=0.05,
        follow_up_probe="infra_state",
        reason="HTTP errors — checking infrastructure state",
    ),
    ChainRule(
        trigger_category=ProbeCategory.SYSTEM,
        trigger_metric="disk_percent",
        trigger_threshold=90.0,
        follow_up_probe="log_analysis",
        reason="Disk critical — checking log growth patterns",
    ),
]


def get_chained_probes(
    probe_results: Sequence[ProbeResult],
    already_running: set[str],
) -> list[tuple[str, str]]:
    """Return a list of (probe_type, reason) to chain based on completed probe results.

    Args:
        probe_results: Completed probe results to examine.
        already_running: Set of probe types already queued or running (prevents duplicates).

    Returns:
        List of (probe_type, reason) tuples for follow-up probes to run.
    """
    triggered: dict[str, str] = {}

    for result in probe_results:
        if not isinstance(result, ProbeResult):
            continue
        for rule in CHAIN_RULES:
            if rule.follow_up_probe in already_running:
                continue
            if rule.follow_up_probe in triggered:
                continue
            if result.category != rule.trigger_category:
                continue
            metric_value = result.metrics.get(rule.trigger_metric)
            if metric_value is None:
                continue
            try:
                if float(metric_value) >= rule.trigger_threshold:
                    triggered[rule.follow_up_probe] = rule.reason
            except (TypeError, ValueError):
                continue

    return list(triggered.items())


__all__ = ["ChainRule", "CHAIN_RULES", "get_chained_probes"]
