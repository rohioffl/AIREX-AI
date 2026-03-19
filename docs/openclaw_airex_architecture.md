# AIREX + OpenClaw Integration Architecture

## Vision

Replace AIREX's static investigation plugins with a dynamic OpenClaw multi-agent swarm,
while keeping AIREX's state machine, action registry, approval flow, and audit trail intact.
The result is a Cleric-class AI SRE: dynamic investigation + safe deterministic execution.

### Autonomy Model

| Phase | Autonomy |
|-------|----------|
| Investigation | ✅ Fully autonomous (OpenClaw swarm) |
| Recommendation | ✅ Autonomous (LiteLLM + RAG + validator) |
| Execution | 🔒 **Always requires human approval** — no auto-approve path exists |

---

## Current vs Target Architecture

### Current (Static)

```
Webhook → Incident (RECEIVED)
  → ARQ: investigate() → fixed plugin script → Evidence
  → ARQ: generate_recommendation() → LiteLLM → Recommendation
  → Policy check → AWAITING_APPROVAL (always — execution requires human approval)
  → ARQ: execute_action_task() → SSM/SSH
  → ARQ: verify_resolution_task()
  → RESOLVED
```

### Target (Dynamic Multi-Agent)

```
Webhook → Incident (RECEIVED)
  → ARQ: investigate() → OpenClaw Investigation → Evidence
      ├── researcher agent  (SSH/logs/metrics/k8s)
      └── validator agent   (cross-check findings)
  → Evidence Aggregator → structured Evidence + Knowledge Graph update
  → ARQ: generate_recommendation() → LiteLLM + RAG (Knowledge Graph) → Recommendation
  → validator agent → trust signals for human review
  → Policy check → AWAITING_APPROVAL (always — execution requires human approval)
  → reviewer agent (HIGH risk only) → adds second opinion (non-blocking, shown in approval UI)
  → Execution Context Resolver → resolve target infra details
  → Pre-Execution Validation → param bounds + environment guards
  → Execution Plan Snapshot → freeze approved plan (immutable audit record)
  → ARQ: execute_action_task() → SSM / K8s / APIs (AIREX owns this - unchanged)
  → ARQ: verify_resolution_task()
  → RESOLVED → Knowledge Graph updated with outcome
  → FAILED  → retry (transient) or re-investigate with failure context
```

---

## Component Map

```
┌─────────────────────────────────────────────────────────────────┐
│                          AIREX CORE                              │
│                                                                   │
│  Webhook → State Machine → ARQ Tasks                             │
│    ├── investigate_task                                          │
│    │       └── InvestigationBridge → OpenClaw                    │
│    │                                                             │
│    ├── generate_recommendation_task                              │
│    │       └── LiteLLM + RAG (Knowledge Graph)                   │
│    │                                                             │
│    ├── (STATE) RECOMMENDATION_READY                              │
│    │                                                             │
│    ├── AWAITING_APPROVAL  ← 🔒 HUMAN GATE (MANDATORY, SLA-bound)│
│    │                                                             │
│    ├── execute_action_task  (AIREX ONLY)                         │
│    │       ├── Execution Context Resolver → target resolution    │
│    │       ├── Pre-Execution Validation → param bounds check     │
│    │       ├── Execution Plan Snapshot → immutable audit record  │
│    │       ├── Idempotency check (incident + action_id hash)     │
│    │       ├── Action Scoping (tenant + project + environment)   │
│    │       └── Action Registry → SSM / K8s / APIs                │
│    │                                                             │
│    └── verify_resolution_task                                    │
│            ├── success → RESOLVED                                │
│            └── failure → retry (transient) or re-investigate     │
│                                                                   │
│  Action Registry | Approval RBAC | Audit Trail (immutable)       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ HTTP (InvestigationBridge)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     OPENCLAW GATEWAY                             │
│                                                                   │
│  Controller Agent (orchestrator)                                 │
│     ├── Researcher Agent                                        │
│     │     - logs / metrics / k8s / SSH                           │
│     │                                                           │
│     ├── Validator Agent                                         │
│     │     - grounding check                                     │
│     │     - hallucination detection                             │
│     │     - confidence signals                                  │
│     │                                                           │
│     └── Reviewer Agent (HIGH risk only)                         │
│           - second opinion (non-blocking insight)               │
│                                                                   │
│                     MCP TOOL LAYER                               │
│                                                                   │
│  SSH │ Docker │ Terraform │ Filesystem │ Metrics                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE GRAPH                               │
│                                                                   │
│  Storage: pgvector + Redis                                       │
│                                                                   │
│  Nodes: services, pods, metrics, configs, incidents, runbooks    │
│  Edges: depends_on, calls, caused_by, resolved_by, deployed_by   │
│                                                                   │
│  Writers:                                                        │
│    - Researcher Agent (investigation)                            │
│    - verify_resolution_task (feedback loop)                      │
│    - Monitor System (background, NOT per-incident)               │
└─────────────────────────────────────────────────────────────────┘
```

