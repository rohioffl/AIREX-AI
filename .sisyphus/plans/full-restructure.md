# Full Codebase Restructure — Backend (Domain-Driven) + Frontend (Feature-Based) + Deployment

## TL;DR

> **Quick Summary**: Restructure the entire AIREX monorepo into a professional-grade layout: domain-driven Python backend, feature-based React frontend, and organized deployment/infrastructure directories.
> 
> **Deliverables**:
> - Backend reorganized into `domains/`, `integrations/`, `middleware/` with slim `core/`
> - Frontend reorganized into feature-based directories with proper separation
> - Deployment configs organized per-service with clear environment separation
> - All tests passing, Docker builds working, zero behavior changes
> 
> **Estimated Effort**: XL
> **Parallel Execution**: YES - 8 waves
> **Critical Path**: Baseline → Backend domains (sequential) → Frontend → Deployment → Verification

---

## Context

### Original Request
Restructure the whole application to professional level: move Python code to responsible folders, refactor frontend with visual engineering, and organize Docker/deployment for ECS with proper pipelines.

### Interview Summary
**Key Discussions**:
- Backend: 126 Python files in flat layer-based layout → domain-driven design (Netflix Dispatch pattern)
- Frontend: 50+ React files in hybrid feature/type layout → clean feature-based organization
- Deployment: Already has Terraform, CodeBuild, ECS task defs → needs cleaner per-service organization
- Migration: Incremental, one domain at a time, tests between each
- Tests: Mirror structure in tests/

**Changes Already Made** (previous session):
1. `docker-compose.yml` updated to use `services/` Dockerfiles
2. `services/airex-frontend/Dockerfile` created
3. `backend/Dockerfile` removed, root `.dockerignore` created
4. `AGENTS.md` rewritten

### Metis Review
**Critical findings** (all addressed in plan):
- `app/models/__init__.py` is a re-export hub for Alembic — MUST be preserved
- `state_machine.py` has lazy imports to prevent circular deps — MUST stay lazy
- Worker path `app.core.worker.WorkerSettings` is string-referenced in docker-compose — update atomically
- 100% absolute imports, zero dynamic imports — mechanically predictable refactor
- ARQ job names are string-based — function names must NOT change
- `alembic/versions/` files must NEVER be modified

---

## Work Objectives

### Core Objective
Transform the AIREX monorepo from a flat, layer-driven layout into a professional domain-driven architecture while preserving 100% behavioral compatibility.

### Concrete Deliverables
- Backend: `backend/app/domains/` with 7 domain packages
- Backend: `backend/app/integrations/` with cloud, llm, rag adapters
- Backend: `backend/app/middleware/` extracted from main.py
- Backend: Slim `core/` with only infra concerns
- Frontend: Feature-based `src/features/` organization
- Frontend: Shared UI components in `src/components/ui/`
- Deployment: Clear per-service organization
- All tests passing, all Docker builds working

### Definition of Done
- [ ] `cd backend && python -m pytest --tb=short -q` — same pass count as baseline
- [ ] `cd backend && ruff check app/` — zero errors
- [ ] `cd backend && python -c "from app.main import app; print('OK')"` — passes
- [ ] `cd backend && python -c "from app.worker import WorkerSettings; print('OK')"` — passes
- [ ] `cd backend && alembic check` — passes
- [ ] `cd frontend && npm run lint && npm run test && npm run build` — all pass
- [ ] `docker compose build backend worker migrate frontend` — exit 0

### Must Have
- All 126 backend Python files relocated to domain-driven layout
- Frontend components organized by feature
- `app/models/__init__.py` preserved as re-export hub for Alembic
- Lazy imports in state_machine.py remain lazy
- Worker entry point updated atomically with docker-compose

### Must NOT Have (Guardrails)
- DO NOT modify function signatures, return values, or control flow
- DO NOT rename Python functions or classes (only move files + update imports)
- DO NOT touch files in `alembic/versions/`
- DO NOT create new abstractions or utility modules that don't exist today
- DO NOT change HTTP endpoint paths (frontend must not break)
- DO NOT modify database schema (no new migrations)
- DO NOT fix bugs found during the move — file issues, keep moving
- DO NOT add type hints, modernize patterns, or update library versions
- DO NOT restructure tests and source in the same task
- DO NOT modify `deployment/ecs/terraform/` IaC files

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: YES (pytest for backend, vitest for frontend)
- **Automated tests**: Tests-after (verify after each move)
- **Frameworks**: pytest (backend), vitest + RTL (frontend)

### QA Policy
Every task includes agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Backend moves**: `ruff check app/` + `pytest` + import validation
- **Frontend moves**: `npm run lint` + `npm run test` + `npm run build`
- **Deployment**: `docker compose build` verification

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 0 (Foundation — MUST complete first):
├── Task 1: Establish test baseline [quick]
├── Task 2: Create backend directory scaffolding [quick]

Wave 1 (Low-risk extractions — parallel):
├── Task 3: Extract middleware/ from main.py [unspecified-high]
├── Task 4: Move cloud/ → integrations/cloud/ [unspecified-high]
├── Task 5: Move llm/ → integrations/llm/ [quick]
├── Task 6: Move rag/ → integrations/rag/ [quick]

Wave 2 (Domain migrations — sequential, one at a time):
├── Task 7: Create domains/health_check/ [unspecified-high]
├── Task 8: Create domains/auth/ [unspecified-high]
├── Task 9: Create domains/incident/ [deep]
├── Task 10: Create domains/investigation/ [deep]
├── Task 11: Create domains/recommendation/ [deep]
├── Task 12: Create domains/execution/ [unspecified-high]
├── Task 13: Create domains/chat/ [unspecified-high]

Wave 3 (Core cleanup — sequential):
├── Task 14: Slim core/ and create api/router.py [unspecified-high]
├── Task 15: Move worker.py to app root + update docker-compose [unspecified-high]

Wave 4 (Backend verification):
├── Task 16: Full backend verification suite [deep]
├── Task 17: Update backend tests/ to mirror new structure [unspecified-high]

Wave 5 (Frontend restructure — sequential):
├── Task 18: Create frontend feature-based directory structure [visual-engineering]
├── Task 19: Reorganize components into features [visual-engineering]
├── Task 20: Reorganize services, hooks, and utils [visual-engineering]
├── Task 21: Update routing and entry points [visual-engineering]
├── Task 22: Frontend build + test verification [visual-engineering]

Wave 6 (Deployment organization):
├── Task 23: Organize deployment/ per-service structure [unspecified-high]
├── Task 24: Update Dockerfiles and docker-compose for new paths [quick]
├── Task 25: Verify all Docker builds [quick]

Wave FINAL (After ALL tasks — independent review):
├── Task F1: Plan compliance audit [deep]
├── Task F2: Code quality review [unspecified-high]
├── Task F3: Full QA — Playwright for frontend, curl for API [unspecified-high]
├── Task F4: Scope fidelity check [deep]

