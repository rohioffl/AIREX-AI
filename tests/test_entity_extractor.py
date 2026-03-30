from airex_core.core.entity_extractor import (
    entities_need_grounding,
    extract_probe_findings,
    extract_reference_snippet,
    needs_grounding,
)


def test_extract_probe_findings_parses_process_host_and_signals():
    findings = extract_probe_findings(
        "=== CPU Investigation: checkout-api-01 ===\n"
        "Overall CPU Usage: 96.2%\n"
        "Load Average (1m/5m/15m): 4.8 / 4.2 / 3.1\n"
        "Diagnosis: High CPU driven by PID 1272 (java -jar checkout.jar)\n"
        "Top pattern: rate limited requests\n"
        "First error: timeout on upstream connection\n"
    )

    assert findings["summary"] == "CPU Investigation: checkout-api-01"
    assert findings["diagnosis"] == "High CPU driven by PID 1272 (java -jar checkout.jar)"
    assert "top_process_pid=1272" in findings["signals"]
    assert "log_pattern=rate limited requests" in findings["signals"]
    assert "process:java -jar checkout.jar".lower() in findings["affected_entities"]
    assert "host:checkout-api-01" in findings["affected_entities"]


def test_extract_reference_snippet_prefers_diagnosis():
    snippet = extract_reference_snippet(
        "=== CPU Investigation: checkout-api-01 ===\n"
        "Diagnosis: High CPU driven by PID 1272 (java -jar checkout.jar)\n"
    )

    assert snippet == "Diagnosis: High CPU driven by PID 1272 (java -jar checkout.jar)"


def test_needs_grounding_flags_generic_text():
    assert needs_grounding("Pending investigation.") is True
    assert needs_grounding("CPU Investigation: checkout-api-01") is False


def test_entities_need_grounding_prefers_concrete_forensics():
    assert entities_need_grounding(
        ["service:checkout"],
        ["process:java -jar checkout.jar"],
    ) is True
    assert entities_need_grounding(
        ["host:checkout-api-01"],
        ["process:java -jar checkout.jar"],
    ) is False
