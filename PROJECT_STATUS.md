# AIREX Project Status & Reference
> Generated: 2026-02-18 | Overall Completion: ~80%

---

## Quick Stats

| Category | Complete | Partial | Missing | Score |
|----------|----------|---------|---------|-------|
| Backend Core | 35 modules | 3 | 0 | 95% |
| Backend Features | — | — | 6 features | 85% |
| Backend Tests | 15 files | 0 | 4 areas | 75% |
| Frontend Core | 28 modules | 7 | 0 | 85% |
| Frontend Features | — | — | 5 features | 70% |
| Frontend Tests | 7 files | 0 | ~20 modules | 25% |
| Infrastructure | 6 configs | 2 | 2 | 75% |
| Documentation | 11 files | 0 | 0 | 100% |

---

## BACKEND STATUS

### Fully Complete

- `app/main.py` — Lifespan, 4 middleware (CORS, CSRF, Prometheus, Correlation ID), 5 routers, /health, /metrics
- `app/core/state_machine.py` — 11 states, strict transition graph, SHA-256 hash chain, immutable audit
- `app/core/config.py` — Pydantic Settings, all env-driven config
- `app/core/database.py` — Async engine (pool_size=20), RLS session management
- `app/core/security.py` — JWT (HS256), bcrypt, token schemas
- `app/core/events.py` — 8 SSE emit functions via Redis pub/sub
- `app/core/rate_limit.py` — Redis sliding window (webhooks 30/60s, approvals 10/60s, auth 5/60s)
- `app/core/csrf.py` — Double-submit cookie pattern
- `app/core/metrics.py` — 12 Prometheus metrics
- `app/core/logging.py` — Structlog JSON, correlation ID
- `app/core/policy.py` — Per-action rules (auto_approve, risk levels)
- `app/core/worker.py` — ARQ: 4 tasks + cron retry scheduler + DLQ
- `app/core/webhook_signature.py` — HMAC-SHA256 verification
- `app/core/retry_scheduler.py` — Cron job for FAILED_ANALYSIS / FAILED_VERIFICATION
- `app/models/*.py` — All 8 models: Incident, Evidence, Execution, StateTransition, User, IncidentLock, TenantLimit, enums
- `app/schemas/*.py` — Webhook, Incident, Recommendation, Common
- `app/api/routes/auth.py` — Register, login, refresh
- `app/api/routes/webhooks.py` — Site24x7 + generic (signature, rate limit, idempotency, cloud tags, auto-discovery)
- `app/api/routes/incidents.py` — List (cursor pagination), detail, approve (distributed lock)
- `app/api/routes/sse.py` — Redis pub/sub fan-out, 8 event types, tenant-scoped
- `app/api/routes/tenants.py` — List, detail, reload, server lookup
- `app/api/dependencies.py` — Tenant ID, RLS session, Redis, auth, RBAC
- `app/services/incident_service.py` — CRUD
- `app/services/investigation_service.py` — Cloud-aware routing, simulation fallback, retry
- `app/services/recommendation_service.py` — LLM + policy check + auto-approve
- `app/services/execution_service.py` — Distributed locking, SSE events, timeout
- `app/services/verification_service.py` — Post-execution checks, retry
- `app/llm/client.py` — LiteLLM + circuit breaker (Redis-backed), primary/fallback
- `app/llm/prompts.py` — Strict JSON-only prompt, injection sanitization
- `app/investigations/cpu_high.py` — Simulated CPU diagnostics
- `app/investigations/disk_full.py` — Simulated disk diagnostics
- `app/investigations/memory_high.py` — Simulated memory diagnostics
- `app/investigations/network_check.py` — Simulated network diagnostics
- `app/investigations/cloud_investigation.py` — Real SSH/SSM + cloud logs, fallback to simulation
- `app/actions/restart_service.py` — AWS SSM + GCP SSH + simulation
- `app/actions/clear_logs.py` — AWS SSM + GCP SSH + simulation
- `app/cloud/aws_auth.py` — STS role assumption, static keys, profile, default chain
- `app/cloud/aws_ssm.py` — RunShellScript, polling
- `app/cloud/aws_ssh.py` — EC2 Instance Connect (ephemeral keys)
- `app/cloud/aws_logs.py` — CloudWatch Logs, auto-discover groups
- `app/cloud/gcp_ssh.py` — OS Login, asyncssh
- `app/cloud/gcp_logging.py` — Cloud Logging queries
- `app/cloud/discovery.py` — Instance lookup by IP (GCP + AWS), Redis-cached
- `app/cloud/tag_parser.py` — Site24x7 tag extraction
- `app/cloud/tenant_config.py` — YAML multi-tenant config, TTL-cached
- `app/cloud/diagnostics.py` — Alert-type to shell command mapping
- `alembic/versions/001_initial_schema.py` — All core tables, RLS, enums, triggers
- `alembic/versions/002_add_users_table.py` — Users with RLS
- `alembic/versions/003_add_incident_host_key.py` — host_key column + index