Critical Path: T1 → T2 → T3-6 → T7-13 (sequential) → T14-15 → T16-17 → T18-22 → T23-25 → F1-F4
Max Concurrent: 4 (Wave 1)
```

### Dependency Matrix

| Task | Depends On | Blocks |
|------|-----------|--------|
| 1 | — | 2-25 |
| 2 | 1 | 3-6 |
| 3-6 | 2 | 7 |
| 7 | 3-6 | 8 |
| 8 | 7 | 9 |
| 9 | 8 | 10 |
| 10 | 9 | 11 |
| 11 | 10 | 12 |
| 12 | 11 | 13 |
| 13 | 12 | 14 |
| 14 | 13 | 15 |
| 15 | 14 | 16 |
| 16 | 15 | 17 |
| 17 | 16 | 18 |
| 18 | 17 | 19 |
| 19 | 18 | 20 |
| 20 | 19 | 21 |
| 21 | 20 | 22 |
| 22 | 21 | 23 |
| 23 | 22 | 24 |
| 24 | 23 | 25 |
| 25 | 24 | F1-F4 |
| F1-F4 | 25 | — |

### Agent Dispatch Summary

- **Wave 0**: T1 → `quick`, T2 → `quick`
- **Wave 1**: T3 → `unspecified-high`, T4 → `unspecified-high`, T5 → `quick`, T6 → `quick`
- **Wave 2**: T7-T8 → `unspecified-high`, T9-T11 → `deep`, T12-T13 → `unspecified-high`
- **Wave 3**: T14-T15 → `unspecified-high`
- **Wave 4**: T16 → `deep`, T17 → `unspecified-high`
- **Wave 5**: T18-T22 → `visual-engineering` + skills: `[frontend-ui-ux]`
- **Wave 6**: T23 → `unspecified-high`, T24-T25 → `quick`
- **FINAL**: F1 → `deep`, F2 → `unspecified-high`, F3 → `unspecified-high` + skills: `[playwright]`, F4 → `deep`

---

## TODOs

- [ ] 1. Establish test baseline and document current state

  **What to do**:
  - Run `cd backend && python -m pytest --tb=line -q 2>&1 | tail -5` and record exact pass/fail count
  - Run `cd backend && ruff check app/ 2>&1 | tail -5` and record current lint state
  - Run `cd frontend && npm run test -- --run 2>&1 | tail -10` and record pass/fail count
  - Run `cd frontend && npm run build 2>&1 | tail -5` and record build status
  - Save all baselines to `.sisyphus/evidence/task-1-baseline.txt`
  - Run `cd backend && python -c "from app.main import app; from app.core.worker import WorkerSettings; print('OK')"` to verify current imports work

  **Must NOT do**:
  - Do not modify any files
  - Do not install dependencies

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 0
  - **Blocks**: All subsequent tasks
  - **Blocked By**: None

  **References**:
  - `backend/pytest.ini` — test configuration
  - `frontend/package.json` — test scripts
  - `backend/app/main.py` — FastAPI entry point
  - `backend/app/core/worker.py` — ARQ entry point

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Baseline captured successfully
    Tool: Bash
    Steps:
      1. Run: cd backend && python -m pytest --tb=line -q 2>&1 | tail -5
      2. Record output as BACKEND_TEST_BASELINE
      3. Run: cd frontend && npm run test -- --run 2>&1 | tail -10
      4. Record output as FRONTEND_TEST_BASELINE
      5. Save both to .sisyphus/evidence/task-1-baseline.txt
    Expected Result: File exists with both baselines recorded
    Evidence: .sisyphus/evidence/task-1-baseline.txt
  ```

  **Commit**: NO

- [ ] 2. Create backend directory scaffolding (empty __init__.py files)

  **What to do**:
  - Create these new directories with empty `__init__.py` files:
    - `backend/app/domains/__init__.py`
    - `backend/app/domains/incident/__init__.py`
    - `backend/app/domains/investigation/__init__.py`
    - `backend/app/domains/recommendation/__init__.py`
    - `backend/app/domains/execution/__init__.py`
    - `backend/app/domains/chat/__init__.py`
    - `backend/app/domains/health_check/__init__.py`
    - `backend/app/domains/auth/__init__.py`
    - `backend/app/middleware/__init__.py`
    - `backend/app/integrations/__init__.py`
    - `backend/app/integrations/cloud/__init__.py`
    - `backend/app/integrations/cloud/aws/__init__.py`
    - `backend/app/integrations/cloud/gcp/__init__.py`
    - `backend/app/integrations/llm/__init__.py`
    - `backend/app/integrations/rag/__init__.py`
  - Verify existing tests still pass after adding empty packages

  **Must NOT do**:
  - Do not move any existing files
  - Do not modify any existing files

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 0 (after Task 1)
  - **Blocks**: Tasks 3-6
  - **Blocked By**: Task 1

  **References**:
  - `backend/app/__init__.py` — existing package init pattern
  - Target structure from plan Context section

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: All new directories created with __init__.py
    Tool: Bash
    Steps:
      1. Run: test -f backend/app/domains/__init__.py && echo "PASS" || echo "FAIL"
      2. Run: test -f backend/app/domains/incident/__init__.py && echo "PASS" || echo "FAIL"
      3. Run: test -f backend/app/middleware/__init__.py && echo "PASS" || echo "FAIL"
      4. Run: test -f backend/app/integrations/cloud/aws/__init__.py && echo "PASS" || echo "FAIL"
      5. Run: cd backend && python -m pytest --tb=short -q 2>&1 | tail -3
      6. Assert: same pass count as baseline
    Expected Result: All dirs exist, tests unchanged
    Evidence: .sisyphus/evidence/task-2-scaffolding.txt
  ```

  **Commit**: YES
  - Message: `chore(backend): create domain-driven directory scaffolding`
  - Files: All new `__init__.py` files

- [ ] 3. Extract middleware/ from main.py

  **What to do**:
  - Read `backend/app/main.py` to identify all middleware registrations
  - Create individual middleware modules:
    - `backend/app/middleware/cors.py` — CORS middleware config
    - `backend/app/middleware/csrf.py` — Move from `core/csrf.py`
    - `backend/app/middleware/rate_limit.py` — Move from `core/rate_limit.py`
    - `backend/app/middleware/metrics.py` — Move from `core/metrics.py` (Prometheus middleware)
  - Update `main.py` to import from `app.middleware.*` instead of `app.core.*`
  - Update all files that import from old locations to use new paths
  - Use `rg "from app.core.csrf" backend/` etc. to find all consumers BEFORE moving

  **Must NOT do**:
  - Do not change middleware logic or configuration
  - Do not change the order middleware is registered in main.py
  - Do not modify core/config.py, core/database.py, or core/security.py

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 4, 5, 6)
  - **Blocks**: Task 7
  - **Blocked By**: Task 2

  **References**:
  - `backend/app/main.py` — middleware registration (lines with `app.add_middleware`)
  - `backend/app/core/csrf.py` — CSRF middleware implementation
  - `backend/app/core/rate_limit.py` — rate limiting implementation
  - `backend/app/core/metrics.py` — Prometheus metrics middleware

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Middleware extracted and imports updated
    Tool: Bash
    Steps:
      1. Run: test -f backend/app/middleware/cors.py && echo "PASS" || echo "FAIL"
      2. Run: test -f backend/app/middleware/csrf.py && echo "PASS" || echo "FAIL"
      3. Run: rg "from app.core.csrf" backend/app/ --count-matches
      4. Assert: 0 matches (all updated to app.middleware.csrf)
      5. Run: cd backend && ruff check app/ 2>&1 | tail -3
      6. Run: cd backend && python -m pytest --tb=short -q 2>&1 | tail -3
      7. Assert: same pass count as baseline
    Expected Result: Middleware in new location, zero stale imports, tests pass
    Evidence: .sisyphus/evidence/task-3-middleware-extracted.txt

  Scenario: main.py still loads correctly
    Tool: Bash
    Steps:
      1. Run: cd backend && python -c "from app.main import app; print('OK')"
    Expected Result: "OK" printed without errors
    Evidence: .sisyphus/evidence/task-3-main-import.txt
  ```

  **Commit**: YES
  - Message: `refactor(backend): extract middleware into dedicated package`
  - Files: `backend/app/middleware/*.py`, `backend/app/main.py`, deleted `backend/app/core/csrf.py`, `backend/app/core/rate_limit.py`, `backend/app/core/metrics.py`

