# AGENTS.md
> [!IMPORTANT]
> Read this before coding, reviewing, or running tests. AIREX is safety-critical incident automation software; prioritize determinism, auditability, and secure defaults.

## Canonical Rule Sources
- Backend: `docs/backend_skill.md`
- Frontend: `docs/frontend_skill.md`
- Database: `docs/database_skill.md`

## Cursor/Copilot Rule Files
- `.cursor/rules/`: not present
- `.cursorrules`: not present
- `.github/copilot-instructions.md`: not present

## 0) Session Workflow Rules
- Use the Memory MCP at the start of meaningful project work to recover relevant repo context, prior decisions, architecture facts, and user preferences.
- Update the Memory MCP after meaningful changes to architecture, deployment, testing status, workflow rules, commits, or other durable project state.
- Treat Memory MCP usage as a default project rule, not an optional step.
- Prefer connected MCP servers when they fit the task, especially: `memory`, `filesystem`, `github`, `docker`, `context7`, `grep_app`, `playwright`, `puppeteer`, `websearch`, and `google-drive`.
- Choose MCP tools by task fit: use documentation/context tools for external library accuracy, browser tools for real UI verification, Docker tools for container/runtime checks, GitHub tools for repository state, and filesystem/search tools for local project inspection.
- If a connected MCP server is relevant and available, prefer it over ad-hoc workarounds unless there is a clear reason not to.

## 1) Build, Lint, and Test Commands
### 1.1 Backend (FastAPI + SQLAlchemy Async + ARQ)
Setup:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
Run API + worker:
```bash
uvicorn app.main:app --reload
arq app.core.worker.WorkerSettings
```
Migrations:
```bash
alembic upgrade head
alembic history
```
Lint + type-check:
```bash
ruff check app/
mypy app/ --ignore-missing-imports
```
Tests:
```bash
pytest
python -m pytest
```
Run a single backend test:
```bash
python -m pytest tests/test_llm_client.py
python -m pytest tests/test_state_machine.py::test_valid_transition
python -m pytest tests/ -k "recommendation and not slow"
```

### 1.2 Frontend (React 19 + Vite + Vitest)
Setup and run:
```bash
cd apps/web
npm install
npm run dev
npm run build
npm run preview
```
Lint + tests:
```bash
npm run lint
npm run test
npm run test:watch
```
Run a single frontend test:
```bash
npm run test -- --run "Incident*"
```

### 1.3 E2E (Playwright)
```bash
cd e2e
npm install
npm run test
npm run test:headed
npm run test:ui
npm run report
```
Run a single E2E file:
```bash
npx playwright test tests/incident-lifecycle.spec.js
```

### 1.4 Local Stack / Infra
```bash
docker-compose up -d db redis ai-platform
docker-compose up -d
docker-compose run migrate
docker-compose ps
```

## 2) Code Style Guidelines
### 2.1 Python Backend
- Type hints required on public and internal functions.
- Keep I/O async for DB, HTTP, cloud APIs, and workers.
- Imports: stdlib -> third-party -> local, alphabetized by block.
- Naming: `PascalCase` classes, `snake_case` funcs/modules, `UPPER_SNAKE_CASE` constants.
- Black-compatible formatting, max line length 100.
- Lint with Ruff and type-check with mypy.
- Catch specific exceptions only; never use bare `except:`.
- Prefer domain-specific exceptions with actionable messages.
- Use structured logging (`structlog`) and include `correlation_id`.

### 2.2 Frontend
- Functional components + hooks only (no class components).
- Prefer Tailwind utilities; avoid ad-hoc CSS.
- Keep API calls in `src/services/*`; avoid inline fetch in components.
- Naming: components `PascalCase`, hooks `useCamelCase`.
- Avoid direct DOM mutation; use React state/refs.
- Treat backend/user strings as untrusted input; never inject raw HTML.

### 2.3 Database
- PostgreSQL is authoritative; use Alembic for schema changes.
- Keep constraints explicit: enums/checks/indexes.
- Preserve auditable state transition and execution history.
- Follow `docs/database_skill.md` for RLS and tenant-safe patterns.

## 3) Architecture and Safety Rules
- Incident lifecycle must follow the backend state machine.
- Use `transition_state(...)` helpers instead of direct state mutation.
- Keep automation failures explicit (`FAILED_*`) unless human-rejected.
- Route LLM calls through LiteLLM with deterministic action policy checks.
- Never execute arbitrary shell generated from LLM output.
- Never commit credentials, tokens, or cloud secrets.

Single-tenant runtime note:
- Current runtime uses DEV tenant `00000000-0000-0000-0000-000000000000`.
- Continue writing tenant-safe code for future multi-tenant re-enablement.

## 4) Testing Expectations
- Add/adjust tests for every meaningful behavior change.
- Backend tests: `backend/tests/` with `pytest` + `pytest-asyncio`.
- Frontend tests: Vitest + React Testing Library.
- E2E tests: Playwright in `e2e/tests/`.
- During iteration, run targeted tests first, then broader suites.

Recommended pre-PR validation:
```bash
# backend
cd backend && ruff check app/ && mypy app/ --ignore-missing-imports && pytest
# frontend
cd apps/web && npm run lint && npm run test && npm run build
# e2e (for UI/API flow changes)
cd e2e && npm run test
```

## 5) PR Hygiene
- Keep changes scoped and atomic.
- Use clear prefixes: `feat:`, `fix:`, `refactor:`, `chore:`.
- Document migration, infra, and rollback implications in PR descriptions.
- Do not merge known failures unless explicitly documented as pre-existing.

If uncertain, follow the stricter rule path from the docs above.
