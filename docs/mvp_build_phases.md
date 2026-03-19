# AIREX — MVP-First Build Phases

> Companion to [openclaw_airex_architecture.md](./openclaw_airex_architecture.md).
> That doc defines the **target**. This doc defines **how to get there** — incrementally, proving value at each step.

## The Only Question That Matters

> "Will an SRE approve this in 5 seconds during an incident?"

Great architecture ≠ useful system. Useful system = **fast, predictable, trustworthy**.

---

## Phase 0 — Brutal MVP (No Overengineering)

**Goal**: Prove the flow works end-to-end with ONE incident type, ONE action, ONE execution path.

### Scope (everything else is banned)

| Element | Choice | Why |
|---------|--------|-----|
| Incident type | CPU spike | Most common, easiest to simulate |
| Action | `scale_deployment` | Already in Action Registry |
| Execution path | Kubernetes | Concrete, verifiable |
| Investigation | Hardcoded | No KG. No RAG. No swarm. |

### The Flow

```
High CPU alert → investigate (hardcoded) → recommend scale → approval → execute → verify
```

### Investigation Logic (Phase 0)

```python
# No AI. No agents. Just this:
if cpu > 90%:
    evidence = "CPU sustained above 90% for 5 minutes"
    recommend = scale_deployment(replicas=5)
```

### What You're Testing (nothing else matters)

| # | Metric | Fail Condition |
|---|--------|----------------|
| 1 | ⏱ **Approval time** | > 30 seconds → trust problem |
| 2 | 🎯 **Recommendation correctness** | Wrong fix suggested → useless |
| 3 | 🛠 **Execution worked** | Didn't fix it → system is useless |

### Deliverables

- [ ] Hardcoded investigation path for CPU spike
- [ ] `scale_deployment` action wired to k8s
- [ ] Approval UI shows recommendation with clear context
- [ ] Execute → verify → RESOLVED in < 2 minutes
- [ ] Measure all 3 metrics above

### What You're NOT Building Yet

❌ Knowledge Graph · ❌ RAG · ❌ OpenClaw / swarm · ❌ Confidence validator · ❌ Proactive monitor · ❌ Approval SLA · ❌ Execution plan snapshots

---

## Phase 1 — Three More Incident Types

**Gate**: Phase 0 metrics pass. SRE trusts the CPU spike flow.

**Goal**: Prove the pattern generalizes. Still hardcoded logic, no AI.

| Incident Type | Action | Execution Path |
|---------------|--------|----------------|
| Memory high | `restart_service` | Kubernetes |
| Disk full | `clear_logs` | SSM/SSH |
| Pod crash loop | `rollback_deployment` | Kubernetes |

### What Changes

```python
# probe_map.py becomes a simple router:
PLAYBOOKS = {
    "cpu_high":        ("scale_deployment",    {"replicas": 5}),
    "memory_high":     ("restart_service",     {"service": target}),
    "disk_full":       ("clear_logs",          {"path": "/var/log", "older_than": "7d"}),
    "crash_loop":      ("rollback_deployment", {"revisions": 1}),
}
```

### Success Criteria

- [ ] All 4 incident types flow end-to-end
- [ ] Approval time stays < 30 seconds
- [ ] Execution success rate > 80%
- [ ] SRE feedback: "I'd use this at 3am"

---

## Phase 2 — Smart Recommendations (Add LLM)

**Gate**: Phase 1 works. Hardcoded playbooks feel limiting.

**Goal**: Replace hardcoded `if/else` with LLM-generated recommendations. Keep investigation static.

### What Changes

| Before | After |
|--------|-------|
| `if cpu > 90%: scale to 5` | LLM reads evidence → proposes action from registry |
| Fixed params | LLM picks params (bounded by action definitions) |
| One recommendation | LLM explains reasoning |

### Architecture

```
Static probes (unchanged) → Evidence
    → LiteLLM → Recommendation (action_id from registry + params + reasoning)
    → Policy check → AWAITING_APPROVAL
```

