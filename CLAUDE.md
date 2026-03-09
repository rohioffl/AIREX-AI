# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

AIREX is a **safety-critical, autonomous SRE incident response platform**. It ingests infrastructure alerts, investigates via SSH/SSM on real servers, generates AI-backed remediation recommendations, and can auto-execute remediations with confidence gating and a full audit trail. Treat every change with the same discipline as production automation code — prioritize determinism, auditability, and secure defaults over convenience.

Full canonical rules: `docs/backend_skill.md`, `docs/frontend_skill.md`, `docs/database_skill.md`.

---

## Commands

### Backend (run from `backend/`)
```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# Run
uvicorn app.main:app --reload
arq app.core.worker.WorkerSettings

# Migrations (Alembic lives in database/, not backend/)
cd ../database && alembic upgrade head && alembic history

# Lint + type-check
ruff check app/
mypy app/ --ignore-missing-imports

# Tests
pytest
pytest tests/test_state_machine.py::test_valid_transition   # single test
pytest tests/ -k "recommendation and not slow"              # filter
```

### Frontend (run from `apps/web/`)
```bash
npm install && npm run dev
npm run build && npm run preview
npm run lint
npm run test
npm run test -- --run "Incident*"   # single test pattern
```

### E2E (run from `e2e/`)
```bash
npm install && npm run test
npx playwright test tests/incident-lifecycle.spec.js
```

### Local Stack
```bash
docker-compose up -d db redis ai-platform   # dependencies only
docker-compose up -d                         # full stack
docker-compose run migrate                   # run migrations in container
```

### Pre-PR Validation
```bash
cd backend && ruff check app/ && mypy app/ --ignore-missing-imports && pytest
cd apps/web && npm run lint && npm run test && npm run build
```

---

## Architecture

### Monorepo Layout
```
backend/app/          # FastAPI application (Python 3.12)
  core/               # state_machine, policy, worker, security, events, rate_limit
  api/routes/         # webhooks, incidents, auth, sse, tenants
  investigations/     # read-only probe plugins per alert type
  actions/            # write plugins: restart_service, clear_logs, scale_instances
  services/           # business logic layer
  llm/                # LiteLLM wrapper + prompt builder
  cloud/              # AWS (SSM, EC2 IC, CloudWatch) + GCP (OS Login, Logging)
  models/             # SQLAlchemy ORM models
  schemas/            # Pydantic request/response schemas
  rag/                # vector embeddings + runbook retrieval
  monitoring/         # health check scheduler (ARE Phase 6)
apps/web/src/         # React 19 + Vite 7 frontend
database/alembic/     # Alembic migrations (isolated pipeline)
services/backend/     # Dockerfile with 'api' and 'worker' build targets (shared backend/ codebase)
services/airex-frontend/  # Dockerfile for frontend (copies apps/web/)
services/litellm/     # LiteLLM proxy Dockerfile + config
deployment/ecs/terraform/
  environments/prod/  # ACTIVE production Terraform root (run all tf commands here)
  modules/vpc/        # VPC, subnets, NAT gateways
  modules/platform/   # ECS, RDS, Redis, ALB, ECR, IAM, SSM/Secrets
  modules/frontend/   # S3 + CloudFront for frontend
infra/                # Prometheus, Grafana, k6 load test configs
e2e/                  # Playwright end-to-end tests
```

### The State Machine Is Law

All incident lifecycle changes MUST go through `app/core/state_machine.py`. **Direct mutation of `incident.state` is prohibited.** Always use `transition_state(incident, new_state, reason)`.

```
RECEIVED → INVESTIGATING → RECOMMENDATION_READY → AWAITING_APPROVAL → EXECUTING → VERIFYING → RESOLVED
                ↓                    ↓                     ↓               ↓           ↓
          FAILED_ANALYSIS         REJECTED             REJECTED     FAILED_EXECUTION  FAILED_VERIFICATION
```

- `REJECTED` is **operator-only** (`POST /incidents/{id}/reject`). Automation failures stay in `FAILED_*` states and set `_manual_review_required` in `incident.meta`.
- Retryable states: `FAILED_ANALYSIS`, `FAILED_EXECUTION`, `FAILED_VERIFICATION` (max 3 retries each, tracked separately).
- Terminal states: `RESOLVED`, `REJECTED`.

### Request Flow (Webhook → Resolution)
1. `POST /webhook/site24x7` or `/webhook/generic` — HMAC-verified, rate-limited, idempotency-keyed
2. Creates `Incident` in `RECEIVED` state → enqueues ARQ task
3. Worker: `investigate()` → runs plugin from `investigations/<alert_type>.py` → produces `Evidence`
4. Worker: `generate_recommendation()` → LiteLLM (Gemini primary / Flash Lite fallback, circuit-breaker backed) → RAG context injected → produces `Recommendation`
5. Policy check (`app/core/policy.py`): if `auto_approve=True` and risk ≤ `max_allowed_risk` → skip to execution; else → `AWAITING_APPROVAL`
6. `POST /incidents/{id}/approve` → distributed Redis lock → ARQ executes action plugin
7. Verification phase → if fails, retry execution is **not** repeated, only verification is
8. SSE events broadcast all state changes to connected frontend clients in real time

