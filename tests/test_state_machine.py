"""Tests for the state machine — THE LAW.

Validates allowed transitions, rejects illegal ones, and verifies hash chaining.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from airex_core.core.state_machine import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    IllegalStateTransition,
    _compute_hash,
    transition_state,
)
from airex_core.models.enums import IncidentState


class TestAllowedTransitions:
    """Verify the transition graph is complete and correct."""

    def test_received_only_goes_to_investigating(self):
        assert ALLOWED_TRANSITIONS[IncidentState.RECEIVED] == [
            IncidentState.INVESTIGATING
        ]

    def test_investigating_transitions(self):
        allowed = ALLOWED_TRANSITIONS[IncidentState.INVESTIGATING]
        assert IncidentState.RECOMMENDATION_READY in allowed
        assert IncidentState.FAILED_ANALYSIS in allowed
        assert IncidentState.REJECTED in allowed
        assert len(allowed) == 3

    def test_executing_cannot_skip_to_resolved(self):
        allowed = ALLOWED_TRANSITIONS[IncidentState.EXECUTING]
        assert IncidentState.RESOLVED not in allowed
        assert IncidentState.REJECTED in allowed

    def test_awaiting_approval_transitions(self):
        allowed = ALLOWED_TRANSITIONS[IncidentState.AWAITING_APPROVAL]
        assert IncidentState.EXECUTING in allowed
        assert IncidentState.REJECTED in allowed
        assert IncidentState.RESOLVED not in allowed

    def test_verifying_can_resolve(self):
        allowed = ALLOWED_TRANSITIONS[IncidentState.VERIFYING]
        assert IncidentState.RESOLVED in allowed
        assert IncidentState.FAILED_VERIFICATION in allowed
        assert IncidentState.REJECTED in allowed

    def test_failed_verification_transitions(self):
        """FAILED_VERIFICATION can retry, fallback to alternative, or be rejected."""
        allowed = ALLOWED_TRANSITIONS[IncidentState.FAILED_VERIFICATION]
        assert IncidentState.REJECTED in allowed
        assert IncidentState.RESOLVED in allowed
        assert IncidentState.FAILED_VERIFICATION in allowed
        assert IncidentState.AWAITING_APPROVAL in allowed  # Phase 3 ARE fallback
        assert len(allowed) == 4

    def test_terminal_states_have_no_transitions(self):
        for state in TERMINAL_STATES:
            assert (
                state not in ALLOWED_TRANSITIONS or ALLOWED_TRANSITIONS.get(state) == []
            )

    def test_no_state_can_skip_investigation(self):
        """RECEIVED -> EXECUTING is BANNED."""
        allowed = ALLOWED_TRANSITIONS[IncidentState.RECEIVED]
        assert IncidentState.EXECUTING not in allowed
        assert IncidentState.AWAITING_APPROVAL not in allowed

    def test_all_states_defined(self):
        """Every non-terminal state should have transitions defined."""
        for state in IncidentState:
            if state not in TERMINAL_STATES:
                assert state in ALLOWED_TRANSITIONS, f"Missing transitions for {state}"


class TestComputeHash:
    """Verify hash chain computation."""

    def test_deterministic(self):
        h1 = _compute_hash("GENESIS", "RECEIVED", "INVESTIGATING", "test")
        h2 = _compute_hash("GENESIS", "RECEIVED", "INVESTIGATING", "test")
        assert h1 == h2

    def test_different_inputs_different_hash(self):
        h1 = _compute_hash("GENESIS", "RECEIVED", "INVESTIGATING", "reason1")
        h2 = _compute_hash("GENESIS", "RECEIVED", "INVESTIGATING", "reason2")
        assert h1 != h2

    def test_hash_length_is_sha256(self):
        h = _compute_hash("GENESIS", "RECEIVED", "INVESTIGATING", "test")
        assert len(h) == 64


class TestTransitionState:
    """Test the transition_state function with mocked DB session."""

    @pytest.mark.asyncio
    async def test_valid_transition(self, tenant_id):
        """RECEIVED -> INVESTIGATING should succeed."""
        incident = MagicMock()
        incident.tenant_id = tenant_id
        incident.id = uuid.uuid4()
        incident.state = IncidentState.RECEIVED

        session = AsyncMock()
        session.add = MagicMock()
        # No previous transitions
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        transition = await transition_state(
            session,
            incident,
            IncidentState.INVESTIGATING,
            reason="Webhook received",
            actor="test",
        )

        assert transition.from_state == IncidentState.RECEIVED
        assert transition.to_state == IncidentState.INVESTIGATING
        assert transition.previous_hash == "GENESIS"
        assert transition.reason == "Webhook received"
        assert incident.state == IncidentState.INVESTIGATING
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_illegal_transition_raises(self, tenant_id):
        """RECEIVED -> EXECUTING should be rejected."""
        incident = MagicMock()
        incident.tenant_id = tenant_id
        incident.id = uuid.uuid4()
        incident.state = IncidentState.RECEIVED

        session = AsyncMock()

        with pytest.raises(IllegalStateTransition) as exc_info:
            await transition_state(
                session,
                incident,
                IncidentState.EXECUTING,
                reason="Skip attempt",
            )

        assert "RECEIVED" in str(exc_info.value)
        assert "EXECUTING" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_illegal_skip_to_resolved(self, tenant_id):
        """INVESTIGATING -> RESOLVED should be rejected (must go through full pipeline)."""
        incident = MagicMock()
        incident.tenant_id = tenant_id
        incident.id = uuid.uuid4()
        incident.state = IncidentState.INVESTIGATING

        session = AsyncMock()

        with pytest.raises(IllegalStateTransition):
            await transition_state(
                session,
                incident,
                IncidentState.RESOLVED,
                reason="Magic fix",
            )

    @pytest.mark.asyncio
    async def test_terminal_state_cannot_transition(self, tenant_id):
        """Terminal states reject follow-up transitions."""
        incident = MagicMock()
        incident.tenant_id = tenant_id
        incident.id = uuid.uuid4()
        incident.state = IncidentState.RESOLVED

        session = AsyncMock()

        with pytest.raises(IllegalStateTransition):
            await transition_state(
                session,
                incident,
                IncidentState.INVESTIGATING,
                reason="Reopen without workflow",
            )

    @pytest.mark.asyncio
    async def test_hash_chain_continuation(self, tenant_id):
        """Second transition should chain from previous hash."""
        incident = MagicMock()
        incident.tenant_id = tenant_id
        incident.id = uuid.uuid4()
        incident.state = IncidentState.INVESTIGATING

        prev_transition = MagicMock()
        prev_transition.hash = "abc123"

        session = AsyncMock()
        session.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = prev_transition
        session.execute.return_value = mock_result

        transition = await transition_state(
            session,
            incident,
            IncidentState.RECOMMENDATION_READY,
            reason="Investigation complete",
        )

        assert transition.previous_hash == "abc123"
        assert transition.hash != "abc123"
