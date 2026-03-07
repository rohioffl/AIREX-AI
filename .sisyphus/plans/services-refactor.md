# Services Directory Refactor

## TL;DR

> **Quick Summary**: Consolidate all Dockerfiles under `services/`, remove redundant files, add root `.dockerignore`, and verify builds work with root context.
> 
> **Deliverables**:
> - Remove `frontend/Dockerfile` (superseded by `services/airex-frontend/Dockerfile`)
> - Create root `.dockerignore` for lean root-context builds
> - Remove inert subdirectory `.dockerignore` files
> - Verify `docker compose build` succeeds for all services
> - Update AGENTS.md if stale Docker references exist
> 
> **Estimated Effort**: Quick
> **Parallel Execution**: YES - 2 waves
> **Critical Path**: Task 1-3 (parallel) → Task 4 (build verify) → Task 5 (docs)

---

## Context

### Original Request
Refactor `services/` directory structure — consolidate backend Dockerfiles under `services/`, align `docker-compose.yml` with CodeBuild buildspec.

### Interview Summary
**Key Discussions**:
- `services/` already contains production Dockerfiles for airex-api, airex-worker, litellm
- `docker-compose.yml` was inconsistent (used `backend/Dockerfile` with `context: ./backend`)
- `apps/web/` is a separate S3+CloudFront deployment, not Docker-based
- `services/airex-frontend/Dockerfile` is for local Docker dev only; production uses `buildspec.frontend.yml` → S3

**Changes Already Made This Session** (before plan):
1. `docker-compose.yml` updated to use `services/` Dockerfiles with `context: .`
2. `services/airex-frontend/Dockerfile` created with root-relative COPY paths
3. `backend/Dockerfile` removed
4. `.opencodeignore` created

### Metis Review
**Identified Gaps** (addressed):
- Subdirectory `.dockerignore` files are now inert (root context ignores them) → include removal in plan
- Root `.dockerignore` missing → critical for build context size and secret exclusion
- No stale-reference verification before file deletion → added grep checks
- `.env` files could leak into Docker context without root `.dockerignore` → addressed

---

## Work Objectives

### Core Objective
Complete the services/ consolidation by removing redundant Dockerfiles and adding proper root-level Docker ignore rules.

### Concrete Deliverables
- `frontend/Dockerfile` deleted
- `backend/.dockerignore` deleted
- `frontend/.dockerignore` deleted (verify exists first)
- `/.dockerignore` created with comprehensive exclusions
- All 4 docker-compose build targets verified
- AGENTS.md updated if needed

### Definition of Done
- [ ] `ls frontend/Dockerfile` returns "not found"
- [ ] `ls backend/.dockerignore` returns "not found"
- [ ] `.dockerignore` exists at repo root
- [ ] `docker compose build backend worker migrate frontend` exits 0
- [ ] `grep -r "backend/Dockerfile\|frontend/Dockerfile" AGENTS.md` returns 0 matches

### Must Have
- Root `.dockerignore` excludes `.git`, `node_modules`, `.venv`, `__pycache__`, `.env*`, `*.pyc`
- Root `.dockerignore` does NOT exclude `backend/`, `frontend/`, `services/`
- No stale references to deleted files in AGENTS.md or docker-compose.yml

### Must NOT Have (Guardrails)
- DO NOT modify any `buildspec*.yml` files
- DO NOT modify any existing Dockerfile content (only delete entire files)
- DO NOT move `frontend/nginx.conf` (still referenced by `services/airex-frontend/Dockerfile`)
- DO NOT touch `services/langfuse/` or the `ai-platform` docker-compose service
- DO NOT change docker-compose service names, ports, or environment variables
- DO NOT add `services/airex-frontend/` to `buildspec.images.yml` (production frontend deploys via S3)

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: NO (no unit tests for Docker config)
- **Automated tests**: None (infrastructure refactor)
- **Framework**: N/A

### QA Policy
Every task includes agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Infrastructure**: Use Bash — run docker commands, grep for references, verify file existence

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — file cleanup, parallel):
├── Task 1: Remove frontend/Dockerfile [quick]
├── Task 2: Remove inert subdirectory .dockerignore files [quick]
├── Task 3: Create root .dockerignore [quick]

Wave 2 (After Wave 1 — verification):
├── Task 4: Verify docker compose build (depends: 1, 2, 3) [quick]
├── Task 5: Update AGENTS.md stale references (depends: 1) [quick]

Wave FINAL (After ALL tasks):
└── Task F1: Scope fidelity check [quick]

