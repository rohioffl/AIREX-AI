"""Standalone evidence grounding — extracted from InvestigationBridge.

Pure data-transformation functions with zero HTTP/gateway dependencies.
Used by the LangGraph ``analyze`` node and available for any future
orchestrator that needs to ground LLM responses with forensic probe data.
"""

from __future__ import annotations

import json
import re
from typing import Any

from airex_core.core.entity_extractor import (
    entities_need_grounding,
    extract_probe_findings,
    extract_reference_snippet,
    needs_grounding,
)
from airex_core.investigations.base import ProbeResult
from airex_core.models.incident import Incident
from airex_core.schemas.evidence import EvidenceContract


# ── Weak-response detection ────────────────────────────────────────


def response_needs_grounding(payload: dict[str, Any]) -> bool:
    """Return *True* when the LLM response is too vague to trust."""
    summary = str(payload.get("summary") or "").strip()
    root_cause = str(payload.get("root_cause") or "").strip()
    affected = payload.get("affected_entities")
    signals = payload.get("signals")
    confidence = payload.get("confidence")

    if needs_grounding(summary) or needs_grounding(root_cause):
        return True
    if entities_need_grounding(affected, []):
        return True
    if not isinstance(signals, list) or not [
        item for item in signals if str(item).strip()
    ]:
        return True
    return not isinstance(confidence, (int, float)) or confidence < 0.6


# ── Fallback evidence construction ─────────────────────────────────


def build_fallback_evidence(
    incident: Incident,
    forensic_results: list[ProbeResult],
) -> dict[str, Any]:
    """Build an evidence contract dict entirely from forensic probe data."""
    signals: list[str] = []
    affected_entities: list[str] = []
    summary_parts: list[str] = []
    diagnosis: str | None = None

    meta = incident.meta or {}
    service_name = str(
        meta.get("service_name") or meta.get("service") or ""
    ).strip()
    host = str(meta.get("host") or meta.get("monitor_name") or "").strip()
    instance_id = str(meta.get("_instance_id") or "").strip()

    if service_name:
        affected_entities.append(f"service:{service_name}")
    if host:
        affected_entities.append(f"host:{host}")
    if instance_id:
        affected_entities.append(f"instance:{instance_id}")

    for result in forensic_results:
        extracted = extract_probe_findings(result.raw_output)
        signals.extend(extracted["signals"])
        affected_entities.extend(extracted["affected_entities"])
        if extracted["summary"] and not summary_parts:
            summary_parts.append(extracted["summary"])
        if extracted["diagnosis"] and diagnosis is None:
            diagnosis = extracted["diagnosis"]

    summary = summary_parts[0] if summary_parts else (
        f"{incident.alert_type} detected and grounded with forensic diagnostics"
    )
    root_cause = diagnosis or summary

    unique_signals = list(
        dict.fromkeys(signal for signal in signals if signal)
    )
    unique_entities = list(
        dict.fromkeys(entity for entity in affected_entities if entity)
    )

    return {
        "summary": summary,
        "signals": unique_signals[:8],
        "root_cause": root_cause,
        "affected_entities": unique_entities[:8],
        "confidence": 0.7,
    }


# ── Raw-refs (forensic tool attribution) ───────────────────────────


def build_raw_refs(
    *,
    existing: dict[str, Any],
    forensic_results: list[ProbeResult],
) -> dict[str, Any]:
    """Construct forensic tool attribution metadata."""
    raw_refs = dict(existing)
    raw_refs["forensic_tools"] = [r.tool_name for r in forensic_results]

    for result in forensic_results:
        snippet = extract_reference_snippet(result.raw_output)
        if snippet:
            raw_refs[result.tool_name] = snippet

    return raw_refs


# ── Core grounding function ────────────────────────────────────────


def ground_evidence_with_probes(
    payload: dict[str, Any],
    incident: Incident,
    forensic_results: list[ProbeResult],
) -> dict[str, Any]:
    """Selectively replace weak LLM fields with forensic evidence."""
    if not forensic_results:
        return payload

    grounded = dict(payload)
    grounded.setdefault("raw_refs", {})
    grounded["raw_refs"] = build_raw_refs(
        existing=grounded.get("raw_refs") or {},
        forensic_results=forensic_results,
    )

    summary = str(grounded.get("summary") or "").strip()
    root_cause = str(grounded.get("root_cause") or "").strip()
    affected = grounded.get("affected_entities")
    confidence = grounded.get("confidence")
    signals = grounded.get("signals")

    fallback = build_fallback_evidence(incident, forensic_results)

    if needs_grounding(summary):
        grounded["summary"] = fallback["summary"]
    if needs_grounding(root_cause):
        grounded["root_cause"] = fallback["root_cause"]
    if entities_need_grounding(affected, fallback["affected_entities"]):
        grounded["affected_entities"] = fallback["affected_entities"]
    if not isinstance(signals, list) or not [
        item for item in signals if str(item).strip()
    ]:
        grounded["signals"] = fallback["signals"]
    if not isinstance(confidence, (int, float)) or confidence < fallback["confidence"]:
        grounded["confidence"] = fallback["confidence"]

    return grounded


# ── JSON parsing from LLM responses ───────────────────────────────


def extract_json_text(content: str) -> str:
    """Strip markdown fences or locate raw JSON braces in LLM output."""
    stripped = content.strip()

    fenced_match = re.search(
        r"```(?:json)?\s*(\{.*\})\s*```", stripped, flags=re.DOTALL
    )
    if fenced_match:
        return fenced_match.group(1).strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1].strip()

    return stripped


def parse_evidence_json(payload: dict[str, Any]) -> EvidenceContract:
    """Parse a raw response dict into a validated ``EvidenceContract``."""
    if "evidence" in payload and isinstance(payload["evidence"], dict):
        payload = payload["evidence"]

    if not isinstance(payload, dict):
        raise ValueError("Investigation evidence payload must be an object")

    return EvidenceContract.model_validate(payload)


def extract_evidence_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract evidence dict from chat-completion or Responses-API payloads."""
    if "output" in raw or "output_text" in raw:
        return _extract_from_responses(raw)
    if "choices" not in raw:
        return raw

    try:
        content = raw["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(
            "Chat completion missing message content"
        ) from exc

    if isinstance(content, list):
        content = "".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict)
        )

    if not isinstance(content, str):
        raise ValueError("Chat completion content must be a string")

    content = extract_json_text(content)

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("Chat completion did not return valid JSON") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Chat completion JSON must be an object")
    return parsed


# ── Internal helpers ───────────────────────────────────────────────


def _extract_from_responses(payload: dict[str, Any]) -> dict[str, Any]:
    """Handle OpenAI Responses API format."""
    content = payload.get("output_text")

    if not isinstance(content, str) or not content.strip():
        output_items = payload.get("output")
        content = _extract_text_from_output(output_items)

    if not isinstance(content, str) or not content.strip():
        raise ValueError("Responses output missing text content")

    content = extract_json_text(content)

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("Responses output did not return valid JSON") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Responses output JSON must be an object")
    return parsed


def _extract_text_from_output(output_items: Any) -> str:
    """Extract text from Responses API ``output`` array."""
    if not isinstance(output_items, list):
        return ""

    chunks: list[str] = []
    for item in output_items:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue

        content = item.get("content")
        if isinstance(content, str):
            chunks.append(content)
            continue

        if not isinstance(content, list):
            continue

        for part in content:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str):
                chunks.append(text)
                continue
            inner_text = part.get("content")
            if isinstance(inner_text, str):
                chunks.append(inner_text)

    return "\n".join(chunk for chunk in chunks if chunk.strip())
