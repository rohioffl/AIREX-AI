"""Tests for enhanced recommendation schema and parse_recommendation (Phase 6)."""

import pytest

from airex_core.llm.client import _parse_recommendation
from airex_core.models.enums import RiskLevel
from airex_core.schemas.recommendation import (
    AlternativeRecommendation,
    Recommendation,
    ReasoningStep,
)


# ═══════════════════════════════════════════════════════════════════
#  Enhanced Recommendation Schema Tests
# ═══════════════════════════════════════════════════════════════════


class TestReasoningStep:
    def test_valid_step(self):
        step = ReasoningStep(
            step=1,
            description="Observed high CPU",
            evidence_used="cpu_diagnostics probe",
        )
        assert step.step == 1
        assert step.description == "Observed high CPU"

    def test_default_evidence(self):
        step = ReasoningStep(step=1, description="desc")
        assert step.evidence_used == ""


class TestAlternativeRecommendation:
    def test_valid_alternative(self):
        alt = AlternativeRecommendation(
            action="scale_instances",
            rationale="Scale horizontally instead",
            confidence=0.65,
            risk_level=RiskLevel.LOW,
        )
        assert alt.action == "scale_instances"
        assert alt.confidence == 0.65

    def test_confidence_boundary(self):
        alt = AlternativeRecommendation(
            action="x",
            rationale="r",
            confidence=0.0,
            risk_level=RiskLevel.LOW,
        )
        assert alt.confidence == 0.0

        alt2 = AlternativeRecommendation(
            action="x",
            rationale="r",
            confidence=1.0,
            risk_level=RiskLevel.HIGH,
        )
        assert alt2.confidence == 1.0


class TestEnhancedRecommendation:
    def test_legacy_fields_only(self):
        rec = Recommendation(
            root_cause="High CPU",
            proposed_action="restart_service",
            risk_level=RiskLevel.MED,
            confidence=0.85,
        )
        assert rec.summary == ""
        assert rec.reasoning_chain == []
        assert rec.alternatives == []
        assert rec.verification_criteria == []

    def test_full_enhanced_fields(self):
        rec = Recommendation(
            root_cause="High CPU from runaway Java process",
            proposed_action="restart_service",
            risk_level=RiskLevel.MED,
            confidence=0.85,
            summary="Restart the stuck service",
            root_cause_category="resource_exhaustion",
            contributing_factors=["memory leak", "missing heap limit"],
            reasoning_chain=[
                ReasoningStep(
                    step=1, description="Observed 95% CPU", evidence_used="cpu probe"
                ),
                ReasoningStep(
                    step=2,
                    description="Java process is top",
                    evidence_used="top output",
                ),
            ],
            rationale="Historical data shows restart works",
            blast_radius="single_instance",
            alternatives=[
                AlternativeRecommendation(
                    action="kill_process",
                    rationale="Kill only the Java process",
                    confidence=0.7,
                    risk_level=RiskLevel.LOW,
                ),
            ],
            evidence_annotations=["CPU at 95%", "Java PID 1234"],
            verification_criteria=["CPU below 80%", "Service responds to health check"],
        )
        assert rec.summary == "Restart the stuck service"
        assert rec.root_cause_category == "resource_exhaustion"
        assert len(rec.contributing_factors) == 2
        assert len(rec.reasoning_chain) == 2
        assert len(rec.alternatives) == 1
        assert len(rec.verification_criteria) == 2

    def test_model_dump_round_trip(self):
        rec = Recommendation(
            root_cause="test",
            proposed_action="restart_service",
            risk_level=RiskLevel.LOW,
            confidence=0.5,
            summary="Test summary",
            alternatives=[
                AlternativeRecommendation(
                    action="flush_cache",
                    rationale="r",
                    confidence=0.3,
                    risk_level=RiskLevel.LOW,
                ),
            ],
        )
        data = rec.model_dump()
        assert data["summary"] == "Test summary"
        assert len(data["alternatives"]) == 1
        assert data["alternatives"][0]["action"] == "flush_cache"

    def test_openclaw_contract_fields_round_trip(self):
        rec = Recommendation(
            root_cause="CPU saturation on checkout-api",
            proposed_action="scale_instances",
            risk_level=RiskLevel.HIGH,
            confidence=0.91,
            action_type="execute_fix",
            action_id="scale_instances",
            target="checkout-api",
            params={"replicas": 5},
            reason="CPU > 90% for 5 minutes",
        )

        data = rec.model_dump()

        assert data["action_type"] == "execute_fix"
        assert data["action_id"] == "scale_instances"
        assert data["target"] == "checkout-api"
        assert data["params"] == {"replicas": 5}
        assert data["reason"] == "CPU > 90% for 5 minutes"