### Partially Complete

| File | Issue |
|------|-------|
| `app/actions/scale_instances.py` | AWS ASG works; GCP MIG is simulation-only; verify() returns random 85% |
| `scripts/validate_migration.py` | Hardcoded head revision references `002` but actual head is `003` |
| `app/core/state_machine.py` | `FAILED_ANALYSIS` is in both TERMINAL_STATES and RETRYABLE_STATES — contradictory |

### Missing Backend Features

1. **DLQ inspection/replay API** — referenced in docs but no route exists
2. **Admin user management** — only register/login/refresh; no user CRUD
3. **Incident soft-delete endpoint** — `deleted_at` field exists but no route
4. **Slack/email notification sending** — config exists, no sending logic
5. **TenantLimit enforcement** — model/table exists but never checked
6. **Manual review endpoint** — frontend skip button now uses reject API; ensure backend exposes audit + undo routes

### Backend Test Coverage

| Tested (15 files) | NOT Tested |
|--------------------|-----------|
| test_state_machine, test_actions, test_auth, test_cloud, test_enums, test_integration, test_investigations, test_llm_client, test_llm_prompts, test_policy, test_schemas, test_security, test_site24x7, test_tenant_config | Services (investigation, recommendation, execution, verification), worker tasks, middleware (CSRF, rate limit), logging |

---

## FRONTEND STATUS

### Fully Complete

- `pages/LandingPage.jsx` + `.css` — Full marketing page, scroll-reveal animations (312 + 973 lines)
- `pages/IncidentDetail.jsx` — Full detail with all sub-components
- `pages/AlertsPage.jsx` — Active alerts triage, severity sorting, filter tabs
- `pages/LiveFeed.jsx` — Real-time SSE stream, 7 filter tabs, pause/resume
- `context/AuthContext.jsx` — JWT decoding, login/logout/refresh, tenant persistence
- `context/ThemeContext.jsx` — Dark/light toggle, localStorage persistence
- `context/ToastContext.jsx` — Toast state, auto-dismiss (6s)
- `hooks/useIncidents.js` — Incident list + SSE (incident_created, state_changed)
- `hooks/useIncidentDetail.js` — Single incident + SSE (7 event types)
- `services/sse.js` — EventSource, exponential backoff, stale detection
- `services/auth.js` — Register, login, refresh, token management
- `utils/formatters.js` — Timestamps, durations, IDs, mailto builder
- `components/common/StateBadge.jsx` — All 11 states
- `components/common/SeverityBadge.jsx` — 4 levels
- `components/common/Terminal.jsx` — macOS-style with copy
- `components/common/MetricCard.jsx` — Trend indicators, critical pulse
- `components/common/ToastContainer.jsx` — Severity-colored, progress bar
- `components/common/ConnectionBanner.jsx` — 3 connection states
- `components/common/ConfirmationModal.jsx` — Backdrop blur, confirm/cancel
- `components/incident/StatePipeline.jsx` — 7-step visual pipeline
- `components/incident/RecommendationCard.jsx` — Risk-level styling, confidence %
- `components/incident/EvidencePanel.jsx` — Accordion with terminal output
- `components/incident/ExecutionLogs.jsx` — Live streaming logs
- `components/incident/VerificationResult.jsx` — 4 state-specific displays
- `components/incident/Timeline.jsx` — Transition history
- `components/incident/IncidentCard.jsx` — Grid card with copy-to-clipboard
- `components/layout/Layout.jsx` — Sidebar, topbar, notifications, theme toggle (429 lines)
- `index.css` — Full dark/light theme system (598 lines)
- `main.jsx` — Error boundary with styled fallback
- `types/api.d.ts` — All API types (not enforced, JSX project)

### Partially Complete

