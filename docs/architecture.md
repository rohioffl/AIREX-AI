# AIREX Architecture

## System Overview

AIREX (Autonomous Incident Resolution Engine Xecution) is an autonomous SRE platform that:
1. **Ingests** alerts from monitoring systems (Site24x7, generic webhooks)
2. **Investigates** incidents using read-only diagnostic plugins
3. **Recommends** actions using AI (LiteLLM with circuit breaker)
4. **Requires** human approval before any changes
5. **Executes** approved actions deterministically
6. **Verifies** that actions resolved the issue

## Incident State Machine

```
  RECEIVED
     │
     ▼
INVESTIGATING ──────▶ FAILED_ANALYSIS ───┐
     │                                    │
     ▼                                    ▼
RECOMMENDATION_READY ───────────────▶ REJECTED (manual review)
     │
     ▼
AWAITING_APPROVAL ────────────────▶ REJECTED
     │
     ▼
  EXECUTING ──────────▶ FAILED_EXECUTION ──▶ REJECTED
     │
     ▼
  VERIFYING ──────────▶ FAILED_VERIFICATION ──▶ REJECTED
     │
     ▼
  RESOLVED
```

**Strict Rules:**
- Transitions are governed by `ALLOWED_TRANSITIONS` — no shortcuts
- Every transition is hash-chained in `state_transitions` table
- `transition_state()` is the ONLY way to change state
- SSE events fire on every transition for real-time UI

## Component Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (React)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ Dashboard │  │ Incident │  │ Approval │  │ Theme  │ │
│  │   List   │  │  Detail  │  │ Controls │  │ Toggle │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┘ │
│       │              │              │                    │
│  ┌────▼──────────────▼──────────────▼────────────────┐  │
│  │              SSE Event Stream                      │  │
│  │    (incident_created, state_changed, etc.)         │  │
│  └────────────────────┬──────────────────────────────┘  │
└───────────────────────┼─────────────────────────────────┘
                        │ EventSource
