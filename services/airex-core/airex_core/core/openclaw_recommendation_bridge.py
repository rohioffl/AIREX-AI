"""OpenClaw-backed recommendation generator."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from airex_core.core.config import settings
from airex_core.llm.client import _parse_recommendation
from airex_core.llm.prompts import build_recommendation_prompt
from airex_core.schemas.recommendation import Recommendation


class OpenClawRecommendationBridge:
    """Generate structured recommendations via the OpenClaw gateway."""

    async def generate_recommendation(
        self,
        *,
        alert_type: str,
        evidence: str,
        severity: str,
        context: str | None = None,
        timeout: int | None = None,
    ) -> Recommendation | None:
        messages = build_recommendation_prompt(
            alert_type=alert_type,
            evidence=evidence,
            severity=severity,
            context=context,
        )
        instructions = messages[0]["content"] if messages else ""
        prompt = messages[-1]["content"] if messages else ""

        headers = {"Content-Type": "application/json"}
        if settings.OPENCLAW_GATEWAY_TOKEN:
            token = settings.OPENCLAW_GATEWAY_TOKEN
            headers["Authorization"] = f"Bearer {token}"
            headers["X-OpenClaw-Token"] = token
        headers["x-openclaw-agent-id"] = settings.OPENCLAW_AGENT_ID

        payload = {
            "model": f"openclaw/{settings.OPENCLAW_AGENT_ID}",
            "instructions": instructions,
            "input": prompt,
            "user": f"recommendation:{alert_type}:{severity}",
        }

        async with httpx.AsyncClient(
            timeout=timeout or settings.OPENCLAW_REQUEST_TIMEOUT
        ) as client:
            response = await client.post(
                f"{settings.OPENCLAW_GATEWAY_URL.rstrip('/')}/v1/responses",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            body = response.json()

        if not isinstance(body, dict):
            return None

        content = self._extract_response_text(body)
        if not content:
            return None

        try:
            parsed = json.loads(self._extract_json_text(content))
        except json.JSONDecodeError:
            return None

        if not isinstance(parsed, dict):
            return None

        return _parse_recommendation(parsed)

    def _extract_response_text(self, payload: dict[str, Any]) -> str:
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        output_items = payload.get("output")
        if not isinstance(output_items, list):
            return ""

        chunks: list[str] = []
        for item in output_items:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "message":
                continue

            content = item.get("content")
            if not isinstance(content, list):
                continue

            for part in content:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str):
                    chunks.append(text)

        return "\n".join(chunk for chunk in chunks if chunk.strip())

    def _extract_json_text(self, content: str) -> str:
        stripped = content.strip()

        fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, flags=re.DOTALL)
        if fenced_match:
            return fenced_match.group(1).strip()

        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            return stripped[start : end + 1].strip()

        return stripped


__all__ = ["OpenClawRecommendationBridge"]
