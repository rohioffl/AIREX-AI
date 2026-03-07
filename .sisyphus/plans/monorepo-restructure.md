# Monorepo Restructure + Deep Code Quality Enhancement

## TL;DR

> **Quick Summary**: Move all code into pipeline-independent service folders (`services/`, `apps/web/`, `database/`) and apply deep code quality enhancement (type safety, error handling, structured logging, docstrings, formatting) across all Python and React code.
>
> **Deliverables**:
> - Frontend fully relocated to `apps/web/`
> - Database/migrations isolated in `database/` at root
> - All Dockerfiles and buildspecs updated with correct paths
> - All ~126 Python files brought to professional standard (types, errors, logging, docs)
> - All React components enhanced (ESLint, prop types, cleanup)
> - Tests added for critical paths (state machine, worker, API routes)
> - docker-compose.yml updated for new structure
>
> **Estimated Effort**: Large
> **Parallel Execution**: YES — 6 waves
> **Critical Path**: Task 1 → Task 2 → Task 5 → Task 7 → Task 18 → Final

---

## Context

### Original Request
Move code into the service folders already created in `services/` so each deployable unit is self-contained with independent pipelines. Frontend moves to `apps/web/`. Database/migrations get their own root-level `database/` folder. Deep code quality enhancement across all Python and React code.

### Interview Summary
**Key Discussions**:
- Backend stays as shared package — API and Worker share ~70% of code (models, DB, state machine, schemas)
- Each service folder has its own Dockerfile with different CMD
- `database/` at root level for migration pipeline independence
- Deep quality: type hints, error handling, clean imports, docstrings, structured logging, ruff/black formatting
- Frontend also gets deep treatment: ESLint, component cleanup, prop types
- Add tests for critical paths

**Research Findings**:
- API-ONLY: `app.api/*`, `app.core.csrf/security/rbac/rate_limit`, `app.cloud.tag_parser/discovery`
- WORKER-ONLY: `app.investigations/*`, `app.actions/*`, `app.llm/*`, `app.rag/*`, execution/recommendation/verification services
- SHARED: `app.models/*`, `app.schemas/*`, `app.core.config/database/state_machine/events`, `incident_service`, `correlation_service`
- State machine has lazy imports at 6 locations — MUST preserve
- `app/models/__init__.py` re-exports all 12 models for Alembic — MUST preserve
- ARQ function names in worker.py must NOT be renamed (serialized in Redis)
- CI/CD is AWS CodePipeline/CodeBuild with buildspec files

### Metis Review
**Identified Gaps** (addressed):
- `monitoring/` move was wrong — `backend/app/monitoring/` already exists, `infra/` is infrastructure configs. Dropped from plan.
- `database/alembic.ini` needs `prepend_sys_path = ../backend` after move
- Lazy imports in `worker.py` and `state_machine.py` are INTENTIONAL — must NOT be moved to module level
- `sys.path` hacks in `create_admin_user.py`, `test_ssm_direct.py`, `test_ssm.py` — fix with pathlib
- Complete path reference inventory provided for all files needing updates

---

## Work Objectives

### Core Objective
Reorganize the AIREX-AI monorepo so every deployable unit owns its code in a dedicated folder, enabling independent CI/CD pipelines, and bring all code to professional quality standard.

### Concrete Deliverables
- `apps/web/` — complete frontend project (moved from `frontend/`)
- `database/` — Alembic migrations + Dockerfile for migration pipeline
- `services/airex-api/Dockerfile` — updated path references
- `services/airex-worker/Dockerfile` — updated path references
- `services/airex-frontend/Dockerfile` — updated to build from `apps/web/`
- `docker-compose.yml` — updated for new structure
- `deployment/ecs/codebuild/buildspec.frontend.yml` — updated paths
- All Python files — type-safe, properly documented, structured logging, clean error handling
- All React files — ESLint clean, prop types, component cleanup
- New tests for critical paths

### Definition of Done
- [ ] `frontend/` directory no longer exists
- [ ] `backend/alembic/` no longer exists (moved to `database/alembic/`)
- [ ] `apps/web/` contains complete working frontend
- [ ] `database/` contains alembic, alembic.ini, Dockerfile
- [ ] `docker-compose up` works with new structure
- [ ] `pytest` passes in `backend/`
- [ ] `npm run build` passes in `apps/web/`
- [ ] `ruff check app/` passes with zero errors in `backend/`
- [ ] `mypy app/ --ignore-missing-imports` passes in `backend/`
- [ ] `npm run lint` passes in `apps/web/`

### Must Have
- Pipeline independence: each service buildable without touching others
- Zero behavior changes to API endpoints or worker tasks
- All existing tests pass after restructure
- `alembic upgrade head` works from `database/` folder

### Must NOT Have (Guardrails)
- DO NOT touch `services/litellm/` or `services/langfuse/`
- DO NOT modify `deployment/ecs/terraform/` IaC files
- DO NOT modify `buildspec.images.yml` (already references `services/` Dockerfiles correctly)
- DO NOT rename Python functions or classes (only enhance quality)
- DO NOT move lazy imports in `worker.py` or `state_machine.py` to module level
- DO NOT rename ARQ task functions (serialized in Redis)
- DO NOT modify files in `alembic/versions/` (historical migrations)
- DO NOT change HTTP endpoint paths
- DO NOT change docker-compose service names, ports, or environment variables
- DO NOT duplicate backend code (single source, multiple Dockerfiles)

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest + vitest + playwright)
- **Automated tests**: Tests-after (add for critical paths during quality phase)
- **Framework**: pytest (backend), vitest (frontend), playwright (e2e)

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Frontend/UI**: Use Playwright — Navigate, interact, assert DOM, screenshot
- **Backend/API**: Use Bash (curl) — Send requests, assert status + response fields
- **Docker**: Use Bash — `docker-compose build`, `docker-compose up`, verify services start
- **Migrations**: Use Bash — `alembic upgrade head` from `database/` folder

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 0 (Foundation — baseline + structural moves):
├── Task 1: Establish test baseline [quick]
├── Task 2: Move frontend/ → apps/web/ + update all references [unspecified-high]
├── Task 3: Move alembic to database/ + create Dockerfile [unspecified-high]

Wave 1 (Docker + Config updates — parallel after Wave 0):
├── Task 4: Update services/airex-frontend/Dockerfile [quick]
├── Task 5: Update docker-compose.yml migrate service [quick]
├── Task 6: Update buildspec.frontend.yml [quick]
├── Task 7: Create database/Dockerfile for migration pipeline [quick]

Wave 2 (Backend Quality — core/ modules, parallel):
├── Task 8: Quality: app/core/config.py, database.py, logging.py [deep]
├── Task 9: Quality: app/core/state_machine.py, events.py, policy.py [deep]
├── Task 10: Quality: app/core/security.py, csrf.py, rbac.py, rate_limit.py [deep]
├── Task 11: Quality: app/core/worker.py, retry_scheduler.py, tenant_limits.py [deep]
├── Task 12: Quality: app/core/metrics.py + remaining core files [deep]

Wave 3 (Backend Quality — services, models, schemas, API, parallel):
├── Task 13: Quality: app/models/ (all model files) [deep]
├── Task 14: Quality: app/schemas/ (all schema files) [deep]
├── Task 15: Quality: app/services/ (all service files) [deep]
├── Task 16: Quality: app/api/ (routes, dependencies) [deep]
├── Task 17: Quality: app/cloud/ (all cloud adapters) [deep]
├── Task 18: Quality: app/investigations/ + app/actions/ [deep]
├── Task 19: Quality: app/llm/ + app/rag/ + app/monitoring/ [deep]

Wave 4 (Frontend Quality + Backend Tests, parallel):
├── Task 20: Frontend quality: ESLint, component cleanup, prop types [visual-engineering]
├── Task 21: Add backend tests: state machine transitions [deep]
├── Task 22: Add backend tests: worker tasks + API routes [deep]

Wave 5 (Verification):
├── Task 23: Full integration verification (docker-compose, alembic, tests) [deep]

Wave FINAL (After ALL tasks — independent review, 4 parallel):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
├── Task F4: Scope fidelity check (deep)

