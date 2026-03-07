# Learnings — monorepo-restructure

## [2026-03-07] Session ses_337dab47bffeuFoesH2qlm1kfg

### Architecture
- Backend stays as shared Python package — API and Worker share ~70% of code
- Both `services/airex-api/Dockerfile` and `services/airex-worker/Dockerfile` use `COPY backend/ .` from root context
- `docker-compose.yml` uses `./backend:/app` volume mounts for both api and worker
- LSP errors in backend files are from missing virtualenv on host — NOT actual code errors

### Critical Guardrails
- Lazy imports in `worker.py` (task functions) and `state_machine.py` (6 locations) are INTENTIONAL — prevent circular imports. DO NOT move to module level.
- ARQ task function names must NOT be renamed: `investigate_incident`, `generate_recommendation_task`, `execute_action_task`, `verify_resolution_task`, `generate_runbook_task`
- `app/models/__init__.py` re-exports all 12 models for Alembic — MUST be preserved
- `alembic/versions/` files must NEVER be modified

### Path Reference Inventory (files that need updating when frontend moves)
- `services/airex-frontend/Dockerfile` — 3 refs to `frontend/` → `apps/web/`
- `deployment/ecs/codebuild/buildspec.frontend.yml` — 4 refs to `frontend/` → `apps/web/`
- `docker-compose.yml:136` — `./backend/scripts/init-multi-db.sql` → `./database/scripts/init-multi-db.sql`
- `database/alembic.ini` — needs `prepend_sys_path = ../backend` (after alembic moves)

### What NOT to Touch
- `services/litellm/` and `services/langfuse/` — already set up, do not touch
- `deployment/ecs/codebuild/buildspec.images.yml` — already references services/ Dockerfiles correctly
- `deployment/ecs/terraform/` — IaC, never modify
- `infra/` directory — prometheus/grafana configs volume-mounted by docker-compose
- `backend/app/monitoring/` — already exists with Site24x7 client (no move needed)

## Task 1: Baseline testing results (2026-03-07)
- Backend baseline:
  - pytest: not available in this environment (command not found)
  - ruff: not available in this environment (command not found)
  - mypy: not available in this environment (command not found)
- Frontend baseline:
  - npm run build: vite not found
  - npm run test: vitest not found

- Observations:
  - The environment lacks essential tooling (pytest, ruff, mypy, vite, vitest), so baseline test results could not be collected.
  - No source files were modified during this attempt; only evidence files were created as placeholders.
- Evidence files created/updated during this run:
  - .sisyphus/evidence/task-1-backend-baseline.txt
  - .sisyphus/evidence/task-1-frontend-baseline.txt
- Next steps:
  - Install required tooling or run in a container with Python/Node tooling available
  - Re-run the baseline in a fully provisioned environment and record exact pass/fail counts
