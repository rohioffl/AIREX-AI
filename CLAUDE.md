# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview
- **Purpose**: AIREX (Autonomous Incident Resolution Engine Xecution) is an autonomous SRE platform that ingests alerts, runs investigations, produces AI-backed recommendations, requires human approval, executes deterministic runbooks, and verifies remediation. See README.md for the high-level flow and AGENTS.md for developer workflow expectations.
- **Single Source of Truth**: All architectural rules live under `docs/*_skill.md`. Always consult `docs/backend_skill.md`, `docs/frontend_skill.md`, and `docs/database_skill.md` before changing code. Violating these documents is considered a failed task.
- **Active Code**: Backend entrypoint is `backend/app/main.py` (FastAPI skeleton; routes commented until implemented). Frontend sources are not yet checked in but follow the structure described in `docs/frontend_skill.md`.

## Daily Commands
### Backend (`/backend`)
```bash
# Install dependencies
pip install -r requirements.txt

# Run FastAPI dev server
uvicorn app.main:app --reload

# Type checking & linting
mypy app
ruff check app

# Test suite
pytest
# Single test
pytest tests/test_incidents.py -k state_machine

# Database migrations
alembic upgrade head
```

### Frontend (`/frontend`)
```bash
npm install
npm run dev           # Vite dev server
npm run test          # Vitest/Jest (configure per docs/frontend_skill.md)
```

### Shared Infrastructure
```bash
# Bring up Postgres + Redis locally
docker-compose up -d db redis

# Populate env vars
cp .env.template .env  # then edit secrets
```

## Architecture & Key Constraints
### Backend (FastAPI, Async, Redis workers)
- **State Machine Law**: Incident lifecycle is fixed (`RECEIVED → … → RESOLVED/FAILED/ESCALATED`). Only transition via the sanctioned helper described in `docs/backend_skill.md`. Never mutate `incident.state` directly.
- **Engines**:
  - *Unification Layer*: Deduplicate webhooks using deterministic idempotency keys before spawning investigation tasks.
  - *Investigation Plugins*: Read-only modules under `app/investigations/`. Hard 60s timeout, capped retries, must fail-safe to `ESCALATED`.
  - *AI Recommendation*: LiteLLM wrapper (`app/llm/`) prioritizes local models with circuit breaker fallback. Output must match `Recommendation` schema and registered actions.
  - *Execution Engine*: Deterministic `ACTION_REGISTRY` under `app/actions/`. Requires Redis distributed locks, respects policy gating, logs every attempt, and never replays executions during verification retries.
- **Safety Rules**: No raw shell commands, no blocking IO on async paths, no implicit fallbacks, all logging structured with `correlation_id`, and every API schema must use Pydantic.
- **Observability**: Emit Prometheus metrics (`incident_latency`, `ai_failure_total`, etc.), hash-chain state transitions, and maintain DLQ visibility.

### Frontend (React + Vite + Tailwind)
- **State-Driven UI**: Treat backend SSE stream as the only authority. Never simulate transitions locally; wait for `state_changed` events before updating UI.
- **Routing**: `/incidents` (list) and `/incidents/:id` (detail) follow the exact render order documented in `docs/frontend_skill.md`.
- **Components**: Keep logic inside hooks/services (`src/hooks`, `src/services/api.js`, `src/services/sse.js`). Components only render data provided by hooks. Approval controls must enforce modal confirmation, idempotency keys, and disabled buttons until SSE confirms the new state.
- **Strict Prohibitions**: No business logic (risk scoring, policy decisions) on the client, no optimistic UI, no HTML injection (`dangerouslySetInnerHTML` is banned), and no cloud SDKs shipped to the browser.

### Database (PostgreSQL 15+, SQLAlchemy 2.0)
- **Multi-Tenancy First**: Every table (except reference data) uses `(tenant_id, id)` composite primary keys, plus enforced Row Level Security policies. The application must SET/RESET `app.tenant_id` on every connection checkout/return.
- **Enums & Constraints**: Implement database enums (`incident_state`, `severity_level`, `execution_status`) and use them in schemas. Retry counters are split across investigation/execution/verification with CHECK constraints.
- **Auditability**: `state_transitions` table is immutable with hash chaining (`previous_hash`, `hash`) to guarantee tamper evidence. Execution logs capture start/end timestamps and durations via generated columns.
- **Performance**: Use the indexed patterns specified in `docs/database_skill.md` (e.g., `idx_incidents_active`, `idx_incidents_awaiting_approval`) and add FK indexes for evidence/state transitions/executions.

## Working Agreements for Future Claude Instances
1. **Follow Docs Before Coding**: Treat the three skill documents plus AGENTS.md as binding contracts. If requirements seem to conflict, default to the stricter rule and leave a note for maintainers.
2. **Never Bypass Safety Controls**: Do not add new states, transitions, or action types without updating the relevant registries, policies, and documentation.
3. **Prefer Determinism Over Heuristics**: Whether in backend services or frontend rendering, identical inputs must yield identical behavior. Avoid randomization, non-idempotent side effects, or UI guessing.
4. **Document Gaps**: If you discover missing implementations (e.g., routes commented in `backend/app/main.py`), describe the expected behavior referencing the skill docs before adding code.