Critical Path: Tasks 1-3 → Task 4 → F1
Parallel Speedup: ~50% faster than sequential
Max Concurrent: 3 (Wave 1)
```

### Dependency Matrix

| Task | Depends On | Blocks |
|------|-----------|--------|
| 1 | — | 4, 5, F1 |
| 2 | — | 4, F1 |
| 3 | — | 4, F1 |
| 4 | 1, 2, 3 | F1 |
| 5 | 1 | F1 |
| F1 | 4, 5 | — |

### Agent Dispatch Summary

- **Wave 1**: 3 tasks — T1 → `quick`, T2 → `quick`, T3 → `quick`
- **Wave 2**: 2 tasks — T4 → `quick`, T5 → `quick`
- **FINAL**: 1 task — F1 → `quick`

---

## TODOs

- [x] 1. Remove frontend/Dockerfile

  **What to do**:
  - Verify no file references `frontend/Dockerfile` (grep across `.yml`, `.yaml`, `.sh`, `.md`, `Makefile`)
  - Delete `frontend/Dockerfile`

  **Must NOT do**:
  - Do not delete `frontend/nginx.conf` or any other frontend file
  - Do not modify any other file

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Tasks 4, 5
  - **Blocked By**: None

  **References**:
  - `services/airex-frontend/Dockerfile` — the replacement that uses root-relative `COPY frontend/` paths
  - `deployment/ecs/codebuild/buildspec.frontend.yml` — production frontend does NOT use Docker (uses npm+S3)

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: frontend/Dockerfile is removed and unreferenced
    Tool: Bash
    Preconditions: frontend/Dockerfile currently exists
    Steps:
      1. Run: grep -r "frontend/Dockerfile" . --include="*.yml" --include="*.yaml" --include="*.sh" --include="*.md" | grep -v ".git/"
      2. Assert: 0 matches (safe to delete)
      3. Run: rm frontend/Dockerfile
      4. Run: test ! -f frontend/Dockerfile && echo "PASS" || echo "FAIL"
    Expected Result: "PASS" — file no longer exists
    Evidence: .sisyphus/evidence/task-1-frontend-dockerfile-removed.txt
  ```

  **Commit**: YES (groups with 2, 3)
  - Message: `refactor: remove redundant Dockerfiles and add root .dockerignore`
  - Files: `frontend/Dockerfile` (deleted)

- [ ] 2. Remove inert subdirectory .dockerignore files

  **What to do**:
  - Delete `backend/.dockerignore` (inert since build context is now root)
  - Check if `frontend/.dockerignore` exists; delete if so
  - These files do nothing for root-context builds and mislead developers

  **Must NOT do**:
  - Do not delete any other dotfiles
  - Do not modify any Dockerfile

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3)
  - **Blocks**: Task 4
  - **Blocked By**: None

  **References**:
  - `backend/.dockerignore` — contains `.venv`, `__pycache__`, `.env` exclusions (now handled by root `.dockerignore`)

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Subdirectory .dockerignore files removed
    Tool: Bash
    Preconditions: backend/.dockerignore exists
    Steps:
      1. Run: rm -f backend/.dockerignore frontend/.dockerignore
      2. Run: test ! -f backend/.dockerignore && test ! -f frontend/.dockerignore && echo "PASS" || echo "FAIL"
    Expected Result: "PASS"
    Evidence: .sisyphus/evidence/task-2-dockerignore-cleanup.txt
  ```

  **Commit**: YES (groups with 1, 3)
  - Message: `refactor: remove redundant Dockerfiles and add root .dockerignore`
  - Files: `backend/.dockerignore` (deleted), `frontend/.dockerignore` (deleted if exists)

- [ ] 3. Create root .dockerignore

  **What to do**:
  - Create `/.dockerignore` at repo root with comprehensive exclusions
  - Must exclude: `.git`, `node_modules`, `.venv`, `__pycache__`, `*.pyc`, `.env*`, `.pytest_cache`, `e2e/`, `deployment/`, `infra/`, `docs/`, `apps/`, `.sisyphus/`, `htmlcov/`, `.coverage`
  - Must NOT exclude: `backend/`, `frontend/`, `services/`

  **Must NOT do**:
  - Do not exclude directories referenced by any Dockerfile COPY instruction
  - Do not modify any existing file

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2)
  - **Blocks**: Task 4
  - **Blocked By**: None

  **References**:
  - `services/airex-api/Dockerfile` — COPY paths: `backend/requirements.txt`, `backend/`
  - `services/airex-worker/Dockerfile` — COPY paths: `backend/requirements.txt`, `backend/`
  - `services/airex-frontend/Dockerfile` — COPY paths: `frontend/package.json`, `frontend/package-lock.json`, `frontend/`, `frontend/nginx.conf`
  - `services/litellm/Dockerfile` — COPY paths: `services/litellm/config.yaml`

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Root .dockerignore exists with correct exclusions
    Tool: Bash
    Preconditions: No root .dockerignore exists
    Steps:
      1. Create .dockerignore with exclusions listed above
      2. Run: test -f .dockerignore && echo "EXISTS" || echo "MISSING"
      3. Run: grep -c ".git" .dockerignore (assert >= 1)
      4. Run: grep -c "node_modules" .dockerignore (assert >= 1)
      5. Run: grep -c ".venv" .dockerignore (assert >= 1)
      6. Run: grep -c ".env" .dockerignore (assert >= 1)
      7. Run: grep "^backend" .dockerignore (assert 0 matches — must not exclude backend/)
      8. Run: grep "^frontend" .dockerignore (assert 0 matches — must not exclude frontend/)
      9. Run: grep "^services" .dockerignore (assert 0 matches — must not exclude services/)
    Expected Result: File exists, all critical exclusions present, no false exclusions
    Evidence: .sisyphus/evidence/task-3-dockerignore-created.txt

  Scenario: .dockerignore does not block Dockerfile COPY targets
    Tool: Bash
    Steps:
      1. Run: docker compose config --services (verify all services parse)
    Expected Result: All service names listed without error
    Evidence: .sisyphus/evidence/task-3-compose-config.txt
  ```

  **Commit**: YES (groups with 1, 2)
  - Message: `refactor: remove redundant Dockerfiles and add root .dockerignore`
  - Files: `.dockerignore` (new)