- [ ] 4. Move cloud/ → integrations/cloud/ (split by provider)

  **What to do**:
  - Use `rg "from app.cloud" backend/` to find ALL consumers of cloud modules
  - Move AWS files: `backend/app/cloud/aws_*.py` → `backend/app/integrations/cloud/aws/`
  - Move GCP files: `backend/app/cloud/gcp_*.py` → `backend/app/integrations/cloud/gcp/`
  - Move shared files: `backend/app/cloud/discovery.py`, `diagnostics.py`, `tag_parser.py`, `ssh_user_resolver.py`, `tenant_config.py` → `backend/app/integrations/cloud/`
  - Update ALL import paths across the codebase (app.cloud.aws_ssm → app.integrations.cloud.aws.aws_ssm)
  - Preserve `backend/app/cloud/__init__.py` as re-export hub if needed for compatibility
  - Run `ruff check` and `pytest` after completion

  **Must NOT do**:
  - Do not modify any function logic inside cloud modules
  - Do not rename any functions or classes

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 3, 5, 6)
  - **Blocks**: Task 7
  - **Blocked By**: Task 2

  **References**:
  - `backend/app/cloud/` — 18 files: aws_auth, aws_autoscaling, aws_cloudtrail, aws_logs, aws_ssh, aws_ssm, aws_vpc_flows, gcp_audit, gcp_logging, gcp_mig, gcp_ssh, gcp_vpc_flows, diagnostics, discovery, ssh_user_resolver, tag_parser, tenant_config, __init__
  - `backend/app/investigations/` — primary consumers of cloud modules (probes call cloud APIs)
  - `backend/app/services/investigation_service.py` — orchestrates cloud probe calls

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Cloud modules moved and all imports updated
    Tool: Bash
    Steps:
      1. Run: test -d backend/app/integrations/cloud/aws && echo "PASS" || echo "FAIL"
      2. Run: test -d backend/app/integrations/cloud/gcp && echo "PASS" || echo "FAIL"
      3. Run: rg "from app\.cloud\." backend/app/ --count-matches | grep -v __pycache__
      4. Assert: 0 matches (all updated to app.integrations.cloud.*)
      5. Run: cd backend && ruff check app/ 2>&1 | tail -3
      6. Run: cd backend && python -m pytest --tb=short -q 2>&1 | tail -3
      7. Assert: same pass count as baseline
    Expected Result: All cloud files in integrations/cloud/, zero stale imports
    Evidence: .sisyphus/evidence/task-4-cloud-moved.txt
  ```

  **Commit**: YES
  - Message: `refactor(backend): move cloud integrations to integrations/cloud/`
  - Files: All moved cloud files, all updated import files

- [ ] 5. Move llm/ → integrations/llm/

  **What to do**:
  - Use `rg "from app.llm" backend/` to find ALL consumers
  - Move `backend/app/llm/client.py`, `prompts.py`, `embeddings.py`, `__init__.py` → `backend/app/integrations/llm/`
  - Update ALL import paths (app.llm.client → app.integrations.llm.client)
  - Run `ruff check` and `pytest`

  **Must NOT do**:
  - Do not modify LiteLLM client logic
  - Do not change prompt templates

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 3, 4, 6)
  - **Blocks**: Task 7
  - **Blocked By**: Task 2

  **References**:
  - `backend/app/llm/` — 4 files: client.py, prompts.py, embeddings.py, __init__.py
  - `backend/app/services/recommendation_service.py` — primary consumer of llm.client
  - `backend/app/services/incident_embedding_service.py` — uses llm.embeddings

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: LLM module moved and imports updated
    Tool: Bash
    Steps:
      1. Run: test -f backend/app/integrations/llm/client.py && echo "PASS" || echo "FAIL"
      2. Run: rg "from app\.llm\." backend/app/ --count-matches | grep -v __pycache__
      3. Assert: 0 matches
      4. Run: cd backend && python -m pytest --tb=short -q 2>&1 | tail -3
    Expected Result: LLM in new location, zero stale imports, tests pass
    Evidence: .sisyphus/evidence/task-5-llm-moved.txt
  ```

  **Commit**: YES
  - Message: `refactor(backend): move llm to integrations/llm/`
  - Files: Moved llm files, updated import files

- [ ] 6. Move rag/ → integrations/rag/

  **What to do**:
  - Use `rg "from app.rag" backend/` to find ALL consumers
  - Move `backend/app/rag/chunker.py`, `vector_store.py`, `__init__.py` → `backend/app/integrations/rag/`
  - Update ALL import paths
  - Run `ruff check` and `pytest`

  **Must NOT do**:
  - Do not modify RAG logic

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 3, 4, 5)
  - **Blocks**: Task 7
  - **Blocked By**: Task 2

  **References**:
  - `backend/app/rag/` — 3 files: chunker.py, vector_store.py, __init__.py
  - `backend/app/services/recommendation_service.py` — uses rag_context for RAG enrichment

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: RAG module moved and imports updated
    Tool: Bash
    Steps:
      1. Run: test -f backend/app/integrations/rag/vector_store.py && echo "PASS" || echo "FAIL"
      2. Run: rg "from app\.rag\." backend/app/ --count-matches | grep -v __pycache__
      3. Assert: 0 matches
      4. Run: cd backend && python -m pytest --tb=short -q 2>&1 | tail -3
    Expected Result: RAG in new location, zero stale imports, tests pass
    Evidence: .sisyphus/evidence/task-6-rag-moved.txt
  ```

  **Commit**: YES
  - Message: `refactor(backend): move rag to integrations/rag/`
  - Files: Moved rag files, updated import files

- [ ] 7. Create domains/health_check/ (smallest domain — proof of concept)

  **What to do**:
  - Move `backend/app/services/health_check_service.py` → `backend/app/domains/health_check/service.py`
  - Move `backend/app/api/routes/health_checks.py` → `backend/app/domains/health_check/router.py`
  - Move `backend/app/models/health_check.py` → `backend/app/domains/health_check/models.py`
  - If schemas exist for health checks, move to `backend/app/domains/health_check/schemas.py`
  - Update `app/models/__init__.py` to re-export HealthCheck model from new location (preserve Alembic compatibility)
  - Update `app/api/routes/__init__.py` to import router from new location
  - Update `main.py` router registration if needed
  - Use `rg "from app.services.health_check" backend/` to find all consumers BEFORE moving
  - Use `rg "from app.api.routes.health_checks" backend/` to find all consumers
  - Run `ruff check` and `pytest` after all moves

  **Must NOT do**:
  - Do not modify health check logic
  - Do not remove the re-export from `app/models/__init__.py`

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (sequential)
  - **Blocks**: Task 8
  - **Blocked By**: Tasks 3-6

  **References**:
  - `backend/app/services/health_check_service.py` — health check business logic
  - `backend/app/api/routes/health_checks.py` — health check API endpoints
  - `backend/app/models/health_check.py` — health check ORM model
  - `backend/app/models/__init__.py` — model re-export hub (MUST preserve)

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Health check domain created with all files
    Tool: Bash
    Steps:
      1. Run: test -f backend/app/domains/health_check/service.py && echo "PASS" || echo "FAIL"
      2. Run: test -f backend/app/domains/health_check/router.py && echo "PASS" || echo "FAIL"
      3. Run: test -f backend/app/domains/health_check/models.py && echo "PASS" || echo "FAIL"
      4. Run: cd backend && python -c "from app.models import HealthCheck; print('Alembic compat OK')"
      5. Run: rg "from app\.services\.health_check" backend/app/ --count-matches | grep -v __pycache__
      6. Assert: 0 matches (all updated)
      7. Run: cd backend && ruff check app/ 2>&1 | tail -3
      8. Run: cd backend && python -m pytest --tb=short -q 2>&1 | tail -3
      9. Assert: same pass count as baseline
    Expected Result: Domain created, Alembic compat preserved, tests pass
    Evidence: .sisyphus/evidence/task-7-health-check-domain.txt
  ```

  **Commit**: YES
  - Message: `refactor(backend): migrate health_check to domains/health_check/`
  - Files: Moved files, updated imports, updated models/__init__.py

