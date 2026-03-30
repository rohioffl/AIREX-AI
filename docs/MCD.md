# AIREX — Master Component Documentation (MCD)

This document maps the repository by **layer**: what lives where, how pieces connect, and where to change behavior. It complements operational commands in [`CLAUDE.md`](../CLAUDE.md) and agent workflow in [`AGENTS.md`](../AGENTS.md). For strict incident and safety rules, see [`.claude/skills/airex-patterns/SKILL.md`](../.claude/skills/airex-patterns/SKILL.md).

---

## 1. Monorepo at a glance

| Area | Path | Role |
|------|------|------|
| Shared domain | `services/airex-core/` | Models, schemas, state machine, actions, investigations, LLM/RAG, cloud execution |
| HTTP API | `services/airex-api/` | FastAPI app, routers, dependencies, Docker image |
| Background jobs | `services/airex-worker/` | ARQ worker: investigate, recommend, execute, verify, retries, DLQ |
| Web UI | `apps/web/` | React 19 + Vite 7 SPA |
| Database | `database/` | Alembic migrations (`alembic/versions/`), init scripts |
| Tests | `tests/` | Pytest (API, core, services) |
| E2E | `e2e/` | Playwright |
| Config samples | `config/` | Static samples; tenant registry and credentials metadata in PostgreSQL |
| OpenClaw (optional) | `services/openclaw/` | Gateway compose + skills for InvestigationBridge |
| AI proxy | `services/litellm/`, `infra/ai-platform/` | LiteLLM routing; local stack config |
| Production IaC | `deployment/ecs/` | Terraform (active root: `terraform/environments/prod/`), CodeBuild, task defs |
| Observability assets | `infra/` | Prometheus, Grafana, k6, etc. |

**Request path (simplified):** webhook or UI → **API** → DB / Redis → **worker** tasks → **airex_core** services → LLM (via LiteLLM) + cloud probes → SSE/events back to UI.

---

## 2. Frontend (`apps/web/`)

- **Stack:** React 19, Vite 7, React Router, Tailwind-style utilities, Vitest + RTL.
- **Entry:** `src/main.jsx`, routes in `src/App.jsx`.
- **API:** Centralized in `src/services/api.js` (Axios). Avoid ad-hoc `fetch()` in components.
- **Auth / tenancy:** `src/context/AuthContext.jsx`; active tenant via JWT and optional `X-Active-Tenant-Id` / `X-Tenant-Id` (see backend dependencies).
- **Layout & nav:** `src/components/layout/Layout.jsx`, workspace switcher hooks (`useTenantWorkspace.js`).
- **Major routes (authenticated shell):** `/dashboard`, `/alerts`, `/incidents/:id`, `/live`, `/settings`, `/analytics`, `/knowledge-base`, `/reports`, `/runbooks`, `/patterns`, `/profile`, `/rejected`; org/tenant admin: `/admin/organizations`, `/admin/workspaces`, `/admin/integrations`, `/admin/cloud-accounts`; platform: `/admin` (platform admin login separate).
- **Rules:** UI is state-driven from backend; no `dangerouslySetInnerHTML`; no cloud SDKs in the browser; avoid hardcoded alert-type UI branches.

---

## 3. Backend API (`services/airex-api/`)

- **Entry:** `app/main.py` — FastAPI app, CORS, CSRF middleware, Prometheus HTTP metrics, Redis lifespan, OpenAPI at `/docs`.
- **Routers** (`app/api/routes/`): include (non-exhaustive by concern) `auth`, `admin_auth`, `users`, `tenants`, `tenant_members`, `organizations`, `platform_admin`, `incidents`, `sse`, `webhooks`, `settings`, `integrations`, `cloud_accounts`, `internal_tools`, `knowledge_base`, `runbooks`, `runbook_executions`, `patterns`, `analytics`, `reports`, `metrics`, `chat`, `notification_preferences`, `dlq`, `anomalies`, `predictions`, `root_causes`, `projects`, `templates`, and related admin surfaces.
- **Cross-cutting:** `app/api/dependencies.py` — DB session, user/tenant resolution, RBAC.
- **Run locally:** `uvicorn app.main:app --reload` from `services/airex-api/` (see `CLAUDE.md` for venv).

---

## 4. Worker (`services/airex-worker/`)

- **Entry:** `app/core/worker.py` — ARQ `WorkerSettings`, Redis queue, DLQ (`airex:dlq`), structured logging.
- **Responsibilities:** Long-running incident pipeline stages (investigate, recommendation generation, execution, verification), scheduled retries (e.g. `retry_scheduler`), cron hooks as configured.
- **Shared logic:** All heavy domain work should live in `airex_core` services; worker orchestrates I/O and task boundaries.

---

## 5. Core library (`services/airex-core/airex_core/`)

