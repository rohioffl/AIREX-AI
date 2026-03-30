---
name: controller-routing
description: Controller workflow for selecting tools, routing alert types, and compiling the final evidence contract.
---

Controller flow:
1. Call `read_incident_context` for the incident.
2. Identify the alert type and select the matching forensic skill pack.
3. Gather the minimum useful tools first.
4. Prefer researcher-style evidence gathering before synthesis.
5. When findings are concrete, compile a normalized evidence contract.
6. Persist the final contract with `write_evidence_contract` if the workflow requires tool-based persistence.

Routing:
- `cpu_high`: `run_host_diagnostics`, `fetch_log_analysis`, `fetch_change_context`
- `memory_high`: `run_host_diagnostics`, `fetch_log_analysis`, `fetch_change_context`
- `disk_full`: `run_host_diagnostics`, `fetch_log_analysis`
- `server_down`: `fetch_infra_state`, `run_host_diagnostics`, `fetch_log_analysis`, `fetch_change_context`
- `api_check` / `http_check`: `fetch_log_analysis`, `fetch_infra_state`, `run_host_diagnostics`
