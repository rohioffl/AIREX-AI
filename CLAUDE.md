# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

AIREX (Autonomous Incident Resolution Engine Xecution) is an autonomous SRE platform: ingest alerts → investigate → AI recommendation → human approval → deterministic execution → verification. The three skill docs (`docs/backend_skill.md`, `docs/frontend_skill.md`, `docs/database_skill.md`) plus `AGENTS.md` are binding contracts — consult them before changing code.

## Commands

### Backend (`cd backend`)
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload                     # API server (port 8000)
arq app.core.worker.WorkerSettings                # ARQ task worker
alembic upgrade head                              # Run migrations
alembic revision --autogenerate -m "description"  # Create migration
pytest                                            # Full test suite
pytest tests/test_incidents.py -k state_machine   # Single test
ruff check app/                                   # Lint
mypy app/ --ignore-missing-imports                # Type check
python scripts/ingest_runbooks.py --tenant-id <uuid>  # Seed RAG knowledge base
```

### Frontend (`cd frontend`)
```bash
npm install
npm run dev          # Vite dev server (port 5173, proxies /api → localhost:8000)
npm run build        # Production build
npm run lint         # ESLint
npm run test         # Vitest
npm run test:watch   # Vitest watch mode
```

### Infrastructure
```bash
docker-compose up -d db redis ai-platform   # Postgres (pgvector), Redis, LiteLLM proxy
docker-compose up -d                        # Full stack including backend, worker, frontend, Prometheus, Grafana
cp .env.template .env                       # Then edit secrets
```

## Architecture

### State Machine (The Law)
`backend/app/core/state_machine.py` — the **only** place incident state may be mutated. All transitions go through `transition_state()` which validates against `ALLOWED_TRANSITIONS`, writes an immutable hash-chained `StateTransition` audit record, emits SSE events, and fires notifications.

```
RECEIVED → INVESTIGATING → RECOMMENDATION_READY → AWAITING_APPROVAL → EXECUTING → VERIFYING → RESOLVED
                ↓                   ↓                     ↓               ↓            ↓
          FAILED_ANALYSIS       REJECTED              REJECTED       FAILED_EXEC   FAILED_VERIF
              ↕ (retry)                                                   ↓           ↕ (retry)
          RECOMMENDATION_READY                                        REJECTED       RESOLVED
```
Terminal: `RESOLVED`, `REJECTED`. Retryable failures: `FAILED_ANALYSIS`, `FAILED_VERIFICATION`. Non-retryable: `FAILED_EXECUTION` → `REJECTED` only.

### Backend Pipeline (FastAPI + ARQ workers)

Request flow: **Webhook → `routes/webhooks.py`** (dedup via idempotency key) → **`incident_service.create_incident()`** → ARQ enqueues **`investigate_incident`** → **`investigation_service.run_investigation()`** (selects plugin from `INVESTIGATION_REGISTRY` by alert_type, 60s timeout) → ARQ enqueues **`generate_recommendation_task`** → **`recommendation_service.generate_recommendation()`** (builds RAG context from `rag_context.py`, calls LLM via `llm/client.py` with circuit breaker) → waits for human approval → **`execution_service.execute_action()`** (acquires Redis distributed lock, runs action from `ACTION_REGISTRY`) → **`verification_service`** health check.

Key modules:
- **`app/actions/`** — Deterministic action classes (`BaseAction` subclasses) registered in `registry.py`. Each has a frozen `ActionPolicy` (auto_approve, risk level). LLM-proposed actions must exist in the registry.
- **`app/investigations/`** — Read-only plugins registered in `__init__.py`. Use seeded RNG for determinism. Never produce side effects.
- **`app/llm/client.py`** — `LLMClient` with `CircuitBreaker` (3 failures → 5min cooldown, state persisted in Redis). Primary model → fallback model → manual review.
- **`app/core/events.py`** — SSE via Redis pub/sub on `tenant:{id}:events` channels.
- **`app/core/rbac.py`** — VIEWER → OPERATOR → ADMIN role hierarchy. Use `require_role()` or `require_permission()` as route dependencies.
- **`app/core/worker.py`** — ARQ task definitions (investigate, recommend, execute, verify, retry scheduler).
- **`app/services/rag_context.py`** — Builds LLM context from past similar incidents + runbook chunks (pgvector similarity search, 4000 char limit).

### Multi-Tenancy
`backend/app/core/database.py` — `get_tenant_session()` sets PostgreSQL session variable `app.tenant_id` on connection checkout, resets on return. All tables (except reference data) use `(tenant_id, id)` composite PKs via `TenantMixin`. PostgreSQL RLS policies enforce isolation.

### Frontend (React 19 + Vite + Tailwind)
- **Pages**: `src/pages/` — DashboardPage, IncidentList, IncidentDetail, LoginPage, UserManagementPage, SettingsPage, AlertsPage, LiveFeed, RejectedPage
- **Components**: `src/components/` — StatePipeline, Timeline, EvidencePanel, AIAnalysisPanel, ApprovalControls (modal confirmation + idempotency keys), ExecutionLogs, VerificationResult
- **Services**: `src/services/api.js` (Axios with auth/CSRF interceptors), `src/services/sse.js` (EventSource with auto-reconnect)
- **Hooks**: `src/hooks/useIncidentDetail.js`, `src/hooks/useIncidents.js` — data fetching + SSE subscription
- **SSE is the single source of truth** — never simulate transitions locally; wait for `state_changed` events

### Database (PostgreSQL 15 + pgvector)
Key models in `app/models/`: `Incident` (retry counters split by phase), `Evidence`, `Execution` (computed `duration_seconds`), `StateTransition` (immutable, hash-chained), `IncidentEmbedding` (1024-dim vectors), `RunbookChunk` (RAG knowledge). Enums in `app/models/enums.py`: `IncidentState`, `SeverityLevel`, `ExecutionStatus`, `RiskLevel`, `UserRole`, `Permission`.

### Observability Stack
Docker Compose includes Prometheus (port 9090), Grafana (port 3001), Alertmanager (port 9093). Backend emits metrics from `app/core/metrics.py` (`state_transition_total`, `ai_failure_total`, `circuit_breaker_state`, etc.). Config in `infra/prometheus/`, `infra/grafana/`.

## Critical Rules

1. **State transitions only via `transition_state()`** — never assign `incident.state` directly.
2. **All I/O must be async** — no blocking calls on async paths.
3. **Actions must be in `ACTION_REGISTRY`** — unregistered actions are rejected.
4. **Investigation plugins are read-only** — no side effects, 60s hard timeout.
5. **No raw shell commands** — use SSM/OS Login/whitelisted templates only.
6. **Structured logging with `correlation_id`** — use `structlog` everywhere.
7. **All API schemas use Pydantic** — no untyped request/response bodies.
8. **Frontend: no optimistic UI, no `dangerouslySetInnerHTML`, no business logic** — SSE is the authority.
9. **Skill docs override defaults** — if `docs/*_skill.md` says something, follow it even if it seems unusual.