| Package | Responsibility |
|---------|----------------|
| `core/` | `state_machine`, `policy`, `rbac`, `config`, `events`, `metrics`, `rate_limit`, `csrf`, `investigation_bridge`, `openclaw_recommendation_bridge`, `execution_safety`, `entity_extractor`, etc. |
| `models/` | SQLAlchemy models: `incident`, `evidence`, `execution`, `state_transition`, `user`, `tenant`, `organization*`, `cloud_account_binding`, KG (`kg_node`, `kg_edge`), RAG/embeddings, runbooks, integrations, etc. |
| `schemas/` | Pydantic DTOs (e.g. `incident`, `recommendation`, `openclaw`, `recommendation_contract`) |
| `services/` | Business logic: `investigation_service`, `recommendation_service`, `execution_service`, `verification_service`, `notification_service`, `incident_embedding_service`, `confidence_validator`, RAG helpers, analytics/chat helpers, etc. |
| `actions/` | Whitelisted remediation plugins + `registry.py` — **only** these actions may run |
| `investigations/` | Alert-type probes: `cpu_high`, `disk_full`, `cloud_investigation`, `k8s_probe`, `site24x7_*`, `generic_checks`, etc. |
| `cloud/` | AWS/GCP discovery and execution paths (`tenant_config`, `secret_resolver`, etc.) |
| `llm/` | LiteLLM client, prompts, embeddings |
| `rag/` | Chunking + vector store integration (pgvector) |

**Invariant:** incident state changes go through `transition_state()` in `core/state_machine.py` — never assign `incident.state` directly outside that path.

---

## 6. Database (`database/`)

- **Engine:** PostgreSQL 15+ with **pgvector** (see `docker-compose.yml` `ankane/pgvector` image).
- **Migrations:** `database/alembic/` — run `alembic upgrade head` from `database/` (not inside service packages).
- **Design:** Composite tenant scoping `(tenant_id, id)` on tenant-owned rows; **RLS** on application tables; `state_transitions` immutable with hash chain; avoid `nullable=True` on `tenant_id`.
- **Model source of truth:** `airex_core.models` — migrations must stay aligned with models and reviewed manually.

---

## 7. AI / LLM stack

- **Routing:** LiteLLM (`LLM_BASE_URL`, models from settings / env — see `airex_core.core.config` and `docker-compose` defaults).
- **Usage:** Recommendations and embeddings go through `airex_core.llm` and related services; RAG context via `rag_context` / embedding services and pgvector.
- **Safety:** No LLM-generated shell; proposals must map to `ACTION_REGISTRY` and pass policy/confidence gates in `policy.py` / `confidence_validator`.

---

## 8. OpenClaw & advanced investigation (optional)

- **Compose / docs:** `services/openclaw/README.md`, `services/openclaw/docker-compose.yml`, env examples.
- **Bridge code:** `airex_core.core.investigation_bridge`, OpenClaw-oriented schemas and recommendation bridge modules under `core/` and `schemas/`.
- **Skills:** `services/openclaw/skills/` (forensics, AIREX investigation, validators).

---

## 9. Webhooks, real-time, external monitoring

- **Ingest:** `app/api/routes/webhooks.py` — HMAC, rate limits, idempotency (see implementation).
- **Live updates:** `sse` router + `airex_core.core.events` with Redis.
- **Monitoring integrations:** Models and routes for external monitors / integrations (`monitoring_integration`, `external_monitor`, etc.).

---

## 10. Testing

| Suite | Location | Command (typical) |
|-------|----------|-------------------|
| Backend | `tests/` | `cd tests && pytest` |
| Frontend | `apps/web/` | `npm run test`, `npm run lint`, `npm run build` |
| E2E | `e2e/` | `npm run test` (Playwright) |

Add or adjust tests whenever behavior changes in the corresponding layer.

---

## 11. Deployment & infrastructure

- **ECS:** `deployment/ecs/` — Terraform modules under `terraform/modules/`, **run plans/applies from** `terraform/environments/prod/` per project rules.
- **Containers:** `services/airex-api/Dockerfile`, `services/airex-worker/Dockerfile`, `apps/web/Dockerfile`.
- **Secrets:** AWS Secrets Manager / SSM in production — not committed to the repo.

---

## 12. Security & multi-tenancy (summary)

- **Tenancy:** Operational data keyed by `tenant_id`; organizations group tenants for SaaS admin UX.
- **Headers:** Authorized callers may send active-tenant headers; platform admins use separate flows.
- **Backend:** Async I/O for DB/HTTP/cloud; structured logs with `correlation_id` and `tenant_id` where applicable.

---

## 13. Related documents

- Commands and stack: [`CLAUDE.md`](../CLAUDE.md), [`AGENTS.md`](../AGENTS.md)
- High-level README: [`README.md`](../README.md)
- OpenClaw: [`services/openclaw/README.md`](../services/openclaw/README.md)
- Core package: [`services/airex-core/README.md`](../services/airex-core/README.md)
- Web app: [`apps/web/README.md`](../apps/web/README.md)
- ECS: [`deployment/ecs/README.md`](../deployment/ecs/README.md)

---

*Generated as a repo map for onboarding and navigation. When file counts or routes drift, update this file in the same PR as structural changes.*
