"""
LiteLLM wrapper with Redis-backed circuit breaker fallback.

Primary: Gemini 2.0 Flash (Vertex AI). Fallback: Gemini 2.0 Flash Lite.
If both fail N consecutive times, circuit opens for T minutes.
State persisted in Redis so it survives worker restarts.
"""

import asyncio
import json
import os
import time
from typing import Any, cast

import structlog

from app.core.config import settings
from app.core.metrics import ai_failure_total, ai_request_total, circuit_breaker_state
from app.llm import build_llm_headers, configure_litellm
from app.llm.prompts import build_recommendation_prompt
from app.models.enums import RiskLevel
from app.schemas.recommendation import Recommendation

logger = structlog.get_logger()

CB_REDIS_KEY = "airex:circuit_breaker:llm"


class CircuitBreaker:
    """Circuit breaker with optional Redis persistence."""

    def __init__(self, threshold: int, cooldown_seconds: int) -> None:
        self.threshold = threshold
        self.cooldown = cooldown_seconds
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.is_open = False

    async def load_from_redis(self, redis) -> None:
        """Restore state from Redis."""
        if redis is None:
            return
        try:
            data = await redis.get(CB_REDIS_KEY)
            if data:
                state = json.loads(data)
                self.failure_count = state.get("failure_count", 0)
                self.last_failure_time = state.get("last_failure_time")
                self.is_open = state.get("is_open", False)
                circuit_breaker_state.set(1 if self.is_open else 0)
        except Exception:
            pass

    async def save_to_redis(self, redis) -> None:
        """Persist state to Redis."""
        if redis is None:
            return
        try:
            state = {
                "failure_count": self.failure_count,
                "last_failure_time": self.last_failure_time,
                "is_open": self.is_open,
            }
            await redis.set(CB_REDIS_KEY, json.dumps(state), ex=self.cooldown * 2)
        except Exception:
            pass

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.threshold:
            self.is_open = True
            circuit_breaker_state.set(1)
            logger.warning(
                "circuit_breaker_opened",
                failures=self.failure_count,
                cooldown=self.cooldown,
            )

    def record_success(self) -> None:
        self.failure_count = 0
        self.is_open = False
        circuit_breaker_state.set(0)

    def can_attempt(self) -> bool:
        if not self.is_open:
            return True
        if (
            self.last_failure_time
            and (time.time() - self.last_failure_time) > self.cooldown
        ):
            self.is_open = False
            self.failure_count = 0
            circuit_breaker_state.set(0)
            logger.info("circuit_breaker_half_open")
            return True
        return False


def _ensure_vertex_credentials() -> None:
    """
    Set GOOGLE_APPLICATION_CREDENTIALS if a service account key path
    is configured and the env var isn't already set.
    """
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return

    sa_key = settings.GCP_SERVICE_ACCOUNT_KEY
    if sa_key and os.path.exists(sa_key):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = sa_key
        logger.info("vertex_credentials_set", path=sa_key)
        return

    # Try the tenant config path for the default project
    default_key = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "config",
        "credentials",
        "smartops-automation.json",
    )
    if os.path.exists(default_key):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = default_key
        logger.info("vertex_credentials_set_default", path=default_key)


