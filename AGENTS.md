# AGENTS.md

> [!IMPORTANT]
> **READ BEFORE CODING OR TESTING.** This project enforces strict architectural, style, test, and safety rules defined in this file and the `docs/` dir. Non-conformance risks automated or human PR rejection.
>
> - Frontend: [docs/frontend_skill.md](docs/frontend_skill.md)
> - Backend: [docs/backend_skill.md](docs/backend_skill.md)
> - Database: [docs/database_skill.md](docs/database_skill.md)

---

## 1. Build, Lint, and Test Commands

### 1.1 Backend: Python (FastAPI, AsyncIO, ARQ)

**Setup:**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
**Migrations:**
```bash
alembic upgrade head
```
**Run API:**
```bash
uvicorn app.main:app --reload
```
**Run Worker:**
```bash
arq app.core.worker.WorkerSettings
```
**Lint:**
```bash
ruff check app/           # If ruff is installed
mypy app/ --ignore-missing-imports
```
**Full Test:**
```bash
pytest         # Or: python -m pytest
```
**Single Test (by file or method):**
```bash
python -m pytest tests/test_llm_client.py
python -m pytest tests/ -k 'TestRecommendation and not slow'
```
**Run Ingestion Script:**
```bash
python scripts/ingest_runbooks.py --tenant-id <uuid>
```

### 1.2 Frontend: React (Vite, Tailwind)
```bash
cd frontend
npm install
npm run dev         # Local dev server
npm run lint        # ESLint
npm run build       # Vite production build
npm run test        # Vitest suite
npm run test -- --run "Incident*"  # Run specific tests
```

### 1.3 Infrastructure
```bash
docker-compose up -d db redis ai-platform
alembic upgrade head
# (optionally) ./backend/scripts/ingest_runbooks.py
```

---

## 2. Code Style & Convention Guidelines

### 2.1 Python Backend
- **Type Hints:** Required everywhere, including function signatures and class attributes. Run `mypy`.
- **Formatting:** Recommend `black` for code and `ruff` for lint. Max line length = 100.
- **Imports:** Standard > Third party > Local. Alphabetize within blocks. No relative imports outside package.
- **Naming:**
  - Classes: PascalCase
  - Functions, modules: snake_case
  - Constants: UPPER_SNAKE
  - No ambiguous two-letter vars outside comprehensions.
- **Error Handling:**
  - Always catch specific exceptions. Never catch bare `except:`.
  - Use custom exceptions where business logic demands.
- **Async:** All I/O, DB, HTTP, and worker code **must** be async/await. No blocking calls!
- **Logging:** Use `structlog` JSON logging. Always attach `correlation_id` where possible.
- **Transitional Safety:** Only mutate incident state with `transition_state()`; never direct attribute assignment.
- **No direct OS commands. All shell logic uses SSM, OS Login, or whitelisted templates.**

### 2.2 Frontend (React)
- **Only functional components, hooks, Tailwind. No class components.**
- **Formatting:** Autosave with Prettier and ESLint rules (`npm run lint`).
- **Naming:**
  - Components: PascalCase
  - Hooks: `useCamelCase`
  - Files: PascalCase for components, kebab-case for utils.
- **No inline fetches. All HTTP via central API client. No direct DOM manipulation.**
- **Real-time state from backend only, via SSE. Never simulate or optimistically update UI state.**
- **All user-generated content is rendered as plain text. Never inject HTML from backend.**

---

## 3. Testing Guidelines & CI/Coverage
- **Backend unit/integration:**
  - All new code must be covered by `pytest`.
  - Put tests in `backend/tests/`, matching module/test names.
  - Use `pytest-asyncio` for async tests.
  - Can run single test like: `pytest tests/test_investigations.py -k some_method`.
- **Frontend:**
  - Use Vitest/Jest with React Testing Library. No Enzyme.
  - Always snapshot test critical components. No shallow tests.
- **CI:**
  - Actions: backend lint (ruff, mypy), backend test (pytest), frontend lint (eslint), frontend test (vitest), docker build.
  - See `.github/workflows/ci.yml` for env vars, matrix, reporting.

## 4. Architectural, Plugin, and Tooling Rules
- **Follow docs/backend_skill.md, docs/frontend_skill.md, and docs/database_skill.md.**
- **Backend State:** Use strict state machine enums and transitions for Incident, no side-effects outside approved plugin boundaries.
- **LLM/RAG:**
  - All LLM calls must go through LiteLLM proxy and be traced with `correlation_id`/Langfuse.
  - All RAG operations must sanitize, chunk, and deduplicate context; see `rag_context.py`.
- **Prohibitions:**
  - No subprocess.run for arbitrary shell commands.
  - No secrets in repos. Use local `.env` for dev.
  - No prompt injection. Sanitize everything sent to LLM; harden prompts in `app/llm/prompts.py`.
  - Never use blocking IO, global queries, or unbounded loops.
  - No business logic leaks between frontend/backend.
  - No direct DB access in frontend, only via approved API routes.
- **Auditability:**
  - All side-effectful actions (state transitions, executions) must be persisted and auditable/logged.

## 5. Commit, PR & Review
- **Atomicity:** Single-feature/fix per PR and commit. No ops mixed with logic changes.
- **Naming:** Prefix as `feat:`, `fix:`, `refactor:`, `chore:`. Messages must be descriptive (no “Update file” commits).
- **Self-review:** Run lints, tests, and CI locally before pushing. Confirm conformance to skill docs.
- **No secrets, keys, or credentials of any kind in PRs.**
- **Change doc/skills if changing domain rules or critical pipeline sections.**

## 6. References & Troubleshooting
- **Ref skill docs for all workflow or code questions.** If agent/coder is unsure about state flows, plugin structure, DB, or RAG/LLM context steps, see `docs/{backend,frontend,database}_skill.md`.
- **Infra tips:**
  - If DB migration fails: ensure up-to-date Alembic heads, run `alembic history`.
  - If SSE hangs: check Redis, check backend logs, use `/health` endpoint.
  - If agent fails: check Langfuse or LiteLLM logs for context.
- **General:** When stuck, ask for a safety review, and always fall back to secure/manual mode if core invariants are in doubt.

---

By following these rules, Opencode/coding agents (and humans!) keep the AIREX platform robust, consistent, safe, and fast to review/ship changes. All agents are equally bound by these standards.