┌───────────────────────┼─────────────────────────────────┐
│                  NGINX (Reverse Proxy)                    │
│           /api/* → backend:8000                          │
│           /*     → static React build                    │
└───────────────────────┼─────────────────────────────────┘
                        │
┌───────────────────────┼─────────────────────────────────┐
│                 BACKEND (FastAPI)                         │
│                                                          │
│  ┌─────────────┐  ┌────────────┐  ┌──────────────────┐ │
│  │ Auth Router  │  │ Webhook    │  │ Incident Router  │ │
│  │  /auth/*    │  │  /webhooks │  │  /incidents/*    │ │
│  └──────┬──────┘  └─────┬──────┘  └────────┬─────────┘ │
│         │               │                   │            │
│  ┌──────▼───────────────▼───────────────────▼──────────┐│
│  │                 Middleware Layer                      ││
│  │  [CORS] [Rate Limit] [Correlation ID] [Prometheus]  ││
│  └──────────────────────┬───────────────────────────────┘│
│                         │                                │
│  ┌──────────────────────▼───────────────────────────────┐│
│  │               Service Layer                           ││
│  │  ┌─────────────┐ ┌──────────┐ ┌───────────────────┐ ││
│  │  │Investigation│ │   LLM    │ │   Execution       │ ││
│  │  │  Service    │ │ Service  │ │   Service         │ ││
│  │  └─────────────┘ └──────────┘ └───────────────────┘ ││
│  └──────────────────────────────────────────────────────┘│
└────────────────┬─────────────────┬───────────────────────┘
                 │                 │
┌────────────────▼──┐  ┌──────────▼───────────────────────┐
│    PostgreSQL     │  │          Redis                    │
│    ┌───────────┐  │  │  ┌──────────┐  ┌──────────────┐ │
│    │ incidents │  │  │  │ Pub/Sub  │  │  Task Queue  │ │
│    │ evidence  │  │  │  │  (SSE)   │  │    (ARQ)     │ │
│    │ users     │  │  │  └──────────┘  └──────────────┘ │
│    │ state_    │  │  │  ┌──────────┐  ┌──────────────┐ │
│    │  trans.   │  │  │  │  DLQ     │  │  Circuit     │ │
│    │ executions│  │  │  │          │  │  Breaker     │ │
│    └───────────┘  │  │  └──────────┘  └──────────────┘ │
│    RLS Enabled    │  │  ┌──────────┐  ┌──────────────┐ │
│    Hash Chains    │  │  │Rate Limit│  │  Idempotency │ │
│                   │  │  │ Counters │  │   Keys       │ │
└───────────────────┘  └──────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────┐
│                  ARQ WORKER                               │
│  ┌──────────────┐  ┌───────────┐  ┌──────────────────┐  │
│  │ investigate  │  │ recommend │  │ execute + verify │  │
│  └──────────────┘  └───────────┘  └──────────────────┘  │
│  ┌──────────────────────────────────────────────────┐    │
│  │         Retry Scheduler (cron every 30s)         │    │
│  │  Re-queues FAILED_ANALYSIS / FAILED_VERIFICATION │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

## Multi-Tenancy

- **Composite Primary Keys**: All tables use `(tenant_id, id)`
- **Row Level Security**: Postgres RLS policies enforce `tenant_id = current_setting('app.tenant_id')::uuid`
- **Session Setup**: Application sets `app.tenant_id` on every DB session checkout
- **JWT Claims**: `tenant_id` is embedded in JWT tokens
- **SSE Channels**: Events scoped to `tenant:{tenant_id}:events`

## Security Layers

| Layer | Mechanism |
|-------|-----------|
| Authentication | JWT (access + refresh tokens), bcrypt password hashing |
| Authorization | Role-based (operator, admin) via JWT claims |
| Multi-tenancy | RLS policies, composite PKs, session-level tenant |
| Rate Limiting | Redis sliding window per IP per endpoint group |
| Idempotency | SHA256 deduplication keys with TTL |
| Execution Safety | Deterministic action registry, no raw shell, Redis locks |
| Audit Trail | Immutable hash-chained state transitions |
| AI Safety | Circuit breaker, prompt injection protection, action whitelist |

## Investigation Plugins

| Plugin | Alert Type | Collects |
|--------|-----------|----------|
| `CpuHighInvestigation` | `cpu_high` | Load avg, top processes, CPU per-core |
| `DiskFullInvestigation` | `disk_full` | df, large files, inode usage |
| `MemoryHighInvestigation` | `memory_high` | Memory usage, top consumers, OOM kills |
| `NetworkCheckInvestigation` | `network_issue` | Ping, DNS, TCP, traceroute |

## Action Registry

| Action | Type | Verifies |
|--------|------|----------|
| `RestartServiceAction` | `restart_service` | Service health check |
| `ClearLogsAction` | `clear_logs` | Disk usage below threshold |
| `ScaleInstancesAction` | `scale_instances` | All instances healthy |

## Retrieval-Augmented Context

- **Storage**: `runbook_chunks` + `incident_embeddings` tables (pgvector) with RLS + composite PKs.
- **Ingestion**: `backend/scripts/ingest_runbooks.py` chunks markdown runbooks and stores embeddings.
- **Vector Store**: `app/rag/vector_store.py` performs cosine search against pgvector for runbooks + prior incidents.
- **Auto-Summarize**: When incidents hit a terminal state, `transition_state()` calls `upsert_incident_embedding()` to embed their final summary/metadata.
- **Prompt Wiring**: `build_recommendation_context()` feeds top matches into the LLM prompt (sanitized + size capped).
- **Config**: Tunable via `RAG_*` settings (limits, char caps, embedding model/dimension).

## Observability Stack

```
Backend → Prometheus Metrics (/metrics)
       → Structured Logs (structlog JSON)
       → Correlation IDs (X-Correlation-ID header)
       → SSE Events (Redis Pub/Sub)

Prometheus → Alerting Rules → Alertmanager → Slack/PagerDuty
```

### Key Metrics
- `airex_incident_created_total` — Counter: incidents by tenant/severity
- `airex_state_transition_total` — Counter: state changes
- `airex_ai_request_total` / `airex_ai_failure_total` — AI success/failure
- `airex_execution_total` / `airex_execution_duration_seconds` — Execution stats
- `airex_circuit_breaker_state` — Gauge: 0=closed, 1=open
- `airex_dlq_size` — Gauge: dead letter queue depth
- `airex_active_incidents` — Gauge: concurrent active incidents
- `airex_http_request_duration_seconds` — Histogram: API latency
