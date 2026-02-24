---
name: backend-sre-core
description: Build the production-grade, fault-tolerant backend for the Agentic AI Incident Response Platform. Focus on strict state management, plugin architecture, and safety-first execution.
license: Private
---

# Backend Skill — AIREX

> **Single-tenant mode:** Multi-tenancy is temporarily disabled while we simplify operations. All API requests execute under the primary DEV tenant ID (`00000000-0000-0000-0000-000000000000`). Any references to tenant switching or `X-Tenant-Id` headers in this document describe the long-term design but are currently no-ops.

This skill defines the backend implementation rules for the autonomous SRE platform.

This is NOT a CRUD app.
This is NOT a simple API.
This is a **Safety-Critical Automation Engine**.

The Backend must be:

- **Fault-Tolerant**: Never crash on investigation failure.
- **Secure**: Zero-trust execution model.
- **Deterministic**: Same inputs = Same actions.
- **Auditable**: Every decision logged.
- **Scalable**: Support 1000+ concurrent investigations.

---

## 1. Tech Stack (Mandatory)

| Component | Choice | Restriction |
| :--- | :--- | :--- |
| **Framework** | FastAPI | Async IO required. Strict Pydantic models. |
| **Database** | PostgreSQL | SQLAlchemy 2.0 (Async) + Alembic. |
| **Queue** | Redis + ARQ/Celery | Distributed task processing. |
| **AI** | LiteLLM | **Model Agnostic**. Supports local/Gemini/OpenAI. |
| **Cloud** | boto3 / google-cloud | **NO** stored keys. Use IAM Roles / Workload Identity. |

---

## 2. Core Architectural Rule: "trust_but_verify"

**The State Machine is Law.**

**Lifecycle (Immutable Enum):**
```python
class IncidentState(str, Enum):
    RECEIVED = "RECEIVED"
    INVESTIGATING = "INVESTIGATING"
    RECOMMENDATION_READY = "RECOMMENDATION_READY"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    RESOLVED = "RESOLVED"
    FAILED_ANALYSIS = "FAILED_ANALYSIS"
    FAILED_EXECUTION = "FAILED_EXECUTION"
    FAILED_VERIFICATION = "FAILED_VERIFICATION"
    REJECTED = "REJECTED"
```
**No additional states allowed.**

**Allowed Transitions (Strict Graph):**
```python
ALLOWED_TRANSITIONS = {
    RECEIVED: [INVESTIGATING],
    INVESTIGATING: [RECOMMENDATION_READY, FAILED_ANALYSIS, REJECTED],
    RECOMMENDATION_READY: [AWAITING_APPROVAL, REJECTED],
    AWAITING_APPROVAL: [EXECUTING, REJECTED],
    EXECUTING: [VERIFYING, FAILED_EXECUTION, REJECTED],
    VERIFYING: [RESOLVED, FAILED_VERIFICATION, REJECTED],
    FAILED_ANALYSIS: [REJECTED],
    FAILED_EXECUTION: [REJECTED],
    FAILED_VERIFICATION: [REJECTED],
}
```
> **Operator-only:** `REJECTED` is assigned exclusively by human action (`POST /api/v1/incidents/{id}/reject`). Backend services must leave automation failures in their respective `FAILED_*` states and set `_manual_review_required` in `incident.meta` instead of transitioning to `REJECTED` automatically.
**Rule**: Any transition not in `ALLOWED_TRANSITIONS` is **REJECTED**.

**Strict Rules for AI:**
1.  **NEVER** skip steps (e.g., `INVESTIGATING` → `EXECUTING` is BANNED).
2.  **NEVER** execute without approval if policy `auto_approve=False`.
3.  **ALWAYS** validate policy before transition.
4.  **ALWAYS** log the `reason` for state changes.
5.  **ATOMICITY**: All state transitions must occur inside a database transaction via a dedicated function:
    ```python
    def transition_state(incident, new_state, reason: str):
        if new_state not in ALLOWED_TRANSITIONS[incident.state]:
            raise IllegalStateTransition()
        incident.state = new_state
        incident.last_state_reason = reason
    ```
    **Direct mutation of `incident.state` is PROHIBITED.**

---

## 3. Module Specifications

### 3.1 Unification Layer (The "Agent Controller")
- **Responsibility**: Ingest webhooks, deduplicate, route to plugins.
- **Requirement**: **Idempotency Key** generation (Hash `alert_type` + `resource_id` + `time_window`).
- **Safety**: Reject duplicate alerts for same active incident.