| File | Issue |
|------|-------|
| `pages/LoginPage.jsx` | **SECURITY:** Auth bypass button at line 288 (`// BYPASS_AUTH_SECURE_GATEWAY`) |
| `pages/IncidentList.jsx` | Hardcoded Quick Stats: MTTR 4m 23s, Avg Investigation 45s, AI Confidence 87% |
| `pages/SettingsPage.jsx` | All config hardcoded, read-only, no backend API. Health URL uses fragile `../` path |
| `components/common/SystemGraph.jsx` | Uses `Math.random()` — completely fake chart data |
| `services/api.js` | Missing: retryIncident(), fetchMetrics(), updateSettings() |
| `App.jsx` | No route guards (all pages accessible without login), no 404 page |
| `index.html` | Title is "frontend" (should be "AIREX"), favicon is default Vite SVG |

### Missing Frontend Features

1. **Route protection** — no PrivateRoute or RequireAuth wrapper
2. **Search functionality** — search bar in Layout is purely decorative
3. **Real metrics data** — SystemGraph and Quick Stats use fake/hardcoded data
4. **Manual review audit trail** — UI lacks timeline notes explaining why incidents were rejected
5. **Settings mutation** — cannot edit settings from UI
6. **404 page** — unmatched routes show empty layout

### Frontend Test Coverage

| Tested (7 files, 37 cases) | NOT Tested |
|-----------------------------|-----------|
| SeverityBadge, StateBadge, ConfirmationModal, EvidencePanel, RecommendationCard, VerificationResult, formatters | All pages, hooks, services, contexts, Layout, ApprovalControls, ExecutionLogs, Timeline, IncidentCard, Terminal, MetricCard, SystemGraph, StatePipeline, ConnectionBanner, ToastContainer |

### Cross-Cutting Frontend Issues

- Fallback tenant ID `00000000-0000-0000-0000-000000000000` duplicated in 6 files (LiveFeed, api.js, SettingsPage, Layout, useIncidents, useIncidentDetail)
- Unused dependencies: three, @react-three/fiber, @react-three/drei, @react-three/postprocessing (large 3D libs never imported)
- Dead file: `App.css` (default Vite template CSS, unused)

---

## INFRASTRUCTURE STATUS

### Complete

- `docker-compose.yml` — 6 services, healthchecks, dependency chain
- `.github/workflows/ci.yml` — 6 jobs: backend-lint, backend-test, frontend-lint, frontend-test, frontend-build, docker-build
- `infra/prometheus/prometheus.yml` — Scrape config for backend
- `infra/prometheus/alerting_rules.yml` — 10 alert rules (DLQ, circuit breaker, AI failures, execution failures, HTTP errors)
- `infra/grafana/airex-dashboard.json` — 14-panel dashboard
- `infra/loadtest/k6_incident_flow.js` — 4 test groups, staged load, thresholds
- `backend/config/tenants.yaml` — 4 tenants, 5 auth methods, extensive comments
- `backend/config/credentials/README.md` — 139 lines covering all IAM methods
- `docs/*` — 8 doc files + 3 runbooks, thorough and consistent
- `AGENTS.md` + `CLAUDE.md` — Consistent project guidelines

### Partially Complete

| Area | Issue |
|------|-------|
| CI/CD | **Uses SQLite instead of PostgreSQL** — RLS, enums, composite PKs, generated columns untested in CI |
| E2E Tests | 1 Playwright file, 13 tests, smoke-level. **Not in CI pipeline** |
| Backend Dockerfile | No non-root user, no .dockerignore, no multi-stage build, no health check |
| Frontend Dockerfile | No non-root user, no .dockerignore |
| .env setup | `backend/.env` appears committed with real GCP project + IP. SECRET_KEY is placeholder |

### Missing

| Area | Issue |
|------|-------|
| Monitoring in compose | Prometheus/Grafana configs exist but no docker-compose services for them |
| Redis persistence | No volume — DLQ data lost on restart |
| E2E in CI | Playwright tests never run in pipeline |
| Security scanning | No Trivy, no dependency audit |
| Image registry push | Docker images built but not pushed anywhere |
| Alertmanager config | No notification channels (Slack/PagerDuty) |

---

## CRITICAL ISSUES (Priority Order)

### P0 — Security

| # | Issue | Location |
|---|-------|----------|
| 1 | Auth bypass button in production code | `apps/web/src/pages/LoginPage.jsx:288` |
| 2 | No route guards — all pages accessible without login | `apps/web/src/App.jsx` |
| 3 | `backend/.env` appears committed with real GCP project/IP | `backend/.env` |
| 4 | SECRET_KEY is placeholder: `CHANGE_THIS_IN_PRODUCTION...` | `backend/.env` |
| 5 | Some deploy images historically ran as root | `services/backend/Dockerfile` |