- [ ] 8. Create domains/auth/ (users, tenants, RBAC, security)

  **What to do**:
  - Move `backend/app/api/routes/auth.py` → `backend/app/domains/auth/router.py`
  - Move `backend/app/api/routes/users.py` → `backend/app/domains/auth/users_router.py`
  - Move `backend/app/api/routes/tenants.py` → `backend/app/domains/auth/tenants_router.py`
  - Move `backend/app/models/user.py` → `backend/app/domains/auth/models.py`
  - Move `backend/app/models/tenant_limit.py` → `backend/app/domains/auth/tenant_limit_models.py`
  - Move `backend/app/core/rbac.py` → `backend/app/domains/auth/rbac.py`
  - Move `backend/app/core/tenant_limits.py` → `backend/app/domains/auth/tenant_limits.py`
  - If auth-related schemas exist, move to domain
  - Update `app/models/__init__.py` re-exports
  - Update ALL import paths using `rg` to find consumers first
  - Run `ruff check` and `pytest`

  **Must NOT do**:
  - Do not modify auth/RBAC logic
  - Do not change JWT handling or security utilities in `core/security.py` (those stay in core/)
  - Do not remove model re-exports from `app/models/__init__.py`

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (after Task 7)
  - **Blocks**: Task 9
  - **Blocked By**: Task 7

  **References**:
  - `backend/app/api/routes/auth.py` — login, token refresh endpoints
  - `backend/app/api/routes/users.py` — user management endpoints
  - `backend/app/api/routes/tenants.py` — tenant management endpoints
  - `backend/app/models/user.py` — User ORM model
  - `backend/app/core/rbac.py` — role-based access control
  - `backend/app/core/tenant_limits.py` — tenant rate/quota limiting
  - `backend/app/api/dependencies.py` — imports RBAC decorators (update import path)

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Auth domain created with all files
    Tool: Bash
    Steps:
      1. Run: test -f backend/app/domains/auth/router.py && echo "PASS" || echo "FAIL"
      2. Run: test -f backend/app/domains/auth/rbac.py && echo "PASS" || echo "FAIL"
      3. Run: cd backend && python -c "from app.models import User; print('Alembic compat OK')"
      4. Run: rg "from app\.core\.rbac" backend/app/ --count-matches | grep -v __pycache__
      5. Assert: 0 matches
      6. Run: cd backend && python -m pytest --tb=short -q 2>&1 | tail -3
      7. Assert: same pass count as baseline
    Expected Result: Auth domain created, all imports updated, tests pass
    Evidence: .sisyphus/evidence/task-8-auth-domain.txt
  ```

  **Commit**: YES
  - Message: `refactor(backend): migrate auth, users, tenants to domains/auth/`
  - Files: Moved files, updated imports

- [ ] 9. Create domains/incident/ (HIGHEST RISK — state machine, models, service)

  **What to do**:
  - Move `backend/app/core/state_machine.py` → `backend/app/domains/incident/state_machine.py`
  - Move `backend/app/services/incident_service.py` → `backend/app/domains/incident/service.py`
  - Move `backend/app/services/incident_embedding_service.py` → `backend/app/domains/incident/embedding_service.py`
  - Move `backend/app/services/notification_service.py` → `backend/app/domains/incident/notification_service.py`
  - Move `backend/app/services/correlation_service.py` → `backend/app/domains/incident/correlation_service.py`
  - Move `backend/app/services/resolution_service.py` → `backend/app/domains/incident/resolution_service.py`
  - Move `backend/app/api/routes/incidents.py` → `backend/app/domains/incident/router.py`
  - Move `backend/app/api/routes/sse.py` → `backend/app/domains/incident/sse_router.py`
  - Move `backend/app/api/routes/webhooks.py` → `backend/app/domains/incident/webhooks_router.py`
  - Move `backend/app/models/incident.py` → `backend/app/domains/incident/models.py`
  - Move `backend/app/models/evidence.py` → `backend/app/domains/incident/evidence_models.py`
  - Move `backend/app/models/incident_lock.py` → `backend/app/domains/incident/lock_models.py`
  - Move `backend/app/models/incident_embedding.py` → `backend/app/domains/incident/embedding_models.py`
  - Move relevant schemas to `backend/app/domains/incident/schemas.py`
  - **CRITICAL**: Keep ALL lazy imports in state_machine.py as lazy — only update the import paths
  - Update `app/models/__init__.py` re-exports for ALL moved models
  - Use `rg "from app.core.state_machine" backend/` — expect 11+ consumers, update ALL
  - Use `rg "from app.services.incident_service" backend/` — update ALL
  - Run `ruff check` and `pytest` after ALL moves

  **Must NOT do**:
  - Do not modify state machine transition logic
  - Do not hoist lazy imports to module level
  - Do not rename any functions (ARQ job names depend on function names)
  - Do not modify the hash chain audit logic
  - Do not remove model re-exports from `app/models/__init__.py`

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (after Task 8)
  - **Blocks**: Task 10
  - **Blocked By**: Task 8

  **References**:
  - `backend/app/core/state_machine.py` — 11+ consumers, lazy imports at lines 108, 159, 173, 190, 202, 217
  - `backend/app/services/incident_service.py` — core CRUD operations
  - `backend/app/models/incident.py` — Incident ORM model (most-referenced model)
  - `backend/app/core/events.py` — SSE event system (consumed by state machine)
  - `backend/app/core/worker.py` — references state_machine for task orchestration

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Incident domain created — highest risk migration
    Tool: Bash
    Steps:
      1. Run: test -f backend/app/domains/incident/state_machine.py && echo "PASS" || echo "FAIL"
      2. Run: test -f backend/app/domains/incident/service.py && echo "PASS" || echo "FAIL"
      3. Run: test -f backend/app/domains/incident/router.py && echo "PASS" || echo "FAIL"
      4. Run: cd backend && python -c "from app.models import Incident, Evidence; print('Alembic compat OK')"
      5. Run: rg "from app\.core\.state_machine" backend/app/ --count-matches | grep -v __pycache__
      6. Assert: 0 matches (all updated to app.domains.incident.state_machine)
      7. Run: rg "from app\.services\.incident_service" backend/app/ --count-matches | grep -v __pycache__
      8. Assert: 0 matches
      9. Run: cd backend && ruff check app/ 2>&1 | tail -5
      10. Run: cd backend && python -m pytest --tb=short -q 2>&1 | tail -3
      11. Assert: same pass count as baseline
    Expected Result: All incident files migrated, zero stale imports, tests pass
    Evidence: .sisyphus/evidence/task-9-incident-domain.txt

  Scenario: Lazy imports preserved in state_machine.py
    Tool: Bash
    Steps:
      1. Run: rg "def transition_state" backend/app/domains/incident/state_machine.py -A 30
      2. Visually confirm: imports inside function bodies, not at module level
    Expected Result: All lazy imports remain inside functions
    Evidence: .sisyphus/evidence/task-9-lazy-imports.txt
  ```

  **Commit**: YES
  - Message: `refactor(backend): migrate incident domain (state machine, services, routes, models)`
  - Files: All moved incident files, all updated imports

- [ ] 10. Create domains/investigation/ (probes + service)

  **What to do**:
  - Move `backend/app/investigations/*.py` → `backend/app/domains/investigation/probes/` (all probe files)
  - Move `backend/app/investigations/base.py` → `backend/app/domains/investigation/probes/base.py`
  - Move `backend/app/investigations/probe_map.py` → `backend/app/domains/investigation/probe_map.py`
  - Move `backend/app/services/investigation_service.py` → `backend/app/domains/investigation/service.py`
  - Move `backend/app/services/anomaly_detector.py` → `backend/app/domains/investigation/anomaly_detector.py`
  - Move `backend/app/services/pattern_analysis.py` → `backend/app/domains/investigation/pattern_analysis.py`
  - Update ALL import paths using `rg` first
  - Run `ruff check` and `pytest`

  **Must NOT do**:
  - Do not modify probe logic or registry patterns
  - Do not change the INVESTIGATION_REGISTRY mapping

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (after Task 9)
  - **Blocks**: Task 11
  - **Blocked By**: Task 9

  **References**:
  - `backend/app/investigations/` — 14 probe files + base.py + probe_map.py + __init__.py
  - `backend/app/services/investigation_service.py` — orchestrates probes
  - `backend/app/core/worker.py` — calls investigation_service.investigate()

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Investigation domain created
    Tool: Bash
    Steps:
      1. Run: test -d backend/app/domains/investigation/probes && echo "PASS" || echo "FAIL"
      2. Run: test -f backend/app/domains/investigation/service.py && echo "PASS" || echo "FAIL"
      3. Run: rg "from app\.investigations\." backend/app/ --count-matches | grep -v __pycache__
      4. Assert: 0 matches
      5. Run: rg "from app\.services\.investigation_service" backend/app/ --count-matches | grep -v __pycache__
      6. Assert: 0 matches
      7. Run: cd backend && python -m pytest --tb=short -q 2>&1 | tail -3
      8. Assert: same pass count as baseline
    Expected Result: Investigation domain created, zero stale imports, tests pass
    Evidence: .sisyphus/evidence/task-10-investigation-domain.txt
  ```

  **Commit**: YES
  - Message: `refactor(backend): migrate investigation domain (probes, service)`
  - Files: All moved investigation files, all updated imports

- [ ] 11. Create domains/recommendation/ (LLM analysis, policy, RAG context)

  **What to do**:
  - Move `backend/app/services/recommendation_service.py` → `backend/app/domains/recommendation/service.py`
  - Move `backend/app/services/rag_context.py` → `backend/app/domains/recommendation/rag_context.py`
  - Move `backend/app/services/runbook_generator.py` → `backend/app/domains/recommendation/runbook_generator.py`
  - Move `backend/app/core/policy.py` → `backend/app/domains/recommendation/policy.py`
  - Move `backend/app/models/runbook_chunk.py` → `backend/app/domains/recommendation/models.py`
  - Move relevant schemas to domain
  - Update `app/models/__init__.py` re-exports
  - Update ALL import paths using `rg` first
  - Run `ruff check` and `pytest`

  **Must NOT do**:
  - Do not modify recommendation/policy logic
  - Do not change LLM prompt templates (those stay in integrations/llm/)
  - Do not remove model re-exports from `app/models/__init__.py`

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (after Task 10)
  - **Blocks**: Task 12
  - **Blocked By**: Task 10

  **References**:
  - `backend/app/services/recommendation_service.py` — LLM recommendation orchestration
  - `backend/app/services/rag_context.py` — RAG context enrichment for prompts
  - `backend/app/core/policy.py` — auto-approval and risk policy evaluation
  - `backend/app/core/worker.py` — calls recommendation_service.recommend()

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Recommendation domain created
    Tool: Bash
    Steps:
      1. Run: test -f backend/app/domains/recommendation/service.py && echo "PASS" || echo "FAIL"
      2. Run: test -f backend/app/domains/recommendation/policy.py && echo "PASS" || echo "FAIL"
      3. Run: rg "from app\.services\.recommendation_service" backend/app/ --count-matches | grep -v __pycache__
      4. Assert: 0 matches
      5. Run: rg "from app\.core\.policy" backend/app/ --count-matches | grep -v __pycache__
      6. Assert: 0 matches
      7. Run: cd backend && python -m pytest --tb=short -q 2>&1 | tail -3
      8. Assert: same pass count as baseline
    Expected Result: Recommendation domain created, zero stale imports, tests pass
    Evidence: .sisyphus/evidence/task-11-recommendation-domain.txt
  ```

  **Commit**: YES
  - Message: `refactor(backend): migrate recommendation domain (service, policy, RAG context)`
  - Files: All moved recommendation files, all updated imports