### 3.2 Investigation Engine (Plugins)
- **Structure**: `investigations/<alert_type>.py`
- **Output**: Strict JSON schema `Evidence` object.
- **Timeout**: Hard limit (e.g., 60s).
- **Failure Handling**:
  - Log failure.
  - Increment `investigation_retry_count`.
  - If `< MAX_INVESTIGATION_RETRY` (3) → Retry.
  - Else → State = `REJECTED` (manual review).
- **Prohibition**: **NO** side effects (ReadOnly actions only).

| Plugin | Alert Type(s) | Notes |
|--------|---------------|-------|
| `CpuHighInvestigation` | `cpu_high` | Deterministic CPU + top-process snapshot |
| `MemoryHighInvestigation` | `memory_high` | Heap/swap profile with leak suspects |
| `DiskFullInvestigation` | `disk_full` | Filesystem usage + largest offenders |
| `NetworkCheckInvestigation` | `network_issue` | Latency/packet-loss/traceroute summary |
| `HealthCheckInvestigation` | `healthcheck` | Routes to CPU/MEM/DISK/NETWORK plugins with synthetic fallback |
| `HttpCheckInvestigation` | `http_check` | Synthetic HTTP probe timeline |
| `ApiCheckInvestigation` | `api_check` | REST call replay incl. upstream trace |
| `CloudCheckInvestigation` | `cloud_check` | Cloud control-plane diagnostics (DescribeEvents) |
| `DatabaseCheckInvestigation` | `database_check` | Test query timings + pg_stat_activity sample |
| `LogAnomalyInvestigation` | `log_anomaly` | Highlighted error logs with trace IDs |
| `PluginCheckInvestigation` | `plugin_check` | Custom plugin stdout/stderr/exit code |
| `HeartbeatCheckInvestigation` | `heartbeat_check` | Missed heartbeat timeline |
| `CronCheckInvestigation` | `cron_check` | Schedule + recent exit codes |
| `PortCheckInvestigation` | `port_check` | TCP dial attempts + timeouts |
| `SslCheckInvestigation` | `ssl_check` | Certificate chain + expiry snapshot |
| `MailCheckInvestigation` | `mail_check` | SMTP handshake transcript |
| `FtpCheckInvestigation` | `ftp_check` | FTP login transcript |

### 3.3 AI Recommendation Engine
- **Strategy**:
    1.  **Primary**: Local Model (Speed).
    2.  **Fallback**: Gemini Pro / GPT-4 (Intelligence).
    3.  **Circuit Breaker**:
        - If AI fails N consecutive times (e.g., 3):
        - Disable AI engine for T minutes (e.g., 5).
        - Transition incidents to `AWAITING_APPROVAL` with `reason="AI_DISABLED"`.
- **Output**: structured `Recommendation` object:
    - `root_cause`: string
    - `proposed_action`: string (Must match `actions/` registry)
    - `risk_level`: LOW/MED/HIGH
    - `confidence`: 0.0 - 1.0

### 3.4 Execution Engine (The "Hands")
- **Structure**: `actions/<action_type>.py`
- **Trigger**: ONLY via `POST /approve` or Policy Auto-Approval.
- **Locking**: **Distributed Lock** (Redis) on `incident_id` with **TTL** (120s). Must store `worker_id` + `timestamp` for traceability.
- **Action Registry (Deterministic)**:
    ```python
    ACTION_REGISTRY = {
        "restart_service": RestartServiceAction,
        "clear_logs": ClearLogsAction,
    }
    ```
    If LLM proposes action not in `ACTION_REGISTRY` → **REJECT**.
- **Execution Verification**:
  - Execution Success ≠ Resolution.
  - Must pass `VERIFYING` phase.
  - If verification fails → Increment `retry_count` -> Backoff (30s, 60s) -> Retry Verification ONLY. **DO NOT** re-run execution.
- **Action Policy Model**:
    ```python
    class ActionPolicy(Base):
        action_type: str
        auto_approve: bool
        requires_senior_approval: bool
        max_allowed_risk: RiskLevel
    ```
