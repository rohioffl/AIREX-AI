---
name: server-down-forensics
description: Host unavailable investigation checklist for reachability, systemd, kernel, and change correlation.
---

Look for:
- instance health and reachability
- systemd failures
- kernel panic or OOM
- disk or network faults
- recent deploy, reboot, scaling, or infra changes

Preferred tools:
- `fetch_infra_state`
- `run_host_diagnostics`
- `fetch_log_analysis`
- `fetch_change_context`
