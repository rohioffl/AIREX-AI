---
name: airex-investigation
description: Core AIREX investigation workflow, evidence contract rules, and safety boundaries.
---

Use AIREX tools to gather machine evidence before making claims.

Rules:
- Treat `run_host_diagnostics`, `fetch_log_analysis`, `fetch_change_context`, and `fetch_infra_state` as primary evidence tools.
- Read `read_incident_context` before investigating when incident history or pattern context may matter.
- Write final structured findings with `write_evidence_contract` only after evidence is grounded.
- Output entities in canonical form such as `service:name`, `host:name`, `instance:id`, `process:cmd`, or `pod:name`.
- Keep summaries concrete and avoid placeholders like `unknown`, `pending investigation`, or `requires further investigation` when tools already returned facts.
- Never perform remediation or destructive actions from investigation skills.
