# AIREX — Autonomous AI Incident Response & Resolution Platform

[![CI](https://github.com/rohioffl/AIREX-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/rohioffl/AIREX-AI/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)
[![Live](https://img.shields.io/badge/live-airex.ankercloud.com-brightgreen)](https://airex.ankercloud.com/)
[![Tests](https://img.shields.io/badge/tests-690%20passing-blue)](#verification-commands)
[![Stack](https://img.shields.io/badge/stack-FastAPI%20%7C%20React%2019%20%7C%20pgvector-informational)](#architecture-overview)

AIREX stands for **Autonomous Incident Resolution Engine Xecution**. It is a safety-conscious incident automation platform that ingests alerts, investigates affected systems, generates AI-assisted recommendations, applies policy and approval rules, executes deterministic remediation actions, and verifies the outcome.

> Live at: **[https://airex.ankercloud.com/](https://airex.ankercloud.com/)**

## Table of Contents

- [Why It Exists](#why-it-exists)
- [What AIREX Does](#what-airex-does)
- [Architecture Overview](#architecture-overview)
- [Safety Principles](#safety-principles)
- [Local Development](#local-development)
- [Verification Commands](#verification-commands)
- [Deployment Notes](#deployment-notes)
- [Documentation Map](#documentation-map)

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

## Architecture Overview

### Monorepo Layout

```text
services/
  airex-core/     Shared Python package (models, services, schemas, actions, cloud, llm, rag)
  airex-api/      FastAPI service — 23 API routers + Dockerfile
  airex-worker/   ARQ worker service — 6 background tasks + Dockerfile
  litellm/        LiteLLM container config
  langfuse/       Langfuse deployment notes
apps/web/         React 19 + Vite 7 frontend — 19 pages, 165 tests + Dockerfile
database/         Alembic migrations (21 applied) + standalone migration image
tests/            Backend pytest suite (525 tests passing)
e2e/              Playwright end-to-end tests
deployment/       ECS Terraform + CodePipeline + CodeBuild assets
infra/            Prometheus, Grafana, and AI platform config
docs/             Architecture, skills, and runbooks
```

### Core Services

- **airex-core** — shared Python package used by API and worker runtimes
- **airex-api** — FastAPI runtime; entry point for all REST operations
- **airex-worker** — ARQ async worker for background investigation and execution tasks
- **apps/web** — operational UI for incident review, approvals, evidence, and health dashboards
- **database** — isolated migration pipeline with Alembic

### Runtime Dependencies

| Component | Purpose |
|-----------|---------|
| PostgreSQL + pgvector | Application data + vector retrieval (RAG) |
| Redis | ARQ queues, pub/sub, runtime coordination |
| LiteLLM | Model routing + external AI provider access |
| Prometheus + Grafana | Observability + alerting |

### Incident Lifecycle (11 States)

```
RECEIVED → INVESTIGATING → RECOMMENDATION_READY → AWAITING_APPROVAL → EXECUTING → VERIFYING → RESOLVED
```

Failure states: `FAILED_ANALYSIS` (retryable), `FAILED_EXECUTION`, `FAILED_VERIFICATION` (retryable), `REJECTED`

## Safety Principles

| Principle | Implementation |
|-----------|---------------|
| Deterministic actions only | 12 whitelisted actions in ACTION_REGISTRY — no arbitrary shell from LLM output |
| State machine is law | All state changes go through `transition_state(...)` with immutable audit trail |
| Zero-trust cloud | No stored credentials — IAM roles / Workload Identity only |
| Policy-first execution | Confidence-based auto-approval with senior approval gates |
| Tenant isolation | Every row is RLS-scoped by `tenant_id` |
| Structured logging | JSON logs with correlation IDs across all backend flows |

## Local Development

### Backend

```bash
cd services/airex-api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Worker

```bash
cd services/airex-worker
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
arq app.core.worker.WorkerSettings
```

### Frontend

```bash
cd apps/web
npm install && npm run dev
```

### Full Local Stack

```bash
docker-compose up -d
# Frontend: http://localhost:5173
# API: http://localhost:8000
# Observability: Prometheus + Grafana included
```

## Verification Commands

```bash
# Backend — 525 tests
cd tests && pytest

# Frontend — 165 tests
cd apps/web && npm run test -- --run

# Lint + type check
pip install ruff mypy
ruff check services/
mypy services/airex-core/airex_core/ --ignore-missing-imports
```

## Deployment Notes

### Live Environments

| Service | URL |
|---------|-----|
| Frontend / API | https://airex.ankercloud.com/ |
| Langfuse | https://airex-langfuse.ankercloud.com/ |
| LiteLLM | https://airex-litellm.ankercloud.com/ |

### Infrastructure
- ECS Fargate via Terraform (`deployment/ecs/`)
- CodePipeline + CodeBuild for CI/CD
- Frontend served from S3 + CloudFront

## Documentation Map

| Doc | Purpose |
|-----|---------|
| [AGENTS.md](AGENTS.md) | Repo workflow rules and validation commands |
| [TECH_STACK.md](TECH_STACK.md) | Expanded technology reference |
| [docs/architecture.md](docs/architecture.md) | Broader architecture notes |
| [docs/backend_skill.md](docs/backend_skill.md) | Backend implementation rules |
| [docs/frontend_skill.md](docs/frontend_skill.md) | Frontend implementation rules |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [SECURITY.md](SECURITY.md) | Vulnerability disclosure policy |

## Ownership

AIREX is maintained as a proprietary project by Rohit P T at Ankercloud.
See [LICENSE](LICENSE) for usage restrictions.

> **License:** Proprietary — all rights reserved. Contact security@ankercloud.com for licensing inquiries.
