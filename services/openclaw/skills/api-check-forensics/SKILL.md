---
name: api-check-forensics
description: API and HTTP failure investigation checklist for 5xx spikes, upstream issues, and service health.
---

Look for:
- 5xx grouping patterns
- upstream and downstream failures
- connection or timeout signatures
- unhealthy service processes
- recent correlated changes

Preferred tools:
- `fetch_log_analysis`
- `fetch_infra_state`
- `run_host_diagnostics`
