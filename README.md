# AIREX

[![Live Demo](https://img.shields.io/badge/Live-airex.rohitpt.online-0f766e?style=for-the-badge)](https://airex.rohitpt.online)
[![Portfolio](https://img.shields.io/badge/Portfolio-rohitpt.online-111827?style=for-the-badge)](https://rohitpt.online)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-rohitpt-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://linkedin.com/in/rohitpt)
[![GitHub](https://img.shields.io/badge/GitHub-rohioffl-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/rohioffl)
[![GitHub Stars](https://img.shields.io/github/stars/rohioffl/AIREX-AI?style=for-the-badge)](https://github.com/rohioffl/AIREX-AI/stargazers)
[![GitHub Issues](https://img.shields.io/github/issues/rohioffl/AIREX-AI?style=for-the-badge)](https://github.com/rohioffl/AIREX-AI/issues)
[![License](https://img.shields.io/badge/License-Proprietary-b91c1c?style=for-the-badge)](LICENSE)

Created by **Rohit** - a production-focused platform engineer building practical AI systems for incident automation, cloud operations, and reliable developer tooling.

Live project: `airex.rohitpt.online`  
Portfolio: `rohitpt.online`  
LinkedIn: `linkedin.com/in/rohitpt`  
GitHub: `github.com/rohioffl`

> [!IMPORTANT]
> Developers and AI agents should start with [AGENTS.md](AGENTS.md). It defines project workflow rules, Memory MCP usage, connected MCP tool preferences, safety constraints, and validation commands.

AIREX stands for **Autonomous Incident Resolution Engine Xecution**. It is a safety-conscious incident automation platform that ingests alerts, investigates affected systems, generates AI-assisted recommendations, applies policy and approval rules, executes deterministic remediation actions, and verifies the outcome.

## Why It Exists

AIREX is designed to reduce mean time to resolution for operational incidents without sacrificing control. It combines deterministic backend rules, auditable state transitions, cloud investigation workflows, and approval-gated AI assistance so operators can move faster without giving up safety.

## What AIREX Does

1. Ingests alerts from sources like Site24x7 and generic webhook senders.
2. Creates and tracks incidents through a strict backend state machine.
3. Runs investigation probes across cloud and system surfaces.
4. Generates structured AI recommendations through LiteLLM.
5. Requires approval when policy demands it and blocks unsafe execution paths.
6. Executes whitelisted remediation actions through controlled worker flows.
7. Verifies post-action health and keeps an auditable incident timeline.

## Current Monorepo Layout

```text
backend/                 FastAPI app, worker code, services, models, tests
apps/web/                React + Vite frontend
database/                Alembic migrations and standalone migration image
services/backend/        Shared backend image targets for API and worker
services/airex-frontend/ Frontend Dockerfile
services/litellm/        LiteLLM container config
services/langfuse/       Langfuse deployment notes
deployment/              ECS and CodeBuild assets
docs/                    Project architecture, skills, and runbooks
infra/                   Prometheus, Grafana, and AI platform config
e2e/                     Playwright end-to-end tests
```

## Architecture Overview

### Core Services
- `backend/`: shared Python codebase for the API and worker runtimes, including domain services, state machine, policies, schemas, and integrations.
- `backend` (Compose) / `airex-api` (image): FastAPI runtime packaged from the shared `backend/` codebase.
- `worker` (Compose) / `airex-worker` (image): ARQ runtime packaged from the shared `backend/` codebase.
- `apps/web`: operational UI for incident review, approvals, evidence, runbooks, and health dashboards.
- `database`: isolated migration pipeline with Alembic under `database/alembic/`.

### Runtime Dependencies
- PostgreSQL with pgvector for application data and retrieval features.
- Redis for ARQ queues, pub/sub, and runtime coordination.
- LiteLLM for model routing and external AI provider access.
- Prometheus, Grafana, and Alertmanager for observability.

### Incident Lifecycle
`RECEIVED -> INVESTIGATING -> RECOMMENDATION_READY -> AWAITING_APPROVAL -> EXECUTING -> VERIFYING -> RESOLVED`

Failure states remain explicit: `FAILED_ANALYSIS`, `FAILED_EXECUTION`, `FAILED_VERIFICATION`, and `REJECTED` for human-driven rejection.

## Safety Principles

- Deterministic actions only; no arbitrary shell generated from LLM output.
- Incident state changes must go through `transition_state(...)` helpers.
- Structured logging and correlation IDs are required across backend flows.
- Cloud access must avoid hardcoded credentials.
- Tenant-safe code patterns stay in place even though the current runtime uses the DEV tenant `00000000-0000-0000-0000-000000000000`.

## Local Development

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Worker

```bash
cd backend
arq app.core.worker.WorkerSettings
```

### Frontend

```bash
cd apps/web
npm install
npm run dev
```

### Database Migrations

```bash
cd database
alembic history
alembic upgrade head
```

### Local Stack

```bash
docker-compose up -d db redis ai-platform
docker-compose up -d
docker-compose run migrate
```

`docker-compose up -d` brings up the full local stack, including `frontend` on `http://localhost:5173`, backend on `http://localhost:8000`, Redis, PostgreSQL, LiteLLM, and observability services. The frontend now waits for a healthy backend before it starts.

## Verification Commands

### Backend

```bash
cd backend
ruff check app/
mypy app/ --ignore-missing-imports
pytest
```

### Frontend

```bash
cd apps/web
npm run lint
npm run test -- --run
npm run build
```

### E2E

```bash
cd e2e
npm install
npm run test
```

## Deployment Notes

- `services/backend/Dockerfile` builds the shared backend image targets for the API and worker runtimes.
- `services/airex-frontend/Dockerfile` builds the frontend image from `apps/web/`.
- `database/Dockerfile` builds a standalone migration image.
- `deployment/ecs/codebuild/buildspec.frontend.yml` publishes the frontend from `apps/web/dist` to S3 + CloudFront.

## Documentation Map

- [AGENTS.md](AGENTS.md) - repo workflow rules and validation commands
- [docs/backend_skill.md](docs/backend_skill.md) - backend implementation rules
- [docs/frontend_skill.md](docs/frontend_skill.md) - frontend implementation rules
- [docs/database_skill.md](docs/database_skill.md) - database and migration rules
- [docs/architecture.md](docs/architecture.md) - broader architecture notes
- [TECH_STACK.md](TECH_STACK.md) - expanded technology reference

## Ownership

AIREX is maintained as a proprietary project. See [LICENSE](LICENSE) for usage restrictions and ownership attribution.