---

## System Contracts

### Evidence Contract (MANDATORY)

The structured output from OpenClaw that `InvestigationBridge._parse_evidence()` must produce.
Without this, OpenClaw ↔ AIREX cannot integrate.

```json
{
  "summary": "string — human-readable investigation summary",
  "signals": ["string — individual findings from investigation"],
  "root_cause": "string — best-guess root cause",
  "affected_entities": ["service:checkout-api", "pod:checkout-api-7f8b9c-x2k"],
  "confidence": 0.0,
  "raw_refs": {}
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `summary` | string | ✅ | One-paragraph investigation summary |
| `signals` | string[] | ✅ | Individual evidence signals collected |
| `root_cause` | string | ✅ | Best-guess root cause from evidence |
| `affected_entities` | string[] | ✅ | Entity refs in `type:name` format |
| `confidence` | float | ✅ | 0.0–1.0 evidence quality score |
| `raw_refs` | object | ❌ | Raw tool outputs for audit trail |

### Recommendation Contract (MANDATORY)

The structured output from `generate_recommendation_task`. Core system contract between
recommendation engine and execution engine.

```json
{
  "action_type": "execute_fix",
  "action_id": "scale_deployment",
  "target": "checkout-api",
  "params": {
    "replicas": 5
  },
  "reason": "CPU > 90% for 5 minutes",
  "confidence": 0.91,
  "risk": "LOW"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action_type` | enum | ✅ | `execute_fix` / `observe_only` / `escalate` |
| `action_id` | string | ✅ | Action Registry key (must exist) |
| `target` | string | ✅ | Affected service/resource name |
| `params` | object | ✅ | Action-specific parameters |
| `reason` | string | ✅ | Human-readable justification |
| `confidence` | float | ✅ | 0.0–1.0 recommendation confidence |
| `risk` | enum | ✅ | `LOW` / `MEDIUM` / `HIGH` / `CRITICAL` |

### Execution Context (resolved at execution time)

Before execution, the Execution Context Resolver maps the recommendation target
to concrete infrastructure details. Without this: wrong cluster, missing namespace, unsafe assumptions.

```json
{
  "cluster": "prod-cluster-1",
  "namespace": "payments",
  "execution_mode": "k8s-api",
  "credentials_ref": "vault:prod/payments/k8s-token",
  "target_verified": true
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `cluster` | string | ✅ | Resolved cluster name |
| `namespace` | string | ✅ | Resolved namespace |
| `execution_mode` | enum | ✅ | `k8s-api` / `ssm` / `ssh` / `api-call` |
| `credentials_ref` | string | ✅ | Vault/secrets path for access |
| `target_verified` | bool | ✅ | Whether target exists in infra |

### Execution Plan Snapshot (Audit Safety)

Before execution, freeze the full execution plan into an immutable snapshot.
Prevents "approval drift" (what was approved vs what actually ran). Makes
audit/compliance and debugging trivial.

```json
{
  "incident_id": "123",
  "approved_by": "rohit",
  "approved_at": "2026-03-19T14:32:00Z",
  "action_id": "scale_deployment",
  "params": { "replicas": 5 },
  "resolved_context": {
    "cluster": "prod-cluster-1",
    "namespace": "payments",
    "execution_mode": "k8s-api"
  },
  "final_command": "kubectl scale deployment checkout-api --replicas=5",
  "snapshot_hash": "sha256:abc123..."
}
```

Rules:
- Snapshot is created AFTER approval, BEFORE execution
- Snapshot is immutable — written to audit trail
- `snapshot_hash` covers all fields — any tampering is detectable
- Execution engine reads ONLY from the snapshot, never from live recommendation

---

## Action Types

| Action Type | Description |
|-------------|-------------|
| `execute_fix` | Run a remediation action (requires approval) |
| `observe_only` | No action needed — monitor and wait |
| `escalate` | Escalate to human team — beyond automation scope |

---

## Execution Safety Rules

### Pre-Execution Validation Layer

After approval, before execution. Catches unsafe parameters that passed human review.

```
Approve → Validate → Snapshot → Execute

Validation checks:
  1. Target exists (via Execution Context Resolver)
  2. Params within safe bounds (per action definition)
  3. Action allowed in this environment (prod vs staging guards)
```

Example action bounds:

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

Prevents: cost explosions, accidental overload, prod-unsafe actions slipping through.

### Action Scoping (Multi-Tenant Safety)

Every action must be scoped to `tenant_id + project_id + environment`.
Without this, one tenant could affect another — massive security issue.

```
Action scope (enforced at execution time):
  tenant_id:    required — from incident ownership
  project_id:   required — from incident context
  environment:  required — from Execution Context Resolver

Validation:
  → Execution Context Resolver MUST return scope fields
  → Action Registry rejects any action missing scope
  → Audit trail records full scope per execution
```

Note: Current runtime uses DEV tenant `00000000-0000-0000-0000-000000000000`.
Scoping is enforced now so multi-tenant re-enablement requires zero execution-layer changes.

### Idempotency Protection

Execution must be idempotent per `incident_id + action_id`. If a user clicks approve twice,
or a retry fires, the system must not execute the same action again.

```
execution_hash = hash(incident_id + action_id + params)

Before execution:
  → Check execution_hash in audit trail
  → If exists and status != FAILED → reject duplicate
  → If exists and status == FAILED → allow retry (controlled)
```

### Retry Policy (Controlled)

Transient failures (API timeout, temporary network issue) get automatic retries.
Non-transient failures (target not found, permission denied) go to re-investigation.

```yaml
retry_policy:
  transient_errors:
    max_retries: 2
    backoff: exponential
    base_delay: 5s
  non_transient_errors:
    action: re_investigate
    include_failure_context: true
```

### Approval SLA + Escalation

Incidents stuck in AWAITING_APPROVAL will auto-escalate based on severity.
Without this, the system stalls during real incidents.

```yaml
approval_sla:
  critical: 2m
  high: 5m
  medium: 15m
  low: 30m
  on_timeout: escalate
  escalation_targets:
    - pagerduty_oncall
    - slack_channel: "#incident-response"
```

---

## New Components to Build

### 1. InvestigationBridge (AIREX side)

`services/airex-core/airex_core/core/investigation_bridge.py`

```python
class InvestigationBridge:
    """
    Replaces static plugin dispatch in investigate().
    Calls OpenClaw gateway to spawn investigation swarm.
    Returns structured Evidence compatible with Evidence Contract.
    """

    async def run(self, incident: Incident, timeout: int = 60) -> Evidence:
        payload = {
            "incident_id": str(incident.id),
            "alert_type": incident.alert_type,
            "alert_data": incident.raw_alert,
            "infrastructure_context": await self._fetch_kg_context(incident),
        }
        response = await self._call_openclaw(
            agent="controller",
            prompt=INVESTIGATION_PROMPT_TEMPLATE.format(**payload),
            timeout=timeout,
        )
        return self._parse_evidence(response)
```

Fallback: if OpenClaw is unreachable, fall back to existing static plugin.

---

### 2. Knowledge Graph Service

`services/airex-core/airex_core/core/knowledge_graph.py`

```python
class KnowledgeGraph:
    """
    Lightweight graph stored as pgvector embeddings + Redis adjacency cache.
    Nodes: infrastructure entities (services, pods, IPs, buckets, configs)
    Edges: relationships (calls, depends_on, caused_by, deployed_by)
    """

    async def upsert_node(self, entity: KGNode) -> None: ...
    async def add_edge(self, src: str, rel: str, dst: str) -> None: ...
    async def causal_walk(self, start_node: str, depth: int = 3) -> list[KGNode]: ...
    async def get_context_for_incident(self, alert_data: dict) -> str: ...
```

---

### 3. Execution Context Resolver

`services/airex-core/airex_core/core/execution_context_resolver.py`

```python
class ExecutionContextResolver:
    """
    Resolves recommendation target → concrete infrastructure details.
    Called BEFORE execution, AFTER approval.

    Resolves: service name → cluster, namespace, execution_mode, credentials.
    Validates: target actually exists in infrastructure.
    Fails fast: if target cannot be resolved, execution is blocked.
    """

    async def resolve(self, target: str, action_id: str) -> ExecutionContext: ...
    async def validate_target_exists(self, context: ExecutionContext) -> bool: ...
```

---

### 4. Monitor System → Proactive Incident Feed

`services/airex-core/airex_core/core/proactive_monitor.py`

```python
# Separate system — NOT part of per-incident investigation swarm.
# Runs on cron (every 5min via OpenClaw).
# Posts to AIREX /webhook/generic with source="proactive_monitor"
# Creates incidents BEFORE alerts fire.
```

---

### 5. Confidence Validator

`services/airex-core/airex_core/core/confidence_validator.py`

```python
class ConfidenceValidator:
    """
    Validates recommendation quality for human approval.

    Outputs:
      - hallucination flags
      - entity mismatches (vs Knowledge Graph)
      - evidence strength assessment
      - confidence explanation (human-readable)

    Does NOT control execution. Approval is always human.
    """
```

---

## Data Flow: Per-Incident Investigation

```
1. Incident created (RECEIVED)

2. investigate_task:
   → OpenClaw (researcher + validator)
   → Evidence generated (per Evidence Contract)
   → Knowledge Graph updated with findings
   → enqueue generate_recommendation_task

3. generate_recommendation_task:
   → RAG: query Knowledge Graph for similar past incidents + runbooks
   → LLM generates Recommendation (per Recommendation Contract)
   → validator adds trust signals (hallucination flags, entity checks)
   → reviewer (if HIGH risk) adds second opinion (non-blocking)
   → Transition → RECOMMENDATION_READY

4. Policy:
   → ALWAYS → AWAITING_APPROVAL
   → SLA timer starts (severity-based)
   → SLA breach → auto-escalate

5. Human approves

6. execute_action_task (AIREX ONLY):
   → Pre-Execution Validation (param bounds + environment guards)
   → Execution Context Resolver (target → cluster/namespace/creds)
   → Action Scoping check (tenant + project + environment)
   → Idempotency check (incident + action_id hash)
   → Execution Plan Snapshot (freeze approved plan → audit trail)
   → action_type: execute_fix → run remediation
   → action_type: observe_only → no-op, mark resolved
   → action_type: escalate → notify team, mark escalated

7. verify_resolution_task:
   → success → RESOLVED (Knowledge Graph updated with outcome)
   → transient failure → retry (max 2, exponential backoff)
   → non-transient failure → re-investigate with failure context (loop to step 2)
```

---

## Data Flow: Proactive Detection

```
Monitor System (separate from investigation, runs on cron every 5min):
  1. Scans infrastructure via MCP tools (k8s, metrics, cloud APIs)
  2. Updates Knowledge Graph with current state
  3. Infers anomalies:
     - Memory growing → will OOM in ~2h
     - S3 bucket public → data exposure
     - Pod restart loop → CrashLoopBackOff imminent
  4. POST /webhook/generic with source="proactive" + severity + prediction
  5. AIREX creates incident in RECEIVED state — normal pipeline from here
```

---

## Knowledge Graph Schema

```
Node types:
  - Service       { name, namespace, cluster, last_deployed }
  - Pod           { name, node, status, restart_count }
  - Metric        { name, labels, current_value, threshold }
  - Config        { resource_type, name, hash }
  - Incident      { id, alert_type, resolution, what_worked }
  - Runbook       { title, steps, applicable_alert_types }

Edge types:
  - calls         Service → Service
  - depends_on    Service → Service / Pod → Config
  - caused_by     Incident → Service / Config
  - resolved_by   Incident → Runbook / Action
  - deployed_by   Service → Pipeline
```

---

## What AIREX Keeps (Unchanged)

| Component | Status | Reason |
|-----------|--------|--------|
| State machine | Unchanged | Law — all lifecycle transitions |
| Action registry | Unchanged | Safety — LLM cannot invent commands |
| Approval RBAC | Unchanged | Security — human gate on ALL executions |
| Audit trail | Unchanged | Compliance — immutable hash chain |
| SSM/SSH execution | Unchanged | AIREX owns infra access |
| ARQ task queue | Unchanged | Reliability — retries, timeouts |
| LiteLLM proxy | Unchanged | Recommendation generation |

---

## What Changes

| Component | Change |
|-----------|--------|
| `investigate()` ARQ task | Calls InvestigationBridge instead of static plugin |
| `generate_recommendation()` | RAG enriched with Knowledge Graph context |
| `verify_resolution_task()` | Failure triggers retry or re-investigation loop |
| `execute_action_task()` | Validation + Context Resolver + Snapshot + Idempotency + Scoping |
| New: `Evidence Contract` | Structured OpenClaw → AIREX investigation output |
| New: `Recommendation Contract` | Structured recommendation → execution input |
| New: `Execution Plan Snapshot` | Immutable record of what was approved vs executed |
| New: `Pre-Execution Validation` | Param bounds + environment guards |
| New: `Action Scoping` | tenant_id + project_id + environment enforcement |
| New: `ExecutionContextResolver` | Target → cluster/namespace/creds resolution |
| New: `KnowledgeGraph` service | Persistent infra entity store |
| New: `InvestigationBridge` | OpenClaw gateway client |
| New: `ConfidenceValidator` | Recommendation quality signals for human review |
| New: `action_type` field | execute_fix / observe_only / escalate |
| New: Approval SLA | Severity-based timeout + auto-escalation |
| New: Idempotency protection | Duplicate execution prevention |
| New: Retry policy | Controlled retries for transient failures |
| New: Proactive monitor feed | Monitor System → /webhook/generic |
| Static plugins | Become fallback (not deleted) |

---

## Build Phases

### Phase 1 — Knowledge Graph (foundation)

- Schema + pgvector storage
- Redis adjacency cache
- Basic upsert/query API
- Seed from existing incidents

### Phase 2 — Contracts + InvestigationBridge

- Evidence Contract schema + parser
- Recommendation Contract schema
- OpenClaw gateway client in AIREX
- Fallback to static plugins on failure
- Timeout + circuit breaker

### Phase 3 — Execution Context Resolver + Safety

- Target resolution (service → cluster/namespace/creds)
- Target existence validation
- Pre-Execution Validation (param bounds + environment guards)
- Execution Plan Snapshot (immutable audit record)
- Action Scoping (tenant + project + environment)
- Idempotency protection (execution hash)
- Retry policy (transient vs non-transient)

### Phase 4 — Confidence Validator + Action Types

- Post-recommendation validator signals
- Entity grounding check against Knowledge Graph
- action_type support (execute_fix / observe_only / escalate)

### Phase 5 — Approval SLA + Proactive Monitor

- Severity-based approval timeout + auto-escalation
- Monitor System posts to /webhook/generic
- Source tagging ("proactive" vs "alert")
- Prediction metadata in incident.meta

### Phase 6 — Knowledge Graph Feedback Loop

- verify_resolution_task updates graph with outcome
- "what_worked" edges for future RAG retrieval
- Self-improving investigation quality over time

---

## Architecture Mental Model

```
🔹 Brain     → OpenClaw (investigation + reasoning)
🔹 Memory    → Knowledge Graph (persistent infra state)
🔹 Control   → AIREX state machine + approval RBAC
🔹 Hands     → Execution Engine (Action Registry + Context Resolver)
🔹 Safety    → Validation + Scoping + Snapshot + Idempotency
```

---

## Why This Beats Cleric's Architecture (on paper)

| Capability | Cleric | AIREX + OpenClaw |
|------------|--------|-----------------|
| Dynamic investigation | Knowledge graph traversal | Multi-agent MCP tool use |
| Proactive detection | Background graph scanning | Monitor System + Knowledge Graph |
| Remediation execution | Not yet | Full SSM/SSH/K8s pipeline |
| Safety guardrails | Not described | Action registry + approval RBAC |
| Audit trail | Not described | Immutable hash chain + execution snapshots |
| Multi-tenancy | Not described | Full RLS + action scoping |
| Self-improvement | Implicit | KG feedback loop from resolutions |
| Failure recovery | Not described | Re-investigation loop + controlled retries |
| Execution safety | Not described | Validation + idempotency + scoping + SLA |
| Approval drift | Not described | Execution Plan Snapshot prevents divergence |
