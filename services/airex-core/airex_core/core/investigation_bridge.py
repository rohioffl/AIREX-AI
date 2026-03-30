"""OpenClaw gateway bridge for dynamic investigations."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any

import httpx

from airex_core.core.config import settings
from airex_core.core.entity_extractor import (
    entities_need_grounding,
    extract_probe_findings,
    extract_reference_snippet,
    needs_grounding,
)
from airex_core.investigations import INVESTIGATION_REGISTRY
from airex_core.investigations.base import ProbeResult
from airex_core.investigations.change_detection_probe import (
    ChangeDetectionProbe,
    should_run_change_detection,
)
from airex_core.investigations.cloud_investigation import CloudInvestigation
from airex_core.investigations.infra_state_probe import (
    InfraStateProbe,
    should_run_infra_state_probe,
)
from airex_core.investigations.k8s_probe import should_run_k8s_status_probe
from airex_core.investigations.log_analysis_probe import (
    LogAnalysisProbe,
    should_run_log_analysis,
)
from airex_core.models.incident import Incident
from airex_core.schemas.openclaw import EvidenceContract


@dataclass
class OpenClawRunMetadata:
    """Runtime metadata about an OpenClaw investigation attempt."""

    agent_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    agent_used_tools: list[str] = field(default_factory=list)
    agent_fallback_used: bool = False
    agent_failure_reason: str = ""


class InvestigationBridge:
    """Call the OpenClaw gateway and normalize the response contract."""

    _OPENCLAW_TOOL_TIMEOUT = 30

    async def ping(self, *, timeout: int | None = None) -> dict[str, Any]:
        """Probe the gateway for reachability and basic health."""
        request_timeout = timeout or min(settings.OPENCLAW_REQUEST_TIMEOUT, 5)
        base_url = settings.OPENCLAW_GATEWAY_URL.rstrip("/")

        async with httpx.AsyncClient(timeout=request_timeout) as client:
            errors: list[str] = []
            for path in ("/health", "/"):
                try:
                    response = await client.get(f"{base_url}{path}")
                    return {
                        "reachable": True,
                        "status_code": response.status_code,
                        "url": f"{base_url}{path}",
                    }
                except httpx.HTTPError as exc:
                    errors.append(str(exc))

        return {
            "reachable": False,
            "status_code": None,
            "url": base_url,
            "error": "; ".join(errors) if errors else "gateway probe failed",
        }

    async def run(
        self,
        incident: Incident,
        *,
        timeout: int | None = None,
        kg_context: str | None = None,
    ) -> EvidenceContract:
        try:
            incident_context = await self._read_incident_context(incident)
        except Exception:
            incident_context = {}
        payload = {
            "incident_id": str(incident.id),
            "tenant_id": str(incident.tenant_id),
            "alert_type": incident.alert_type,
            "title": incident.title,
            "severity": getattr(getattr(incident, "severity", None), "value", ""),
            "alert_data": getattr(incident, "raw_alert", None) or {},
            "meta": incident.meta or {},
            "knowledge_graph_context": kg_context or "",
            "incident_context": incident_context or {},
            "recommended_tools": self._build_openclaw_tool_hints(incident),
        }
        call_result = await self._call_openclaw(
            payload,
            timeout=timeout or settings.OPENCLAW_REQUEST_TIMEOUT,
        )
        response, run_metadata = self._normalize_call_result(call_result)
        forensic_results: list[ProbeResult] = []
        if self._response_needs_fallback(response):
            forensic_results = await self._gather_fallback_forensic_results(incident)
            if forensic_results:
                run_metadata.agent_fallback_used = True
                run_metadata.agent_failure_reason = "weak_or_under_grounded_agent_response"
                response = self._ground_payload_with_forensics(
                    response,
                    incident,
                    forensic_results,
                )
        contract = self._parse_evidence(response)
        contract.raw_refs = self._merge_run_metadata(
            existing=contract.raw_refs,
            run_metadata=run_metadata,
            forensic_results=forensic_results,
        )
        return contract

    async def _call_openclaw(
        self,
        payload: dict[str, Any],
        *,
        timeout: int,
    ) -> tuple[dict[str, Any], OpenClawRunMetadata]:
        headers = {"Content-Type": "application/json"}
        if settings.OPENCLAW_GATEWAY_TOKEN:
            token = settings.OPENCLAW_GATEWAY_TOKEN
            headers["Authorization"] = f"Bearer {token}"
            # OpenClaw accepts Bearer and/or this header (see gateway auth docs).
            headers["X-OpenClaw-Token"] = token
        headers["x-openclaw-agent-id"] = settings.OPENCLAW_AGENT_ID

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{settings.OPENCLAW_GATEWAY_URL.rstrip('/')}/v1/responses",
                json=self._build_responses_payload(payload),
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("OpenClaw response must be a JSON object")
            return self._extract_evidence_payload(data), self._extract_run_metadata(data)

    def _build_responses_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        system_instructions = (
            "You produce deterministic incident investigation summaries "
            "for machine consumption."
        )
        prompt = (
            "You are OpenClaw investigating an infrastructure incident for AIREX.\n"
            "Return exactly one JSON object with these keys:\n"
            "summary (string), signals (array of strings), root_cause (string), "
            "affected_entities (array of strings), confidence (number 0-1), "
            "raw_refs (object, optional).\n"
            "Do not wrap the JSON in markdown.\n\n"
            "When AIREX Investigation Tools are available, prefer calling them to gather "
            "host diagnostics, log analysis, change context, incident context, infrastructure state, "
            "and Kubernetes status before concluding.\n"
            "The recommended_tools field lists the tools that are most relevant for this incident. "
            "Do not assume they have already been run.\n\n"
            "Use agent tool calls to ground the result in machine diagnostics, logs, and cloud evidence. "
            "Prefer exact process, "
            "host, service, instance, or pod names over generic placeholders.\n\n"
            "Incident payload:\n"
            f"{json.dumps(payload, indent=2, sort_keys=True)}"
        )
        return {
            "model": f"openclaw/{settings.OPENCLAW_AGENT_ID}",
            "instructions": system_instructions,
            "input": prompt,
            "user": str(payload.get("incident_id") or ""),
        }

    def _extract_evidence_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if "output" in payload or "output_text" in payload:
            return self._extract_evidence_from_responses(payload)
        if "choices" not in payload:
            return payload

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("OpenClaw chat completion missing message content") from exc

        if isinstance(content, list):
            content = "".join(
                str(part.get("text", ""))
                for part in content
                if isinstance(part, dict)
            )

        if not isinstance(content, str):
            raise ValueError("OpenClaw chat completion content must be a string")

        content = self._extract_json_text(content)

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("OpenClaw chat completion did not return valid JSON") from exc

        if not isinstance(parsed, dict):
            raise ValueError("OpenClaw chat completion JSON must be an object")
        return parsed

    def _extract_evidence_from_responses(self, payload: dict[str, Any]) -> dict[str, Any]:
        content = payload.get("output_text")

        if not isinstance(content, str) or not content.strip():
            output_items = payload.get("output")
            content = self._extract_text_from_response_output(output_items)

        if not isinstance(content, str) or not content.strip():
            raise ValueError("OpenClaw responses output missing text content")

        content = self._extract_json_text(content)

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("OpenClaw responses output did not return valid JSON") from exc

        if not isinstance(parsed, dict):
            raise ValueError("OpenClaw responses output JSON must be an object")
        return parsed

    def _extract_text_from_response_output(self, output_items: Any) -> str:
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

    async def _gather_forensic_results(self, incident: Incident) -> list[ProbeResult]:
        return await self._gather_fallback_forensic_results(incident)

    async def _gather_fallback_forensic_results(self, incident: Incident) -> list[ProbeResult]:
        meta = dict(incident.meta or {})
        meta.setdefault("alert_type", incident.alert_type)
        openclaw_results = await self._gather_openclaw_tool_results(incident, meta)
        if openclaw_results:
            return openclaw_results

        results: list[ProbeResult] = []

        primary = await self._run_primary_forensic_probe(meta)
        if primary is not None:
            results.append(primary)

        extra_probes: list[Any] = []
        if should_run_log_analysis(meta):
            extra_probes.append(LogAnalysisProbe())
        if should_run_change_detection(meta):
            extra_probes.append(ChangeDetectionProbe())
        if should_run_infra_state_probe(meta):
            extra_probes.append(InfraStateProbe())

        for probe in extra_probes:
            try:
                result = await probe.investigate(meta)
            except Exception:
                continue
            if isinstance(result, ProbeResult):
                results.append(result)

        return results

    def _build_openclaw_tool_hints(self, incident: Incident) -> list[str]:
        meta = dict(incident.meta or {})
        meta.setdefault("alert_type", incident.alert_type)
        tool_hints = ["read_incident_context", "write_evidence_contract", "run_host_diagnostics"]
        if should_run_log_analysis(meta):
            tool_hints.append("fetch_log_analysis")
        if should_run_change_detection(meta):
            tool_hints.append("fetch_change_context")
        if should_run_infra_state_probe(meta):
            tool_hints.append("fetch_infra_state")
        if should_run_k8s_status_probe(meta):
            tool_hints.append("fetch_k8s_status")
        return list(dict.fromkeys(tool_hints))

    def _normalize_call_result(
        self,
        result: dict[str, Any] | tuple[dict[str, Any], OpenClawRunMetadata],
    ) -> tuple[dict[str, Any], OpenClawRunMetadata]:
        if isinstance(result, tuple) and len(result) == 2:
            payload, metadata = result
            if isinstance(payload, dict) and isinstance(metadata, OpenClawRunMetadata):
                return payload, metadata
        if isinstance(result, dict):
            return result, OpenClawRunMetadata()
        raise ValueError("OpenClaw bridge returned an invalid payload")

    def _response_needs_fallback(self, payload: dict[str, Any]) -> bool:
        summary = str(payload.get("summary") or "").strip()
        root_cause = str(payload.get("root_cause") or "").strip()
        affected = payload.get("affected_entities")
        signals = payload.get("signals")
        confidence = payload.get("confidence")

        if needs_grounding(summary) or needs_grounding(root_cause):
            return True
        if entities_need_grounding(affected, []):
            return True
        if not isinstance(signals, list) or not [item for item in signals if str(item).strip()]:
            return True
        return not isinstance(confidence, (int, float)) or confidence < 0.6

    def _extract_run_metadata(self, payload: dict[str, Any]) -> OpenClawRunMetadata:
        output_items = payload.get("output")
        if not isinstance(output_items, list):
            return OpenClawRunMetadata()

        tool_calls: list[dict[str, Any]] = []
        used_tools: list[str] = []
        for item in output_items:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type") or "").strip().lower()
            if "tool" not in item_type and "function" not in item_type:
                continue
            tool_name = self._extract_tool_name(item)
            if not tool_name:
                continue
            used_tools.append(tool_name)
            tool_calls.append(
                {
                    "name": tool_name,
                    "type": item_type,
                    "id": str(item.get("id") or item.get("call_id") or ""),
                    "status": str(item.get("status") or ""),
                }
            )

        return OpenClawRunMetadata(
            agent_tool_calls=tool_calls,
            agent_used_tools=list(dict.fromkeys(used_tools)),
        )

    def _extract_tool_name(self, item: dict[str, Any]) -> str:
        candidates = [
            item.get("name"),
            item.get("tool_name"),
            item.get("tool"),
        ]
        call = item.get("call")
        if isinstance(call, dict):
            candidates.append(call.get("name"))

        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return ""

    async def _gather_openclaw_tool_results(
        self,
        incident: Incident,
        meta: dict[str, Any],
    ) -> list[ProbeResult]:
        base_args: dict[str, Any] = {
            "tenant_id": str(incident.tenant_id),
            "incident_meta": meta,
        }
        host_args = dict(base_args)
        host_args["alert_type"] = incident.alert_type

        if meta.get("_cloud"):
            host_args["cloud"] = meta.get("_cloud")
        if meta.get("_instance_id"):
            host_args["instance_id"] = meta.get("_instance_id")
        if meta.get("_private_ip"):
            host_args["private_ip"] = meta.get("_private_ip")

        plan: list[tuple[str, dict[str, Any]]] = [("run_host_diagnostics", host_args)]
        if should_run_log_analysis(meta):
            plan.append(("fetch_log_analysis", dict(base_args)))
        if should_run_change_detection(meta):
            plan.append(("fetch_change_context", dict(base_args)))
        if should_run_infra_state_probe(meta):
            plan.append(("fetch_infra_state", dict(base_args)))
        if should_run_k8s_status_probe(meta):
            plan.append(("fetch_k8s_status", dict(base_args)))

        results: list[ProbeResult] = []
        for tool_name, args in plan:
            try:
                result = await self._invoke_openclaw_tool(tool_name, args=args)
            except Exception:
                continue
            if result is not None:
                results.append(result)

        return results

    async def _invoke_openclaw_tool(
        self,
        tool_name: str,
        *,
        args: dict[str, Any],
    ) -> ProbeResult | None:
        body = await self._invoke_openclaw_json_tool(tool_name, args=args)
        if not isinstance(body, dict) or not body.get("ok"):
            return None

        result = body.get("result")
        if not isinstance(result, dict):
            return None

        content = result.get("content")
        if not isinstance(content, list):
            return None

        for part in content:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            payload_text = self._extract_json_text(text)
            try:
                return ProbeResult.model_validate_json(payload_text)
            except Exception:
                continue

        return None

    async def _invoke_openclaw_json_tool(
        self,
        tool_name: str,
        *,
        args: dict[str, Any],
    ) -> dict[str, Any] | None:
        headers = {"Content-Type": "application/json"}
        if settings.OPENCLAW_GATEWAY_TOKEN:
            token = settings.OPENCLAW_GATEWAY_TOKEN
            headers["Authorization"] = f"Bearer {token}"
            headers["X-OpenClaw-Token"] = token

        payload = {
            "tool": tool_name,
            "args": args,
            "sessionKey": f"incident:{args.get('tenant_id', 'unknown')}",
        }

        async with httpx.AsyncClient(timeout=self._OPENCLAW_TOOL_TIMEOUT) as client:
            response = await client.post(
                f"{settings.OPENCLAW_GATEWAY_URL.rstrip('/')}/tools/invoke",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            body = response.json()

        return body if isinstance(body, dict) else None

    async def _read_incident_context(self, incident: Incident) -> dict[str, Any]:
        body = await self._invoke_openclaw_json_tool(
            "read_incident_context",
            args={
                "tenant_id": str(incident.tenant_id),
                "incident_id": str(incident.id),
            },
        )
        if not isinstance(body, dict) or not body.get("ok", True):
            return {}

        result = body.get("result")
        if not isinstance(result, dict):
            return {}

        content = result.get("content")
        if not isinstance(content, list):
            return {}

        for part in content:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            payload_text = self._extract_json_text(text)
            try:
                parsed = json.loads(payload_text)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return {}

    async def _run_primary_forensic_probe(self, meta: dict[str, Any]) -> ProbeResult | None:
        if self._should_use_cloud_investigation(meta):
            result = await CloudInvestigation().investigate(meta)
            return result if isinstance(result, ProbeResult) else None

        primary_cls = INVESTIGATION_REGISTRY.get(meta.get("alert_type", ""))
        if primary_cls is None:
            return None

        result = await primary_cls().investigate(meta)
        return result if isinstance(result, ProbeResult) else None

    def _serialize_forensic_results(self, results: list[ProbeResult]) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for result in results:
            serialized.append(
                {
                    "tool_name": result.tool_name,
                    "category": result.category.value,
                    "probe_type": result.probe_type,
                    "metrics": result.metrics,
                    "raw_output": result.raw_output,
                }
            )
        return serialized

    def _ground_payload_with_forensics(
        self,
        payload: dict[str, Any],
        incident: Incident,
        forensic_results: list[ProbeResult],
    ) -> dict[str, Any]:
        if not forensic_results:
            return payload

        grounded = dict(payload)
        grounded.setdefault("raw_refs", {})
        grounded["raw_refs"] = self._build_raw_refs(
            existing=grounded.get("raw_refs") or {},
            forensic_results=forensic_results,
        )

        summary = str(grounded.get("summary") or "").strip()
        root_cause = str(grounded.get("root_cause") or "").strip()
        affected = grounded.get("affected_entities")
        confidence = grounded.get("confidence")
        signals = grounded.get("signals")

        fallback = self._build_fallback_contract(incident, forensic_results)

        if needs_grounding(summary):
            grounded["summary"] = fallback["summary"]
        if needs_grounding(root_cause):
            grounded["root_cause"] = fallback["root_cause"]
        if entities_need_grounding(affected, fallback["affected_entities"]):
            grounded["affected_entities"] = fallback["affected_entities"]
        if not isinstance(signals, list) or not [item for item in signals if str(item).strip()]:
            grounded["signals"] = fallback["signals"]
        if not isinstance(confidence, (int, float)) or confidence < fallback["confidence"]:
            grounded["confidence"] = fallback["confidence"]

        return grounded

    def _build_fallback_contract(
        self,
        incident: Incident,
        forensic_results: list[ProbeResult],
    ) -> dict[str, Any]:
        signals: list[str] = []
        affected_entities: list[str] = []
        summary_parts: list[str] = []
        diagnosis: str | None = None

        meta = incident.meta or {}
        service_name = str(meta.get("service_name") or meta.get("service") or "").strip()
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

        unique_signals = list(dict.fromkeys(signal for signal in signals if signal))
        unique_entities = list(dict.fromkeys(entity for entity in affected_entities if entity))

        return {
            "summary": summary,
            "signals": unique_signals[:8],
            "root_cause": root_cause,
            "affected_entities": unique_entities[:8],
            "confidence": 0.7,
        }

    def _build_raw_refs(
        self,
        *,
        existing: dict[str, Any],
        forensic_results: list[ProbeResult],
    ) -> dict[str, Any]:
        raw_refs = dict(existing)
        raw_refs["forensic_tools"] = [result.tool_name for result in forensic_results]

        for result in forensic_results:
            snippet = extract_reference_snippet(result.raw_output)
            if snippet:
                raw_refs[result.tool_name] = snippet

        return raw_refs

    def _merge_run_metadata(
        self,
        *,
        existing: dict[str, Any],
        run_metadata: OpenClawRunMetadata,
        forensic_results: list[ProbeResult],
    ) -> dict[str, Any]:
        raw_refs = (
            self._build_raw_refs(existing=existing, forensic_results=forensic_results)
            if forensic_results
            else dict(existing)
        )
        if run_metadata.agent_tool_calls:
            raw_refs["agent_tool_calls"] = run_metadata.agent_tool_calls
        if run_metadata.agent_used_tools:
            raw_refs["agent_used_tools"] = run_metadata.agent_used_tools
        raw_refs["agent_fallback_used"] = run_metadata.agent_fallback_used
        if run_metadata.agent_failure_reason:
            raw_refs["agent_failure_reason"] = run_metadata.agent_failure_reason
        return raw_refs

    def _should_use_cloud_investigation(self, meta: dict[str, Any]) -> bool:
        cloud = (meta.get("_cloud") or "").lower()
        has_target = meta.get("_has_cloud_target", False)
        return cloud in ("gcp", "aws") and has_target

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

    def _parse_evidence(self, payload: dict[str, Any]) -> EvidenceContract:
        if "evidence" in payload and isinstance(payload["evidence"], dict):
            payload = payload["evidence"]

        if not isinstance(payload, dict):
            raise ValueError("OpenClaw evidence payload must be an object")

        return EvidenceContract.model_validate(payload)


__all__ = ["InvestigationBridge"]