Critical Path: Task 1 → Task 2 → Task 4/5/6 → Task 8-19 → Task 20-22 → Task 23 → F1-F4
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 7 (Wave 3)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | — | 2, 3 | 0 |
| 2 | 1 | 4, 6, 20 | 0 |
| 3 | 1 | 5, 7, 23 | 0 |
| 4 | 2 | 23 | 1 |
| 5 | 3 | 23 | 1 |
| 6 | 2 | 23 | 1 |
| 7 | 3 | 23 | 1 |
| 8-12 | 1 | 23 | 2 |
| 13-19 | 1 | 23 | 3 |
| 20 | 2 | 23 | 4 |
| 21-22 | 8-19 | 23 | 4 |
| 23 | 4-7, 8-22 | F1-F4 | 5 |
| F1-F4 | 23 | — | FINAL |

### Agent Dispatch Summary

- **Wave 0**: T1 → `quick`, T2 → `unspecified-high`, T3 → `unspecified-high`
- **Wave 1**: T4-T7 → `quick`
- **Wave 2**: T8-T12 → `deep`
- **Wave 3**: T13-T19 → `deep`
- **Wave 4**: T20 → `visual-engineering` + `frontend-ui-ux`, T21-T22 → `deep`
- **Wave 5**: T23 → `deep`
- **FINAL**: F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high` + `playwright`, F4 → `deep`

---

## TODOs

> Implementation + verification = ONE Task. EVERY task has QA Scenarios.

- [x] 1. Establish Test Baseline

  **What to do**:
  - Run `pytest` in `backend/` and record pass/fail count
  - Run `npm run build` and `npm run test` in `frontend/` and record results
  - Run `ruff check app/` in `backend/` and record error count
  - Run `mypy app/ --ignore-missing-imports` in `backend/` and record error count
  - Save all outputs as baseline evidence

  **Must NOT do**:
  - Do not fix any issues — only record current state

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (must complete before everything else)
  - **Parallel Group**: Wave 0 (first)
  - **Blocks**: Tasks 2, 3
  - **Blocked By**: None

  **References**:
  - `backend/pytest.ini` — pytest configuration
  - `frontend/package.json` — npm scripts (build, test, lint)
  - `backend/requirements.txt` — Python dependencies

  **Acceptance Criteria**:
  - [ ] Baseline evidence files exist with pass/fail counts

  **QA Scenarios**:
  ```
  Scenario: Record backend test baseline
    Tool: Bash
    Steps:
      1. cd backend && python -m pytest --tb=short 2>&1 | tee /tmp/baseline-pytest.txt
      2. cd backend && ruff check app/ 2>&1 | tee /tmp/baseline-ruff.txt
      3. cd backend && mypy app/ --ignore-missing-imports 2>&1 | tee /tmp/baseline-mypy.txt
    Expected Result: Outputs captured regardless of pass/fail
    Evidence: .sisyphus/evidence/task-1-backend-baseline.txt

  Scenario: Record frontend test baseline
    Tool: Bash
    Steps:
      1. cd frontend && npm run build 2>&1 | tee /tmp/baseline-frontend-build.txt
      2. cd frontend && npm run test -- --run 2>&1 | tee /tmp/baseline-frontend-test.txt
    Expected Result: Outputs captured regardless of pass/fail
    Evidence: .sisyphus/evidence/task-1-frontend-baseline.txt
  ```

  **Commit**: NO (no files changed)

---

- [ ] 2. Move frontend/ → apps/web/

  **What to do**:
  - Move ALL files from `frontend/` to `apps/web/`: `src/`, `public/`, `package.json`, `package-lock.json`, `vite.config.js`, `eslint.config.js`, `index.html`, `nginx.conf`, `scripts/`, `tests/`, `playwright.config.js`
  - Preserve the existing `apps/web/deploy-s3.sh` and `apps/web/README.md`
  - Delete `frontend/` directory after move
  - Verify `npm install && npm run build` works in `apps/web/`

  **Must NOT do**:
  - Do not modify any source code during the move
  - Do not change vite.config.js paths (they are relative to project root)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 3)
  - **Parallel Group**: Wave 0
  - **Blocks**: Tasks 4, 6, 20
  - **Blocked By**: Task 1

  **References**:
  - `frontend/` — current frontend location (all files to move)
  - `apps/web/deploy-s3.sh` — existing file, do not overwrite
  - `apps/web/README.md` — existing file, do not overwrite
  - `frontend/vite.config.js` — check for absolute path references
  - `frontend/package.json` — verify no path references to `../backend`

  **Acceptance Criteria**:
  - [ ] `frontend/` directory no longer exists
  - [ ] `apps/web/src/` exists with all React source files
  - [ ] `apps/web/package.json` exists
  - [ ] `cd apps/web && npm install && npm run build` succeeds

  **QA Scenarios**:
  ```
  Scenario: Frontend build works from new location
    Tool: Bash
    Steps:
      1. test ! -d frontend && echo "PASS: frontend/ deleted"
      2. test -f apps/web/package.json && echo "PASS: package.json exists"
      3. test -d apps/web/src && echo "PASS: src/ exists"
      4. cd apps/web && npm install && npm run build
    Expected Result: Build succeeds with exit code 0
    Failure Indicators: "Error" in build output, missing files
    Evidence: .sisyphus/evidence/task-2-frontend-move.txt

  Scenario: Existing apps/web files preserved
    Tool: Bash
    Steps:
      1. test -f apps/web/deploy-s3.sh && echo "PASS: deploy script preserved"
      2. test -f apps/web/README.md && echo "PASS: README preserved"
    Expected Result: Both files exist
    Evidence: .sisyphus/evidence/task-2-preserved-files.txt
  ```

  **Commit**: YES
  - Message: `refactor: move frontend to apps/web for pipeline independence`
  - Files: `apps/web/*`, delete `frontend/`
  - Pre-commit: `cd apps/web && npm run build`

---

- [ ] 3. Move alembic to database/ at root level

  **What to do**:
  - Move `backend/alembic/` → `database/alembic/`
  - Move `backend/alembic.ini` → `database/alembic.ini`
  - Edit `database/alembic.ini`: change `prepend_sys_path = .` to `prepend_sys_path = ../backend`
  - Verify `alembic/env.py` can still import `app.models` with the new sys.path
  - Create `database/scripts/` directory and move `backend/scripts/init-multi-db.sql` there
  - Update `docker-compose.yml` line 136: change `./backend/scripts/init-multi-db.sql` to `./database/scripts/init-multi-db.sql`
  - DO NOT modify any files in `alembic/versions/`

  **Must NOT do**:
  - Do not modify migration files in `alembic/versions/`
  - Do not change alembic `env.py` logic (only path config in `.ini`)
  - Do not move `backend/scripts/validate_migration.py` (it stays in backend)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 2)
  - **Parallel Group**: Wave 0
  - **Blocks**: Tasks 5, 7, 23
  - **Blocked By**: Task 1

  **References**:
  - `backend/alembic.ini` — current location, line 6: `script_location = alembic`, line 9: `prepend_sys_path = .`
  - `backend/alembic/env.py` — imports `from app.models import Base` (needs `../backend` on sys.path)
  - `backend/alembic/versions/` — historical migrations, DO NOT TOUCH
  - `docker-compose.yml:136` — references `./backend/scripts/init-multi-db.sql`
  - `backend/scripts/init-multi-db.sql` — SQL init script to move to `database/scripts/`

  **Acceptance Criteria**:
  - [ ] `database/alembic/` exists with all migration files
  - [ ] `database/alembic.ini` has `prepend_sys_path = ../backend`
  - [ ] `database/scripts/init-multi-db.sql` exists
  - [ ] `backend/alembic/` no longer exists
  - [ ] `backend/alembic.ini` no longer exists
  - [ ] `cd database && alembic history` works (shows migration history)

  **QA Scenarios**:
  ```
  Scenario: Alembic works from new location
    Tool: Bash
    Preconditions: DATABASE_URL environment variable set, database running
    Steps:
      1. test ! -d backend/alembic && echo "PASS: backend/alembic deleted"
      2. test -d database/alembic/versions && echo "PASS: versions/ exists"
      3. grep "prepend_sys_path = ../backend" database/alembic.ini && echo "PASS: sys.path configured"
      4. cd database && alembic history 2>&1 | head -5
    Expected Result: Alembic history shows migrations without import errors
    Failure Indicators: "ModuleNotFoundError: No module named 'app'" in output
    Evidence: .sisyphus/evidence/task-3-alembic-move.txt

  Scenario: Docker-compose init-db path updated
    Tool: Bash
    Steps:
      1. grep "init-multi-db.sql" docker-compose.yml
    Expected Result: Path shows `./database/scripts/init-multi-db.sql`
    Evidence: .sisyphus/evidence/task-3-compose-path.txt
  ```

  **Commit**: YES
  - Message: `refactor: move alembic to database/ for migration pipeline independence`
  - Files: `database/*`, delete `backend/alembic/`, `backend/alembic.ini`
  - Pre-commit: `cd database && alembic history`

---

- [ ] 4. Update services/airex-frontend/Dockerfile for apps/web/ paths

  **What to do**:
  - Update line 5: `frontend/package.json frontend/package-lock.json` → `apps/web/package.json apps/web/package-lock.json`
  - Update line 8: `COPY frontend/ .` → `COPY apps/web/ .`
  - Update line 18: `COPY frontend/nginx.conf` → `COPY apps/web/nginx.conf`

  **Must NOT do**:
  - Do not change any other Dockerfile content (base images, stages, ports, CMD)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 5, 6, 7)
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 23
  - **Blocked By**: Task 2

  **References**:
  - `services/airex-frontend/Dockerfile` — current content (lines 5, 8, 18 reference `frontend/`)

  **Acceptance Criteria**:
  - [ ] Dockerfile references `apps/web/` instead of `frontend/`
  - [ ] `docker build -f services/airex-frontend/Dockerfile .` succeeds

  **QA Scenarios**:
  ```
  Scenario: Dockerfile has correct paths
    Tool: Bash
    Steps:
      1. grep -c "frontend/" services/airex-frontend/Dockerfile
      2. grep "apps/web/" services/airex-frontend/Dockerfile
    Expected Result: Zero occurrences of "frontend/", multiple of "apps/web/"
    Evidence: .sisyphus/evidence/task-4-dockerfile-paths.txt
  ```

  **Commit**: NO (groups with Task 5, 6, 7)

- [ ] 5. Update docker-compose.yml for database/ structure

  **What to do**:
  - Update migrate service (line 69): change `command: alembic upgrade head` to `command: bash -c "cd /database && alembic upgrade head"`
  - Add volume mount to migrate service: `./database:/database` alongside existing `./backend:/app`
  - Update line 136: `./backend/scripts/init-multi-db.sql:/docker-entrypoint-initdb.d/init-multi-db.sql` → `./database/scripts/init-multi-db.sql:/docker-entrypoint-initdb.d/init-multi-db.sql`
  - Verify migrate service still depends on `db` with health check

  **Must NOT do**:
  - Do not change service names, ports, environment variables, or network config
  - Do not modify airex-api, airex-worker, litellm, langfuse, db, or redis service definitions
  - Do not change docker-compose version

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 4, 6, 7)
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 23
  - **Blocked By**: Task 3

  **References**:
  - `docker-compose.yml:64-78` — migrate service definition
  - `docker-compose.yml:136` — init-multi-db.sql volume mount on db service
  - `database/alembic.ini` — alembic config in new location

  **Acceptance Criteria**:
  - [ ] `docker-compose config` parses without errors
  - [ ] migrate service has both `./backend:/app` and `./database:/database` volumes
  - [ ] db service references `./database/scripts/init-multi-db.sql`

  **QA Scenarios**:
  ```
  Scenario: docker-compose config validates
    Tool: Bash
    Steps:
      1. docker-compose config > /dev/null 2>&1 && echo "PASS" || echo "FAIL"
      2. grep "database/scripts/init-multi-db.sql" docker-compose.yml
      3. grep "./database:/database" docker-compose.yml
    Expected Result: Config validates, both paths present
    Evidence: .sisyphus/evidence/task-5-compose-update.txt
  ```

  **Commit**: NO (groups with Tasks 4, 6, 7)

---

- [ ] 6. Update buildspec.frontend.yml for apps/web/ paths

  **What to do**:
  - Line 16: `npm ci --prefix frontend` → `npm ci --prefix apps/web`
  - Line 21: `npm run build --prefix frontend` → `npm run build --prefix apps/web`
  - Line 26: `frontend/dist` → `apps/web/dist`
  - Line 31: `frontend/node_modules/**/*` → `apps/web/node_modules/**/*`

  **Must NOT do**:
  - Do not change environment variables, S3 bucket references, or CloudFront invalidation
  - Do not modify `buildspec.images.yml` (it already references `services/` Dockerfiles correctly)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 4, 5, 7)
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 23
  - **Blocked By**: Task 2

  **References**:
  - `deployment/ecs/codebuild/buildspec.frontend.yml` — 4 references to `frontend/` (lines 16, 21, 26, 31)
  - `deployment/ecs/codebuild/buildspec.images.yml` — DO NOT TOUCH (already correct)

  **Acceptance Criteria**:
  - [ ] Zero occurrences of `frontend/` in `buildspec.frontend.yml`
  - [ ] All 4 references now use `apps/web/`

  **QA Scenarios**:
  ```
  Scenario: buildspec has correct paths
    Tool: Bash
    Steps:
      1. grep -c "frontend/" deployment/ecs/codebuild/buildspec.frontend.yml
      2. grep "apps/web" deployment/ecs/codebuild/buildspec.frontend.yml
    Expected Result: Zero "frontend/" occurrences, 4 "apps/web" occurrences
    Evidence: .sisyphus/evidence/task-6-buildspec-paths.txt
  ```

  **Commit**: NO (groups with Tasks 4, 5, 7)

---

- [ ] 7. Create database/Dockerfile for migration pipeline

  **What to do**:
  - Create `database/Dockerfile` — a slim Python image that:
    - Installs only alembic + psycopg2 + sqlalchemy (migration dependencies from `backend/requirements.txt`)
    - COPY `backend/` to `/app` (for model imports)
    - COPY `database/` to `/database`
    - WORKDIR `/database`
    - CMD `["alembic", "upgrade", "head"]`
  - This Dockerfile is for the standalone migration pipeline (not used by docker-compose locally, which uses the migrate service)

  **Must NOT do**:
  - Do not install unnecessary dependencies (no FastAPI, no ARQ, no LLM libs)
  - Do not duplicate backend code — COPY from build context

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 4, 5, 6)
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 23
  - **Blocked By**: Task 3

  **References**:
  - `services/airex-api/Dockerfile` — pattern reference for Python base image and system deps
  - `backend/requirements.txt` — full dependency list (extract only migration-relevant ones)
  - `database/alembic.ini` — will be in the image at `/database/alembic.ini`

  **Acceptance Criteria**:
  - [ ] `database/Dockerfile` exists
  - [ ] `docker build -f database/Dockerfile .` succeeds from repo root
  - [ ] Image contains alembic, sqlalchemy, and can run `alembic history`

  **QA Scenarios**:
  ```
  Scenario: Database Dockerfile builds
    Tool: Bash
    Steps:
      1. test -f database/Dockerfile && echo "PASS: Dockerfile exists"
      2. docker build -f database/Dockerfile -t airex-migrate-test . 2>&1 | tail -5
    Expected Result: Build completes successfully
    Failure Indicators: "ERROR" or "failed" in build output
    Evidence: .sisyphus/evidence/task-7-db-dockerfile.txt
  ```

  **Commit**: YES
  - Message: `chore: update Dockerfiles and buildspecs for new monorepo structure`
  - Files: `services/airex-frontend/Dockerfile`, `docker-compose.yml`, `deployment/ecs/codebuild/buildspec.frontend.yml`, `database/Dockerfile`
  - Pre-commit: `docker-compose config`

- [ ] 8. Quality Enhancement: app/core/config.py, database.py, logging.py

  **What to do**:
  - `app/core/config.py`: Add type hints to all Settings fields, add field validators with descriptive errors, add docstring explaining each config group, ensure `model_config` uses proper Pydantic v2 patterns
  - `app/core/database.py`: Add type hints to all functions (return types for `get_db`, engine factories), add proper error handling for connection failures with structured logging, add module-level docstring explaining RLS session pattern, ensure `async with` patterns are used correctly
  - `app/core/logging.py`: Ensure structlog is configured with `correlation_id` processor, add type hints, add docstring, verify JSON output format for production
  - Run `ruff check` and `mypy` on these 3 files after changes
  - Run `ruff format` on these 3 files

  **Must NOT do**:
  - Do not change config variable names (other modules import them)
  - Do not change database engine creation logic or connection pool settings
  - Do not change logging output format for production (may break log ingestion)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 9, 10, 11, 12)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 23
  - **Blocked By**: Task 1

  **References**:
  - `backend/app/core/config.py` — Pydantic Settings class, currently has LSP error on `pydantic_settings` import (missing venv, not a code issue)
  - `backend/app/core/database.py` — SQLAlchemy async engine + RLS session management
  - `backend/app/core/logging.py` — structlog configuration
  - `docs/backend_skill.md` — Backend coding standards (type hints, structured logging with correlation_id)

  **Acceptance Criteria**:
  - [ ] `ruff check backend/app/core/config.py backend/app/core/database.py backend/app/core/logging.py` → 0 errors
  - [ ] `mypy backend/app/core/config.py backend/app/core/database.py backend/app/core/logging.py --ignore-missing-imports` → 0 errors
  - [ ] All public functions have type hints and docstrings
  - [ ] No bare `except:` statements

  **QA Scenarios**:
  ```
  Scenario: Core config/db/logging pass quality checks
    Tool: Bash
    Steps:
      1. cd backend && ruff check app/core/config.py app/core/database.py app/core/logging.py
      2. cd backend && mypy app/core/config.py app/core/database.py app/core/logging.py --ignore-missing-imports
      3. cd backend && python -c "from app.core.config import settings; print(type(settings))"
    Expected Result: Zero ruff errors, zero mypy errors, settings imports successfully
    Evidence: .sisyphus/evidence/task-8-core-config-quality.txt

  Scenario: No bare except statements
    Tool: Bash
    Steps:
      1. grep -n "except:" backend/app/core/config.py backend/app/core/database.py backend/app/core/logging.py | grep -v "except.*Error" | grep -v "except.*Exception"
    Expected Result: No output (no bare excepts)
    Evidence: .sisyphus/evidence/task-8-bare-excepts.txt
  ```

  **Commit**: NO (groups with Wave 2)

---

- [ ] 9. Quality Enhancement: app/core/state_machine.py, events.py, policy.py

  **What to do**:
  - `app/core/state_machine.py`: Add type hints to all functions, add comprehensive docstrings explaining state transitions and the state diagram, add proper error handling with domain-specific exceptions (e.g. `InvalidTransitionError`), improve structured logging with `correlation_id` on all log calls. **CRITICAL: DO NOT move lazy imports at lines 108, 159, 173, 190, 202, 217 to module level — they prevent circular imports.**
  - `app/core/events.py`: Add type hints, docstrings, proper error handling for Redis pub/sub failures, structured logging
  - `app/core/policy.py`: Add type hints, docstrings, proper error handling for policy evaluation failures
  - Run `ruff check`, `mypy`, and `ruff format` on all 3 files

  **Must NOT do**:
  - DO NOT move lazy imports in `state_machine.py` to module level (they are intentional circular import prevention)
  - Do not change state transition logic or add/remove states
  - Do not change event emission format (frontend SSE depends on it)
  - Do not change policy evaluation logic

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 8, 10, 11, 12)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 23
  - **Blocked By**: Task 1

  **References**:
  - `backend/app/core/state_machine.py` — 11 consumers, lazy imports at lines 108, 159, 173, 190, 202, 217
  - `backend/app/core/events.py` — SSE event emission, Redis pub/sub
  - `backend/app/core/policy.py` — Risk evaluation, approval requirements
  - `docs/backend_skill.md` — Error handling and logging standards

  **Acceptance Criteria**:
  - [ ] `ruff check` and `mypy` pass on all 3 files
  - [ ] All public functions have type hints and docstrings
  - [ ] Lazy imports in state_machine.py are still inside function bodies (NOT at module level)
  - [ ] `pytest tests/test_state_machine.py` still passes (if it exists)

  **QA Scenarios**:
  ```
  Scenario: State machine quality + lazy imports preserved
    Tool: Bash
    Steps:
      1. cd backend && ruff check app/core/state_machine.py app/core/events.py app/core/policy.py
      2. cd backend && mypy app/core/state_machine.py app/core/events.py app/core/policy.py --ignore-missing-imports
      3. grep -n "from app\." backend/app/core/state_machine.py | head -20
    Expected Result: Ruff/mypy pass, lazy imports still inside function bodies (high line numbers like 108+)
    Evidence: .sisyphus/evidence/task-9-state-machine-quality.txt

  Scenario: State machine tests still pass
    Tool: Bash
    Steps:
      1. cd backend && python -m pytest tests/test_state_machine.py -v 2>&1 || echo "No state machine tests found"
    Expected Result: Tests pass or no tests exist yet (will be added in Task 21)
    Evidence: .sisyphus/evidence/task-9-state-machine-tests.txt
  ```

  **Commit**: NO (groups with Wave 2)

---

- [ ] 10. Quality Enhancement: app/core/security.py, csrf.py, rbac.py, rate_limit.py

  **What to do**:
  - Add type hints to all functions across all 4 files
  - Add docstrings explaining security mechanisms, RBAC roles, rate limit strategies
  - Replace any bare `except:` with specific exception types
  - Add structured logging with `correlation_id` for auth failures and rate limit hits
  - Ensure all password/token handling follows secure patterns (no logging of secrets)
  - Run `ruff check`, `mypy`, `ruff format`

  **Must NOT do**:
  - Do not change authentication/authorization logic
  - Do not change RBAC role definitions or permission mappings
  - Do not change rate limit thresholds or window sizes
  - Do not log secrets, tokens, or passwords (even in debug mode)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 8, 9, 11, 12)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 23
  - **Blocked By**: Task 1

  **References**:
  - `backend/app/core/security.py` — JWT/auth token handling
  - `backend/app/core/csrf.py` — CSRF protection middleware
  - `backend/app/core/rbac.py` — Role-based access control
  - `backend/app/core/rate_limit.py` — Rate limiting middleware
  - `docs/backend_skill.md` — Security coding standards

  **Acceptance Criteria**:
  - [ ] `ruff check` and `mypy` pass on all 4 files
  - [ ] Zero bare `except:` statements
  - [ ] Zero instances of logging secrets/tokens
  - [ ] All public functions have type hints and docstrings

  **QA Scenarios**:
  ```
  Scenario: Security modules pass quality checks
    Tool: Bash
    Steps:
      1. cd backend && ruff check app/core/security.py app/core/csrf.py app/core/rbac.py app/core/rate_limit.py
      2. cd backend && mypy app/core/security.py app/core/csrf.py app/core/rbac.py app/core/rate_limit.py --ignore-missing-imports
    Expected Result: Zero errors on both
    Evidence: .sisyphus/evidence/task-10-security-quality.txt

  Scenario: No secrets in logging
    Tool: Bash
    Steps:
      1. grep -n "log.*password\|log.*token\|log.*secret\|log.*key" backend/app/core/security.py backend/app/core/csrf.py || echo "PASS: no secret logging"
    Expected Result: No matches (no secrets logged)
    Evidence: .sisyphus/evidence/task-10-no-secret-logging.txt
  ```

  **Commit**: NO (groups with Wave 2)

---

- [ ] 11. Quality Enhancement: app/core/worker.py, retry_scheduler.py, tenant_limits.py

  **What to do**:
  - `app/core/worker.py`: Fix the `_send_to_dlq` type error (parameter `error` typed as `str` but receives `Exception` — change to `str(error)` at call sites OR change parameter type to `Union[str, Exception]`). Add type hints to all task functions, add docstrings explaining each worker task, improve structured logging with `correlation_id`, add proper error handling with specific exception types. **CRITICAL: DO NOT move lazy imports inside task functions to module level. DO NOT rename any task function (ARQ serializes names in Redis).**
  - `app/core/retry_scheduler.py`: Add type hints, docstrings, structured logging, proper error handling
  - `app/core/tenant_limits.py`: Add type hints, docstrings, structured logging
  - Run `ruff check`, `mypy`, `ruff format`

  **Must NOT do**:
  - DO NOT move lazy imports in worker task functions to module level
  - DO NOT rename task functions (`investigate_incident`, `generate_recommendation_task`, `execute_action_task`, `verify_resolution_task`, `generate_runbook_task`)
  - Do not change worker configuration (redis URL, timeouts, cron schedules)
  - Do not change DLQ (dead letter queue) logic

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 8, 9, 10, 12)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 23
  - **Blocked By**: Task 1

  **References**:
  - `backend/app/core/worker.py` — ARQ worker, 5 task functions, lazy imports, `_send_to_dlq` type errors at lines 79, 111, 156, 185, 220
  - `backend/app/core/worker.py:265-288` — `WorkerSettings` class with function registration (function references, NOT strings)
  - `backend/app/core/retry_scheduler.py` — Retry logic for failed incidents
  - `backend/app/core/tenant_limits.py` — Concurrency and execution limits

  **Acceptance Criteria**:
  - [ ] `ruff check` and `mypy` pass on all 3 files
  - [ ] The 5 `_send_to_dlq` type errors are fixed
  - [ ] Lazy imports are still inside task function bodies
  - [ ] Task function names unchanged

  **QA Scenarios**:
  ```
  Scenario: Worker module quality + type errors fixed
    Tool: Bash
    Steps:
      1. cd backend && ruff check app/core/worker.py app/core/retry_scheduler.py app/core/tenant_limits.py
      2. cd backend && mypy app/core/worker.py app/core/retry_scheduler.py app/core/tenant_limits.py --ignore-missing-imports
      3. grep -n "def investigate_incident\|def generate_recommendation_task\|def execute_action_task\|def verify_resolution_task\|def generate_runbook_task" backend/app/core/worker.py
    Expected Result: Zero ruff/mypy errors, all 5 function names present unchanged
    Evidence: .sisyphus/evidence/task-11-worker-quality.txt

  Scenario: Lazy imports preserved in worker
    Tool: Bash
    Steps:
      1. grep -n "from app\." backend/app/core/worker.py | head -30
    Expected Result: All app imports are inside function bodies (line numbers > 50), not at module level
    Evidence: .sisyphus/evidence/task-11-lazy-imports.txt
  ```

  **Commit**: NO (groups with Wave 2)

---

- [ ] 12. Quality Enhancement: app/core/metrics.py + remaining core files

  **What to do**:
  - Identify ALL remaining files in `backend/app/core/` not covered by Tasks 8-11
  - For each: add type hints, docstrings, structured logging, proper error handling, clean imports
  - Run `ruff check`, `mypy`, `ruff format` on all core files
  - Run `pytest` to verify nothing is broken

  **Must NOT do**:
  - Do not change Prometheus metric names or labels (dashboards depend on them)
  - Do not change any public API that other modules depend on

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 8, 9, 10, 11)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 23
  - **Blocked By**: Task 1

  **References**:
  - `backend/app/core/metrics.py` — Prometheus metrics definitions
  - `backend/app/core/` — list all files to identify remaining ones not in Tasks 8-11

  **Acceptance Criteria**:
  - [ ] `cd backend && ruff check app/core/` → 0 errors
  - [ ] `cd backend && mypy app/core/ --ignore-missing-imports` → 0 errors
  - [ ] `cd backend && pytest` → all tests still pass

  **QA Scenarios**:
  ```
  Scenario: Entire core/ passes quality checks
    Tool: Bash
    Steps:
      1. cd backend && ruff check app/core/
      2. cd backend && mypy app/core/ --ignore-missing-imports
      3. cd backend && python -m pytest --tb=short 2>&1 | tail -5
    Expected Result: Zero ruff errors, zero mypy errors, all tests pass
    Evidence: .sisyphus/evidence/task-12-core-quality.txt
  ```

  **Commit**: YES
  - Message: `refactor: enhance backend core module quality (types, errors, logging, docs)`
  - Files: `backend/app/core/*`
  - Pre-commit: `cd backend && ruff check app/core/ && pytest`

- [ ] 13. Quality Enhancement: app/models/ (all model files)

  **What to do**:
  - Enhance ALL files in `backend/app/models/`
  - Add type hints to all columns, relationships, and methods
  - Add class-level docstrings explaining each model's domain purpose and relationships
  - Add `__repr__` methods where missing for debugging
  - Ensure all SQLAlchemy column types use proper Python type annotations
  - Verify `backend/app/models/__init__.py` still re-exports ALL 12 models (Alembic depends on this)
  - Clean up imports, remove unused ones
  - Run `ruff check`, `mypy`, `ruff format`

  **Must NOT do**:
  - DO NOT remove any model class or change model class names
  - DO NOT modify `__init__.py` re-exports (Alembic `env.py` imports `Base` from here)
  - DO NOT change column names, types, or constraints (would require a migration)
  - DO NOT add new columns or relationships
  - DO NOT modify `alembic/versions/` files

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 14-19)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 23
  - **Blocked By**: Task 1

  **References**:
  - `backend/app/models/__init__.py` — re-export hub for all 12 models (Alembic depends on this)
  - `backend/app/models/` — list all files to identify every model
  - `docs/database_skill.md` — Database coding standards
  - `docs/backend_skill.md` — Type hint and docstring standards

  **Acceptance Criteria**:
  - [ ] `ruff check backend/app/models/` → 0 errors
  - [ ] `mypy backend/app/models/ --ignore-missing-imports` → 0 errors
  - [ ] `python -c "from app.models import Base; print(Base.metadata.tables.keys())"` works from `backend/`
  - [ ] All 12 model classes still re-exported from `__init__.py`

  **QA Scenarios**:
  ```
  Scenario: Models pass quality + re-exports preserved
    Tool: Bash
    Steps:
      1. cd backend && ruff check app/models/
      2. cd backend && mypy app/models/ --ignore-missing-imports
      3. cd backend && python -c "from app.models import Base; print(len(Base.metadata.tables))"
    Expected Result: Zero errors, 12+ tables detected
    Evidence: .sisyphus/evidence/task-13-models-quality.txt

  Scenario: Model __init__.py re-exports intact
    Tool: Bash
    Steps:
      1. grep -c "from app.models" backend/app/models/__init__.py
    Expected Result: 12+ import lines present
    Evidence: .sisyphus/evidence/task-13-reexports.txt
  ```

  **Commit**: NO (groups with Wave 3)

---

- [ ] 14. Quality Enhancement: app/schemas/ (all schema files)

  **What to do**:
  - Enhance ALL Pydantic schema files in `backend/app/schemas/`
  - Add type hints to all fields (Pydantic v2 style with `Field()` where appropriate)
  - Add class-level docstrings explaining each schema's purpose and usage context (request vs response)
  - Add field validators with descriptive error messages where data integrity matters
  - Ensure consistent naming: `*Create`, `*Update`, `*Response` patterns
  - Clean up imports, run `ruff check`, `mypy`, `ruff format`

  **Must NOT do**:
  - Do not change field names (API contract with frontend)
  - Do not change validation logic that would reject currently-valid input
  - Do not change response shapes (frontend depends on them)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 13, 15-19)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 23
  - **Blocked By**: Task 1

  **References**:
  - `backend/app/schemas/` — all Pydantic schema files
  - `docs/backend_skill.md` — Type hint standards

  **Acceptance Criteria**:
  - [ ] `ruff check backend/app/schemas/` → 0 errors
  - [ ] `mypy backend/app/schemas/ --ignore-missing-imports` → 0 errors
  - [ ] All schema classes have docstrings

  **QA Scenarios**:
  ```
  Scenario: Schemas pass quality checks
    Tool: Bash
    Steps:
      1. cd backend && ruff check app/schemas/
      2. cd backend && mypy app/schemas/ --ignore-missing-imports
    Expected Result: Zero errors
    Evidence: .sisyphus/evidence/task-14-schemas-quality.txt
  ```

  **Commit**: NO (groups with Wave 3)

---

- [ ] 15. Quality Enhancement: app/services/ (all service files)

  **What to do**:
  - Enhance ALL files in `backend/app/services/`
  - Add type hints to all functions (parameters and return types)
  - Add function-level docstrings explaining business logic, parameters, return values, and raised exceptions
  - Replace bare `except:` with specific exception types
  - Add structured logging with `correlation_id` on all significant operations (DB writes, external calls, state changes)
  - Ensure async patterns are correct (proper `await`, no blocking calls in async functions)
  - Clean up imports, run `ruff check`, `mypy`, `ruff format`

  **Must NOT do**:
  - Do not change function signatures (other modules call these)
  - Do not change business logic or state transition sequences
  - Do not rename functions (ARQ worker references some by name)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 13, 14, 16-19)
  - **Parallel Group**: Wave 3
  - **Blocks**: Tasks 21, 22, 23
  - **Blocked By**: Task 1

  **References**:
  - `backend/app/services/` — all service files (incident_service, correlation_service, investigation_service, recommendation_service, execution_service, verification_service, runbook_generator, health_check_service)
  - `backend/app/core/worker.py` — references service functions by import (lazy)
  - `docs/backend_skill.md` — Structured logging and error handling standards

  **Acceptance Criteria**:
  - [ ] `ruff check backend/app/services/` → 0 errors
  - [ ] `mypy backend/app/services/ --ignore-missing-imports` → 0 errors
  - [ ] All public functions have type hints, docstrings, and structured logging
  - [ ] Zero bare `except:` statements

  **QA Scenarios**:
  ```
  Scenario: Services pass quality checks
    Tool: Bash
    Steps:
      1. cd backend && ruff check app/services/
      2. cd backend && mypy app/services/ --ignore-missing-imports
      3. grep -rn "except:" backend/app/services/ | grep -v "except.*Error\|except.*Exception" || echo "PASS: no bare excepts"
    Expected Result: Zero ruff/mypy errors, no bare excepts
    Evidence: .sisyphus/evidence/task-15-services-quality.txt
  ```

  **Commit**: NO (groups with Wave 3)

---

- [ ] 16. Quality Enhancement: app/api/ (routes, dependencies)

  **What to do**:
  - Enhance ALL files in `backend/app/api/` including `dependencies.py` and all route files under `routes/`
  - Add type hints to all endpoint functions (parameters and response models)
  - Add docstrings to all endpoints (these appear in FastAPI auto-generated docs)
  - Fix the `Variable not allowed in type expression` errors in `routes/incidents.py` (lines 51, 151, 307, 308, 445, 510, 565, 629) — likely using runtime type checks instead of proper typing patterns
  - Ensure all endpoints have proper HTTP status codes and error responses
  - Add structured logging for request handling (correlation_id from request context)
  - Clean up imports, run `ruff check`, `mypy`, `ruff format`

  **Must NOT do**:
  - Do not change URL paths or HTTP methods
  - Do not change request/response schemas
  - Do not change authentication/authorization decorators
  - Do not change dependency injection patterns

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 13-15, 17-19)
  - **Parallel Group**: Wave 3
  - **Blocks**: Tasks 22, 23
  - **Blocked By**: Task 1

  **References**:
  - `backend/app/api/dependencies.py` — shared FastAPI dependencies
  - `backend/app/api/routes/incidents.py` — main incident routes, has 8 type expression errors
  - `backend/app/api/routes/` — all route modules
  - `docs/backend_skill.md` — API coding standards

  **Acceptance Criteria**:
  - [ ] `ruff check backend/app/api/` → 0 errors
  - [ ] `mypy backend/app/api/ --ignore-missing-imports` → 0 errors
  - [ ] All `Variable not allowed in type expression` errors fixed in incidents.py
  - [ ] All endpoints have docstrings (visible in `/docs` Swagger UI)

  **QA Scenarios**:
  ```
  Scenario: API routes pass quality checks
    Tool: Bash
    Steps:
      1. cd backend && ruff check app/api/
      2. cd backend && mypy app/api/ --ignore-missing-imports
    Expected Result: Zero errors
    Evidence: .sisyphus/evidence/task-16-api-quality.txt

  Scenario: Type expression errors fixed in incidents.py
    Tool: Bash
    Steps:
      1. cd backend && mypy app/api/routes/incidents.py --ignore-missing-imports 2>&1 | grep "Variable not allowed"
    Expected Result: No output (all type expression errors fixed)
    Evidence: .sisyphus/evidence/task-16-incidents-type-fix.txt
  ```

  **Commit**: NO (groups with Wave 3)

---

- [ ] 17. Quality Enhancement: app/cloud/ (all cloud adapters)

  **What to do**:
  - Enhance ALL files in `backend/app/cloud/` (~18 files: AWS SSM, OS Login, discovery, tag_parser, etc.)
  - Add type hints to all functions, especially cloud API call wrappers
  - Add docstrings explaining which AWS/GCP APIs are used and what permissions are required
  - Replace bare `except:` with specific boto3/GCP exception types
  - Add structured logging with `correlation_id` for all cloud API calls (request/response timing)
  - Ensure all cloud credentials are handled securely (no logging of access keys)
  - Clean up imports, run `ruff check`, `mypy`, `ruff format`

  **Must NOT do**:
  - Do not change cloud API call logic or parameters
  - Do not change IAM permission requirements
  - Do not log cloud credentials or access keys

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 13-16, 18, 19)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 23
  - **Blocked By**: Task 1

  **References**:
  - `backend/app/cloud/` — all cloud adapter files (AWS SSM, GCP OS Login, discovery, tag_parser, etc.)
  - `docs/backend_skill.md` — Structured logging and security standards

  **Acceptance Criteria**:
  - [ ] `ruff check backend/app/cloud/` → 0 errors
  - [ ] `mypy backend/app/cloud/ --ignore-missing-imports` → 0 errors
  - [ ] Zero instances of logged credentials

  **QA Scenarios**:
  ```
  Scenario: Cloud modules pass quality checks
    Tool: Bash
    Steps:
      1. cd backend && ruff check app/cloud/
      2. cd backend && mypy app/cloud/ --ignore-missing-imports
      3. grep -rn "log.*access_key\|log.*secret\|log.*credential" backend/app/cloud/ || echo "PASS: no credential logging"
    Expected Result: Zero errors, no credential logging
    Evidence: .sisyphus/evidence/task-17-cloud-quality.txt
  ```

  **Commit**: NO (groups with Wave 3)

---

- [ ] 18. Quality Enhancement: app/investigations/ + app/actions/

  **What to do**:
  - Enhance ALL files in `backend/app/investigations/` (~14 probe files) and `backend/app/actions/` (~15 action plugin files)
  - Add type hints to all functions (probe/action entry points, helper functions)
  - Add docstrings explaining what each probe investigates and what each action remediates
  - Add proper error handling — probes should catch specific exceptions and return structured failure results instead of crashing
  - Add structured logging with `correlation_id` for probe execution and action execution
  - Ensure all cloud/external calls have timeout handling
  - Clean up imports, run `ruff check`, `mypy`, `ruff format`

  **Must NOT do**:
  - Do not change probe/action registration names (referenced by worker)
  - Do not change probe output format (consumed by recommendation service)
  - Do not change action execution logic

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 13-17, 19)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 23
  - **Blocked By**: Task 1

  **References**:
  - `backend/app/investigations/` — ~14 investigation probe files
  - `backend/app/actions/` — ~15 remediation action plugin files
  - `backend/app/core/worker.py` — references probes and actions via service layer

  **Acceptance Criteria**:
  - [ ] `ruff check backend/app/investigations/ backend/app/actions/` → 0 errors
  - [ ] `mypy backend/app/investigations/ backend/app/actions/ --ignore-missing-imports` → 0 errors
  - [ ] All probe and action files have class/function docstrings

  **QA Scenarios**:
  ```
  Scenario: Investigations and actions pass quality checks
    Tool: Bash
    Steps:
      1. cd backend && ruff check app/investigations/ app/actions/
      2. cd backend && mypy app/investigations/ app/actions/ --ignore-missing-imports
    Expected Result: Zero errors
    Evidence: .sisyphus/evidence/task-18-probes-actions-quality.txt
  ```

  **Commit**: NO (groups with Wave 3)

---

- [ ] 19. Quality Enhancement: app/llm/ + app/rag/ + app/monitoring/

  **What to do**:
  - Enhance ALL files in `backend/app/llm/` (4 files: LiteLLM client, prompt management)
  - Enhance ALL files in `backend/app/rag/` (3 files: vector store, chunking)
  - Enhance ALL files in `backend/app/monitoring/` (Site24x7 client)
  - Add type hints, docstrings, structured logging, proper error handling
  - For LLM files: ensure prompt templates are well-documented, API call timeouts handled, token usage logged
  - For RAG files: ensure vector operations have proper error handling for embedding failures
  - For monitoring: ensure Site24x7 API calls have proper timeout and error handling
  - Fix `sys.path` hacks in any scripts (`create_admin_user.py`, `test_ssm_direct.py`, `test_ssm.py`) — replace with `pathlib.Path(__file__).resolve().parent.parent`
  - Run `ruff check`, `mypy`, `ruff format` on all files
  - Run full `pytest` to verify nothing is broken after all Wave 2+3 quality changes

  **Must NOT do**:
  - Do not change LLM prompt templates or model parameters
  - Do not change RAG chunking strategy or vector dimensions
  - Do not change Site24x7 API endpoints or auth

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 13-18)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 23
  - **Blocked By**: Task 1

  **References**:
  - `backend/app/llm/` — LiteLLM client, prompt management
  - `backend/app/rag/` — vector store, chunking logic
  - `backend/app/monitoring/` — Site24x7 client (already exists, NOT moved)
  - `backend/scripts/create_admin_user.py` — has sys.path hack to fix
  - `backend/scripts/test_ssm_direct.py`, `backend/scripts/test_ssm.py` — have sys.path hacks

  **Acceptance Criteria**:
  - [ ] `ruff check backend/app/llm/ backend/app/rag/ backend/app/monitoring/` → 0 errors
  - [ ] `mypy` passes on all 3 directories
  - [ ] `sys.path` hacks replaced with `pathlib` in scripts
  - [ ] Full `pytest` suite passes after all Wave 2+3 changes

  **QA Scenarios**:
  ```
  Scenario: LLM/RAG/monitoring pass quality + full test suite
    Tool: Bash
    Steps:
      1. cd backend && ruff check app/llm/ app/rag/ app/monitoring/
      2. cd backend && mypy app/llm/ app/rag/ app/monitoring/ --ignore-missing-imports
      3. cd backend && python -m pytest --tb=short 2>&1 | tail -10
    Expected Result: Zero ruff/mypy errors, all tests pass
    Evidence: .sisyphus/evidence/task-19-llm-rag-monitoring-quality.txt

  Scenario: sys.path hacks fixed in scripts
    Tool: Bash
    Steps:
      1. grep -rn "sys.path" backend/scripts/ || echo "PASS: no sys.path hacks"
    Expected Result: No sys.path manipulation found (replaced with pathlib)
    Evidence: .sisyphus/evidence/task-19-syspath-fixed.txt
  ```

  **Commit**: YES
  - Message: `refactor: enhance backend models, schemas, services, API, cloud, and plugin quality`
  - Files: `backend/app/models/*`, `schemas/*`, `services/*`, `api/*`, `cloud/*`, `investigations/*`, `actions/*`, `llm/*`, `rag/*`, `monitoring/*`, `scripts/*`
  - Pre-commit: `cd backend && ruff check app/ && pytest`

- [ ] 20. Frontend Quality Enhancement: ESLint, component cleanup, prop types

  **What to do**:
  - Run `npm run lint` in `apps/web/` and fix ALL ESLint errors and warnings
  - Add PropTypes or JSDoc type annotations to ALL React components
  - Clean up component files: remove unused imports, unused state variables, dead code
  - Ensure all components are functional (no class components)
  - Ensure all API calls are in `services/` (not inline fetch in components)
  - Ensure Tailwind utilities are used consistently (no ad-hoc CSS)
  - Add component-level JSDoc comments explaining purpose, props, and usage
  - Ensure no direct DOM mutation (use React state/refs)
  - Ensure no raw HTML injection (treat backend strings as untrusted)
  - Run `npm run lint` and `npm run build` after all changes
  - Run `npm run test -- --run` to verify existing tests pass

  **Must NOT do**:
  - Do not change component behavior or UI layout
  - Do not change API call URLs or request shapes
  - Do not change routing paths
  - Do not add new dependencies (use existing ESLint config)
  - Do not change CSS/Tailwind class names that affect visual appearance

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]
    - `frontend-ui-ux`: React component quality patterns, accessibility, prop type best practices

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 21, 22)
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 23
  - **Blocked By**: Task 2

  **References**:
  - `apps/web/src/` — all React source files (after move from frontend/)
  - `apps/web/eslint.config.js` — ESLint configuration
  - `apps/web/src/services/api.js` — API service layer (Axios)
  - `apps/web/src/services/sse.js` — SSE client
  - `apps/web/src/App.jsx` — Routing hub (React Router v7)
  - `apps/web/src/context/` — AuthContext, ThemeContext
  - `docs/frontend_skill.md` — Frontend coding standards

  **Acceptance Criteria**:
  - [ ] `cd apps/web && npm run lint` → 0 errors, 0 warnings
  - [ ] `cd apps/web && npm run build` → success
  - [ ] `cd apps/web && npm run test -- --run` → all tests pass
  - [ ] All components have PropTypes or JSDoc type annotations
  - [ ] Zero inline fetch calls in component files

  **QA Scenarios**:
  ```
  Scenario: Frontend lint and build pass
    Tool: Bash
    Steps:
      1. cd apps/web && npm run lint 2>&1
      2. cd apps/web && npm run build 2>&1
      3. cd apps/web && npm run test -- --run 2>&1
    Expected Result: Zero lint errors/warnings, build succeeds, tests pass
    Failure Indicators: "error" or "warning" in lint output, non-zero exit code
    Evidence: .sisyphus/evidence/task-20-frontend-quality.txt

  Scenario: No inline fetch in components
    Tool: Bash
    Steps:
      1. grep -rn "fetch(" apps/web/src/components/ apps/web/src/pages/ 2>/dev/null | grep -v "node_modules" || echo "PASS: no inline fetch"
    Expected Result: No matches (all API calls should be in services/)
    Evidence: .sisyphus/evidence/task-20-no-inline-fetch.txt
  ```

  **Commit**: YES
  - Message: `refactor: enhance frontend code quality (lint, prop types, cleanup)`
  - Files: `apps/web/src/*`
  - Pre-commit: `cd apps/web && npm run lint && npm run build`

---

- [ ] 21. Add Backend Tests: State Machine Transitions

  **What to do**:
  - Create/enhance `backend/tests/test_state_machine.py` with comprehensive state transition tests
  - Test ALL valid state transitions defined in the state machine
  - Test ALL invalid state transitions (should raise appropriate errors)
  - Test edge cases: transition from terminal states, duplicate transitions, concurrent transitions
  - Test that state machine properly calls downstream services (mock them)
  - Test that lazy imports in state machine resolve correctly
  - Use `pytest-asyncio` for async tests
  - Ensure structured logging is captured in tests (verify correlation_id presence)

  **Must NOT do**:
  - Do not modify the state machine source code (only add tests)
  - Do not create real database connections (use mocks/fixtures)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 20, 22)
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 23
  - **Blocked By**: Tasks 8-19 (quality changes must be done first)

  **References**:
  - `backend/app/core/state_machine.py` — source code to test (state transitions, lazy imports)
  - `backend/tests/test_state_machine.py` — may already exist (check first, enhance if so)
  - `backend/tests/conftest.py` — existing test fixtures
  - `backend/app/models/enums.py` — state enum definitions (IncidentStatus, etc.)

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_state_machine.py -v` → all pass
  - [ ] Tests cover every valid state transition
  - [ ] Tests cover at least 3 invalid transitions (expect errors)
  - [ ] At least 15 test cases total

  **QA Scenarios**:
  ```
  Scenario: State machine tests pass
    Tool: Bash
    Steps:
      1. cd backend && python -m pytest tests/test_state_machine.py -v 2>&1
    Expected Result: All tests pass, 15+ test cases
    Failure Indicators: FAILED or ERROR in output
    Evidence: .sisyphus/evidence/task-21-state-machine-tests.txt

  Scenario: Tests cover valid and invalid transitions
    Tool: Bash
    Steps:
      1. grep -c "def test_" backend/tests/test_state_machine.py
      2. grep -c "invalid\|error\|reject\|fail" backend/tests/test_state_machine.py
    Expected Result: 15+ test functions, 3+ invalid/error test cases
    Evidence: .sisyphus/evidence/task-21-test-coverage.txt
  ```

  **Commit**: NO (groups with Task 22)

---

- [ ] 22. Add Backend Tests: Worker Tasks + API Routes

  **What to do**:
  - Create/enhance `backend/tests/test_worker.py` with tests for all 5 ARQ task functions:
    - `investigate_incident`, `generate_recommendation_task`, `execute_action_task`, `verify_resolution_task`, `generate_runbook_task`
  - Mock external dependencies (database, Redis, LLM, cloud APIs)
  - Test happy path and error handling for each task
  - Test DLQ (dead letter queue) behavior on failures
  - Create/enhance `backend/tests/test_api_routes.py` with tests for critical API endpoints:
    - Health check, incident CRUD, webhook ingestion, incident state transitions
  - Use FastAPI `TestClient` or `httpx.AsyncClient` for API tests
  - Use `pytest-asyncio` for async tests

  **Must NOT do**:
  - Do not modify source code (only add tests)
  - Do not make real HTTP/cloud/LLM calls (mock everything external)
  - Do not create real database state (use fixtures/mocks)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 20, 21)
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 23
  - **Blocked By**: Tasks 8-19 (quality changes must be done first)

  **References**:
  - `backend/app/core/worker.py` — worker task functions to test
  - `backend/app/api/routes/` — API route modules to test
  - `backend/app/main.py` — FastAPI app instance for TestClient
  - `backend/tests/conftest.py` — existing test fixtures and configuration
  - `backend/tests/` — existing test files for patterns to follow

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_worker.py -v` → all pass
  - [ ] `pytest tests/test_api_routes.py -v` → all pass
  - [ ] At least 5 worker tests (1 per task function)
  - [ ] At least 8 API route tests (health, CRUD, webhooks, transitions)
  - [ ] All tests use mocks for external dependencies

  **QA Scenarios**:
  ```
  Scenario: Worker and API tests pass
    Tool: Bash
    Steps:
      1. cd backend && python -m pytest tests/test_worker.py tests/test_api_routes.py -v 2>&1
    Expected Result: All tests pass
    Failure Indicators: FAILED or ERROR in output
    Evidence: .sisyphus/evidence/task-22-worker-api-tests.txt

  Scenario: Adequate test coverage
    Tool: Bash
    Steps:
      1. grep -c "def test_" backend/tests/test_worker.py
      2. grep -c "def test_" backend/tests/test_api_routes.py
    Expected Result: 5+ worker tests, 8+ API route tests
    Evidence: .sisyphus/evidence/task-22-test-count.txt
  ```

  **Commit**: YES
  - Message: `feat: add tests for state machine, worker tasks, and API routes`
  - Files: `backend/tests/test_state_machine.py`, `backend/tests/test_worker.py`, `backend/tests/test_api_routes.py`
  - Pre-commit: `cd backend && pytest`

---

- [ ] 23. Full Integration Verification

  **What to do**:
  - Run the COMPLETE verification suite from a clean state:
  - **Backend**: `cd backend && ruff check app/ && mypy app/ --ignore-missing-imports && pytest`
  - **Frontend**: `cd apps/web && npm run lint && npm run build && npm run test -- --run`
  - **Database**: `cd database && alembic history` (verify alembic works from new location)
  - **Docker**: `docker-compose config` (verify compose file is valid)
  - **Docker build**: `docker-compose build` (verify all services build)
  - **Directory structure**: Verify `frontend/` deleted, `backend/alembic/` deleted, `apps/web/src/` exists, `database/alembic/` exists
  - Compare test results against Task 1 baseline — ensure no regressions
  - Fix any issues found during verification

  **Must NOT do**:
  - Do not introduce new code — only fix issues found during verification
  - Do not change test expectations (fix source code if tests fail)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (must run after all other tasks)
  - **Parallel Group**: Wave 5 (solo)
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 4-7, 8-22

  **References**:
  - `.sisyphus/evidence/task-1-backend-baseline.txt` — baseline test results for comparison
  - `.sisyphus/evidence/task-1-frontend-baseline.txt` — baseline frontend results
  - All previous task evidence files

  **Acceptance Criteria**:
  - [ ] `ruff check app/` → 0 errors (in backend/)
  - [ ] `mypy app/ --ignore-missing-imports` → 0 errors (in backend/)
  - [ ] `pytest` → all pass (in backend/)
  - [ ] `npm run lint` → 0 errors (in apps/web/)
  - [ ] `npm run build` → success (in apps/web/)
  - [ ] `npm run test -- --run` → all pass (in apps/web/)
  - [ ] `docker-compose config` → valid
  - [ ] `frontend/` does not exist
  - [ ] `backend/alembic/` does not exist
  - [ ] `apps/web/src/` exists
  - [ ] `database/alembic/versions/` exists
  - [ ] Test count >= baseline count (no test regressions)

  **QA Scenarios**:
  ```
  Scenario: Full backend verification
    Tool: Bash
    Steps:
      1. cd backend && ruff check app/ 2>&1
      2. cd backend && mypy app/ --ignore-missing-imports 2>&1
      3. cd backend && python -m pytest --tb=short 2>&1
    Expected Result: Zero lint errors, zero type errors, all tests pass
    Evidence: .sisyphus/evidence/task-23-backend-verify.txt

  Scenario: Full frontend verification
    Tool: Bash
    Steps:
      1. cd apps/web && npm run lint 2>&1
      2. cd apps/web && npm run build 2>&1
      3. cd apps/web && npm run test -- --run 2>&1
    Expected Result: Zero lint errors, build succeeds, all tests pass
    Evidence: .sisyphus/evidence/task-23-frontend-verify.txt

  Scenario: Directory structure verification
    Tool: Bash
    Steps:
      1. test ! -d frontend && echo "PASS: frontend/ deleted" || echo "FAIL: frontend/ still exists"
      2. test ! -d backend/alembic && echo "PASS: backend/alembic/ deleted" || echo "FAIL"
      3. test -d apps/web/src && echo "PASS: apps/web/src/ exists" || echo "FAIL"
      4. test -d database/alembic/versions && echo "PASS: database/alembic/versions/ exists" || echo "FAIL"
      5. test -f database/Dockerfile && echo "PASS: database/Dockerfile exists" || echo "FAIL"
    Expected Result: All PASS
    Evidence: .sisyphus/evidence/task-23-directory-verify.txt

  Scenario: Docker compose validation
    Tool: Bash
    Steps:
      1. docker-compose config > /dev/null 2>&1 && echo "PASS" || echo "FAIL"
    Expected Result: PASS
    Evidence: .sisyphus/evidence/task-23-compose-verify.txt

  Scenario: No regression from baseline
    Tool: Bash
    Steps:
      1. Compare test counts from task-23-backend-verify.txt against task-1-backend-baseline.txt
      2. Compare frontend build results against task-1-frontend-baseline.txt
    Expected Result: Test count >= baseline, no new failures
    Evidence: .sisyphus/evidence/task-23-regression-check.txt
  ```

  **Commit**: NO (evidence only — all code commits already done in prior tasks)

---

## Final Verification Wave

> 4 review agents run in PARALLEL. ALL must APPROVE.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists. For each "Must NOT Have": search codebase for forbidden patterns. Check evidence files exist in `.sisyphus/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check app/` + `mypy app/ --ignore-missing-imports` + `pytest` in `backend/`. Run `npm run lint` + `npm run build` in `apps/web/`. Review changed files for: `as any`/`@ts-ignore`, empty catches, console.log in prod, commented-out code, unused imports. Check for excessive comments, over-abstraction.
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high` + `playwright`
  Start from clean state. Run `docker-compose up`. Verify all services start. Test API health endpoint. Test frontend loads. Run all QA scenarios from all tasks. Save evidence to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: verify what was specified was built, and nothing beyond. Check "Must NOT do" compliance. Detect unaccounted file changes. Verify `frontend/` directory is deleted. Verify `backend/alembic/` is deleted.
  Output: `Tasks [N/N compliant] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| Wave | Commit Message | Files |
|------|---------------|-------|
| 0 | `refactor: move frontend to apps/web` | `apps/web/*`, delete `frontend/` |
| 0 | `refactor: move alembic to database/` | `database/*`, delete `backend/alembic/`, `backend/alembic.ini` |
| 1 | `chore: update Dockerfiles and buildspecs for new paths` | `services/airex-frontend/Dockerfile`, `docker-compose.yml`, `buildspec.frontend.yml`, `database/Dockerfile` |
| 2 | `refactor: enhance core module quality (types, errors, logging)` | `backend/app/core/*` |
| 3 | `refactor: enhance models, schemas, services, API quality` | `backend/app/models/*`, `schemas/*`, `services/*`, `api/*`, `cloud/*`, etc. |
| 4 | `feat: add tests for critical paths` | `backend/tests/*` |
| 4 | `refactor: enhance frontend code quality` | `apps/web/src/*` |
| 5 | `test: full integration verification` | Evidence files only |

---

## Success Criteria

### Verification Commands
```bash
# Backend tests
cd backend && pytest                                    # Expected: all pass
cd backend && ruff check app/                           # Expected: 0 errors
cd backend && mypy app/ --ignore-missing-imports        # Expected: 0 errors

# Frontend
cd apps/web && npm run lint                             # Expected: 0 errors
cd apps/web && npm run build                            # Expected: success
cd apps/web && npm run test                             # Expected: all pass

# Database migrations
cd database && alembic upgrade head                     # Expected: success (with DATABASE_URL set)

# Docker
docker-compose build                                    # Expected: all services build
docker-compose up -d                                    # Expected: all services start
curl http://localhost:8000/health                        # Expected: 200 OK

# Directory verification
test ! -d frontend && echo "PASS"                       # Expected: PASS (frontend/ deleted)
test ! -d backend/alembic && echo "PASS"                # Expected: PASS (alembic moved)
test -d apps/web/src && echo "PASS"                     # Expected: PASS
test -d database/alembic && echo "PASS"                 # Expected: PASS
```

### Final Checklist
- [ ] All "Must Have" items present
- [ ] All "Must NOT Have" items absent
- [ ] All backend tests pass
- [ ] All frontend tests pass
- [ ] Docker-compose builds and starts all services
- [ ] Alembic works from `database/` folder
- [ ] No duplicate code (single `backend/` source)
- [ ] Each service folder has Dockerfile
- [ ] Pipeline independence verified