### Action Registry (deterministic — LLM cannot invent actions)
```python
ACTION_REGISTRY = {
    "restart_service": RestartServiceAction,   # auto_approve=False, max_risk=HIGH
    "clear_logs":      ClearLogsAction,        # auto_approve=True,  max_risk=MED
    "scale_instances": ScaleInstancesAction,   # auto_approve=False, requires_senior=True
}
```
If LLM proposes an action not in `ACTION_REGISTRY` → reject it.

### Cloud Execution
- **AWS**: SSM `RunShellScript` (preferred) → EC2 Instance Connect ephemeral SSH → simulation fallback
- **GCP**: OS Login + asyncssh → simulation fallback
- Discovery: `app/cloud/discovery.py` looks up instance by IP via GCP/AWS APIs, Redis-cached

### Frontend Architecture
The UI is **purely state-driven** — it never infers or simulates state transitions locally. Every UI section renders based on an **explicit** `state === 'EXACT_VALUE'` check. It always waits for an SSE `state_changed` event before updating. No optimistic UI.

SSE event types: `incident_created`, `state_changed`, `evidence_added`, `execution_started`, `execution_log`, `execution_completed`, `verification_result`.

All API calls are centralized in `apps/web/src/services/api.js` (Axios instance). No inline `fetch()` in components.

### Database
- PostgreSQL 15 with **Row-Level Security** (RLS) on all tables
- Composite PKs: `(tenant_id, id)` everywhere
- `state_transitions` table is **immutable** with a SHA-256 hash chain — never UPDATE or DELETE
- Migrations live in `database/alembic/` — independent from application deployment
- Current runtime: single-tenant, fixed to DEV tenant `00000000-0000-0000-0000-000000000000` — but all code must remain tenant-safe (always filter by `tenant_id`)

### Infrastructure (ECS Fargate)
Terraform is split into modules (`vpc`, `platform`, `frontend`) under `deployment/ecs/terraform/modules/`. The active production root is `deployment/ecs/terraform/environments/prod` — **always run Terraform from there, not the modules directly**.
- Remote state: S3 bucket `airex-prod-terraform-state-ap-south-1-547361935557` + DynamoDB `airex-prod-terraform-locks` in `ap-south-1`
- `modules/platform`: ECS cluster, 4 services (api, worker, litellm, langfuse), RDS PostgreSQL 15 ×2, ElastiCache Redis 7 (TLS), ALB, ECR repos, IAM roles, CloudWatch log groups
- All secrets in AWS Secrets Manager only — never in tfvars; config in SSM Parameter Store
- Database migrations run in CodeBuild deploy phase (not a separate ECS task)

---

## Hard Rules

### Backend
- All DB/HTTP/cloud I/O must be `async`
- LLM-generated shell commands are **strictly prohibited** — only whitelisted action templates via SSM/OS Login
- No bare `except:` — catch specific exceptions
- Use `structlog` with `correlation_id` and `tenant_id` on every log line
- Timeouts enforced: investigation 60s, AI 15s/30s, execution 20s, verification 30s, Redis lock TTL 120s

### Frontend
- `dangerouslySetInnerHTML` is **banned** — all backend/user content rendered as text
- No cloud SDK imports (`aws-sdk`, `google-cloud-node`)
- No business logic — use backend fields (`risk_level`, `confidence`) as-is
- No hardcoded alert type checks (`if alert_type === 'DiskFull'`) — UI must be generic

### Database
- `nullable=True` on `tenant_id` is banned
- Never auto-generate Alembic migrations without review
- Schema changes and data backfills must be separate migration files
- Use `NOT VALID` + `VALIDATE CONSTRAINT` for FKs on large tables

---

## MCP Tools
Prefer connected MCP servers over ad-hoc workarounds:
- `memory` — recover/update project context at session start/end
- `context7` / `grep_app` — external library docs and code search
- `playwright` / `puppeteer` — real UI verification
- `docker` — container and runtime checks
- `github` — repository state
- `filesystem` — local project inspection
- `terraform` — infrastructure analysis

### jcodemunch — Codebase Analysis (MANDATORY)
**Always use `jcodemunch` MCP for analyzing and understanding this codebase.** Never re-read files directly when the index can answer the question.

Rules:
1. At the start of every session, call `mcp__jcodemunch__list_repos` to check whether index `local/AIREX-AI-69bee4bf` exists. If it is **missing**, run `mcp__jcodemunch__index_folder` with `path=/home/ubuntu/AIREX-AI/AIREX-AI` and `incremental=false` (full index) before performing any codebase analysis. If it **exists**, run `mcp__jcodemunch__index_folder` with `incremental=true` to pick up changed files.
2. Index ID: `local/AIREX-AI-69bee4bf` — source root `/home/ubuntu/AIREX-AI/AIREX-AI`.
3. For all code searches, symbol lookups, and architecture questions use `mcp__jcodemunch__search_text`, `mcp__jcodemunch__get_symbols`, `mcp__jcodemunch__get_file_content`, and `mcp__jcodemunch__get_file_tree` before falling back to `Grep` or `Read`.
4. After creating or significantly modifying files, re-run the incremental index so the index stays current.
5. Use `mcp__jcodemunch__get_repo_outline` for a quick architecture overview at any time.
