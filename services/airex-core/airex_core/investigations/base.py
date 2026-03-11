"""Base class for investigation plugins. All plugins are read-only."""

from __future__ import annotations

import abc
import hashlib
import random as _random
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Probe category taxonomy — used by anomaly detector and frontend badges
# ---------------------------------------------------------------------------


class ProbeCategory(str, Enum):
    """Classification for probe results."""

    SYSTEM = "system"  # CPU, memory, disk, load
    NETWORK = "network"  # Connectivity, latency, DNS, ports
    APPLICATION = "application"  # HTTP, API, healthcheck, logs
    INFRASTRUCTURE = "infrastructure"  # Cloud, ASG, VPC, container
    DATABASE = "database"  # DB health, queries, connections
    SECURITY = "security"  # SSL, credentials, blocked IPs
    SCHEDULING = "scheduling"  # Cron, heartbeat, FTP, mail
    MONITORING = "monitoring"  # Site24x7, external probes
    CHANGE = "change"  # CloudTrail, audit, deployments
    LOG_ANALYSIS = "log_analysis"  # Enhanced log pattern analysis


# ---------------------------------------------------------------------------
# Anomaly — detected by the anomaly detector after probes complete
# ---------------------------------------------------------------------------


class Anomaly(BaseModel):
    """A single anomaly detected in probe metrics."""

    metric_name: str
    value: float
    threshold: float
    severity: str = "warning"  # "warning" | "critical"
    description: str = ""


# ---------------------------------------------------------------------------
# InvestigationResult — backward-compatible, still works as before
# ---------------------------------------------------------------------------


class InvestigationResult(BaseModel):
    """Structured output from an investigation plugin (legacy compat)."""

    tool_name: str
    raw_output: str


# ---------------------------------------------------------------------------
# ProbeResult — extended result with structured metrics + anomalies
# ---------------------------------------------------------------------------


class ProbeResult(InvestigationResult):
    """
    Extended investigation result with structured metrics and anomalies.

    Inherits from InvestigationResult for full backward compatibility.
    All existing code that expects InvestigationResult will work unchanged.
    """

    category: ProbeCategory = ProbeCategory.SYSTEM
    metrics: dict[str, Any] = Field(default_factory=dict)
    anomalies: list[Anomaly] = Field(default_factory=list)
    duration_ms: float = 0.0
    probe_type: str = ""  # e.g. "primary", "secondary", "correlation"


# ---------------------------------------------------------------------------
# Seeded RNG helper
# ---------------------------------------------------------------------------


def _make_seeded_rng(incident_meta: dict) -> _random.Random:
    """
    Create a deterministic Random instance seeded from incident context.

    Uses host + monitor_name + alert_type to produce consistent values
    for the same incident while varying across different incidents.
    """
    seed_parts = [
        incident_meta.get("host", ""),
        incident_meta.get("monitor_name", ""),
        incident_meta.get("alert_type", ""),
        incident_meta.get("_instance_id", ""),
        incident_meta.get("_private_ip", ""),
    ]
    seed_str = ":".join(str(p) for p in seed_parts)
    seed_int = int(hashlib.sha256(seed_str.encode()).hexdigest()[:16], 16)
    return _random.Random(seed_int)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class BaseInvestigation(abc.ABC):
    """
    Abstract base for investigation plugins.

    Rules:
    - Read-only: NO side effects.
    - Hard timeout enforced by the orchestrator (60s).
    - Must return InvestigationResult (or ProbeResult) or raise.
    - Simulated evidence must ALWAYS indicate the problem that triggered the alert.
    - Use _make_seeded_rng() for deterministic variation, never bare random.
    """

    alert_type: str

    @abc.abstractmethod
    async def investigate(self, incident_meta: dict) -> InvestigationResult:
        """Run the investigation and return evidence."""
        ...
