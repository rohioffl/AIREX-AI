---
name: cpu-forensics
description: CPU saturation investigation checklist for host- and process-level incidents.
---

Look for:
- overall CPU usage
- load average
- hottest PID / command
- throttling, rate limiting, or GC patterns
- correlation with recent deploys or config changes

Preferred tools:
- `run_host_diagnostics`
- `fetch_log_analysis`
- `fetch_change_context`
