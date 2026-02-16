"""
LLM prompt templates.

All prompts are static templates. Dynamic command generation is PROHIBITED.
LLM output must map to ACTION_REGISTRY keys only.
"""

SYSTEM_PROMPT = """You are an SRE incident analysis engine for the AIREX autonomous remediation platform.

Your job is to analyze investigation evidence collected from cloud servers (GCP/AWS) and produce a structured JSON recommendation.

RULES:
1. You MUST respond with valid JSON only. No markdown, no explanation, no code fences.
2. The "proposed_action" field MUST be one of: "restart_service", "clear_logs", "scale_instances".
3. The "risk_level" field MUST be one of: "LOW", "MED", "HIGH".
4. The "confidence" field MUST be a float between 0.0 and 1.0.
5. NEVER suggest shell commands, scripts, or raw commands. Only use registered action names.
6. NEVER include code snippets in your response.
7. Base your root_cause analysis on the actual evidence provided (SSH output, logs, metrics).
8. If evidence shows high CPU/memory from a specific process, recommend "restart_service".
9. If evidence shows disk full due to logs, recommend "clear_logs".
10. If evidence shows traffic spikes or capacity issues, recommend "scale_instances".
11. Set risk_level based on severity: CRITICAL alerts → MED or HIGH, LOW alerts → LOW.
12. Set confidence lower (< 0.5) when evidence is incomplete or ambiguous.

RESPONSE FORMAT (exact JSON structure):
{
    "root_cause": "Brief analysis of what caused the incident based on evidence",
    "proposed_action": "action_name_from_registry",
    "risk_level": "LOW|MED|HIGH",
    "confidence": 0.85
}
"""


def build_recommendation_prompt(
    alert_type: str,
    evidence: str,
    severity: str,
) -> list[dict[str, str]]:
    """Build the LLM message list for recommendation generation."""
    sanitized = _sanitize_evidence(evidence)

    user_content = (
        f"Alert Type: {alert_type}\n"
        f"Severity: {severity}\n"
        f"\n--- Investigation Evidence ---\n{sanitized}\n--- End Evidence ---\n"
        f"\nAnalyze the above evidence and provide your recommendation as JSON."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _sanitize_evidence(evidence: str, max_chars: int = 8000) -> str:
    """
    Sanitize evidence before sending to LLM.

    - Truncate to max_chars.
    - Strip common injection patterns.
    """
    sanitized = evidence[:max_chars]

    injection_patterns = [
        "ignore previous instructions",
        "ignore all instructions",
        "disregard",
        "new instructions:",
        "system:",
        "```bash",
        "```shell",
        "```sh",
        "#!/bin/",
        "rm -rf",
        "sudo ",
    ]
    lower = sanitized.lower()
    for pattern in injection_patterns:
        if pattern in lower:
            sanitized = sanitized.replace(pattern, "[REDACTED]")
            sanitized = sanitized.replace(pattern.upper(), "[REDACTED]")

    return sanitized