### Safety Rails (add these NOW, not later)

Recommendation MUST produce the **Recommendation Contract** from the architecture doc:

```python
{
    "action_id": "scale_deployment",     # MUST exist in ACTION_REGISTRY
    "params": {"replicas": 5},           # MUST be within bounds
    "reason": "CPU >90% for 5 min",      # MUST be human-readable
    "confidence": 0.91,                  # For display, not auto-decision
    "risk": "LOW"                        # LOW / MEDIUM / HIGH / CRITICAL
}
```

Action bounds (enforced, not advisory):

```yaml
action_bounds:
  scale_deployment:
    max_replicas: 20
    min_replicas: 1
  restart_service:
    cooldown: 5m
  delete_pod:
    environments: [staging, dev]  # blocked in prod
```

### Success Criteria

- [ ] LLM picks correct action from registry >90% of the time
- [ ] Invalid action_id → rejected before approval screen
- [ ] Params within bounds → enforced
- [ ] Approval time unchanged (SRE trusts LLM reasoning display)

---

## Phase 3 — Execution Safety Hardening

**Gate**: Phase 2 works. You're executing in staging. Now harden for prod.

**Goal**: Make execution bulletproof. This is the "never run the wrong thing" phase.

> References: Execution Safety Rules, Execution Context, Execution Plan Snapshot sections in [architecture doc](./openclaw_airex_architecture.md).

### Add These (All Independent, Ship Incrementally)

#### 3a. Execution Context Resolver

```
Recommendation target "checkout-api"
    → resolve: cluster=prod-cluster-1, namespace=payments, mode=k8s-api
    → validate: target actually exists in infra
    → fail fast if not found
```

#### 3b. Idempotency Protection

```python
execution_hash = hash(incident_id + action_id + params)
# Already ran with status != FAILED? → reject duplicate
```

#### 3c. Action Scoping (Multi-Tenant Safety)

```
Every execution must include:
  tenant_id   → from incident
  project_id  → from incident
  environment → from context resolver
# Missing any? → reject
```

#### 3d. Execution Plan Snapshot

```python
# AFTER approval, BEFORE execution — freeze everything:
snapshot = {
    "incident_id": "123",
    "approved_by": "rohit",
    "action_id": "scale_deployment",
    "params": {"replicas": 5},
    "resolved_context": {"cluster": "prod-cluster-1", "namespace": "payments"},
    "snapshot_hash": "sha256:abc123..."
}
# Execution reads ONLY from snapshot, never from live recommendation
# Prevents approval drift
```

### Success Criteria

- [ ] Can't execute against wrong cluster
- [ ] Can't execute same action twice
- [ ] Can't execute across tenant boundaries
- [ ] Audit trail shows exactly what was approved vs executed
- [ ] All above adds < 500ms to execution path

---

## Phase 4 — Knowledge Graph + RAG

**Gate**: Phase 3 is in prod. Execution is safe. NOW add intelligence.

**Goal**: System learns from past incidents. Recommendations improve over time.

> References: Knowledge Graph Schema, Knowledge Graph Service sections in [architecture doc](./openclaw_airex_architecture.md).

### What to Build

```
Knowledge Graph (pgvector + Redis):
  Nodes: services, pods, metrics, configs, incidents, runbooks
  Edges: calls, depends_on, caused_by, resolved_by

Writers:
  - Investigation probes → write findings
  - verify_resolution_task → write outcomes ("what worked")

Readers:
  - generate_recommendation_task → "show me similar past incidents"
  - RAG context → enrich LLM prompt with historical resolutions
```

### This Is Where RAG Plugs In

```
Before (Phase 2):  Evidence → LLM → Recommendation
After  (Phase 4):  Evidence + KG context (similar incidents, runbooks) → LLM → Recommendation
```

### Success Criteria

- [ ] After 20+ resolved incidents, recommendation accuracy measurably improves
- [ ] KG query adds < 200ms to recommendation generation
- [ ] "what_worked" edges enable self-improving suggestions

