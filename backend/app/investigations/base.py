"""Base class for investigation plugins. All plugins are read-only."""

import abc

from pydantic import BaseModel


class InvestigationResult(BaseModel):
    """Structured output from an investigation plugin."""

    tool_name: str
    raw_output: str


class BaseInvestigation(abc.ABC):
    """
    Abstract base for investigation plugins.

    Rules:
    - Read-only: NO side effects.
    - Hard timeout enforced by the orchestrator (60s).
    - Must return InvestigationResult or raise.
    """

    alert_type: str

    @abc.abstractmethod
    async def investigate(self, incident_meta: dict) -> InvestigationResult:
        """Run the investigation and return evidence."""
        ...
