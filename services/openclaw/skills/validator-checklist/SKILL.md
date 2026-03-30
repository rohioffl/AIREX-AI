---
name: validator-checklist
description: Grounding and confidence checklist for validating OpenClaw evidence before it is accepted.
---

Validation rules:
- Reject vague summaries when concrete tool output exists.
- Prefer exact host, process, pod, service, and instance identifiers.
- Lower confidence when diagnostics are missing or contradictory.
- Keep `confidence` within `0.0` to `1.0`.
- Ensure `signals` are short factual observations, not speculation.