---

## Phase 5 — Dynamic Investigation (OpenClaw or Enhanced Probes)

**Gate**: Phase 4 KG exists. Static probes feel limiting for complex incidents.

**Goal**: Investigation adapts to what it finds. Two paths — choose one.

> References: InvestigationBridge, Component Map, Evidence Contract sections in [architecture doc](./openclaw_airex_architecture.md).

### Path A: OpenClaw Integration

```
InvestigationBridge:
  - Calls OpenClaw gateway
  - Researcher agent: SSH/logs/metrics/k8s (dynamic exploration)
  - Validator agent: cross-check findings, hallucination detection
  - Returns structured Evidence (same contract as static probes)
  - Fallback: if OpenClaw down → static probes (Phase 0-1 code)
```

### Path B: Enhanced Static Probes (No OpenClaw)

```
Smart probe chaining:
  - Probe 1 finds high CPU → triggers Probe 2 (check recent deploys)
  - Probe 2 finds deploy 10min ago → triggers Probe 3 (compare metrics pre/post)
  - Chain produces richer evidence without multi-agent framework
```

### Either Path Produces Same Output

```json
{
  "summary": "CPU spike caused by memory leak in checkout-api after deploy v2.3.1",
  "signals": ["cpu >90%", "deploy 10min ago", "memory growing linearly"],
  "root_cause": "Memory leak in checkout-api v2.3.1",
  "confidence": 0.87
}
```

### Success Criteria

- [ ] Investigation finds root cause (not just symptom) >70% of time
- [ ] Evidence quality measurably improves vs static probes
- [ ] Fallback to static probes works when dynamic path fails

---

## Phase 6 — Operational Polish

**Gate**: Phases 0-5 in prod. System is useful. Now make it reliable.

**Goal**: Production hardening for real incident response teams.

> References: Approval SLA, Confidence Validator, Proactive Monitor, Retry Policy sections in [architecture doc](./openclaw_airex_architecture.md).

### Add Incrementally (Each Is Independent)

| Feature | What | Why |
|---------|------|-----|
| **Approval SLA** | Critical: 2min, High: 5min, Medium: 15min → auto-escalate | Incidents stall without this |
| **Confidence Validator** | Check recommendation against KG entities, flag hallucinations | Trust signal for SRE |
| **Proactive Monitor** | Cron scans infra → creates incidents BEFORE alerts fire | Prevent > react |
| **Retry Policy** | Transient: retry 2x. Non-transient: re-investigate | Don't give up on API timeouts |
| **Reviewer Agent** | HIGH risk only: second LLM opinion shown in approval UI | Extra safety for dangerous actions |

---

## Phase Progression Mental Model

```
Phase 0-1:  Can this thing work at all?         → FLOW
Phase 2:    Can AI pick the right action?        → INTELLIGENCE
Phase 3:    Can we trust it in prod?             → SAFETY
Phase 4:    Can it learn from the past?          → MEMORY
Phase 5:    Can it investigate dynamically?       → AUTONOMY
Phase 6:    Can an SRE rely on it at 3am?         → RELIABILITY
```

---

## Current Status (What Already Exists)

| Phase | Status | What's Built |
|-------|--------|-------------|
| **0** | ✅ ~90% | `cpu_high.py` probe, `scale_instances` action, state machine, approval flow, ARQ pipeline |
| **1** | ✅ ~90% | `memory_high.py`, `disk_full.py`, `network_check.py` + 12 more probes, 13 actions |
| **2** | ✅ ~80% | LiteLLM generates recommendations, `recommendation_service.py`, `rag_context.py` |
| **3** | ❌ Not started | No execution context resolver, no idempotency, no snapshots, no action scoping |
| **4** | ❌ Not started | pgvector exists for embeddings but no KG entity model |
| **5** | ❌ Not started | Static probes only, no dynamic investigation |
| **6** | ❌ Not started | No SLA, no proactive monitor, no confidence validator |

**→ Start work at Phase 3 (Execution Safety).**