# ═══════════════════════════════════════════════════════════════════
#  _parse_recommendation Tests
# ═══════════════════════════════════════════════════════════════════


class TestParseRecommendation:
    def test_legacy_four_fields(self):
        data = {
            "root_cause": "Disk full",
            "proposed_action": "clear_logs",
            "risk_level": "LOW",
            "confidence": 0.9,
        }
        rec = _parse_recommendation(data)
        assert rec.root_cause == "Disk full"
        assert rec.proposed_action == "clear_logs"
        assert rec.risk_level == RiskLevel.LOW
        assert rec.confidence == 0.9
        assert rec.summary == ""
        assert rec.reasoning_chain == []

    def test_enhanced_fields_parsed(self):
        data = {
            "root_cause": "Memory leak",
            "proposed_action": "restart_service",
            "risk_level": "MED",
            "confidence": 0.85,
            "summary": "Restart to clear memory",
            "root_cause_category": "resource_exhaustion",
            "contributing_factors": ["no heap limit", "long uptime"],
            "rationale": "Restart frees leaked memory",
            "blast_radius": "single_instance",
            "evidence_annotations": ["Memory at 98%", "Uptime 30 days"],
            "verification_criteria": ["Memory below 70%", "No OOM in 10 min"],
        }
        rec = _parse_recommendation(data)
        assert rec.summary == "Restart to clear memory"
        assert rec.root_cause_category == "resource_exhaustion"
        assert len(rec.contributing_factors) == 2
        assert rec.rationale == "Restart frees leaked memory"
        assert rec.blast_radius == "single_instance"
        assert len(rec.evidence_annotations) == 2
        assert len(rec.verification_criteria) == 2

    def test_openclaw_contract_fields_parsed(self):
        data = {
            "action_type": "execute_fix",
            "action_id": "scale_instances",
            "target": "checkout-api",
            "params": {"replicas": 5},
            "reason": "CPU > 90% for 5 minutes",
            "risk": "HIGH",
            "confidence": 0.91,
            "root_cause": "CPU saturation caused by insufficient capacity",
        }

        rec = _parse_recommendation(data)

        assert rec.proposed_action == "scale_instances"
        assert rec.risk_level == RiskLevel.HIGH
        assert rec.action_type == "execute_fix"
        assert rec.action_id == "scale_instances"
        assert rec.target == "checkout-api"
        assert rec.params == {"replicas": 5}
        assert rec.reason == "CPU > 90% for 5 minutes"

    def test_reasoning_chain_parsed(self):
        data = {
            "root_cause": "CPU",
            "proposed_action": "restart_service",
            "risk_level": "MED",
            "confidence": 0.8,
            "reasoning_chain": [
                {"step": 1, "description": "Saw high CPU", "evidence_used": "probe"},
                {"step": 2, "description": "Java is top", "evidence_used": "top"},
                {
                    "step": 3,
                    "description": "Restart recommended",
                    "evidence_used": "history",
                },
            ],
        }
        rec = _parse_recommendation(data)
        assert len(rec.reasoning_chain) == 3
        assert rec.reasoning_chain[0].step == 1
        assert rec.reasoning_chain[1].description == "Java is top"
        assert rec.reasoning_chain[2].evidence_used == "history"

    def test_alternatives_parsed(self):
        data = {
            "root_cause": "CPU",
            "proposed_action": "restart_service",
            "risk_level": "MED",
            "confidence": 0.8,
            "alternatives": [
                {
                    "action": "kill_process",
                    "rationale": "Kill only the Java process",
                    "confidence": 0.65,
                    "risk_level": "LOW",
                },
                {
                    "action": "scale_instances",
                    "rationale": "Add capacity",
                    "confidence": 0.5,
                    "risk_level": "MED",
                },
            ],
        }
        rec = _parse_recommendation(data)
        assert len(rec.alternatives) == 2
        assert rec.alternatives[0].action == "kill_process"
        assert rec.alternatives[0].risk_level == RiskLevel.LOW
        assert rec.alternatives[1].confidence == 0.5

    def test_malformed_reasoning_chain_skipped(self):
        data = {
            "root_cause": "test",
            "proposed_action": "restart_service",
            "risk_level": "LOW",
            "confidence": 0.5,
            "reasoning_chain": ["not a dict", 42, None],
        }
        rec = _parse_recommendation(data)
        assert rec.reasoning_chain == []

    def test_malformed_alternatives_skipped(self):
        data = {
            "root_cause": "test",
            "proposed_action": "restart_service",
            "risk_level": "LOW",
            "confidence": 0.5,
            "alternatives": [
                {"no_action_key": "oops"},
                "not a dict",
            ],
        }
        rec = _parse_recommendation(data)
        assert rec.alternatives == []

    def test_missing_core_field_raises(self):
        data = {
            "root_cause": "test",
            # missing proposed_action
            "risk_level": "LOW",
            "confidence": 0.5,
        }
        with pytest.raises(KeyError):
            _parse_recommendation(data)

    def test_invalid_risk_level_raises(self):
        data = {
            "root_cause": "test",
            "proposed_action": "restart_service",
            "risk_level": "ULTRA_HIGH",
            "confidence": 0.5,
        }
        with pytest.raises(ValueError):
            _parse_recommendation(data)

    def test_partial_enhanced_fields(self):
        """Only some enhanced fields present — others default."""
        data = {
            "root_cause": "test",
            "proposed_action": "restart_service",
            "risk_level": "HIGH",
            "confidence": 0.9,
            "summary": "Quick fix",
            # No other enhanced fields
        }
        rec = _parse_recommendation(data)
        assert rec.summary == "Quick fix"
        assert rec.root_cause_category == ""
        assert rec.contributing_factors == []
        assert rec.reasoning_chain == []
        assert rec.alternatives == []

    def test_non_list_contributing_factors_ignored(self):
        data = {
            "root_cause": "test",
            "proposed_action": "restart_service",
            "risk_level": "LOW",
            "confidence": 0.5,
            "contributing_factors": "not a list",
        }
        rec = _parse_recommendation(data)
        assert rec.contributing_factors == []

    def test_non_list_verification_criteria_ignored(self):
        data = {
            "root_cause": "test",
            "proposed_action": "restart_service",
            "risk_level": "LOW",
            "confidence": 0.5,
            "verification_criteria": "single string",
        }
        rec = _parse_recommendation(data)
        assert rec.verification_criteria == []