### P1 — Data Integrity

| # | Issue | Location |
|---|-------|----------|
| 6 | CI uses SQLite not PostgreSQL — PG features untested | `.github/workflows/ci.yml` |
| 7 | FAILED_ANALYSIS in both TERMINAL and RETRYABLE states | `backend/app/core/state_machine.py` |
| 8 | validate_migration.py references wrong head revision | `backend/scripts/validate_migration.py` |

### P2 — Functionality Gaps

| # | Issue | Location |
|---|-------|----------|
| 9 | Reject button does not capture operator note/reason | `apps/web/src/components/incident/ApprovalControls.jsx:59` |
| 10 | Search bar is decorative (no input, no logic) | `apps/web/src/components/layout/Layout.jsx:226` |
| 11 | SystemGraph uses Math.random() — fake data | `apps/web/src/components/common/SystemGraph.jsx:8` |
| 12 | Settings page remains mostly static and limited in configuration scope | `apps/web/src/pages/SettingsPage.jsx` |
| 13 | GCP MIG scaling not implemented | `backend/app/actions/scale_instances.py` |
| 14 | TenantLimit never enforced | `backend/app/models/tenant_limit.py` (model only) |
| 15 | Missing API endpoints: DLQ replay, user CRUD, soft-delete, manual-review tooling | Backend routes |

### P3 — Cleanup

| # | Issue | Location |
|---|-------|----------|
| 16 | Orphaned empty `backend/backend/` directory | `backend/backend/` |
| 17 | Dead `App.css` (default Vite template) | `apps/web/src/App.css` |
| 18 | Unused Three.js dependencies (~2MB bundle waste) | `apps/web/package.json` |
| 19 | index.html title is "frontend", default favicon | `apps/web/index.html` |
| 20 | Cursor agent files corrupted (frontmatter 50-100x duplicated) | `.cursor/agents/*.md` |
| 21 | Fallback tenant ID duplicated in 6 files | Multiple frontend files |
| 22 | Orphaned root files: commands.txt, test.mp4, hero.png | Project root |

---

## ARCHITECTURE REFERENCE

### State Machine (11 States)

```
RECEIVED → INVESTIGATING → RECOMMENDATION_READY → AWAITING_APPROVAL → EXECUTING → VERIFYING → RESOLVED
               ↓                         ↓                        ↓                ↓            ↓
         FAILED_ANALYSIS           REJECTED (manual)        FAILED_EXECUTION  FAILED_VERIFICATION
                                                            ↓                        ↓
                                                        REJECTED                REJECTED
```

Terminal: RESOLVED, FAILED_ANALYSIS, FAILED_EXECUTION, FAILED_VERIFICATION, REJECTED

### Action Registry (3 Actions)

| Action | auto_approve | requires_senior | max_risk |
|--------|-------------|-----------------|----------|
| restart_service | false | false | HIGH |
| clear_logs | **true** | false | MED |
| scale_instances | false | **true** | HIGH |

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Python 3.12, SQLAlchemy 2.0, Alembic, ARQ |
| Frontend | React 19, Vite 7, Tailwind v4, Axios, Recharts |
| Database | PostgreSQL 15, RLS, asyncpg |
| Queue | Redis 7, ARQ |
| AI | LiteLLM → Vertex AI Gemini 2.0 Flash (primary) / Flash Lite (fallback) |
| Cloud | AWS (boto3, SSM, EC2 IC) + GCP (OS Login, Cloud Logging) |
| CI | GitHub Actions (6 jobs) |
| Monitoring | Prometheus + Grafana + k6 |
| E2E | Playwright |

### Key Ports

| Service | Port |
|---------|------|
| Backend (FastAPI) | 8000 |
| Frontend (Vite/Nginx) | 5173 |
| PostgreSQL | 5432 |
| Redis | 6379 |

### Key Commands

```bash
# Backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
npm install
npm run dev

# Infrastructure
docker-compose up -d db redis

# Tests
pytest tests/ -x --tb=short          # backend
npm run test                          # frontend
npx playwright test                   # e2e

# Full stack
docker-compose up -d
```

---

## GIT HISTORY

Only 4 commits:
1. `75c1054` — first commit
2. `0ebe7e1` — initialize
3. `0fa0efb` — phase-1
4. `a5718a7` — feat: implement AWS EC2 Instance Connect + new frontend pages
