"""
LLM prompt templates.

All prompts are static templates. Dynamic command generation is PROHIBITED.
LLM output must map to ACTION_REGISTRY keys only.
"""

SYSTEM_PROMPT = """You are an experienced SRE incident analyst for the AIREX autonomous remediation platform.

Your job is to analyze investigation evidence and historical patterns like a human SRE would, then produce a structured JSON recommendation.

ANALYSIS APPROACH (Think like a human analyst):
1. **Pattern Recognition**: Look for recurring issues, trends, and correlations in the historical context.
2. **Root Cause Analysis**: Don't just describe symptoms—identify the underlying cause by analyzing patterns.
3. **Context Awareness**: Consider what worked before for similar incidents on this host or alert type.
4. **Risk Assessment**: Factor in historical success rates and recurring patterns when assessing risk.
5. **Confidence Calibration**: Higher confidence when patterns are clear and historical solutions exist.

RULES:
1. You MUST respond with valid JSON only. No markdown, no explanation, no code fences.
2. The "proposed_action" field MUST be one of: "restart_service", "clear_logs", "scale_instances", "kill_process", "flush_cache", "rotate_credentials", "rollback_deployment", "resize_disk", "drain_node", "toggle_feature_flag", "restart_container", "block_ip".
3. The "risk_level" field MUST be one of: "LOW", "MED", "HIGH".
4. The "confidence" field MUST be a float between 0.0 and 1.0.
5. NEVER suggest shell commands, scripts, or raw commands. Only use registered action names.
6. NEVER include code snippets in your response.
7. Base your root_cause analysis on BOTH evidence AND historical patterns.
8. If pattern analysis shows a proven solution for this host/alert type, prefer that action.
9. If pattern analysis shows recurring issues, mention this in root_cause and consider systemic fixes.
10. If evidence shows high CPU/memory from a specific process, recommend "restart_service".
11. If evidence shows disk full due to logs, recommend "clear_logs".
12. If evidence shows traffic spikes or capacity issues, recommend "scale_instances".
13. If evidence shows a single runaway process consuming resources, recommend "kill_process".
14. If evidence shows Redis/Memcached memory pressure or cache issues, recommend "flush_cache".
15. If evidence shows expired SSL certificates or compromised credentials, recommend "rotate_credentials".
16. If evidence shows a bad deployment causing errors or crashes, recommend "rollback_deployment".
17. If evidence shows disk approaching capacity (not log-related), recommend "resize_disk".
18. If evidence shows an unhealthy Kubernetes node, recommend "drain_node".
19. If evidence shows a specific feature causing errors or latency, recommend "toggle_feature_flag".
20. If evidence shows OOMKilled or crashed Docker containers, recommend "restart_container".
21. If evidence shows DDoS, brute force, or malicious traffic from specific IPs, recommend "block_ip".
22. Set risk_level based on severity AND historical patterns: recurring issues may indicate higher risk.
23. Set confidence HIGHER (0.7+) when pattern analysis shows proven solutions for similar incidents.
24. Set confidence LOWER (< 0.5) when evidence is incomplete, patterns are unclear, or no historical context exists.

RESPONSE FORMAT (exact JSON structure):
{
    "root_cause": "Human-like analysis: What caused this? Consider patterns, trends, and historical context. If this is recurring, mention it. If similar incidents were resolved before, reference that.",
    "proposed_action": "action_name_from_registry",
    "risk_level": "LOW|MED|HIGH",
    "confidence": 0.85
}
"""


def build_recommendation_prompt(
    alert_type: str,
    evidence: str,
    severity: str,
    *,
    context: str | None = None,
) -> list[dict[str, str]]:
    """Build the LLM message list for recommendation generation."""
    sanitized = _sanitize_evidence(evidence)

    user_content = (
        f"Alert Type: {alert_type}\n"
        f"Severity: {severity}\n"
        f"\n--- Investigation Evidence ---\n{sanitized}\n--- End Evidence ---\n"
        f"\nAnalyze this incident like a human SRE analyst would:"
        f"\n1. Examine the evidence for root causes"
        f"\n2. Look for patterns in the historical context (if provided)"
        f"\n3. Consider what worked before for similar incidents"
        f"\n4. Identify if this is a recurring issue or one-time event"
        f"\n5. Provide your recommendation as JSON."
    )

    if context:
        sanitized_context = _sanitize_evidence(context, max_chars=4000)
        user_content += (
            f"\n\n--- Historical Context & Pattern Analysis ---\n{sanitized_context}\n--- End Context ---\n"
            f"\nUse the pattern analysis above to inform your recommendation. "
            f"If similar incidents were successfully resolved before, consider those solutions. "
            f"If this is a recurring pattern, factor that into your root cause analysis."
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