# ═══════════════════════════════════════════════════════════════════
#  Action DESCRIPTION Tests
# ═══════════════════════════════════════════════════════════════════


class TestActionDescriptions:
    def test_all_actions_have_description(self):
        from airex_core.actions.registry import ACTION_REGISTRY

        for name, cls in ACTION_REGISTRY.items():
            desc = getattr(cls, "DESCRIPTION", "")
            assert desc, f"Action '{name}' is missing DESCRIPTION"
            assert len(desc) > 10, f"Action '{name}' has too-short DESCRIPTION"

    def test_dynamic_prompt_includes_descriptions(self):
        from airex_core.llm.prompts import _build_action_descriptions

        descriptions = _build_action_descriptions()
        assert "restart_service" in descriptions
        assert "clear_logs" in descriptions
        # Should include description text, not just names
        assert "Restart" in descriptions or "restart" in descriptions


# ═══════════════════════════════════════════════════════════════════
#  Serialize Recommendation Tests
# ═══════════════════════════════════════════════════════════════════


class TestSerializeRecommendation:
    def test_converts_enums(self):
        from airex_core.services.recommendation_service import _serialize_recommendation

        rec_dict = {
            "risk_level": RiskLevel.HIGH,
            "alternatives": [
                {"action": "x", "risk_level": RiskLevel.LOW},
                {"action": "y", "risk_level": RiskLevel.MED},
            ],
        }
        result = _serialize_recommendation(rec_dict)
        assert result["risk_level"] == "HIGH"
        assert result["alternatives"][0]["risk_level"] == "LOW"
        assert result["alternatives"][1]["risk_level"] == "MED"

    def test_handles_string_risk_levels(self):
        from airex_core.services.recommendation_service import _serialize_recommendation

        rec_dict = {
            "risk_level": "LOW",
            "alternatives": [
                {"action": "x", "risk_level": "MED"},
            ],
        }
        result = _serialize_recommendation(rec_dict)
        assert result["risk_level"] == "LOW"
        assert result["alternatives"][0]["risk_level"] == "MED"

    def test_handles_no_alternatives(self):
        from airex_core.services.recommendation_service import _serialize_recommendation

        rec_dict = {"risk_level": RiskLevel.MED}
        result = _serialize_recommendation(rec_dict)
        assert result["risk_level"] == "MED"


