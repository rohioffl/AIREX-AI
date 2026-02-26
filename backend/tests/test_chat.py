"""Tests for chat schemas, service, and prompt building (Phase 7)."""

import json
import uuid

import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.chat import ChatRequest, ChatResponse, ChatMessage
from app.llm.prompts import build_chat_messages, CHAT_SYSTEM_PROMPT


# ═══════════════════════════════════════════════════════════════════
#  Chat Schema Tests
# ═══════════════════════════════════════════════════════════════════


class TestChatRequest:
    def test_valid_message(self):
        req = ChatRequest(message="What caused this incident?")
        assert req.message == "What caused this incident?"

    def test_empty_message_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="")

    def test_long_message_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="x" * 2001)

    def test_boundary_message_length(self):
        req = ChatRequest(message="x" * 2000)
        assert len(req.message) == 2000

    def test_single_char_message(self):
        req = ChatRequest(message="?")
        assert req.message == "?"


class TestChatResponse:
    def test_valid_response(self):
        resp = ChatResponse(reply="The root cause is high CPU.", conversation_length=2)
        assert resp.reply == "The root cause is high CPU."
        assert resp.conversation_length == 2

    def test_missing_fields_rejected(self):
        with pytest.raises(ValidationError):
            ChatResponse(reply="hello")  # missing conversation_length


class TestChatMessage:
    def test_valid_message(self):
        msg = ChatMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"

    def test_assistant_role(self):
        msg = ChatMessage(role="assistant", content="I can help with that.")
        assert msg.role == "assistant"


# ═══════════════════════════════════════════════════════════════════
#  Chat Prompt Tests
# ═══════════════════════════════════════════════════════════════════


class TestChatSystemPrompt:
    def test_system_prompt_exists(self):
        assert len(CHAT_SYSTEM_PROMPT) > 100

    def test_system_prompt_prohibits_shell(self):
        assert "NEVER suggest running shell commands" in CHAT_SYSTEM_PROMPT

    def test_system_prompt_prohibits_fabrication(self):
        assert "NEVER fabricate data" in CHAT_SYSTEM_PROMPT

    def test_system_prompt_mentions_airex(self):
        assert "AIREX" in CHAT_SYSTEM_PROMPT


class TestBuildChatMessages:
    def test_returns_correct_structure(self):
        messages = build_chat_messages(
            incident_context="Alert: cpu_high on web-01",
            conversation_history=[],
            user_message="What happened?",
        )
        assert isinstance(messages, list)
        # system + context_user + ack_assistant + user_message = 4
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"
        assert messages[3]["role"] == "user"

    def test_includes_incident_context(self):
        messages = build_chat_messages(
            incident_context="CPU at 95% on web-01",
            conversation_history=[],
            user_message="Why?",
        )
        assert "CPU at 95% on web-01" in messages[1]["content"]

    def test_includes_user_message(self):
        messages = build_chat_messages(
            incident_context="ctx",
            conversation_history=[],
            user_message="Should I restart?",
        )
        assert messages[-1]["content"] == "Should I restart?"
        assert messages[-1]["role"] == "user"

    def test_includes_conversation_history(self):
        history = [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
        ]
        messages = build_chat_messages(
            incident_context="ctx",
            conversation_history=history,
            user_message="Follow up?",
        )
        # system + context + ack + 2 history + new user = 6
        assert len(messages) == 6
        assert messages[3]["content"] == "First question"
        assert messages[4]["content"] == "First answer"
        assert messages[5]["content"] == "Follow up?"

    def test_uses_chat_system_prompt(self):
        messages = build_chat_messages(
            incident_context="ctx",
            conversation_history=[],
            user_message="hi",
        )
        assert messages[0]["content"] == CHAT_SYSTEM_PROMPT


# ═══════════════════════════════════════════════════════════════════
#  Chat Service Tests
# ═══════════════════════════════════════════════════════════════════


