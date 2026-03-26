# AIREX — Master Plan: Multi-Organization Tenancy & Platform Alignment

**Purpose:** One document for **SaaS hierarchy** (organizations → tenants), **data isolation** (`tenant_id` / RLS), **webhooks**, **background jobs**, **real-time (SSE)**, **security**, **documentation**, **tests/tooling**, and **known gaps**. Update this file when milestones land.

**Audience:** Engineers, operators, and agents working on the AIREX monorepo.

---

## Table of contents

1. [Goals and status](#1-goals-and-status)  
2. [Canonical architecture](#2-canonical-architecture)  
3. [Authenticated API vs webhooks (comparison)](#3-authenticated-api-vs-webhooks-comparison)  
4. [Webhooks (design, security, gaps)](#4-webhooks-design-security-gaps)  
5. [Non-webhook gaps](#5-non-webhook-gaps)  
6. [Schema and product rules](#6-schema-and-product-rules)  
7. [Documentation inventory](#7-documentation-inventory)  
8. [Workstreams (checklists)](#8-workstreams-checklists)  
9. [Verification and release](#9-verification-and-release)  
10. [Code reference map](#10-code-reference-map)  
11. [Changelog](#11-changelog)  

---

## 1. Goals and status

| Goal | Status |
|------|--------|
| Multiple **organizations** (customer accounts), each with one or more **tenant workspaces** | Implemented (DB, API, admin UI) |
| Operational data isolated by **`tenant_id`** (incidents, evidence, etc.) | Implemented (RLS, composite PKs `(tenant_id, id)`) |
| JWT + optional **`X-Active-Tenant-Id`** / **`X-Tenant-Id`** with **org/tenant membership** checks | Implemented (`resolve_active_tenant_id`, `dependencies.py`) |
| **Webhooks** resolve tenant without JWT via **URL path** (`org_slug`, `tenant_slug`) + **integration binding** where applicable | Implemented (`webhooks.py`) |
| **Worker** scheduled jobs process **all** tenants (or configured set) | Implemented (`worker.py` fan-out across active tenants) |
| **SSE** live stream subscribes to the **correct** tenant channel | Implemented (`sse.py`, frontend `sse.js`) |
| Integration API + Admin UI show **correct** webhook URLs | Implemented (`integrations.py`, `IntegrationsAdminPage.jsx`) |
| Tests, E2E, scripts, k6 use **current** webhook paths and multi-tenant scenarios | Implemented |
| Docs and operator copy match runtime | Implemented |

---

## 2. Canonical architecture

### 2.1 Data model

| Concept | Table / model | Notes |
|---------|----------------|--------|
| Organization | `organizations` | `name`, `slug`, `status`. Seed default `11111111-1111-1111-1111-111111111111` in migrations. |
| Tenant workspace | `tenants` | **`organization_id`** FK. **`name`** = unique slug (URLs, tags). **`aws_config`** / **`gcp_config`** JSONB. |
| Tenant-scoped domain | incidents, evidence, … | Composite PK `(tenant_id, id)`; RLS enforced when using tenant-scoped DB session. |
| Memberships | `organization_memberships`, `tenant_memberships` | Who may access which org/tenant for switching and admin. |
| Projects | `projects` | Optional finer routing (e.g. monitor bindings) under an organization. |

### 2.2 Incident lifecycle (unchanged law)

- All state changes go through **`transition_state`** (`airex_core/core/state_machine.py`). No direct `incident.state` mutation.
- Terminal: `RESOLVED`, `REJECTED`. Retryable: `FAILED_ANALYSIS`, `FAILED_EXECUTION`, `FAILED_VERIFICATION` (with limits).

### 2.3 Authenticated API

- **`GET /auth/me`** (and session context) exposes **`organizations`**, **`tenants`**, **`active_tenant`**, **`active_organization`**, memberships.
- **`get_tenant_id`** resolves: JWT default tenant; optional **`X-Active-Tenant-Id`** or **`X-Tenant-Id`**; **organization** or **tenant** membership validation; **monitoring integration** binding when `integration_id` is used in dependencies.
- **`get_db_session`** → tenant-scoped session (RLS `app.tenant_id`).
- **Platform admin** flows use a **sentinel tenant UUID** in JWT for platform identities (`auth.py`, `admin_auth.py`) — not a real customer workspace; RLS-backed app data uses normal tenant sessions for tenant users.

### 2.4 Configuration

- **`settings.DEV_TENANT_ID`** (`airex_core/core/config.py`) — default UUID `00000000-0000-0000-0000-000000000000` for bootstrap, tests, and **explicit** unauthenticated fallbacks.
- **`WEBHOOK_SECRET`** — when set, **`verify_webhook_signature`** requires HMAC on routes that include it.

### 2.5 Tenant config source (DB vs YAML)

- **Authoritative:** PostgreSQL **`tenants`** table + Admin/API updates; **`tenant_config.py`** reads DB with cache.
- **Legacy:** `config/tenants.yaml` and comments in **`ssh_user_resolver.py`**, **`tag_parser.py`**, **`discovery.py`** — treat DB as source of truth in production; YAML as fallback/dev only unless you standardize on one story.

---

## 3. Authenticated API vs webhooks (comparison)

| Dimension | REST / SSE (authenticated) | Webhooks |
|-----------|----------------------------|----------|
| **Identity** | JWT (+ optional tenant headers) | None; URL + optional HMAC |
| **Tenant resolution** | `resolve_active_tenant_id` + membership | `_resolve_tenant_by_slugs` + Site24x7 **`monitoring_integrations`** match |
| **DB session** | Often **`get_tenant_session`** (RLS) | **`get_auth_session`** — **manual** `tenant_id` on every query/write |
| **Authorization** | RBAC / membership | URL secrecy + rate limit + signature (where wired) |
| **Risk** | Misconfigured route leaks data if tenant not checked | **Wrong URL** or **leaked URL** sends data to wrong workspace; **defense:** slugs + integration ID + HMAC |

---

## 4. Webhooks (design, security, gaps)

### 4.1 URL shape (current target)

```text
/api/v1/webhooks/{org_slug}/{tenant_slug}/<provider>[/<integration_id>]
```

| Provider | Path | Tenant binding |
|----------|------|----------------|
| Site24x7 | `.../{org_slug}/{tenant_slug}/site24x7/{integration_id}` | Slugs → `tenant_id`; **`monitoring_integrations.id`** must belong to same **`tenant_id`**. |
| Generic | `.../{org_slug}/{tenant_slug}/generic` | Slugs only. |
| Prometheus | `.../{org_slug}/{tenant_slug}/prometheus` | Slugs only. |
| Grafana | `.../{org_slug}/{tenant_slug}/grafana` | Slugs only. |
| PagerDuty | `.../{org_slug}/{tenant_slug}/pagerduty` | Slugs only. |

### 4.2 Security layers

| Layer | Site24x7 / Generic | Prometheus / Grafana / PagerDuty |
|-------|---------------------|-----------------------------------|
| Rate limit | Yes | Yes |
| HMAC (`verify_webhook_signature`) | Yes (when `WEBHOOK_SECRET` set) | **Not** on route today — optional parity |
| Tenant isolation | Slugs + integration row for Site24x7 | Slugs only |

### 4.3 Payload vs URL (Site24x7)

- **TAGS** drive cloud discovery (`tag_parser`); **URL tenant** owns the **incident** (authoritative for RLS).
- **Optional product rule:** reject or warn if tag `tenant:` disagrees with path tenant.

### 4.4 Known webhook gaps (product + engineering)

1. **`_build_webhook_path`** in `integrations.py` still returns legacy  
   `/api/v1/webhooks/{integration_type_key}/{integration_id}` — missing **`{org_slug}/{tenant_slug}`** and segment order **`.../site24x7/{id}`**.
2. **`IntegrationsAdminPage.jsx`** copies  
   `/api/v1/webhooks/site24x7/${integration.id}` — does not match server.
3. **Tests** still POST to old paths → **404** until updated.
4. **E2E** (`approval-flow`, `incident-lifecycle`, `admin-workspace`), **`scripts/seed_demo.py`**, **`infra/loadtest/k6_incident_flow.js`** — old paths / DEV tenant only.
5. **Docs** (`docs/api_guide.md`, `docs/site24x7_integration.md`, etc.) — grep for legacy URLs and align.
6. **Tests** (`test_site24x7_integration_webhook_uses_integration_tenant`) — monkeypatch signature and expectations must match **slug-first** tenant + `(session, integration_id, expected_tenant_id)`.

---

## 5. Non-webhook gaps

### 5.1 Worker (ARQ) scheduled tasks

- **`approval_sla_check`** and **`proactive_health_check`** (`services/airex-worker/app/core/worker.py`) use **`settings.DEV_TENANT_ID`** only.
- **Gap:** SLA and proactive health runs **do not** iterate all active tenants (or a configurable tenant list). Multi-org production needs **per-tenant** or **multi-tenant fan-out** with **`get_tenant_session(tenant_id)`** (or equivalent).

### 5.2 SSE (Server-Sent Events)

- **`sse.py`** — `_resolve_tenant` validates JWT if present but **always** returns **`DEV_TENANT_ID`** for the Redis channel. Docstring mentions dev `x_tenant_id`; implementation does **not** derive tenant from JWT claims or query params for the **subscription channel**.
- **Gap:** Dashboard **EventSource** may listen to the **wrong** `tenant:{id}:events` channel in multi-tenant deployments until tenant is resolved from token (or query) consistently with **`fetchAuthMe` / active tenant**.

### 5.3 Unauthenticated API fallback

- **`resolve_active_tenant_id`**: if **`current_user is None`** and no tenant header, returns **`DEV_TENANT_ID`**.
- **Gap:** Any route allowing anonymous access without forcing headers can hit the **dev** tenant — acceptable for local dev; **must** be audited for production exposure.

### 5.4 Frontend

- **`apps/web/src/utils/constants.js`**: **`FALLBACK_TENANT_ID`** = DEV UUID — used when displaying tenant id (e.g. SuperAdmin) if missing.
- **Gap:** Can **mask** missing session data; prefer explicit empty/loading state where possible.

### 5.5 Auth registration bootstrap

- **`auth.py`**: registration may default **`tenant_id`** to **`DEV_TENANT_ID`** when omitted.
- **Gap:** Product may require **invite-only** or **organization-scoped** signup instead of defaulting to dev tenant.

### 5.6 Platform admin sentinel

- **`_PLATFORM_SENTINEL_TENANT_ID`** — same UUID as dev in places; used for platform admin identity in JWT.
- **Requirement:** Any code interpreting **`tenant_id`** must **not** treat sentinel as a customer workspace for RLS customer data.

### 5.7 Tests and coverage

- Many tests and fixtures use **`00000000-0000-0000-0000-000000000000`** — fine for unit isolation.
- **Gap:** Add explicit **multi-org** scenarios (org switch, cross-org denial, webhook slug resolution) so regressions are caught.

### 5.8 Observability and metrics

- Metrics often label **`tenant_id`** — ensure cardinality and privacy policies are acceptable in production.
- **Gap:** Review Prometheus/Grafana dashboards for **single-tenant** assumptions if any.

### 5.9 Misc code notes

- **`webhooks.py`** Site24x7 recovery path may return a **dummy UUID** incident id in edge cases (documented in code for “no active incident”) — clients must not rely on that id as a persisted incident in all branches.
- **Worker** `investigate_incident` tasks receive **`tenant_id`** from enqueueing path — **queue path is correct**; **cron** paths are the main multi-tenant gap.

---

## 6. Schema and product rules

| Rule | Detail |
|------|--------|
| **`tenant_id` nullable** | Banned on domain tables (`docs/database_skill.md`). |
| **`tenants.name` uniqueness** | **Globally unique** today. Same slug under two organizations **not** supported without migration to e.g. **`UNIQUE (organization_id, name)`** and URL/query updates. |
| **Org slug** in webhook URL | Validates tenant belongs to that org via JOIN; **not** a substitute for global uniqueness of `tenant.name` under current schema. |

---

## 7. Documentation inventory

Keep these aligned with **§4** and **§5** when behavior changes:

| Area | Paths |
|------|--------|
| Agent / entry | `CLAUDE.md`, `AGENTS.md`, `README.md` |
| Skills | `docs/backend_skill.md`, `docs/database_skill.md`, `docs/frontend_skill.md`, `.claude/skills/airex-patterns/SKILL.md` |
| Architecture | `docs/architecture.md`, `docs/openclaw_airex_architecture.md`, `docs/CODEMAPS/*.md` |
| API / integration | `docs/api_guide.md`, `docs/site24x7_integration.md`, `docs/tenant-management/TENANT_MANAGEMENT.md` |
| Runbooks | `docs/runbooks/*.md` (e.g. SSH user from tenant DB) |
| Core / config | `services/airex-core/README.md`, `services/airex-core/config/credentials/README.md` |
| **This plan** | `plan.md` (root) |

---

## 8. Workstreams (checklists)

### 8.1 Webhook URL parity (backend + UI)

- [x] Replace **`_build_webhook_path`** with helper that loads **`organizations.slug`** and **`tenants.name`** for the integration’s **`tenant_id`**.
- [x] Return full path: `/api/v1/webhooks/{org_slug}/{tenant_slug}/site24x7/{integration_id}` (and equivalents if other providers get stored paths).
- [x] Update API tests asserting **`webhook_path`** on integration create/list.
- [x] Fix **`IntegrationsAdminPage.jsx`** to use API **`webhook_path`** or compose from context.

### 8.2 Webhook tests and fixtures

- [x] Update `tests/test_api_routes.py`, `tests/test_integration.py` to new paths; use seeded org/tenant slugs or mocks.
- [x] Rewrite **`test_site24x7_integration_webhook_uses_integration_tenant`** for slug-first + new `_resolve_site24x7_integration_context` signature.
- [x] `python3 -m pytest -k webhook` then full `pytest`.

### 8.3 E2E, scripts, load tests

- [x] `e2e/tests/*.spec.js` — webhook URLs and tenant headers.
- [x] `scripts/seed_demo.py`, `infra/loadtest/k6_incident_flow.js`.

### 8.4 Webhook hardening (optional)

- [x] Add **`verify_webhook_signature`** to Prometheus, Grafana, PagerDuty **or** document why not (provider limitations) and compensate (network ACL, private ingress).
- [x] Optional: validate Site24x7 **tag** tenant vs URL tenant.

### 8.5 Documentation sweep

- [x] Grep repo `docs/` for `/webhooks/` without `{org_slug}/{tenant_slug}`; update **`api_guide.md`**, **`site24x7_integration.md`**, runbooks.

### 8.6 Worker multi-tenant crons

- [x] Design: iterate **all active tenants** (or env allowlist) for **`approval_sla_check`** and **`proactive_health_check`**.
- [x] Use **`get_tenant_session`** per tenant; structured logging with **`tenant_id`**; failure isolation per tenant.

### 8.7 SSE

- [x] Resolve the SSE subscription tenant from authenticated session context and active tenant selection instead of `DEV_TENANT_ID`.
- [x] Propagate the active tenant from the frontend SSE client.

### 8.8 Phase 1 admin UX parity

- [x] Add dedicated admin ACL components for org and tenant membership management.
- [x] Implement **`AccessMatrixView.jsx`** for organization roles and per-user tenant access inspection.
- [x] Implement **`TenantAccessDrawer.jsx`** to visualize inherited and explicit tenant access.
- [x] Implement **`TenantMembersPanel.jsx`** for explicit tenant member management.
- [x] Wire the new components into `OrganizationsAdminPage.jsx` and `TenantWorkspaceAdminPage.jsx`.
- [x] Verify org analytics scope toggle behavior with focused frontend tests.

- [ ] Resolve **`tenant_id`** from JWT claims (and/or signed query param) to match **`tenant:{uuid}:events`** for the logged-in user’s active tenant.
- [ ] Update frontend **`EventSource`** URL construction if needed.
- [ ] Remove or gate “single-tenant mode” comments in **`sse.py`** when fixed.

### 8.8 Auth and unauthenticated routes audit

- [ ] Audit routes that allow **`get_current_user`** = None; ensure production does not accidentally rely on **`DEV_TENANT_ID`**.
- [ ] Align registration / invite policy with product.

---

## 9. Verification and release

```text
[ ] database: alembic upgrade head on staging
[ ] GET /auth/me shows expected orgs/tenants for test users
[ ] Tenant switch: X-Active-Tenant-Id + membership → correct tenant RLS
[ ] Webhook: wrong org_slug + correct tenant_slug → 404
[ ] Webhook: correct slugs + integration_id for another tenant → 404
[ ] Admin UI copied webhook URL returns 202 with valid test payload (+ signature if enabled)
[ ] SSE: events for tenant A do not appear when subscribed as tenant B
[ ] Worker crons: SLA / health checks cover intended tenant set (not only DEV)
[ ] pytest + targeted E2E for incident lifecycle and webhooks
```

---

## 10. Code reference map

| Topic | Location |
|------|----------|
| Tenant resolution (API) | `services/airex-api/app/api/dependencies.py` |
| Webhooks | `services/airex-api/app/api/routes/webhooks.py` |
| Integration webhook path | `services/airex-api/app/api/routes/integrations.py` — `_build_webhook_path` |
| Webhook HMAC | `services/airex-core/airex_core/core/webhook_signature.py` |
| SSE | `services/airex-api/app/api/routes/sse.py` |
| Auth / me | `services/airex-api/app/api/routes/auth.py` |
| Worker crons | `services/airex-worker/app/core/worker.py` |
| Models | `services/airex-core/airex_core/models/organization.py`, `tenant.py`, memberships |
| State machine | `services/airex-core/airex_core/core/state_machine.py` |
| Config | `services/airex-core/airex_core/core/config.py` |
| Admin UI webhooks | `apps/web/src/pages/admin/IntegrationsAdminPage.jsx` |
| Frontend tenant fallback | `apps/web/src/utils/constants.js` |

---

## 11. Changelog

| Date | Notes |
|------|--------|
| 2026-03-26 | Initial master plan: multi-org, webhooks, gaps, workstreams |
| 2026-03-26 | Expanded: non-webhook gaps (worker, SSE, auth, frontend, tests), schema rules, doc inventory, verification, code map |