class TestRecommendationContract:
    def test_builds_contract_from_internal_recommendation(self):
        from airex_core.schemas.recommendation_contract import RecommendationContract

        rec = Recommendation(
            root_cause="CPU saturation",
            proposed_action="scale_instances",
            risk_level=RiskLevel.HIGH,
            confidence=0.91,
            summary="Scale checkout-api",
            rationale="CPU has remained above threshold",
            target="checkout-api",
            params={"replicas": 5},
        )

        contract = RecommendationContract.from_recommendation(rec)

        assert contract.action_type == "execute_fix"
        assert contract.action_id == "scale_instances"
        assert contract.target == "checkout-api"
        assert contract.params == {"replicas": 5}
        assert contract.reason == "CPU has remained above threshold"

    def test_legacy_view_preserves_current_consumers(self):
        from airex_core.schemas.recommendation_contract import ConfidenceBreakdown, RecommendationContract

        contract = RecommendationContract(
            action_type="execute_fix",
            action_id="restart_service",
            target="web-01",
            params={"service_name": "nginx"},
            reason="Service is unresponsive",
            confidence=0.83,
            risk="MED",
            root_cause="Runaway process",
            summary="Restart nginx on web-01",
            confidence_breakdown=ConfidenceBreakdown(
                model_confidence=0.83,
                evidence_strength_score=0.6,
                tool_grounding_score=0.7,
                kg_match_score=0.33,
                hallucination_penalty=0.0,
                composite_confidence=0.725,
            ),
            grounding_summary="3 evidence source(s) considered; grounding checks passed",
        )

        legacy = contract.to_legacy_recommendation()

        assert legacy["proposed_action"] == "restart_service"
        assert legacy["risk_level"] == "MED"
        assert legacy["confidence"] == 0.83
        assert legacy["params"] == {"service_name": "nginx"}
        assert legacy["summary"] == "Restart nginx on web-01"
        assert legacy["confidence_breakdown"]["composite_confidence"] == 0.725
        assert legacy["grounding_summary"] == "3 evidence source(s) considered; grounding checks passed"