- [ ] 12. Create domains/execution/ (actions + service + registry)

  **What to do**:
  - Move `backend/app/actions/*.py` → `backend/app/domains/execution/actions/` (all action files)
  - Move `backend/app/actions/base.py` → `backend/app/domains/execution/actions/base.py`
  - Move `backend/app/actions/registry.py` → `backend/app/domains/execution/registry.py`
  - Move `backend/app/services/execution_service.py` → `backend/app/domains/execution/service.py`
  - Move `backend/app/services/verification_service.py` → `backend/app/domains/execution/verification_service.py`
  - Move `backend/app/services/fallback_service.py` → `backend/app/domains/execution/fallback_service.py`
  - Update ALL import paths using `rg` first
  - Run `ruff check` and `pytest`

  **Must NOT do**:
  - Do not modify action logic or the ACTION_REGISTRY
  - Do not rename action functions

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (after Task 11)
  - **Blocks**: Task 13
  - **Blocked By**: Task 11

  **References**:
  - `backend/app/actions/` — 15 action files: restart_service, scale_instances, drain_node, etc.
  - `backend/app/actions/registry.py` — ACTION_REGISTRY static dict
  - `backend/app/services/execution_service.py` — executes approved actions
  - `backend/app/core/worker.py` — calls execution_service.execute()

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Execution domain created
    Tool: Bash
    Steps:
      1. Run: test -d backend/app/domains/execution/actions && echo "PASS" || echo "FAIL"
      2. Run: test -f backend/app/domains/execution/registry.py && echo "PASS" || echo "FAIL"
      3. Run: test -f backend/app/domains/execution/service.py && echo "PASS" || echo "FAIL"
      4. Run: rg "from app\.actions\." backend/app/ --count-matches | grep -v __pycache__
      5. Assert: 0 matches
      6. Run: rg "from app\.services\.execution_service" backend/app/ --count-matches | grep -v __pycache__
      7. Assert: 0 matches
      8. Run: cd backend && python -m pytest --tb=short -q 2>&1 | tail -3
      9. Assert: same pass count as baseline
    Expected Result: Execution domain created, zero stale imports, tests pass
    Evidence: .sisyphus/evidence/task-12-execution-domain.txt
  ```

  **Commit**: YES
  - Message: `refactor(backend): migrate execution domain (actions, service, registry)`
  - Files: All moved execution files, all updated imports

- [ ] 13. Create domains/chat/ (chat service + DLQ)

  **What to do**:
  - Move `backend/app/services/chat_service.py` → `backend/app/domains/chat/service.py`
  - Move `backend/app/api/routes/chat.py` → `backend/app/domains/chat/router.py`
  - Move `backend/app/api/routes/dlq.py` → `backend/app/domains/chat/dlq_router.py`
  - Move relevant schemas to domain
  - Update ALL import paths using `rg` first
  - Run `ruff check` and `pytest`

  **Must NOT do**:
  - Do not modify chat or DLQ logic

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (after Task 12)
  - **Blocks**: Task 14
  - **Blocked By**: Task 12

  **References**:
  - `backend/app/services/chat_service.py` — chat business logic
  - `backend/app/api/routes/chat.py` — chat API endpoints
  - `backend/app/api/routes/dlq.py` — dead letter queue management

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Chat domain created
    Tool: Bash
    Steps:
      1. Run: test -f backend/app/domains/chat/service.py && echo "PASS" || echo "FAIL"
      2. Run: test -f backend/app/domains/chat/router.py && echo "PASS" || echo "FAIL"
      3. Run: rg "from app\.services\.chat_service" backend/app/ --count-matches | grep -v __pycache__
      4. Assert: 0 matches
      5. Run: cd backend && python -m pytest --tb=short -q 2>&1 | tail -3
      6. Assert: same pass count as baseline
    Expected Result: Chat domain created, zero stale imports, tests pass
    Evidence: .sisyphus/evidence/task-13-chat-domain.txt
  ```

  **Commit**: YES
  - Message: `refactor(backend): migrate chat domain (service, router, DLQ)`
  - Files: All moved chat files, all updated imports