- [ ] 4. Verify docker compose build

  **What to do**:
  - Run `docker compose build backend worker migrate frontend` and verify exit code 0
  - Confirm all 4 images are created

  **Must NOT do**:
  - Do not run `docker compose up` (may start services that fail without DB)
  - Do not modify any files

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2
  - **Blocks**: F1
  - **Blocked By**: Tasks 1, 2, 3

  **References**:
  - `docker-compose.yml` — service definitions with `context: .` and `services/` Dockerfiles

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: All docker compose services build successfully
    Tool: Bash
    Preconditions: Tasks 1-3 complete, Docker daemon running
    Steps:
      1. Run: docker compose build backend worker migrate frontend
      2. Assert: exit code 0
      3. Run: docker compose images | grep -E "backend|worker|frontend"
      4. Assert: 3+ image entries listed
    Expected Result: All services build without errors
    Failure Indicators: Non-zero exit code, "COPY failed" errors, missing file errors
    Evidence: .sisyphus/evidence/task-4-docker-build.txt

  Scenario: Build fails gracefully if Docker not available
    Tool: Bash
    Steps:
      1. Run: docker info 2>/dev/null || echo "Docker not available — skip build verification"
    Expected Result: If Docker unavailable, skip with clear message rather than failing the task
    Evidence: .sisyphus/evidence/task-4-docker-check.txt
  ```

  **Commit**: NO

- [ ] 5. Update AGENTS.md stale references

  **What to do**:
  - Grep AGENTS.md for references to `backend/Dockerfile` or `frontend/Dockerfile`
  - If found, update to reference `services/` Dockerfiles instead
  - If not found, no changes needed

  **Must NOT do**:
  - Do not rewrite AGENTS.md beyond fixing stale Docker references
  - Do not change sections unrelated to Docker/infrastructure

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 4)
  - **Parallel Group**: Wave 2
  - **Blocks**: F1
  - **Blocked By**: Task 1

  **References**:
  - `AGENTS.md` — current content (recently rewritten this session)

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: No stale Dockerfile references in AGENTS.md
    Tool: Bash
    Steps:
      1. Run: grep -c "backend/Dockerfile\|frontend/Dockerfile" AGENTS.md
      2. Assert: 0 matches
    Expected Result: Zero stale references
    Evidence: .sisyphus/evidence/task-5-agents-md-clean.txt
  ```

  **Commit**: YES (if changes made)
  - Message: `docs: update AGENTS.md Docker references to services/ layout`
  - Files: `AGENTS.md`

---

## Final Verification Wave

- [ ] F1. **Scope Fidelity Check** — `quick`
  Verify: (1) `services/` contains exactly 5 subdirs: airex-api, airex-worker, airex-frontend, langfuse, litellm. (2) No Dockerfile exists outside `services/` except potentially `frontend/Dockerfile` (should be gone). (3) `docker-compose.yml` references only `services/` Dockerfiles. (4) `buildspec.images.yml` is unchanged. (5) No files outside scope were modified.
  Output: `Files [N removed/N created] | Stale refs [CLEAN/N] | VERDICT: APPROVE/REJECT`

---

## Commit Strategy

- **Wave 1**: `refactor: remove redundant Dockerfiles and add root .dockerignore` — `frontend/Dockerfile` (del), `backend/.dockerignore` (del), `.dockerignore` (new)
- **Wave 2 (if needed)**: `docs: update AGENTS.md Docker references to services/ layout` — `AGENTS.md`

---

## Success Criteria

### Verification Commands
```bash
# All Dockerfiles consolidated under services/
find . -name "Dockerfile" -not -path "./.git/*" -not -path "./services/*"
# Expected: no output (zero Dockerfiles outside services/)

# Root .dockerignore exists
test -f .dockerignore && echo "PASS"
# Expected: PASS

# docker-compose references only services/ Dockerfiles
grep "dockerfile:" docker-compose.yml | grep -v "services/"
# Expected: no output

# No stale references
grep -r "backend/Dockerfile\|frontend/Dockerfile" AGENTS.md docker-compose.yml
# Expected: no output
```

### Final Checklist
- [ ] All Dockerfiles live exclusively under `services/`
- [ ] Root `.dockerignore` exists with proper exclusions
- [ ] `docker compose build` succeeds for backend, worker, migrate, frontend
- [ ] No stale file references in docs or config
- [ ] No files outside declared scope were modified
