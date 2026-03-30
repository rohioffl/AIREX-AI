---
name: k8s-forensics
description: Kubernetes investigation guidance for pods, rollouts, restarts, and resource pressure.
---

Use this skill when the incident targets pods, deployments, or cluster-managed services.

Look for:
- pod readiness and restart count
- rollout history
- resource saturation
- node or namespace health
- container log patterns

Current limitation:
- dedicated Kubernetes tools are not implemented yet in AIREX, so use existing diagnostics and logs as fallback context.