class LLMClient:
    """Model-agnostic LLM client with circuit breaker."""

    def __init__(self) -> None:
        configure_litellm()
        self.circuit_breaker = CircuitBreaker(
            threshold=settings.LLM_CIRCUIT_BREAKER_THRESHOLD,
            cooldown_seconds=settings.LLM_CIRCUIT_BREAKER_COOLDOWN,
        )

    async def generate_recommendation(
        self,
        alert_type: str,
        evidence: str,
        severity: str,
        context: str | None = None,
        redis=None,
    ) -> Recommendation | None:
        """
        Generate a structured recommendation.

        Returns None if circuit breaker is open or all attempts fail.
        """
        await self.circuit_breaker.load_from_redis(redis)

        if not self.circuit_breaker.can_attempt():
            logger.warning("llm_circuit_breaker_open")
            return None

        _ensure_vertex_credentials()

        messages = build_recommendation_prompt(
            alert_type,
            evidence,
            severity,
            context=context,
        )

        # Attempt primary model
        ai_request_total.labels(model=settings.LLM_PRIMARY_MODEL).inc()
        result = await self._call_model(
            settings.LLM_PRIMARY_MODEL,
            messages,
            timeout=settings.LLM_LOCAL_TIMEOUT,
        )
        if result is not None:
            self.circuit_breaker.record_success()
            await self.circuit_breaker.save_to_redis(redis)
            return result

        # Attempt fallback model
        logger.info(
            "llm_primary_failed_trying_fallback", fallback=settings.LLM_FALLBACK_MODEL
        )
        ai_request_total.labels(model=settings.LLM_FALLBACK_MODEL).inc()
        result = await self._call_model(
            settings.LLM_FALLBACK_MODEL,
            messages,
            timeout=settings.LLM_FALLBACK_TIMEOUT,
        )
        if result is not None:
            self.circuit_breaker.record_success()
            await self.circuit_breaker.save_to_redis(redis)
            return result

        # Both failed
        self.circuit_breaker.record_failure()
        await self.circuit_breaker.save_to_redis(redis)
        return None

    async def _call_model(
        self,
        model: str,
        messages: list[dict],
        timeout: int,
    ) -> Recommendation | None:
        """Call a single LLM model with timeout. Returns None on failure."""
        try:
            import litellm

            # When routing through a LiteLLM proxy, use the openai/
            # prefix so the local litellm SDK treats it as an
            # OpenAI-compatible endpoint and forwards to the proxy.
            effective_model = model
            if settings.LLM_BASE_URL:
                if not model.startswith("openai/"):
                    effective_model = f"openai/{model}"

            call_kwargs: dict[str, Any] = {
                "model": effective_model,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
            }

            # Pass proxy base URL and API key when configured
            if settings.LLM_BASE_URL:
                call_kwargs["api_base"] = settings.LLM_BASE_URL
            if settings.LLM_API_KEY:
                call_kwargs["api_key"] = settings.LLM_API_KEY

            headers = build_llm_headers()
            if headers:
                call_kwargs["extra_headers"] = headers

            # Vertex AI requires project and location (direct mode only)
            if model.startswith("vertex_ai/") and not settings.LLM_BASE_URL:
                call_kwargs["vertex_project"] = settings.VERTEX_PROJECT
                call_kwargs["vertex_location"] = settings.VERTEX_LOCATION

            raw_response = await asyncio.wait_for(
                litellm.acompletion(**call_kwargs),
                timeout=timeout,
            )
            response = cast(dict[str, Any], raw_response)
            choice = response["choices"][0]
            message = choice["message"]
            content = cast(str, message["content"])
            data = json.loads(content)

            recommendation = Recommendation(
                root_cause=data["root_cause"],
                proposed_action=data["proposed_action"],
                risk_level=RiskLevel(data["risk_level"]),
                confidence=float(data["confidence"]),
            )

            logger.info(
                "llm_recommendation_generated",
                model=model,
                action=recommendation.proposed_action,
                risk=recommendation.risk_level.value,
                confidence=recommendation.confidence,
            )

            return recommendation

        except asyncio.TimeoutError:
            logger.warning("llm_timeout", model=model, timeout=timeout)
            ai_failure_total.labels(model=model, error_type="timeout").inc()
            return None
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.warning("llm_parse_error", model=model, error=str(exc))
            ai_failure_total.labels(model=model, error_type="parse_error").inc()
            return None
        except Exception as exc:
            logger.warning("llm_call_failed", model=model, error=str(exc))
            ai_failure_total.labels(model=model, error_type="call_failed").inc()
            return None
