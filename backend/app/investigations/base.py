"""Base class for investigation plugins. All plugins are read-only."""

import abc
import hashlib
import random as _random

from pydantic import BaseModel


class InvestigationResult(BaseModel):
    """Structured output from an investigation plugin."""

    tool_name: str
    raw_output: str


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


class BaseInvestigation(abc.ABC):
    """
    Abstract base for investigation plugins.

    Rules:
    - Read-only: NO side effects.
    - Hard timeout enforced by the orchestrator (60s).
    - Must return InvestigationResult or raise.
    - Simulated evidence must ALWAYS indicate the problem that triggered the alert.
    - Use _make_seeded_rng() for deterministic variation, never bare random.
    """

    alert_type: str

    @abc.abstractmethod
    async def investigate(self, incident_meta: dict) -> InvestigationResult:
        """Run the investigation and return evidence."""
        ...
