# AGENTS.md

> [!IMPORTANT]
> **READ BEFORE CODING**: This project has strict architectural rules defined in `docs/`.
> - **Frontend**: [docs/frontend_skill.md](docs/frontend_skill.md) - State-driven UI, SSE, No Business Logic.
> - **Backend**: [docs/backend_skill.md](docs/backend_skill.md) - Strict Transitions, Idempotency, DLQ.
> - **Database**: [docs/database_skill.md](docs/database_skill.md) - RLS, Composite PKs, Immutable Audit.

## Project Overview
**AIREX** (**A**utonomous **I**ncident **R**esolution **E**ngine **X**ecution) is an autonomous SRE system designed to investigate alerts, generate AI recommendations, and execute safe actions upon approval. It is built for high reliability and security.

### Core Architecture
- **Backend**: FastAPI (Async), SQLAlchemy 2.0, Alembic, Redis (ARQ/Celery).
- **Frontend**: React (Vite), Tailwind CSS, Server-Sent Events (SSE).
- **Database**: PostgreSQL 15+ (RLS Enabled).
- **AI**: LiteLLM (Gemini Pro / GPT-4).

---

## Development Workflow

### 1. Backend Setup (`backend/`)
```bash
# Install Dependencies
pip install -r requirements.txt

# Run Database Migrations
alembic upgrade head

# Start Dev Server
uvicorn app.main:app --reload
```

### 2. Frontend Setup (`frontend/`)
```bash
# Install Dependencies
npm install

# Start Dev Server
npm run dev
```

### 3. Infrastructure
```bash
# Start detailed infrastructure stack
docker-compose up -d db redis
```

---

## Code Quality Standards

### General Rules
- **No Magic**: Explicit logic > Implicit behavior.
- **Type Hints**: Mandatory for all Python code (`mypy` strict mode).
- **Error Handling**: Catch specific exceptions, never bare `except:`.
- **Logging**: Use structured logging (JSON) with `correlation_id`.

### Backend Rules
- **Async First**: Use `async def` and `await` for all I/O.
- **Pydantic**: Use Pydantic models for all API schemas.
- **Testing**: `pytest` coverage required for core logic.
- **Security**: Never commit secrets. Use `.env`.

### Frontend Rules
- **Functional Components**: No Class Components.
- **Hooks**: Use custom hooks for logic separation.
- **No Direct DOM**: Use React refs if absolutely necessary.
- **State Management**: React Context or Zustand (No Redux unless specified).

---

## PR / Commit Guidelines
- **Atomic Commits**: One feature/fix per commit.
- **Descriptive Messages**: `feat: add incident metrics`, `fix: resolve race condition in approval`.
- **Review**: Self-review code against `docs/*_skill.md` before submitting.

---

## Troubleshooting
- **Database Locked**: Check `alembic` heads.
- **SSE Not Updating**: Verify Redis connection.
- **AI Hallucinations**: Update `docs/backend_skill.md` with stricter prompt rules.
