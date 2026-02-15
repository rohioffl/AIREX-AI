# AIREX

> [!IMPORTANT]
> **Developers & AI Agents**: Please refer to [AGENTS.md](AGENTS.md) for all architectural rules, setup instructions, and coding standards.

This repository contains the source code for **AIREX** (**A**utonomous **I**ncident **R**esolution **E**ngine **X**ecution), an autonomous SRE system designed to investigate alerts, generate AI recommendations, and execute safe actions upon approval.

## 🏗 System Architecture
An **Autonomous SRE Platform** that reduces MTTR by closing the loop between detection and resolution.

### 🔄 High-Level Flow
1.  **Ingestion**: Receives webhooks (e.g., Site24x7) and enforces idempotency.
2.  **Investigation**: Automatically runs modular plugins (AWS SSM / GCP OS Login) to gather evidence.
3.  **AI Analysis**: Uses LiteLLM (Local -> Gemini Pro fallback) to determine root cause and suggest logic.
4.  **Human Approval**: Policy-based gating. SRE authorizes actions via the [Frontend Dashboard](docs/frontend_skill.md).
5.  **Execution**: deterministic, mapped actions (e.g., `restart_service`) run in isolated environments.
6.  **Verification**: Post-execution health checks ensure resolution. Retries or escalates if failed.

### 🛠 Tech Stack
-   **Backend**: FastAPI (Async), SQLAlchemy 2.0 (Async), Alembic, Redis (ARQ/Celery).
-   **Frontend**: React (Vite), Tailwind CSS, Server-Sent Events (SSE).
-   **Database**: PostgreSQL 15+ with **Row Level Security (RLS)** and Composite PKs.
-   **AI**: LiteLLM (Model-agnostic: Local + Cloud fallback).

### 🔐 Security & Safety
-   **Zero Trust**: No stored SSH keys. Uses IAM Roles / Workload Identity.
-   **State Machine**: Strict, immutable transitions (see [Backend Skill](docs/backend_skill.md)).
-   **Multi-Tenancy**: Enforced via `(tenant_id, id)` Composite PKs and RLS policies.
-   **Auditability**: Tamper-evident, hash-chained logs for every state change.

## 📂 Documentation Rules
-   **Developer Guide**: [AGENTS.md](AGENTS.md)
-   **Frontend Skill**: [docs/frontend_skill.md](docs/frontend_skill.md)
-   **Backend Skill**: [docs/backend_skill.md](docs/backend_skill.md)
-   **Database Skill**: [docs/database_skill.md](docs/database_skill.md)
