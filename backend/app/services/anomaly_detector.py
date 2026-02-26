"""
Anomaly detector service.

Analyzes structured metrics from ProbeResults to detect anomalies
by comparing values against known thresholds. Runs after all probes
complete, adding anomaly annotations to each ProbeResult.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.investigations.base import Anomaly, ProbeCategory, ProbeResult

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Threshold definitions per metric name
# Each entry: (threshold_value, operator, severity, description_template)
#   operator: "gt" = value > threshold is anomalous
#             "lt" = value < threshold is anomalous
# ---------------------------------------------------------------------------

THRESHOLDS: dict[str, tuple[float, str, str, str]] = {
    # System metrics
    "cpu_percent": (85.0, "gt", "critical", "CPU usage {value}% exceeds {threshold}%"),
    "memory_percent": (
        85.0,
        "gt",
        "critical",
        "Memory usage {value}% exceeds {threshold}%",
    ),
    "disk_percent": (
        90.0,
        "gt",
        "critical",
        "Disk usage {value}% exceeds {threshold}%",
    ),
    "swap_percent": (50.0, "gt", "warning", "Swap usage {value}% exceeds {threshold}%"),
    "load_1m": (4.0, "gt", "warning", "Load average {value} exceeds {threshold}"),
    "inode_percent": (
        80.0,
        "gt",
        "warning",
        "Inode usage {value}% exceeds {threshold}%",
    ),
    "oom_kills_24h": (0.0, "gt", "critical", "{value} OOM kills detected in 24h"),
    # Network metrics
    "packet_loss_percent": (
        5.0,
        "gt",
        "critical",
        "Packet loss {value}% exceeds {threshold}%",
    ),
    "avg_latency_ms": (
        100.0,
        "gt",
        "warning",
        "Avg latency {value}ms exceeds {threshold}ms",
    ),
    "dns_resolution_ms": (
        50.0,
        "gt",
        "warning",
        "DNS resolution {value}ms exceeds {threshold}ms",
    ),
    # Application metrics
    "error_rate_percent": (
        5.0,
        "gt",
        "warning",
        "Error rate {value}% exceeds {threshold}%",
    ),
    "latency_ms": (500.0, "gt", "warning", "Latency {value}ms exceeds {threshold}ms"),
    "error_count_15m": (
        20.0,
        "gt",
        "warning",
        "{value} errors in 15 min exceeds {threshold}",
    ),
    "http_status": (499.0, "gt", "critical", "HTTP {value} server error detected"),
    # Database metrics
    "query_time_ms": (
        1000.0,
        "gt",
        "warning",
        "Query time {value}ms exceeds {threshold}ms",
    ),
    "connection_failures": (
        1.0,
        "gt",
        "warning",
        "{value} connection failures detected",
    ),
    # Infrastructure metrics
    "api_error_rate_percent": (
        1.0,
        "gt",
        "warning",
        "API error rate {value}% exceeds {threshold}%",
    ),
    "throttle_count_5m": (
        100.0,
        "gt",
        "warning",
        "{value} throttles in 5m exceeds {threshold}",
    ),
    "control_plane_latency_ms": (
        200.0,
        "gt",
        "warning",
        "Control plane latency {value}ms exceeds {threshold}ms",
    ),
    # Security metrics
    "days_until_expiry": (
        7.0,
        "lt",
        "critical",
        "SSL cert expires in {value} days (threshold {threshold})",
    ),
    # Scheduling metrics
    "last_heartbeat_minutes_ago": (
        5.0,
        "gt",
        "critical",
        "Last heartbeat {value} min ago exceeds {threshold} min",
    ),
    "consecutive_failures": (
        2.0,
        "gt",
        "warning",
        "{value} consecutive failures exceeds {threshold}",
    ),
    "last_success_hours_ago": (
        2.0,
        "gt",
        "warning",
        "Last success {value}h ago exceeds {threshold}h",
    ),
}


def detect_anomalies(probe: ProbeResult) -> list[Anomaly]:
    """
    Analyze a ProbeResult's metrics and return detected anomalies.

    Compares each metric value against known thresholds.
    Only numeric values are checked.
    """
    anomalies: list[Anomaly] = []

    for metric_name, value in probe.metrics.items():
        if not isinstance(value, (int, float)):
            continue

        threshold_def = THRESHOLDS.get(metric_name)
        if threshold_def is None:
            continue

        threshold_value, operator, severity, desc_template = threshold_def

        is_anomalous = False
        if operator == "gt" and value > threshold_value:
            is_anomalous = True
        elif operator == "lt" and value < threshold_value:
            is_anomalous = True

        if is_anomalous:
            description = desc_template.format(value=value, threshold=threshold_value)
            anomalies.append(
                Anomaly(
                    metric_name=metric_name,
                    value=float(value),
                    threshold=threshold_value,
                    severity=severity,
                    description=description,
                )
            )

    return anomalies


def annotate_probe_results(probes: list[ProbeResult]) -> list[ProbeResult]:
    """
    Run anomaly detection on all probe results and attach anomalies.

    Modifies probes in-place and returns them.
    """
    total_anomalies = 0
    for probe in probes:
        detected = detect_anomalies(probe)
        probe.anomalies = detected
        total_anomalies += len(detected)

    if total_anomalies > 0:
        logger.info(
            "anomalies_detected",
            total=total_anomalies,
            probes_with_anomalies=sum(1 for p in probes if p.anomalies),
        )

    return probes


def summarize_anomalies(probes: list[ProbeResult]) -> dict[str, Any]:
    """
    Build a summary dict of all anomalies across probes for storage in incident meta.

    Returns a dict with:
      - total_count: int
      - critical_count: int
      - warning_count: int
      - by_category: dict of category -> list of anomaly descriptions
      - top_anomalies: list of the most severe anomaly descriptions
    """
    all_anomalies: list[Anomaly] = []
    for probe in probes:
        all_anomalies.extend(probe.anomalies)

    if not all_anomalies:
        return {
            "total_count": 0,
            "critical_count": 0,
            "warning_count": 0,
            "by_category": {},
            "top_anomalies": [],
        }

    critical = [a for a in all_anomalies if a.severity == "critical"]
    warnings = [a for a in all_anomalies if a.severity == "warning"]

    by_category: dict[str, list[str]] = {}
    for probe in probes:
        if probe.anomalies:
            cat = probe.category.value
            if cat not in by_category:
                by_category[cat] = []
            for anomaly in probe.anomalies:
                by_category[cat].append(anomaly.description)

    # Top anomalies: critical first, then warnings, max 5
    top = [a.description for a in critical[:3]] + [a.description for a in warnings[:2]]

    return {
        "total_count": len(all_anomalies),
        "critical_count": len(critical),
        "warning_count": len(warnings),
        "by_category": by_category,
        "top_anomalies": top[:5],
    }