- [ ] 14. Slim core/ and create api/router.py aggregator

  **What to do**:
  - Verify `backend/app/core/` now contains ONLY these infra files: `config.py`, `database.py`, `security.py`, `logging.py`, `events.py`, `webhook_signature.py`, `retry_scheduler.py`, `__init__.py`
  - Delete empty/orphaned files from old `app/core/` that were moved (csrf, rate_limit, metrics, rbac, tenant_limits, policy, state_machine)
  - Create `backend/app/api/router.py` that aggregates all domain routers into a single APIRouter
  - Update `main.py` to import from `app.api.router` instead of individual route modules
  - Move `backend/app/api/routes/settings.py` and `backend/app/api/routes/metrics.py` to appropriate locations if not already moved
  - Clean up `backend/app/api/routes/` — it should be mostly empty after domain migrations
  - Remove empty `backend/app/services/` directory if all services have been moved
  - Remove empty `backend/app/actions/` directory if all actions have been moved
  - Remove empty `backend/app/investigations/` directory if all probes have been moved
  - Run `ruff check` and `pytest`

  **Must NOT do**:
  - Do not remove `core/config.py`, `core/database.py`, `core/security.py`, `core/logging.py`
  - Do not modify core infrastructure logic
  - Do not remove `app/models/__init__.py` (Alembic needs it)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 15
  - **Blocked By**: Task 13

  **References**:
  - `backend/app/main.py` — current router registration pattern
  - `backend/app/api/routes/__init__.py` — current route aggregation
  - All domain router files created in Tasks 7-13

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Core slimmed and API router aggregator created
    Tool: Bash
    Steps:
      1. Run: ls backend/app/core/*.py | wc -l
      2. Assert: ~8 files (config, database, security, logging, events, webhook_signature, retry_scheduler, __init__)
      3. Run: test -f backend/app/api/router.py && echo "PASS" || echo "FAIL"
      4. Run: test ! -d backend/app/services || [ -z "$(ls backend/app/services/*.py 2>/dev/null | grep -v __init__)" ] && echo "PASS" || echo "FAIL"
      5. Run: cd backend && python -c "from app.main import app; print('OK')"
      6. Run: cd backend && ruff check app/ 2>&1 | tail -3
      7. Run: cd backend && python -m pytest --tb=short -q 2>&1 | tail -3
      8. Assert: same pass count as baseline
    Expected Result: Core is slim, empty dirs cleaned, API router works, tests pass
    Evidence: .sisyphus/evidence/task-14-core-slim.txt
  ```

  **Commit**: YES
  - Message: `refactor(backend): slim core, create API router aggregator, clean empty dirs`
  - Files: Updated core/, api/router.py, main.py, removed empty dirs

- [ ] 15. Move worker.py to app root + update docker-compose

  **What to do**:
  - Move `backend/app/core/worker.py` → `backend/app/worker.py`
  - Update ALL imports of `app.core.worker` to `app.worker`
  - Use `rg "app.core.worker" .` (repo-wide, not just backend/) to find ALL references including docker-compose, scripts, docs
  - Update `docker-compose.yml` worker service command: `arq app.core.worker.WorkerSettings` → `arq app.worker.WorkerSettings`
  - Check `infrastructure/docker-compose.dev.yml` for similar references
  - Check `deployment/ecs/task-definitions/airex-worker.json` for command references
  - Check `AGENTS.md` for documentation references
  - Run `ruff check` and `pytest`
  - Run `docker compose build worker` to verify

  **Must NOT do**:
  - Do not rename WorkerSettings class or any task functions
  - Do not change worker task logic
  - Do not modify ARQ function names (string-referenced in enqueue_job calls)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (after Task 14)
  - **Blocks**: Task 16
  - **Blocked By**: Task 14

  **References**:
  - `backend/app/core/worker.py` — ARQ WorkerSettings and task definitions
  - `docker-compose.yml` line 63 — `arq app.core.worker.WorkerSettings`
  - `infrastructure/docker-compose.dev.yml` — may reference worker path
  - `deployment/ecs/task-definitions/airex-worker.json` — ECS task command
  - `AGENTS.md` — documentation references to worker

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Worker moved and all references updated
    Tool: Bash
    Steps:
      1. Run: test -f backend/app/worker.py && echo "PASS" || echo "FAIL"
      2. Run: test ! -f backend/app/core/worker.py && echo "PASS" || echo "FAIL"
      3. Run: rg "app\.core\.worker" . --count-matches | grep -v __pycache__ | grep -v .git
      4. Assert: 0 matches across entire repo
      5. Run: cd backend && python -c "from app.worker import WorkerSettings; print('OK')"
      6. Run: cd backend && python -m pytest --tb=short -q 2>&1 | tail -3
      7. Assert: same pass count as baseline

  Scenario: Docker compose builds worker with new path
    Tool: Bash
    Steps:
      1. Run: grep "arq app.worker" docker-compose.yml
      2. Assert: found (updated from app.core.worker)
      3. Run: docker compose build worker 2>&1 | tail -5
      4. Assert: exit code 0
    Expected Result: Worker builds successfully with new entry point
    Evidence: .sisyphus/evidence/task-15-worker-moved.txt
  ```

  **Commit**: YES
  - Message: `refactor(backend): move worker entry point to app root`
  - Files: `backend/app/worker.py`, `docker-compose.yml`, possibly `AGENTS.md`, `infrastructure/docker-compose.dev.yml`

- [ ] 16. Full backend verification suite

  **What to do**:
  - Run complete backend test suite: `cd backend && python -m pytest --tb=short -q`
  - Compare pass count against baseline from Task 1
  - Run `cd backend && ruff check app/` — must be zero errors
  - Run `cd backend && python -c "from app.main import app; from app.worker import WorkerSettings; print('OK')"`
  - Run `cd backend && alembic check` (or `alembic heads`)
  - Run `cd backend && python -c "import app.main; import app.worker; print('No circular imports')"`
  - Verify zero references to old paths: `rg "from app\.services\.[a-z]" backend/app/` should return 0
  - Verify zero references to old paths: `rg "from app\.actions\." backend/app/` should return 0
  - Verify zero references to old paths: `rg "from app\.investigations\." backend/app/` should return 0
  - Verify zero references to old paths: `rg "from app\.cloud\." backend/app/` should return 0
  - Verify zero references to old paths: `rg "from app\.llm\." backend/app/` should return 0
  - Verify zero references to old paths: `rg "from app\.rag\." backend/app/` should return 0
  - Save comprehensive report

  **Must NOT do**:
  - Do not modify any files — this is verification only
  - If tests fail, report which tests and why — do NOT fix them in this task

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 17
  - **Blocked By**: Task 15

  **References**:
  - `.sisyphus/evidence/task-1-baseline.txt` — original test counts to compare against
  - All domain directories created in Tasks 7-13

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Full backend passes with zero stale imports
    Tool: Bash
    Steps:
      1. Run: cd backend && python -m pytest --tb=short -q 2>&1 | tail -5
      2. Compare against baseline
      3. Run: cd backend && ruff check app/ 2>&1 | tail -3
      4. Assert: 0 errors
      5. Run: rg "from app\.(services|actions|investigations|cloud|llm|rag)\." backend/app/ --count-matches | grep -v __pycache__
      6. Assert: 0 total matches
    Expected Result: Same test count as baseline, zero lint errors, zero stale imports
    Evidence: .sisyphus/evidence/task-16-backend-verification.txt
  ```

  **Commit**: NO

- [ ] 17. Update backend tests/ to mirror new domain structure

  **What to do**:
  - Examine `backend/tests/` for files that import from old paths
  - Update ALL test imports to use new paths (app.domains.*, app.integrations.*, app.middleware.*)
  - Optionally reorganize test files to mirror domain structure:
    - `tests/domains/incident/test_state_machine.py`
    - `tests/domains/incident/test_incident_service.py`
    - `tests/integrations/test_llm_client.py`
    - etc.
  - Run `pytest` after updates to verify all pass
  - Create `tests/conftest.py` updates if path-sensitive fixtures exist

  **Must NOT do**:
  - Do not modify test logic or assertions
  - Do not add new tests
  - Do not change test naming conventions

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4 (after Task 16)
  - **Blocks**: Task 18
  - **Blocked By**: Task 16

  **References**:
  - `backend/tests/` — existing test files
  - `backend/tests/conftest.py` — test configuration and fixtures

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Tests updated and passing
    Tool: Bash
    Steps:
      1. Run: cd backend && python -m pytest --tb=short -q 2>&1 | tail -5
      2. Assert: same pass count as baseline
      3. Run: rg "from app\.(services|actions|investigations|cloud|llm|rag)\." backend/tests/ --count-matches
      4. Assert: 0 matches (all test imports updated)
    Expected Result: Tests use new import paths, all pass
    Evidence: .sisyphus/evidence/task-17-tests-updated.txt
  ```

  **Commit**: YES
  - Message: `refactor(backend): update test imports to match domain-driven structure`
  - Files: All updated test files

- [ ] 18. Create frontend feature-based directory structure

  **What to do**:
  - Create new feature-based directory structure under `frontend/src/`:
    - `frontend/src/features/` — domain feature modules
    - `frontend/src/features/incidents/` — incident management feature
    - `frontend/src/features/incidents/components/`
    - `frontend/src/features/incidents/hooks/`
    - `frontend/src/features/dashboard/` — dashboard feature
    - `frontend/src/features/dashboard/components/`
    - `frontend/src/features/auth/` — auth feature
    - `frontend/src/features/auth/components/`
    - `frontend/src/features/settings/` — settings feature
    - `frontend/src/components/ui/` — shared design-system primitives (badges, modals, terminal, etc.)
    - `frontend/src/components/layout/` — keep existing layout components
    - `frontend/src/lib/` — shared utilities, constants, formatters (replaces utils/)
  - Create empty index.js barrel files in each new directory
  - Verify `npm run build` still passes (no imports broken yet — just adding dirs)

  **Must NOT do**:
  - Do not move any files in this task — just create directory structure
  - Do not modify existing code

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]
    - `frontend-ui-ux`: Understands frontend project organization patterns and best practices

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 5
  - **Blocks**: Task 19
  - **Blocked By**: Task 17

  **References**:
  - `frontend/src/` — current directory structure
  - `frontend/src/components/` — current component organization (incident/, common/, layout/, alert/)
  - Librarian findings: Plane.so, Twenty CRM feature-based patterns

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Feature directories created
    Tool: Bash
    Steps:
      1. Run: test -d frontend/src/features/incidents/components && echo "PASS" || echo "FAIL"
      2. Run: test -d frontend/src/features/dashboard && echo "PASS" || echo "FAIL"
      3. Run: test -d frontend/src/features/auth && echo "PASS" || echo "FAIL"
      4. Run: test -d frontend/src/components/ui && echo "PASS" || echo "FAIL"
      5. Run: cd frontend && npm run build 2>&1 | tail -5
      6. Assert: build succeeds
    Expected Result: All directories created, build still works
    Evidence: .sisyphus/evidence/task-18-frontend-scaffold.txt
  ```

  **Commit**: YES
  - Message: `chore(frontend): create feature-based directory scaffolding`
  - Files: New directories with index files

- [ ] 19. Reorganize frontend components into features

  **What to do**:
  - Move `frontend/src/components/incident/*.jsx` → `frontend/src/features/incidents/components/`
  - Move `frontend/src/components/alert/*.jsx` → `frontend/src/features/incidents/components/` (alerts are part of incident domain)
  - Move `frontend/src/components/common/*.jsx` → `frontend/src/components/ui/` (shared UI primitives)
  - Keep `frontend/src/components/layout/` as-is (global layout)
  - Move page components to features:
    - `frontend/src/pages/Dashboard.jsx` → `frontend/src/features/dashboard/DashboardPage.jsx`
    - `frontend/src/pages/IncidentDetail.jsx` → `frontend/src/features/incidents/IncidentDetailPage.jsx`
    - `frontend/src/pages/LoginPage.jsx` → `frontend/src/features/auth/LoginPage.jsx`
    - `frontend/src/pages/SettingsPage.jsx` → `frontend/src/features/settings/SettingsPage.jsx`
  - Update ALL import paths in every moved file and every consumer
  - Update `App.jsx` route imports to point to new feature page locations
  - Run `npm run lint`, `npm run test`, `npm run build` after each batch of moves

  **Must NOT do**:
  - Do not change component logic, props, or styling
  - Do not rename components
  - Do not change CSS classes or Tailwind utilities
  - Do not modify routing paths (URL structure stays identical)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]
    - `frontend-ui-ux`: Understands React component organization and import patterns

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 5 (after Task 18)
  - **Blocks**: Task 20
  - **Blocked By**: Task 18

  **References**:
  - `frontend/src/components/incident/` — IncidentChat, IncidentTimeline, EvidencePanel, etc.
  - `frontend/src/components/common/` — Badge, Modal, Terminal, etc. (shared UI)
  - `frontend/src/components/alert/` — AlertRow, etc.
  - `frontend/src/pages/` — Dashboard, IncidentDetail, LoginPage, SettingsPage
  - `frontend/src/App.jsx` — route definitions importing page components

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Components reorganized into features
    Tool: Bash
    Steps:
      1. Run: ls frontend/src/features/incidents/components/ | wc -l
      2. Assert: > 0 files present
      3. Run: ls frontend/src/components/ui/ | wc -l
      4. Assert: > 0 files present (shared UI primitives)
      5. Run: test -f frontend/src/features/dashboard/DashboardPage.jsx && echo "PASS" || echo "FAIL"
      6. Run: test -f frontend/src/features/auth/LoginPage.jsx && echo "PASS" || echo "FAIL"
      7. Run: cd frontend && npm run lint 2>&1 | tail -5
      8. Run: cd frontend && npm run test -- --run 2>&1 | tail -10
      9. Run: cd frontend && npm run build 2>&1 | tail -5
      10. Assert: all three pass
    Expected Result: Components in features, lint/test/build all pass
    Evidence: .sisyphus/evidence/task-19-components-reorganized.txt

  Scenario: No broken imports after move
    Tool: Bash
    Steps:
      1. Run: cd frontend && npm run build 2>&1 | grep -i "error" | head -10
      2. Assert: 0 build errors
    Expected Result: Clean build with zero import errors
    Evidence: .sisyphus/evidence/task-19-build-clean.txt
  ```

  **Commit**: YES
  - Message: `refactor(frontend): reorganize components into feature-based structure`
  - Files: All moved component files, updated imports

- [ ] 20. Reorganize frontend services, hooks, and utils

  **What to do**:
  - Move domain-specific hooks to features:
    - `frontend/src/hooks/useIncidents.js` → `frontend/src/features/incidents/hooks/useIncidents.js`
    - `frontend/src/hooks/useIncidentDetail.js` → `frontend/src/features/incidents/hooks/useIncidentDetail.js` (if exists)
  - Keep global hooks in `frontend/src/hooks/`:
    - `useAuth.js`, `useTheme.js`, `useToast.js` — these are app-wide
  - Move `frontend/src/utils/` → `frontend/src/lib/` (rename to lib/ for professional convention)
  - Keep `frontend/src/services/api.js`, `auth.js`, `sse.js` in `frontend/src/services/` (global service layer)
  - Update ALL import paths
  - Run `npm run lint`, `npm run test`, `npm run build`

  **Must NOT do**:
  - Do not modify hook logic or API service implementations
  - Do not change the Axios instance or SSE client
  - Do not rename exported functions/hooks

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]
    - `frontend-ui-ux`: Understands React hooks organization and service layer patterns

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 5 (after Task 19)
  - **Blocks**: Task 21
  - **Blocked By**: Task 19

  **References**:
  - `frontend/src/hooks/` — useIncidents, useAuth, useTheme, etc.
  - `frontend/src/utils/` — formatters, constants
  - `frontend/src/services/` — api.js, auth.js, sse.js

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Hooks and utils reorganized
    Tool: Bash
    Steps:
      1. Run: test -f frontend/src/features/incidents/hooks/useIncidents.js && echo "PASS" || echo "FAIL"
      2. Run: test -d frontend/src/lib && echo "PASS" || echo "FAIL"
      3. Run: test -f frontend/src/services/api.js && echo "PASS" || echo "FAIL" (global services stay)
      4. Run: cd frontend && npm run build 2>&1 | tail -5
      5. Assert: build succeeds
    Expected Result: Domain hooks colocated, utils renamed to lib, build passes
    Evidence: .sisyphus/evidence/task-20-hooks-utils-reorganized.txt
  ```

  **Commit**: YES
  - Message: `refactor(frontend): reorganize hooks and utils into feature-based layout`
  - Files: Moved hook files, renamed utils → lib, updated imports

- [ ] 21. Update frontend routing and entry points

  **What to do**:
  - Update `frontend/src/App.jsx` to import all page components from new `features/` locations
  - Verify all route paths remain identical (URL structure unchanged)
  - Update `frontend/src/main.jsx` if any imports changed
  - Clean up empty directories: `frontend/src/pages/` (if all pages moved), `frontend/src/components/incident/`, `frontend/src/components/alert/`, `frontend/src/components/common/`
  - Update test imports in `frontend/src/__tests__/` to reference new locations
  - Run `npm run lint`, `npm run test`, `npm run build`

  **Must NOT do**:
  - Do not change route paths or URL structure
  - Do not modify routing logic (guards, redirects, lazy loading)
  - Do not change error boundary configuration

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]
    - `frontend-ui-ux`: Understands React Router patterns and entry point configuration

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 5 (after Task 20)
  - **Blocks**: Task 22
  - **Blocked By**: Task 20

  **References**:
  - `frontend/src/App.jsx` — current route definitions and imports
  - `frontend/src/main.jsx` — entry point
  - `frontend/src/__tests__/` — test files needing import updates

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Routing updated and empty dirs cleaned
    Tool: Bash
    Steps:
      1. Run: cd frontend && npm run build 2>&1 | tail -5
      2. Assert: build succeeds
      3. Run: cd frontend && npm run test -- --run 2>&1 | tail -10
      4. Assert: tests pass with same count as baseline
      5. Run: test ! -d frontend/src/pages || [ -z "$(ls frontend/src/pages/ 2>/dev/null)" ] && echo "PASS" || echo "REMAINS"
    Expected Result: Build and tests pass, empty dirs cleaned
    Evidence: .sisyphus/evidence/task-21-routing-updated.txt
  ```

  **Commit**: YES
  - Message: `refactor(frontend): update routing imports and clean empty directories`
  - Files: App.jsx, main.jsx, test files, removed empty dirs

- [ ] 22. Frontend build + test full verification

  **What to do**:
  - Run complete frontend verification:
    - `cd frontend && npm run lint` — zero errors
    - `cd frontend && npm run test -- --run` — same pass count as baseline
    - `cd frontend && npm run build` — exit 0
  - Compare test count against baseline from Task 1
  - Verify no broken imports: `npm run build 2>&1 | grep -i error`
  - Save comprehensive report

  **Must NOT do**:
  - Do not modify any files — this is verification only

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`, `playwright`]
    - `frontend-ui-ux`: Understands frontend build pipelines and test frameworks
    - `playwright`: For browser-based verification of the running app

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 5 (after Task 21)
  - **Blocks**: Task 23
  - **Blocked By**: Task 21

  **References**:
  - `.sisyphus/evidence/task-1-baseline.txt` — original frontend test counts
  - `frontend/package.json` — build and test scripts

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Full frontend verification
    Tool: Bash
    Steps:
      1. Run: cd frontend && npm run lint 2>&1 | tail -5
      2. Assert: 0 errors
      3. Run: cd frontend && npm run test -- --run 2>&1 | tail -10
      4. Compare against baseline
      5. Run: cd frontend && npm run build 2>&1 | tail -5
      6. Assert: exit 0
    Expected Result: Lint clean, tests match baseline, build succeeds
    Evidence: .sisyphus/evidence/task-22-frontend-verification.txt

  Scenario: Frontend renders in browser
    Tool: Playwright (playwright skill)
    Steps:
      1. Start dev server: cd frontend && npm run dev (background)
      2. Navigate to http://localhost:5173
      3. Assert: page loads without white screen
      4. Check browser console for errors
      5. Navigate to /login — assert login form renders
      6. Screenshot evidence
    Expected Result: App renders correctly with zero console errors
    Evidence: .sisyphus/evidence/task-22-playwright-screenshot.png
  ```

  **Commit**: NO

- [ ] 23. Organize deployment/ per-service structure

  **What to do**:
  - Verify `deployment/ecs/` is already organized per-service (task definitions, scripts)
  - If task definitions reference old backend paths (e.g., `app.core.worker`), update them
  - Verify `deployment/ecs/codebuild/buildspec.images.yml` references correct Dockerfile paths under `services/`
  - Verify `deployment/ecs/codebuild/buildspec.frontend.yml` still works for S3 deploy
  - Check `deployment/ecs/scripts/` for any hardcoded paths that need updating
  - Update `deployment/ecs/task-definitions/airex-worker.json` if it references `app.core.worker.WorkerSettings` → `app.worker.WorkerSettings`
  - Verify `apps/web/deploy-s3.sh` still works
  - Document any pipeline changes needed in `.sisyphus/evidence/`

  **Must NOT do**:
  - Do not modify Terraform files in `deployment/ecs/terraform/`
  - Do not change ECS service names or cluster configuration
  - Do not modify CodePipeline configuration
  - Do not change S3 bucket names or CloudFront distributions

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 6
  - **Blocks**: Task 24
  - **Blocked By**: Task 22

  **References**:
  - `deployment/ecs/task-definitions/airex-worker.json` — may reference worker command path
  - `deployment/ecs/codebuild/buildspec.images.yml` — Docker build commands
  - `deployment/ecs/scripts/render-task-defs.sh` — template injection script
  - `deployment/ecs/scripts/run-migration.sh` — runs alembic via ECS task

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Deployment configs reference correct paths
    Tool: Bash
    Steps:
      1. Run: rg "app\.core\.worker" deployment/ --count-matches
      2. Assert: 0 matches (all updated to app.worker)
      3. Run: rg "backend/Dockerfile\|frontend/Dockerfile" deployment/ --count-matches
      4. Assert: 0 matches (all reference services/ Dockerfiles)
      5. Run: cat deployment/ecs/task-definitions/airex-worker.json | grep -i "command\|entrypoint" | head -5
      6. Verify: references app.worker.WorkerSettings (not app.core.worker)
    Expected Result: All deployment configs use new paths
    Evidence: .sisyphus/evidence/task-23-deployment-updated.txt
  ```

  **Commit**: YES
  - Message: `refactor(deploy): update deployment configs for restructured backend paths`
  - Files: Updated task definitions, scripts if needed

- [ ] 24. Update Dockerfiles and docker-compose for final paths

  **What to do**:
  - Verify `services/airex-api/Dockerfile` still works with restructured backend/app/ (it should — it copies entire backend/)
  - Verify `services/airex-worker/Dockerfile` command references `app.worker.WorkerSettings` (updated in Task 15)
  - Verify `docker-compose.yml` has correct volume mounts and build contexts
  - Run `docker compose config` to verify compose file parses correctly
  - Run `docker compose build backend worker migrate frontend`

  **Must NOT do**:
  - Do not modify Dockerfile base images or system packages
  - Do not change exposed ports or health checks
  - Do not modify docker-compose service names

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 6 (after Task 23)
  - **Blocks**: Task 25
  - **Blocked By**: Task 23

  **References**:
  - `services/airex-api/Dockerfile` — backend API container
  - `services/airex-worker/Dockerfile` — worker container
  - `docker-compose.yml` — local dev stack

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: All Docker services build successfully
    Tool: Bash
    Steps:
      1. Run: docker compose config --services
      2. Assert: all services listed without error
      3. Run: docker compose build backend worker migrate frontend 2>&1 | tail -10
      4. Assert: exit code 0, all 4 images built
    Expected Result: All Docker builds succeed
    Evidence: .sisyphus/evidence/task-24-docker-builds.txt
  ```

  **Commit**: YES (if changes needed)
  - Message: `fix(docker): update Dockerfiles and compose for restructured paths`
  - Files: Any updated Dockerfiles, docker-compose.yml

- [ ] 25. Final Docker + integration verification

  **What to do**:
  - Run `docker compose build` for ALL services (not just the 4 buildable ones)
  - Verify `docker compose config` parses without errors
  - Verify `docker compose up -d db redis` starts infrastructure services
  - Run `docker compose run --rm migrate` to verify Alembic migration works (if DB available)
  - Save evidence

  **Must NOT do**:
  - Do not run `docker compose up` for all services (may fail without full env)
  - Do not modify any files

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 6 (after Task 24)
  - **Blocks**: F1-F4
  - **Blocked By**: Task 24

  **References**:
  - `docker-compose.yml` — full service definitions
  - `.dockerignore` — build context exclusions

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Docker stack operational
    Tool: Bash
    Steps:
      1. Run: docker compose build backend worker migrate frontend 2>&1 | tail -5
      2. Assert: exit 0
      3. Run: docker compose config --services | wc -l
      4. Assert: all services listed
    Expected Result: Full Docker stack builds and configures correctly
    Evidence: .sisyphus/evidence/task-25-docker-final.txt
  ```

  **Commit**: NO

---

## Final Verification Wave

- [ ] F1. **Plan Compliance Audit** — `deep`
  Read the plan end-to-end. For each "Must Have": verify implementation exists. For each "Must NOT Have": search codebase for forbidden patterns. Check evidence files exist. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `cd backend && ruff check app/ && mypy app/ --ignore-missing-imports && python -m pytest`. Run `cd frontend && npm run lint && npm run test && npm run build`. Review for broken imports, stale references, circular dependencies.
  Output: `Backend [PASS/FAIL] | Frontend [PASS/FAIL] | VERDICT`

- [ ] F3. **Full QA** — `unspecified-high`, Skills: `[playwright]`
  Start backend with `uvicorn app.main:app`. Hit `/docs` to verify API loads. Start frontend with `npm run dev`. Use Playwright to navigate dashboard, verify page loads, check console for errors. Test SSE connection. Test incident list page.
  Output: `API [UP/DOWN] | Frontend [UP/DOWN] | Console Errors [N] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: verify the move was clean (git diff shows only path changes, no logic modifications). Check "Must NOT do" compliance. Flag any function signature changes, new abstractions, or modified control flow.
  Output: `Tasks [N/N compliant] | Logic Changes [CLEAN/N issues] | VERDICT`

---

## Commit Strategy

- **Wave 0**: `chore: establish restructure baseline and create directory scaffolding`
- **Wave 1**: `refactor(backend): extract middleware and move integrations` (one commit per task)
- **Wave 2**: `refactor(backend): migrate {domain} to domains/{domain}` (one commit per domain)
- **Wave 3**: `refactor(backend): slim core and move worker entry point`
- **Wave 4**: `refactor(backend): update test structure to mirror domains`
- **Wave 5**: `refactor(frontend): reorganize to feature-based structure` (one commit per task)
- **Wave 6**: `refactor(deploy): organize deployment per-service structure`

---

## Success Criteria

### Verification Commands
```bash
# Backend tests pass
cd backend && python -m pytest --tb=short -q
# Expected: same pass count as baseline

# Backend linting clean
cd backend && ruff check app/
# Expected: 0 errors

# Backend imports valid
cd backend && python -c "from app.main import app; from app.worker import WorkerSettings; print('OK')"
# Expected: OK

# Alembic works
cd backend && alembic check
# Expected: no errors

# Frontend builds
cd frontend && npm run lint && npm run test && npm run build
# Expected: all pass

# Docker builds
docker compose build backend worker migrate frontend
# Expected: exit 0
```

### Final Checklist
- [ ] All backend files in domain-driven layout
- [ ] All frontend files in feature-based layout
- [ ] Deployment configs organized per-service
- [ ] All tests pass (same count as baseline)
- [ ] All Docker builds succeed
- [ ] Zero behavior changes
- [ ] No stale imports or references
