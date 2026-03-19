"""Tests for dynamic probe chainer — Phase 5 Dynamic Investigation."""

import pytest

from airex_core.investigations.base import ProbeCategory, ProbeResult
from airex_core.investigations.probe_chainer import (
    CHAIN_RULES,
    ChainRule,
    get_chained_probes,
)


def _make_probe(category: ProbeCategory, metrics: dict) -> ProbeResult:
    return ProbeResult(
        tool_name="test_probe",
        raw_output="",
        category=category,
        metrics=metrics,
    )


class TestChainRuleDataclass:
    def test_frozen(self):
        rule = CHAIN_RULES[0]
        with pytest.raises((AttributeError, TypeError)):
            rule.trigger_metric = "changed"  # type: ignore[misc]

    def test_all_rules_have_nonempty_fields(self):
        for rule in CHAIN_RULES:
            assert rule.trigger_metric
            assert rule.follow_up_probe
            assert rule.reason
            assert rule.trigger_threshold >= 0


class TestGetChainedProbes:
    def test_empty_results_returns_nothing(self):
        assert get_chained_probes([], set()) == []

    def test_non_probe_result_skipped(self):
        from airex_core.investigations.base import InvestigationResult

        non_probe = InvestigationResult(tool_name="x", raw_output="y")
        result = get_chained_probes([non_probe], set())  # type: ignore[list-item]
        assert result == []

    def test_high_cpu_triggers_change_detection(self):
        probe = _make_probe(ProbeCategory.SYSTEM, {"cpu_percent": 85.0})
        results = get_chained_probes([probe], set())
        probe_types = [r[0] for r in results]
        assert "change_detection" in probe_types

    def test_cpu_at_exact_threshold_triggers(self):
        probe = _make_probe(ProbeCategory.SYSTEM, {"cpu_percent": 80.0})
        results = get_chained_probes([probe], set())
        assert any(r[0] == "change_detection" for r in results)

    def test_cpu_below_threshold_no_trigger(self):
        probe = _make_probe(ProbeCategory.SYSTEM, {"cpu_percent": 79.9})
        results = get_chained_probes([probe], set())
        assert not any(r[0] == "change_detection" for r in results)

    def test_high_memory_triggers_log_analysis(self):
        probe = _make_probe(ProbeCategory.SYSTEM, {"memory_percent": 90.0})
        results = get_chained_probes([probe], set())
        assert any(r[0] == "log_analysis" for r in results)

    def test_memory_below_threshold_no_trigger(self):
        probe = _make_probe(ProbeCategory.SYSTEM, {"memory_percent": 84.9})
        results = get_chained_probes([probe], set())
        assert not any(r[0] == "log_analysis" for r in results)

    def test_high_error_rate_triggers_infra_state(self):
        probe = _make_probe(ProbeCategory.APPLICATION, {"error_rate": 0.10})
        results = get_chained_probes([probe], set())
        assert any(r[0] == "infra_state" for r in results)

    def test_error_rate_below_threshold_no_trigger(self):
        probe = _make_probe(ProbeCategory.APPLICATION, {"error_rate": 0.04})
        results = get_chained_probes([probe], set())
        assert not any(r[0] == "infra_state" for r in results)

    def test_critical_disk_triggers_log_analysis(self):
        probe = _make_probe(ProbeCategory.SYSTEM, {"disk_percent": 95.0})
        results = get_chained_probes([probe], set())
        assert any(r[0] == "log_analysis" for r in results)

    def test_already_running_prevents_duplicate(self):
        probe = _make_probe(ProbeCategory.SYSTEM, {"cpu_percent": 90.0})
        results = get_chained_probes([probe], {"change_detection"})
        assert not any(r[0] == "change_detection" for r in results)

    def test_each_probe_type_triggered_once(self):
        """Two probes both triggering log_analysis should only produce one entry."""
        probe1 = _make_probe(ProbeCategory.SYSTEM, {"memory_percent": 90.0})
        probe2 = _make_probe(ProbeCategory.SYSTEM, {"disk_percent": 95.0})
        results = get_chained_probes([probe1, probe2], set())
        log_analysis_hits = [r for r in results if r[0] == "log_analysis"]
        assert len(log_analysis_hits) == 1

    def test_multiple_probes_trigger_different_followups(self):
        probe1 = _make_probe(ProbeCategory.SYSTEM, {"cpu_percent": 90.0})
        probe2 = _make_probe(ProbeCategory.APPLICATION, {"error_rate": 0.10})
        results = get_chained_probes([probe1, probe2], set())
        probe_types = {r[0] for r in results}
        assert "change_detection" in probe_types
        assert "infra_state" in probe_types

    def test_result_includes_reason_string(self):
        probe = _make_probe(ProbeCategory.SYSTEM, {"cpu_percent": 85.0})
        results = get_chained_probes([probe], set())
        for probe_type, reason in results:
            assert isinstance(reason, str)
            assert len(reason) > 0

    def test_wrong_category_no_trigger(self):
        """A NETWORK probe with cpu_percent should not trigger SYSTEM rule."""
        probe = _make_probe(ProbeCategory.NETWORK, {"cpu_percent": 99.0})
        results = get_chained_probes([probe], set())
        assert not any(r[0] == "change_detection" for r in results)

    def test_missing_metric_no_trigger(self):
        probe = _make_probe(ProbeCategory.SYSTEM, {"latency_ms": 5000.0})
        results = get_chained_probes([probe], set())
        assert results == []

    def test_non_numeric_metric_does_not_crash(self):
        probe = _make_probe(ProbeCategory.SYSTEM, {"cpu_percent": "not_a_number"})
        results = get_chained_probes([probe], set())
        assert not any(r[0] == "change_detection" for r in results)

    def test_returns_list_of_tuples(self):
        probe = _make_probe(ProbeCategory.SYSTEM, {"cpu_percent": 90.0})
        results = get_chained_probes([probe], set())
        assert isinstance(results, list)
        for item in results:
            assert isinstance(item, tuple)
            assert len(item) == 2
