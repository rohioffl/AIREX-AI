"""Base class for execution actions."""

import abc

from pydantic import BaseModel


class ActionResult(BaseModel):
    """Structured output from an action execution."""

    success: bool
    logs: str
    exit_code: int = 0


class BaseAction(abc.ABC):
    """
    Abstract base for execution actions.

    Rules:
    - Deterministic: identical inputs -> identical behavior.
    - Sandboxed: run in isolated sessions (restricted SSH user / SSM).
    - NO raw shell commands. NO dynamic command generation.
    - Timeout enforced by the orchestrator (20s).
    """

    action_type: str
    DESCRIPTION: str = ""  # Human-readable description for LLM prompt

    @abc.abstractmethod
    async def execute(self, incident_meta: dict) -> ActionResult:
        """Execute the action. Returns ActionResult."""
        ...

    @abc.abstractmethod
    async def verify(self, incident_meta: dict) -> bool:
        """Verify the action resolved the issue. Returns True if resolved."""
        ...