- **Idempotency**: Prevent double-tap on frontend.
- **Sandboxing**: Run commands in isolated sessions (e.g., restricted SSH user).
- **Guardrails (Infra Safety)**:
  - Max disk increase per action (e.g., +50GB).
  - **NO** deletion of root filesystem.
  - **NO** security group modification unless explicitly allowed.
  - **NO** instance termination allowed in v1.

### 3.5 SaaS Constraints
- **Rate Limiting**: Max concurrent incidents per tenant. Exceeding limit → Queue or Reject.
- **Observability**:
  - **Structured JSON Logs**: `correlation_id`, `tenant_id`, `incident_id`.
  - **Prometheus Metrics**: `incident_latency`, `investigation_duration`, `execution_duration`, `ai_failure_total`, `manual_review_total`.
  - **Health**: `/health` endpoint.
- **Tenant Isolation Enforcement**:
  - Every query MUST filter by `tenant_id`.
  - All repository methods require `tenant_id`.
  - **NO** global incident fetch allowed.

### 3.6 Resiliency
- **Dead Letter Queue (DLQ)**:
  - Failed async tasks (Investigate/Execute/Verify) after max retries → Move to DLQ.
  - Unhandled exceptions in worker → Move to DLQ.
  - DLQ must be observable via metrics.

### 3.7 Security & Limits
- **Timeouts (Hard Limits)**:
  - Investigation: 60s
  - AI Analysis: 15s (local) / 30s (fallback)
  - Execution: 20s
  - Verification: 30s
  - Lock TTL: 120s
- **Prompt Injection Protection**:
  - Sanitize LLM input (strip shell snippets, "ignore instructions").
  - Truncate and filter raw logs before sending to LLM.


---

## 4. STRICT PROHIBITIONS (The "Instant Reject" List)

1.  **NO Raw Shell Commands**: `subprocess.run("rm -rf ...")` is **BANNED**. Use specific libraries or whitelisted tool wrappers.
    - All OS interactions via **AWS SSM** / **GCP OS Login** / **Whitelisted Templates**.
    - **Dynamic command generation from LLM is STRICTLY PROHIBITED.**
2.  **NO Blocking Code**: Blocking IO in async path is **BANNED**.
3.  **NO Hardcoded Creds**: Finding an API Key in code = **Immediate Failure**.
4.  **NO Implicit Fallback**: "If action fails, try random thing" is **BANNED**.
5.  **NO Infinite Loops**: Max retry count (3) MUST be enforced.

---

## 5. Expected Database Schema

```python
class Incident(Base):
    __tablename__ = "incidents"
    
    id: UUID = primary_key
    tenant_id: UUID = index  # Multi-tenancy
    alert_type: str
    state: Enum(IncidentState)
    severity: Enum(Severity)
    retry_count: int = 0
    
    # Relationships
    evidence: List[Evidence]
    recommendation: Recommendation
    executions: List[ExecutionLog]
    timeline: List[TimelineEvent]
```

## 6. API Contracts

### `POST /webhook/site24x7`
- **Input**: Site24x7 payload.
- **Logic**: Deduplicate -> Create Incident -> Trigger Async Investigation.
- **Output**: `202 Accepted` ({"incident_id": "..."}).

### `POST /incidents/{id}/approve`
- **Input**: `{"action": "restart_service", "idempotency_key": "..."}`
- **Logic**:
    1.  Check State == `AWAITING_APPROVAL`.
    2.  Acquire Lock.
    3.  Trigger Async Execution.
- **Output**: `202 Accepted`.

---

## 7. Folder Structure
```
backend/
  app/
    core/
      state_machine.py  # The Law
      policy.py         # The Rules
      celery_app.py     # The Workers
    investigations/     # Read-Only Plugins
      cpu_high.py
      disk_full.py
    actions/            # Write-Critical Plugins
      restart_service.py
      clear_logs.py
    llm/
      client.py         # LiteLLM wrapper
    api/
      routes/
        webhooks.py
        incidents.py
    models/             # DB Models
    services/           # Business Logic
```

## 8. Acceptance Criteria

- [ ] **Resilient**: If AI is down, system falls back to manual mode (`AWAITING_APPROVAL` with "AI Failed" note).
- [ ] **Secure**: Impossible to execute `rm -rf /` via prompt injection.
- [ ] **Isolated**: Tenant A cannot see Tenant B's incidents.
- [ ] **Auditable**: `ExecutionLog` contains start, end, user, output, and exit code.

This skill defines the **ONLY** acceptable way to build the backend.