class TestChatServiceHistory:
    """Test Redis-backed conversation history."""

    @pytest.mark.asyncio
    async def test_get_empty_history(self):
        from app.services.chat_service import get_conversation_history

        redis = AsyncMock()
        redis.get.return_value = None

        history = await get_conversation_history(redis, "t1", "i1")
        assert history == []

    @pytest.mark.asyncio
    async def test_get_existing_history(self):
        from app.services.chat_service import get_conversation_history

        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        redis = AsyncMock()
        redis.get.return_value = json.dumps(msgs)

        history = await get_conversation_history(redis, "t1", "i1")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_get_history_handles_redis_error(self):
        from app.services.chat_service import get_conversation_history

        redis = AsyncMock()
        redis.get.side_effect = Exception("Redis down")

        history = await get_conversation_history(redis, "t1", "i1")
        assert history == []

    @pytest.mark.asyncio
    async def test_save_history(self):
        from app.services.chat_service import (
            save_conversation_history,
            CHAT_TTL_SECONDS,
        )

        redis = AsyncMock()
        msgs = [{"role": "user", "content": "hi"}]

        await save_conversation_history(redis, "t1", "i1", msgs)

        redis.set.assert_called_once()
        call_args = redis.set.call_args
        assert call_args[1]["ex"] == CHAT_TTL_SECONDS

    @pytest.mark.asyncio
    async def test_save_trims_long_history(self):
        from app.services.chat_service import (
            save_conversation_history,
            MAX_HISTORY_MESSAGES,
        )

        redis = AsyncMock()
        # Create more messages than MAX_HISTORY_MESSAGES
        msgs = [{"role": "user", "content": f"msg {i}"} for i in range(60)]

        await save_conversation_history(redis, "t1", "i1", msgs)

        # Verify the saved data is trimmed
        saved_json = redis.set.call_args[0][1]
        saved = json.loads(saved_json)
        assert len(saved) == MAX_HISTORY_MESSAGES


class TestChatServiceBuildContext:
    """Test incident context building."""

    def test_builds_basic_context(self):
        from app.services.chat_service import _build_incident_context

        incident = MagicMock()
        incident.id = uuid.uuid4()
        incident.alert_type = "cpu_high"
        incident.severity.value = "CRITICAL"
        incident.state.value = "INVESTIGATING"
        incident.title = "High CPU on web-01"
        incident.host_key = "web-01"
        incident.created_at = "2024-01-01T00:00:00Z"
        incident.evidence = []
        incident.meta = {}
        incident.state_transitions = []
        incident.executions = []

        ctx = _build_incident_context(incident)
        assert "cpu_high" in ctx
        assert "CRITICAL" in ctx
        assert "High CPU on web-01" in ctx

    def test_includes_evidence(self):
        from app.services.chat_service import _build_incident_context

        evidence = MagicMock()
        evidence.tool_name = "cpu_diagnostics"
        evidence.raw_output = "CPU at 95%"

        incident = MagicMock()
        incident.id = uuid.uuid4()
        incident.alert_type = "cpu_high"
        incident.severity.value = "HIGH"
        incident.state.value = "INVESTIGATING"
        incident.title = "CPU"
        incident.host_key = "web-01"
        incident.created_at = "2024-01-01"
        incident.evidence = [evidence]
        incident.meta = {}
        incident.state_transitions = []
        incident.executions = []

        ctx = _build_incident_context(incident)
        assert "cpu_diagnostics" in ctx
        assert "CPU at 95%" in ctx

    def test_includes_recommendation(self):
        from app.services.chat_service import _build_incident_context

        incident = MagicMock()
        incident.id = uuid.uuid4()
        incident.alert_type = "cpu_high"
        incident.severity.value = "HIGH"
        incident.state.value = "RECOMMENDATION_READY"
        incident.title = "CPU"
        incident.host_key = "web-01"
        incident.created_at = "2024-01-01"
        incident.evidence = []
        incident.meta = {
            "recommendation": {
                "root_cause": "Runaway Java process",
                "proposed_action": "restart_service",
                "risk_level": "MED",
                "confidence": 0.85,
                "summary": "Restart the stuck service",
                "rationale": "Historical pattern shows restart fixes this",
            }
        }
        incident.state_transitions = []
        incident.executions = []

        ctx = _build_incident_context(incident)
        assert "Runaway Java process" in ctx
        assert "restart_service" in ctx
        assert "Restart the stuck service" in ctx

    def test_includes_anomalies(self):
        from app.services.chat_service import _build_incident_context

        incident = MagicMock()
        incident.id = uuid.uuid4()
        incident.alert_type = "cpu_high"
        incident.severity.value = "HIGH"
        incident.state.value = "INVESTIGATING"
        incident.title = "CPU"
        incident.host_key = None
        incident.created_at = "2024-01-01"
        incident.evidence = []
        incident.meta = {
            "anomalies": [
                {
                    "severity": "critical",
                    "metric": "cpu_usage",
                    "description": "CPU at 98%",
                }
            ]
        }
        incident.state_transitions = []
        incident.executions = []

        ctx = _build_incident_context(incident)
        assert "CPU at 98%" in ctx
        assert "Detected Anomalies" in ctx


