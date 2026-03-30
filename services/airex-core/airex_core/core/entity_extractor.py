"""Helpers for extracting grounded entities and signals from forensic outputs."""

from __future__ import annotations

import re
from typing import Any


def extract_probe_findings(raw_output: str) -> dict[str, Any]:
    """Extract summary, diagnosis, signals, and affected entities from probe text."""

    lines = [line.strip() for line in raw_output.splitlines() if line.strip()]
    summary = ""
    diagnosis = ""
    signals: list[str] = []
    affected_entities: list[str] = []

    for line in lines:
        lowered = line.lower()

        if line.startswith("=== ") and not summary:
            summary = line.strip("= ").strip()
        if lowered.startswith("diagnosis:"):
            diagnosis = line.split(":", 1)[1].strip()
        if any(
            token in lowered
            for token in ("cpu usage", "load average", "memory:", "swap:", "oom", "disk at")
        ):
            signals.append(line)
        if any(
            token in lowered
            for token in (
                "critical",
                "error",
                "rate limit",
                "throttl",
                "rejected_count",
                "deployment_detected",
                "unhealthy_count",
            )
        ):
            signals.append(line)

        if lowered.startswith("instance:"):
            instance_name = line.split(":", 1)[1].strip().lower()
            if instance_name and instance_name != "n/a":
                affected_entities.append(f"instance:{instance_name}")

        if lowered.startswith("private ip:"):
            ip = line.split(":", 1)[1].strip().lower()
            if ip and ip != "n/a":
                affected_entities.append(f"host:{ip}")

    process_match = re.search(
        r"Diagnosis:\s+.*PID\s+(\d+)\s+\(([^)]+)\)", raw_output, flags=re.IGNORECASE
    )
    if process_match:
        pid, command = process_match.groups()
        command = command.strip()
        signals.append(f"top_process_pid={pid}")
        signals.append(f"top_process_cmd={command}")
        affected_entities.append(f"process:{command.lower()}")

    log_pattern_match = re.search(r"Top pattern:\s*(.+)", raw_output, flags=re.IGNORECASE)
    if log_pattern_match:
        signals.append(f"log_pattern={log_pattern_match.group(1).strip()}")

    first_error_match = re.search(r"First error:\s*(.+)", raw_output, flags=re.IGNORECASE)
    if first_error_match:
        signals.append(f"first_error={first_error_match.group(1).strip()}")

    host_match = re.search(r"=== .*?:\s*(.+?)\s*===", raw_output)
    if host_match:
        host_name = host_match.group(1).strip().lower()
        if host_name and host_name != "unknown-host":
            affected_entities.append(f"host:{host_name}")

    return {
        "summary": summary,
        "diagnosis": diagnosis,
        "signals": list(dict.fromkeys(signal for signal in signals if signal)),
        "affected_entities": list(dict.fromkeys(entity for entity in affected_entities if entity)),
    }


def extract_reference_snippet(raw_output: str) -> str:
    """Return a short deterministic reference line from probe output."""

    lines = [line.strip() for line in raw_output.splitlines() if line.strip()]
    for prefix in ("Diagnosis:", "Top pattern:", "First error:", "Cloud:", "Instance:"):
        for line in lines:
            if line.startswith(prefix):
                return line
    return lines[0] if lines else ""


def needs_grounding(value: str) -> bool:
    """Return True when text is generic enough to require deterministic grounding."""

    text = value.strip().lower()
    if not text:
        return True
    return any(
        marker in text
        for marker in (
            "investigating ",
            "unknown",
            "requires further investigation",
            "further investigation is required",
            "needs identification",
            "unspecified resource",
            "pending investigation",
            "investigation initiated",
            "requires diagnostic data",
            "awaiting data",
            "awaiting diagnostics",
        )
    )


def entities_need_grounding(
    affected_entities: Any,
    fallback_entities: list[str],
) -> bool:
    """Return True when current entities are weaker than forensic entities."""

    if not isinstance(affected_entities, list):
        return True

    cleaned = [str(item).strip().lower() for item in affected_entities if str(item).strip()]
    if not cleaned:
        return True

    if any("unknown" in item for item in cleaned):
        return True

    concrete_prefixes = ("host:", "instance:", "process:", "pod:")
    has_concrete_current = any(item.startswith(concrete_prefixes) for item in cleaned)
    has_concrete_fallback = any(item.startswith(concrete_prefixes) for item in fallback_entities)
    if not has_concrete_current and has_concrete_fallback:
        return True

    return False


__all__ = [
    "entities_need_grounding",
    "extract_probe_findings",
    "extract_reference_snippet",
    "needs_grounding",
]