class TestChatServiceChatWithIncident:
    """Test the main chat_with_incident function."""

    @pytest.mark.asyncio
    async def test_incident_not_found_raises(self):
        from app.services.chat_service import chat_with_incident

        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock
        redis = AsyncMock()
        redis.get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await chat_with_incident(
                session=session,
                incident_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                user_message="hello",
                redis=redis,
            )

    @pytest.mark.asyncio
    async def test_llm_failure_raises_runtime_error(self):
        from app.services.chat_service import chat_with_incident

        incident = MagicMock()
        incident.id = uuid.uuid4()
        incident.tenant_id = uuid.uuid4()
        incident.alert_type = "cpu_high"
        incident.severity.value = "HIGH"
        incident.state.value = "INVESTIGATING"
        incident.title = "CPU"
        incident.host_key = None
        incident.created_at = "2024-01-01"
        incident.evidence = []
        incident.meta = {}
        incident.state_transitions = []
        incident.executions = []

        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = incident
        session.execute.return_value = result_mock

        redis = AsyncMock()
        redis.get.return_value = None

        with patch("app.services.chat_service.llm_client") as mock_llm:
            mock_llm.chat = AsyncMock(return_value=None)  # LLM failure

            with pytest.raises(RuntimeError, match="temporarily unavailable"):
                await chat_with_incident(
                    session=session,
                    incident_id=incident.id,
                    tenant_id=incident.tenant_id,
                    user_message="hello",
                    redis=redis,
                )

    @pytest.mark.asyncio
    async def test_successful_chat_returns_reply_and_length(self):
        from app.services.chat_service import chat_with_incident

        incident = MagicMock()
        incident.id = uuid.uuid4()
        incident.tenant_id = uuid.uuid4()
        incident.alert_type = "cpu_high"
        incident.severity.value = "HIGH"
        incident.state.value = "INVESTIGATING"
        incident.title = "CPU"
        incident.host_key = None
        incident.created_at = "2024-01-01"
        incident.evidence = []
        incident.meta = {}
        incident.state_transitions = []
        incident.executions = []

        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = incident
        session.execute.return_value = result_mock

        redis = AsyncMock()
        redis.get.return_value = None  # No prior history

        with patch("app.services.chat_service.llm_client") as mock_llm:
            mock_llm.chat = AsyncMock(
                return_value="The CPU is high due to a Java process."
            )

            reply, length = await chat_with_incident(
                session=session,
                incident_id=incident.id,
                tenant_id=incident.tenant_id,
                user_message="What's wrong?",
                redis=redis,
            )

            assert reply == "The CPU is high due to a Java process."
            assert length == 2  # user + assistant

    @pytest.mark.asyncio
    async def test_chat_preserves_history(self):
        from app.services.chat_service import chat_with_incident

        incident = MagicMock()
        incident.id = uuid.uuid4()
        incident.tenant_id = uuid.uuid4()
        incident.alert_type = "cpu_high"
        incident.severity.value = "HIGH"
        incident.state.value = "INVESTIGATING"
        incident.title = "CPU"
        incident.host_key = None
        incident.created_at = "2024-01-01"
        incident.evidence = []
        incident.meta = {}
        incident.state_transitions = []
        incident.executions = []

        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = incident
        session.execute.return_value = result_mock

        prior_history = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
        ]
        redis = AsyncMock()
        redis.get.return_value = json.dumps(prior_history)

        with patch("app.services.chat_service.llm_client") as mock_llm:
            mock_llm.chat = AsyncMock(return_value="Answer 2")

            reply, length = await chat_with_incident(
                session=session,
                incident_id=incident.id,
                tenant_id=incident.tenant_id,
                user_message="q2",
                redis=redis,
            )

            assert reply == "Answer 2"
            assert length == 4  # 2 prior + 2 new

            # Verify the LLM chat was called once
            mock_llm.chat.assert_called_once()
            # The conversation_history list is mutated after the call
            # (user + assistant appended), so call_args shows 4 items.
            # Verify the call included the user_message kwarg.
            call_kwargs = mock_llm.chat.call_args
            assert call_kwargs[1]["user_message"] == "q2"
