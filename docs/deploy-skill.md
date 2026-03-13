---
name: deploy-skill
description: Complete source of truth for AIREX production infrastructure, CI/CD pipelines, manual deployment, Docker builds, database migrations, and connectivity. Any AI agent reading this file has full context to understand, debug, or modify the deployment.
license: Private
---

# Deploy Skill — AIREX

This skill is the **complete source of truth** for the AIREX production deployment. It covers the entire system: infrastructure (Terraform), CI/CD pipelines (CodePipeline/CodeBuild — managed manually, NOT in Terraform), manual deployment scripts, Docker builds, database migrations, security group connectivity, and troubleshooting.

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AIREX Production — ap-south-1                        │
│                                                                         │
│  GitHub (anker-cloud/airex, branch: main)                               │
│     │                                                                   │
│     ├──► CodePipeline (airex-prod) ──► CodeBuild ──► ECR + ECS deploy  │
│     └──► CodePipeline (airex-prod-litellm) ──► ECR + ECS deploy        │
│                                                                         │
│  ┌─── CloudFront ──────────────────────────────────────────────────┐    │
│  │  airex.ankercloud.com → S3 (airex-prod-frontend-547361935557)   │    │
│  │  /api/* → ALB → ECS API                                        │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─── ALB (airex-prod-alb) ────────────────────────────────────────┐    │
│  │  Default         → ECS API    (:8000)                           │    │
│  │  litellm domain  → ECS LiteLLM (:4000)                         │    │
│  │  langfuse domain → ECS Langfuse (:3000)                         │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─── ECS Cluster (airex-prod-cluster) ────────────────────────────┐    │
│  │  airex-prod-api     (2 tasks) — FastAPI backend                 │    │
│  │  airex-prod-worker  (1 task)  — ARQ background worker           │    │
│  │  airex-prod-litellm (1 task)  — LiteLLM model proxy             │    │
│  │  airex-prod-langfuse(1 task)  — LLM observability               │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─── Data Layer (private subnets only) ───────────────────────────┐    │
│  │  RDS: airex-prod-airex-db    (Postgres 15, db.t4g.micro)       │    │
│  │  RDS: airex-prod-langfuse-db (Postgres 15, db.t4g.micro)       │    │
│  │  ElastiCache: airex-prod-redis (Redis 7, cache.t4g.micro)      │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

- **Frontend:** React SPA built statically → S3 → CloudFront (`https://airex.ankercloud.com/`)
- **Backend API (FastAPI):** `airex-prod-api` ECS service, `/api/*` via CloudFront→ALB
- **Background Workers:** `airex-prod-worker` ECS service, consumes from Redis via ARQ framework
- **LiteLLM:** `airex-prod-litellm`, accessible at `https://airex-litellm.ankercloud.com/`
- **Langfuse:** `airex-prod-langfuse`, accessible at `https://airex-langfuse.ankercloud.com/`

---

## 2. Monorepo Structure

```
AIREX-AI/
├── apps/
│   └── web/                          # React frontend (Vite)
│       ├── Dockerfile                # Multi-stage: node:20-alpine → nginx:alpine
│       ├── package.json
│       └── src/
├── services/
│   ├── airex-core/                   # Shared Python package (editable install)
│   │   ├── config/                   # Tenant configuration
│   │   └── setup.py / pyproject.toml
│   ├── airex-api/                    # FastAPI backend
│   │   ├── Dockerfile                # python:3.12-slim
│   │   ├── requirements.txt
│   │   └── app/
│   ├── airex-worker/                 # ARQ background worker
│   │   ├── Dockerfile                # python:3.12-slim
│   │   ├── requirements.txt
│   │   └── app/
│   ├── litellm/                      # LiteLLM proxy
│   │   ├── Dockerfile                # ghcr.io/berriai/litellm:main-v1.60.0
│   │   └── config.yaml
│   └── langfuse/                     # Langfuse (uses public ECR image, no custom Dockerfile)
├── database/
│   ├── alembic.ini                   # Alembic migration config
│   ├── alembic/                      # Migration scripts
│   └── scripts/
│       └── init-multi-db.sql         # Local dev: creates multiple databases
├── deployment/
│   └── ecs/
│       ├── terraform/                # Infrastructure as Code
│       │   ├── environments/prod/    # Production root module
│       │   ├── modules/platform/     # ECS, ALB, RDS, Redis, IAM, Secrets
│       │   ├── modules/vpc/          # VPC, subnets, NAT, routing
│       │   ├── modules/frontend/     # S3, CloudFront
│       │   └── bootstrap/            # Terraform state bucket + DynamoDB lock
│       ├── task-definitions/         # ECS task definition JSON templates
│       │   ├── airex-api.json
│       │   ├── airex-worker.json
│       │   ├── airex-litellm.json
│       │   └── airex-langfuse.json
│       ├── scripts/                  # Manual deploy scripts
│       │   ├── manual-deploy-all.sh  # One-shot full deploy
│       │   ├── render-task-defs.sh   # sed-based template rendering
│       │   ├── register-task-defs.sh # aws ecs register-task-definition
│       │   └── deploy-services.sh    # aws ecs update-service
│       ├── codebuild/                # CodeBuild buildspec files (manually created)
│       │   ├── buildspec.images.api.yml
│       │   ├── buildspec.images.worker.yml
│       │   ├── buildspec.images.litellm.yml
│       │   ├── buildspec.deploy.api.yml
│       │   ├── buildspec.deploy.worker.yml
│       │   ├── buildspec.deploy.litellm.yml
│       │   ├── buildspec.db-migrate.yml
│       │   └── buildspec.frontend.yml
│       ├── codepipeline/             # CodePipeline definitions (manually created)
│       │   ├── pipeline.prod.json        # Main pipeline: API + Worker + DB + Frontend
│       │   └── pipeline.litellm.prod.json # Separate LiteLLM pipeline
│       ├── .manual-deploy.env.example    # Template for manual deploy env vars
│       └── README.md
├── docker-compose.yml                # Local development stack
├── infra/
│   ├── ai-platform/config.yaml       # Local LiteLLM config
│   ├── prometheus/                   # Prometheus + Alertmanager config
│   └── grafana/                      # Grafana dashboard JSON
└── e2e/                              # Playwright E2E tests
```

---

## 3. ECS Services & Task Layout

| Service | Desired | Image Source | Port | Entrypoint | Dependencies |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `airex-prod-api` | 2 | `services/airex-api/Dockerfile` → ECR `airex-prod-api` | 8000 | `uvicorn app.main:app` | DB, Redis, LiteLLM, SMTP |
| `airex-prod-worker` | 1 | `services/airex-worker/Dockerfile` → ECR `airex-prod-worker` | none | `arq app.core.worker.WorkerSettings` | DB, Redis, LiteLLM, IAM Task Role |
| `airex-prod-litellm` | 1 | `services/litellm/Dockerfile` → ECR `airex-prod-litellm` | 4000 | `--config /app/config.yaml` | Gemini API Key, Langfuse |
| `airex-prod-langfuse` | 1 | `public.ecr.aws/langfuse/langfuse:2` (no custom build) | 3000 | default | Langfuse DB |

### Shared Code
Both `airex-api` and `airex-worker` share business logic via `services/airex-core/` which is installed as an editable Python package (`pip install -e`) during Docker build.

### IAM Roles
- **Execution Role:** `arn:aws:iam::547361935557:role/airex-prod-ecs-execution-role` — pulls images from ECR, reads Secrets Manager & SSM Parameter Store at container startup
- **Task Role:** `arn:aws:iam::547361935557:role/airex-prod-ecs-task-role` — used by running container code for AWS API calls (CloudWatch investigations, remediation actions, etc.)

---

## 4. CI/CD Pipelines (Manually Managed — NOT in Terraform)

CI/CD is implemented using **AWS CodePipeline + CodeBuild**, managed manually outside Terraform. ACM certificates and GitHub connections are also wired manually.

### 4.1 Main Pipeline — `airex-prod`

**Source:** GitHub `anker-cloud/airex` (branch: `main`) via CodeStar Connection  
**Trigger:** Push to `main` branch  
**Pipeline Role:** `arn:aws:iam::547361935557:role/airex-prod-codepipeline-role`  
**Artifact Store:** `s3://airex-prod-codepipeline-547361935557`

```
Stage 1: Source
  └─ GitHubSource → SourceArtifact

Stage 2: BuildImages (parallel)
  ├─ BuildApiImage    (airex-prod-images-api)     → ApiImageArtifact
  └─ BuildWorkerImage (airex-prod-images-worker)  → WorkerImageArtifact

Stage 3: DbMigration
  └─ RunDbMigration   (airex-prod-db-migrate)

Stage 4: DeployEcs (parallel)
  ├─ DeployApi    (airex-prod-deploy-api)
  └─ DeployWorker (airex-prod-deploy-worker)

Stage 5: DeployFrontend
  └─ DeployFrontend   (airex-prod-frontend)
```

### 4.2 LiteLLM Pipeline — `airex-prod-litellm`

Separate pipeline because LiteLLM deploys independently (config changes don't need API/worker rebuild).

```
Stage 1: Source → GitHubSource

Stage 2: BuildLitellm
  └─ BuildAndPushLitellm (airex-prod-images-litellm) → ImageArtifact

Stage 3: DeployLitellm
  └─ DeployLitellmEcs (airex-prod-deploy-litellm)
```

### 4.3 CodeBuild Projects — Detailed Breakdown

#### Image Build Projects

| Project | Buildspec | What It Does |
| :--- | :--- | :--- |
| `airex-prod-images-api` | `buildspec.images.api.yml` | Docker build `services/airex-api/Dockerfile`, push to ECR `airex-prod-api:<commit_sha>` |
| `airex-prod-images-worker` | `buildspec.images.worker.yml` | Docker build `services/airex-worker/Dockerfile`, push to ECR `airex-prod-worker:<commit_sha>` |
| `airex-prod-images-litellm` | `buildspec.images.litellm.yml` | Docker build `services/litellm/Dockerfile`, push to ECR `airex-prod-litellm:<commit_sha>` |

**Image tagging:** All images are tagged with `CODEBUILD_RESOLVED_SOURCE_VERSION` (the full Git commit SHA). An `image-detail-*.json` artifact carries the tag between stages.

#### Database Migration Project

| Project | Buildspec | What It Does |
| :--- | :--- | :--- |
| `airex-prod-db-migrate` | `buildspec.db-migrate.yml` | `pip install -e services/airex-core`, then `cd database && alembic upgrade head` |

**Important:** The CodeBuild project must run inside the VPC (private subnets) with access to the RDS security group, since the database is not publicly accessible. The `DATABASE_URL` is injected as an environment variable from Secrets Manager.

#### ECS Deploy Projects

| Project | Buildspec | What It Does |
| :--- | :--- | :--- |
| `airex-prod-deploy-api` | `buildspec.deploy.api.yml` | Renders task def template → register → `aws ecs update-service --force-new-deployment` |
| `airex-prod-deploy-worker` | `buildspec.deploy.worker.yml` | Same flow for worker service |
| `airex-prod-deploy-litellm` | `buildspec.deploy.litellm.yml` | Same flow for LiteLLM service |

The deploy buildspecs use `sed` to render the JSON task definition templates in `deployment/ecs/task-definitions/`, replacing `__PLACEHOLDER__` tokens with environment variables configured in the CodeBuild project. They then call:
1. `aws ecs register-task-definition --cli-input-json file://rendered.json`
2. `aws ecs update-service --task-definition <new_arn> --force-new-deployment`

#### Frontend Deploy Project

| Project | Buildspec | What It Does |
| :--- | :--- | :--- |
| `airex-prod-frontend` | `buildspec.frontend.yml` | `npm ci && npm run build`, then `aws s3 sync dist/ s3://<bucket> --delete`, then `aws cloudfront create-invalidation` |

**Special:** The frontend build fetches `VITE_GOOGLE_CLIENT_ID` from Secrets Manager at build time (`/airex/prod/frontend/google_oauth_client_id`). It also downloads `land_final.jpg` from S3 if missing locally.

### 4.4 CodeBuild Environment Variables

Each CodeBuild deploy project has these environment variables configured (as project-level env vars pointing to Secrets Manager ARNs and plaintext values):

```
# IAM
EXECUTION_ROLE_ARN, TASK_ROLE_ARN

# Task Definition Families
TASKDEF_FAMILY_API, TASKDEF_FAMILY_WORKER, TASKDEF_FAMILY_LITELLM, TASKDEF_FAMILY_LANGFUSE

# CloudWatch Log Groups
LOG_GROUP_API, LOG_GROUP_WORKER, LOG_GROUP_LITELLM, LOG_GROUP_LANGFUSE

# Secrets (ARNs)
SECRET_DATABASE_URL_ARN, SECRET_REDIS_URL_ARN, SECRET_APP_SECRET_KEY_ARN
SECRET_LITELLM_MASTER_KEY_ARN, SECRET_GEMINI_API_KEY_ARN
SECRET_SITE24X7_CLIENT_SECRET_ARN, SECRET_SITE24X7_REFRESH_TOKEN_ARN
SECRET_EMAIL_SMTP_PASSWORD_ARN
SECRET_LANGFUSE_PUBLIC_KEY_ARN, SECRET_LANGFUSE_SECRET_KEY_ARN
SECRET_LANGFUSE_DATABASE_URL_ARN, SECRET_LANGFUSE_NEXTAUTH_SECRET_ARN
SECRET_LANGFUSE_SALT_ARN

# Plaintext Config
LLM_BASE_URL, LLM_PRIMARY_MODEL, LLM_FALLBACK_MODEL, LLM_EMBEDDING_MODEL
CORS_ORIGINS, FRONTEND_URL, GOOGLE_OAUTH_CLIENT_ID
SITE24X7_ENABLED, SITE24X7_CLIENT_ID, SITE24X7_BASE_URL, SITE24X7_ACCOUNTS_URL
EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, EMAIL_SMTP_USER, EMAIL_FROM
LANGFUSE_HOST, NEXTAUTH_URL
```

### 4.5 Task Definition Templates

Templates live at `deployment/ecs/task-definitions/`. They use `__PLACEHOLDER__` syntax that `sed` replaces during rendering.

| Template | Container | Port | Command |
| :--- | :--- | :--- | :--- |
| `airex-api.json` | `api` | 8000 | default (uvicorn) |
| `airex-worker.json` | `worker` | none | `arq app.core.worker.WorkerSettings` |
| `airex-litellm.json` | `litellm` | 4000 | `--config /app/config.yaml --port 4000` |
| `airex-langfuse.json` | `langfuse` | 3000 | default |

All templates share: `FARGATE`, `awsvpc`, 1024 CPU, 2048 MEM, same execution/task roles.

---

## 5. Manual Deployment (Alternative to CodePipeline)

For deploying from a trusted local runner without CodePipeline:

### 5.1 One-Shot Script

```bash
# 1. Copy and fill the env file
cp deployment/ecs/.manual-deploy.env.example deployment/ecs/.manual-deploy.env
# Edit deployment/ecs/.manual-deploy.env with all values

# 2. Run full deploy
deployment/ecs/scripts/manual-deploy-all.sh
```

### 5.2 Script Execution Flow

The `manual-deploy-all.sh` script executes these phases in order:

```
Phase 1: Docker Build & Push (--skip-images to skip)
  ├─ ECR login
  ├─ Build API image    (services/airex-api/Dockerfile)
  ├─ Build Worker image (services/airex-worker/Dockerfile)
  ├─ Build LiteLLM image (services/litellm/Dockerfile)
  └─ Push all to ECR (tagged with git short SHA or --image-tag)

Phase 2: Database Migration (--skip-migrations to skip)
  ├─ Fetch DATABASE_URL from Secrets Manager
  ├─ Create Python venv, install airex-core + API requirements
  └─ alembic -c database/alembic.ini upgrade heads

Phase 3: ECS Backend Deploy (--skip-backend to skip)
  ├─ render-task-defs.sh  → sed-based template rendering → .rendered-task-definitions/
  ├─ register-task-defs.sh → aws ecs register-task-definition for each service
  └─ deploy-services.sh   → aws ecs update-service --force-new-deployment

Phase 4: Frontend Deploy (--skip-frontend to skip)
  ├─ Fetch VITE_GOOGLE_CLIENT_ID from Secrets Manager
  ├─ npm ci && npm run build  (apps/web)
  ├─ aws s3 sync dist/ s3://<bucket> --delete
  └─ aws cloudfront create-invalidation --paths "/*" + wait
```

### 5.3 Useful Flags

```bash
# Deploy with specific image tag
deployment/ecs/scripts/manual-deploy-all.sh --image-tag abc1234

# Skip image build (reuse existing images)
deployment/ecs/scripts/manual-deploy-all.sh --skip-images

# Skip migrations
deployment/ecs/scripts/manual-deploy-all.sh --skip-migrations

# Deploy only backend (skip frontend)
deployment/ecs/scripts/manual-deploy-all.sh --skip-frontend

# Deploy only frontend (skip everything else)
deployment/ecs/scripts/manual-deploy-all.sh --skip-images --skip-migrations --skip-backend
```

### 5.4 Required Environment Variables

See `deployment/ecs/.manual-deploy.env.example` for the complete list. Key defaults:

| Variable | Default |
| :--- | :--- |
| `AWS_REGION` | `ap-south-1` |
| `ECS_CLUSTER` | `airex-prod-cluster` |
| `ECR_API_REPO` | `airex-prod-api` |
| `ECR_WORKER_REPO` | `airex-prod-worker` |
| `ECR_LITELLM_REPO` | `airex-prod-litellm` |
| `LANGFUSE_IMAGE` | `public.ecr.aws/langfuse/langfuse:2` |
| `FRONTEND_BUCKET` | `airex-prod-frontend-<account_id>` |
| `IMAGE_TAG` | Current git short SHA |

---

## 6. Docker Images

### 6.1 API Image (`services/airex-api/Dockerfile`)

```
Base: python:3.12-slim
Build:
  1. Install system deps (build-essential, libpq-dev)
  2. COPY + pip install airex-core (editable)
  3. pip install API requirements (non-editable deps)
  4. COPY app/ code + airex-core/config/
Run: uvicorn app.main:app --host 0.0.0.0 --port 8000
User: airex (non-root)
```

### 6.2 Worker Image (`services/airex-worker/Dockerfile`)

```
Base: python:3.12-slim
Build: Same as API (different requirements.txt)
Run: arq app.core.worker.WorkerSettings
User: airex (non-root)
```

### 6.3 LiteLLM Image (`services/litellm/Dockerfile`)

```
Base: ghcr.io/berriai/litellm:main-v1.60.0
Build: Just copies config.yaml
Run: --config /app/config.yaml --port 4000 --host 0.0.0.0
```

### 6.4 Frontend Image (`apps/web/Dockerfile` — local dev only)

```
Base: node:20-alpine (build) → nginx:alpine (serve)
Build: npm ci → npm run build → copy dist to nginx
Note: In production, frontend is NOT served from ECS. It goes to S3 + CloudFront.
```

### 6.5 ECR Repositories (Terraform-managed)

| Repository | Image |
| :--- | :--- |
| `airex-prod-api` | API service image |
| `airex-prod-worker` | Worker service image |
| `airex-prod-litellm` | LiteLLM proxy image |

Langfuse uses a public ECR image (`public.ecr.aws/langfuse/langfuse:2`), no custom ECR repo needed.

---

## 7. Data Services — RDS (Postgres) & ElastiCache (Redis)

All data services run in **private subnets** and are **never publicly accessible**.

### 7.1 RDS — PostgreSQL Databases

| Instance | Identifier | DB Name | Driver | Port |
| :--- | :--- | :--- | :--- | :--- |
| AIREX DB | `airex-prod-airex-db` | `airex` | `postgresql+asyncpg://` | 5432 |
| Langfuse DB | `airex-prod-langfuse-db` | `langfuse` | `postgresql://` | 5432 |

**Config:** PostgreSQL 15, `db.t4g.micro`, 20 GB encrypted storage, private subnets only, passwords auto-generated (24 chars) stored in Secrets Manager.

**Connection strings** are auto-built by Terraform and stored as secrets:
- AIREX: `/airex/prod/backend/database_url` → `postgresql+asyncpg://<user>:<pass>@<host>:5432/airex`
- Langfuse: `/airex/prod/langfuse/database_url` → `postgresql://<user>:<pass>@<host>:5432/langfuse`

### 7.2 ElastiCache — Redis

| Instance | Replication Group ID | Engine | Node Type | Port |
| :--- | :--- | :--- | :--- | :--- |
| Redis | `airex-prod-redis` | Redis 7 | `cache.t4g.micro` | 6379 |

**Config:** 1 cache cluster, TLS enabled (in-transit + at-rest), auth token auto-generated (32 chars), parameter group `default.redis7`.

**Connection string:** `/airex/prod/backend/redis_url` → `rediss://:<auth_token>@<endpoint>:6379/0`

> **CRITICAL:** The protocol is `rediss://` (double `s`) because TLS is enabled. Using `redis://` will fail.

### 7.3 Database Migrations

Migrations use Alembic and are stored in `database/alembic/`.

```bash
# Config file
database/alembic.ini

# Run migrations locally
DATABASE_URL=postgresql+asyncpg://... alembic -c database/alembic.ini upgrade heads

# In CodeBuild (buildspec.db-migrate.yml)
pip install -e services/airex-core
cd database && alembic upgrade head

# In manual deploy (Phase 2)
# Automatically handled by manual-deploy-all.sh
```

---

## 8. Network Security & Connectivity

### 8.1 Security Group Architecture

```
Internet ──────────────────────────────────────────────────────────
    │
    ▼  (443/80)
┌────────────────────────┐
│   ALB (alb-sg)         │  Public subnets
│   airex-prod-alb-sg    │
└────────┬───────────────┘
         │  (8000, 4000, 3000)
         ▼
┌────────────────────────┐     ┌────────────────────────┐
│  ECS Tasks (ecs-sg)    │────▶│  Data Services(data-sg)│
│  airex-prod-ecs-sg     │     │  airex-prod-data-sg    │
│                        │     │                        │
│  API     :8000         │     │  RDS Postgres :5432    │
│  Worker  (no port)     │     │  Redis        :6379    │
│  LiteLLM :4000         │     │                        │
│  Langfuse:3000         │     └────────────────────────┘
└────────────────────────┘     Private subnets
         Private subnets
```

### 8.2 Security Group Rules

#### `airex-prod-alb-sg`
| Direction | Port | Source | Description |
| :--- | :--- | :--- | :--- |
| Ingress | 443 (or 80) | `0.0.0.0/0` | HTTPS from internet |
| Egress | All | `0.0.0.0/0` | All outbound |

#### `airex-prod-ecs-sg`
| Direction | Port | Source | Description |
| :--- | :--- | :--- | :--- |
| Ingress | 8000 | `alb-sg` | API from ALB |
| Ingress | 4000 | `alb-sg` | LiteLLM from ALB |
| Ingress | 3000 | `alb-sg` | Langfuse from ALB |
| Egress | All | `0.0.0.0/0` | Outbound (internet via NAT, data services) |

#### `airex-prod-data-sg`
| Direction | Port | Source | Description |
| :--- | :--- | :--- | :--- |
| Ingress | **5432** | `ecs-sg` | **Postgres from ECS** ✅ |
| Ingress | **6379** | `ecs-sg` | **Redis from ECS** ✅ |
| Egress | All | `0.0.0.0/0` | All outbound |

### 8.3 Connection Flows

| Path | How It Works |
| :--- | :--- |
| Internet → Frontend | CloudFront → S3 bucket |
| Internet → API | CloudFront → ALB → ECS API (or direct ALB for non-CloudFront paths) |
| Internet → LiteLLM | ALB host-header rule → ECS LiteLLM |
| Internet → Langfuse | ALB host-header rule → ECS Langfuse |
| ECS → RDS | Private subnet, ecs-sg → data-sg on port 5432 |
| ECS → Redis | Private subnet, ecs-sg → data-sg on port 6379 (TLS) |
| ECS → Internet | Private subnet → NAT Gateway → Internet |
| Internet → RDS/Redis | **BLOCKED** — not publicly accessible |

---

## 9. Configuration Management

**HARD RULE: Secrets belong in AWS Secrets Manager. Non-secrets belong in plain text Task Definitions or SSM Parameter Store.**

### 9.1 AWS Secrets Manager

All secrets use prefix `/airex/prod/` and are fetched at container startup via `valueFrom`.

#### Backend Secrets (`/airex/prod/backend/*`)
| Secret Key | Description | Auto-Generated? |
| :--- | :--- | :--- |
| `database_url` | Postgres connection string | Yes (Terraform) |
| `redis_url` | Redis connection string (TLS) | Yes (Terraform) |
| `secret_key` | JWT + encryption token | Yes (Terraform) |
| `site24x7_client_id` | Site24x7 client ID | Manual |
| `site24x7_client_secret` | Site24x7 API validation | Manual |
| `site24x7_refresh_token` | Site24x7 OAuth flow | Manual |
| `email_smtp_host` | SMTP server hostname | Manual |
| `email_smtp_port` | SMTP port | Manual |
| `email_smtp_user` | SMTP username | Manual |
| `email_smtp_password` | SMTP password | Manual |
| `email_from` | Sender email | Manual |

#### LiteLLM Secrets (`/airex/prod/litellm/*`)
| Secret Key | Description |
| :--- | :--- |
| `master_key` | Internal apps → LiteLLM auth (also `LLM_API_KEY` in backend) |
| `gemini_api_key` | Google Gemini API key |

#### Langfuse Secrets (`/airex/prod/langfuse/*`)
| Secret Key | Description | Auto-Generated? |
| :--- | :--- | :--- |
| `database_url` | Telemetry DB connection string | Yes (Terraform) |
| `nextauth_secret` | NextJS session security | Yes (Terraform) |
| `salt` | Password salt | Yes (Terraform) |
| `public_key` | Used by LiteLLM for metrics | Yes (Terraform) |
| `secret_key` | Used by LiteLLM for metrics | Yes (Terraform) |

#### Frontend Secrets (`/airex/prod/frontend/*`)
| Secret Key | Description |
| :--- | :--- |
| `google_oauth_client_id` | Google OAuth client ID (fetched at build time) |

### 9.2 SSM Parameter Store

| Parameter Path | Value |
| :--- | :--- |
| `/airex/prod/app/cors_origins` | JSON array of allowed origins |
| `/airex/prod/app/llm_primary_model` | `gemini-2.0-flash` |
| `/airex/prod/app/llm_fallback_model` | `nova-lite` |
| `/airex/prod/app/llm_embedding_model` | `text-embedding` |
| `/airex/prod/app/frontend_url` | `https://airex.ankercloud.com` |
| `/airex/prod/langfuse/host` | `https://airex-langfuse.ankercloud.com` |
| `/airex/prod/litellm/base_url` | `https://airex-litellm.ankercloud.com/v1` |

### 9.3 Task Definition Environment Variables (Plaintext)

| Variable | Used By | Example Value |
| :--- | :--- | :--- |
| `PYTHONPATH` | API, Worker | `/app` |
| `LLM_BASE_URL` | API, Worker | From SSM |
| `LLM_PRIMARY_MODEL` | API, Worker | `gemini-2.0-flash` |
| `LLM_FALLBACK_MODEL` | API, Worker | `nova-lite` |
| `LLM_EMBEDDING_MODEL` | API, Worker | `text-embedding` |
| `CORS_ORIGINS` | API | `["https://airex.ankercloud.com"]` |
| `FRONTEND_URL` | API, Worker | `https://airex.ankercloud.com` |
| `GOOGLE_OAUTH_CLIENT_ID` | API | From Secrets Manager |
| `SITE24X7_ENABLED` | API, Worker | `true` |
| `SITE24X7_CLIENT_ID` | API, Worker | From CodeBuild env |
| `SITE24X7_BASE_URL` | API, Worker | `https://www.site24x7.in/api` |
| `SITE24X7_ACCOUNTS_URL` | API, Worker | `https://accounts.zoho.in` |
| `EMAIL_SMTP_HOST` | API, Worker | `smtp.gmail.com` |
| `EMAIL_SMTP_PORT` | API, Worker | `587` |
| `EMAIL_SMTP_USER` | API, Worker | From CodeBuild env |
| `EMAIL_FROM` | API, Worker | From CodeBuild env |
| `NEXTAUTH_URL` | Langfuse | `https://airex-langfuse.ankercloud.com` |
| `TELEMETRY_ENABLED` | Langfuse | `false` |
| `LANGFUSE_DISABLE_SIGNUP` | Langfuse | `true` |
| `LANGFUSE_HOST` | LiteLLM | From SSM |

---

## 10. Terraform Infrastructure

### 10.1 Module Layout

| Module | Path | Manages |
| :--- | :--- | :--- |
| **prod** (root) | `deployment/ecs/terraform/environments/prod` | Wires all modules together |
| **vpc** | `deployment/ecs/terraform/modules/vpc` | VPC, subnets, IGW, NAT, route tables |
| **platform** | `deployment/ecs/terraform/modules/platform` | ECS cluster/services/tasks, ALB, RDS, Redis, ECR, IAM, Secrets, SSM |
| **frontend** | `deployment/ecs/terraform/modules/frontend` | S3, CloudFront, OAC |
| **bootstrap** | `deployment/ecs/terraform/bootstrap` | Terraform state S3 bucket + DynamoDB lock table |

### 10.2 Key Terraform Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `create_vpc` | `true` | Create dedicated VPC or use existing |
| `vpc_cidr` | `10.40.0.0/16` | VPC CIDR block |
| `public_subnet_cidrs` | `["10.40.0.0/24", "10.40.1.0/24"]` | Public subnets |
| `private_subnet_cidrs` | `["10.40.10.0/24", "10.40.11.0/24"]` | Private subnets |
| `database_instance_class` | `db.t4g.micro` | RDS instance type |
| `redis_node_type` | `cache.t4g.micro` | ElastiCache node type |
| `enable_custom_domains` | `false` | Attach custom domains + ACM certs |
| `api_image` | *required* | ECR image URI for API |
| `worker_image` | *required* | ECR image URI for Worker |
| `litellm_image` | *required* | ECR image URI for LiteLLM |

### 10.3 Terraform Commands

```bash
# Bootstrap (one-time)
cd deployment/ecs/terraform/bootstrap
terraform init && terraform apply

# Production deploy
cd deployment/ecs/terraform/environments/prod
terraform init -reconfigure -backend-config=backend.hcl
terraform plan \
  -var='api_image=<acct>.dkr.ecr.ap-south-1.amazonaws.com/airex-prod-api:latest' \
  -var='worker_image=<acct>.dkr.ecr.ap-south-1.amazonaws.com/airex-prod-worker:latest' \
  -var='litellm_image=<acct>.dkr.ecr.ap-south-1.amazonaws.com/airex-prod-litellm:latest'
terraform apply

# Enable custom domains later
terraform apply \
  -var='enable_custom_domains=true' \
  -var='alb_certificate_arn=arn:aws:acm:ap-south-1:...' \
  -var='cloudfront_certificate_arn=arn:aws:acm:us-east-1:...' \
  -var='frontend_domain=airex.ankercloud.com' \
  -var='litellm_domain=airex-litellm.ankercloud.com' \
  -var='langfuse_domain=airex-langfuse.ankercloud.com'
```

### 10.4 Terraform State

- **Backend:** S3 (`airex-prod-terraform-state-ap-south-1-547361935557`)
- **Lock:** DynamoDB
- **Config:** `deployment/ecs/terraform/environments/prod/backend.hcl`

### 10.5 What Terraform Does NOT Manage

| Resource | How It's Managed |
| :--- | :--- |
| ACM Certificates | Created manually in AWS Console |
| CodePipeline pipelines | Created manually from JSON definitions in `deployment/ecs/codepipeline/` |
| CodeBuild projects | Created manually from JSON definitions in `deployment/ecs/codebuild/` |
| CodeStar GitHub connection | Created manually in AWS Console |
| DNS records (Hostinger) | Created manually using Terraform output values |
| CodeBuild IAM roles/policies | Created manually from `deployment/ecs/codebuild/iam.*.json` |
| CodePipeline IAM roles | Created manually from `deployment/ecs/codepipeline/iam.*.json` |
| CodePipeline artifact bucket | Created manually |

---

## 11. Local Development

```bash
# Start all services
docker-compose up -d

# Services available at:
#   Frontend:    http://localhost:5173
#   API:         http://localhost:8000
#   LiteLLM:     http://localhost:4000
#   Postgres:    localhost:5432
#   Redis:       localhost:6379
#   Prometheus:  http://localhost:9090
#   Grafana:     http://localhost:3001
#   Alertmanager:http://localhost:9093

# Run migrations
docker-compose run migrate

# Required .env variables for local dev:
#   POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
#   DATABASE_URL, REDIS_URL
#   GEMINI_API_KEY (optional)
```

---

## 12. Modifying the Deployment

### Adding a New Environment Variable to Backend

1. **Is it a Secret?**
   - Yes → Add to Secrets Manager at `/airex/prod/backend/<key>`, add `aws_secretsmanager_secret` resource in `modules/platform/main.tf`, add to IAM policy, add to task definition templates `secrets[]` array
   - No → Add to task definition templates `environment[]` array

2. **Update these files:**
   - `deployment/ecs/task-definitions/airex-api.json` and/or `airex-worker.json`
   - `deployment/ecs/scripts/render-task-defs.sh` (add sed replacement)
   - `deployment/ecs/.manual-deploy.env.example` (add variable)
   - Relevant CodeBuild project env vars (if using CodePipeline)
   - `deployment/ecs/terraform/modules/platform/main.tf` (if Terraform-managed)

### Adding a New ECS Service

1. Create Dockerfile in `services/<name>/`
2. Add ECR repo in `modules/platform/main.tf`
3. Add CloudWatch log group
4. Add task definition (template + Terraform resource)
5. Add ECS service resource
6. Add ALB target group + listener rule (if needs HTTP access)
7. Add security group ingress rule (if custom port)
8. Update `deploy-services.sh`, `render-task-defs.sh`, `register-task-defs.sh`
9. Add CodeBuild buildspecs and CodePipeline stage

### Scaling an Existing Service

```bash
# Quick scale (no Terraform)
aws ecs update-service --cluster airex-prod-cluster --service airex-prod-api --desired-count 3

# Permanent scale (via Terraform)
# Update api_desired_count variable in terraform.tfvars
terraform apply -var='api_desired_count=3'
```

---

## 13. Connecting to Infrastructure

There is **NO bastion host or VPN**. All access to private resources (RDS, Redis) goes through **ECS Exec** — the only way to get a shell inside the VPC.

### 13.1 Prerequisites

```bash
# Install the Session Manager plugin (required for ECS Exec)
# macOS:
brew install session-manager-plugin

# Linux:
curl "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_64bit/session-manager-plugin.deb" \
  -o "session-manager-plugin.deb"
sudo dpkg -i session-manager-plugin.deb

# Verify
session-manager-plugin --version
```

> ECS Exec is enabled on ALL services via `enable_execute_command = true` in Terraform, and the Task Role has `ssmmessages:*` permissions. These are already configured in `modules/platform/main.tf`.

### 13.2 Connect to an ECS Task (Shell)

```bash
# Step 1: List running tasks
aws ecs list-tasks --cluster airex-prod-cluster --service-name airex-prod-api \
  --query 'taskArns[0]' --output text

# Step 2: Exec into the container
aws ecs execute-command \
  --cluster airex-prod-cluster \
  --task <TASK_ARN_OR_ID> \
  --container api \
  --interactive \
  --command "/bin/bash"

# Quick one-liner (auto-selects first running task):
TASK=$(aws ecs list-tasks --cluster airex-prod-cluster --service-name airex-prod-api --query 'taskArns[0]' --output text) && \
aws ecs execute-command --cluster airex-prod-cluster --task $TASK --container api --interactive --command /bin/bash
```

**Container names per service:**

| Service | `--container` value |
| :--- | :--- |
| `airex-prod-api` | `api` |
| `airex-prod-worker` | `worker` |
| `airex-prod-litellm` | `litellm` |
| `airex-prod-langfuse` | `langfuse` |

### 13.3 Connect to RDS (PostgreSQL)

RDS is in a private subnet and is NOT publicly accessible. You must tunnel through an ECS task.

```bash
# Option A: From inside an ECS task shell (see 13.2)
# The DATABASE_URL env var is already set inside the container
echo $DATABASE_URL

# Quick connectivity test
python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
import os
async def test():
    e = create_async_engine(os.environ['DATABASE_URL'])
    async with e.connect() as conn:
        result = await conn.execute(__import__('sqlalchemy').text('SELECT 1'))
        print('DB OK:', result.scalar())
    await e.dispose()
asyncio.run(test())
"

# Option B: Use psql if available
# Install inside container first: apt-get update && apt-get install -y postgresql-client
psql "$DATABASE_URL"
```

**For Langfuse DB:**
```bash
# Exec into the langfuse container
TASK=$(aws ecs list-tasks --cluster airex-prod-cluster --service-name airex-prod-langfuse --query 'taskArns[0]' --output text) && \
aws ecs execute-command --cluster airex-prod-cluster --task $TASK --container langfuse --interactive --command /bin/sh
# Then: echo $DATABASE_URL
```

### 13.4 Connect to Redis

Redis is in a private subnet with TLS. You must tunnel through an ECS task.

```bash
# From inside an ECS task shell (api or worker)
echo $REDIS_URL

# Test connectivity
python -c "
import redis, os
r = redis.from_url(os.environ['REDIS_URL'])
print('PING:', r.ping())
print('INFO server:', r.info('server')['redis_version'])
print('DBSIZE:', r.dbsize())
"

# Check ARQ queues
python -c "
import redis, os
r = redis.from_url(os.environ['REDIS_URL'])
keys = r.keys('arq:*')
for k in keys:
    print(k.decode(), '->', r.type(k).decode())
"
```

### 13.5 View Logs (CloudWatch)

```bash
# API logs
aws logs tail /ecs/airex-prod-api --follow

# Worker logs
aws logs tail /ecs/airex-prod-worker --follow

# LiteLLM logs
aws logs tail /ecs/airex-prod-litellm --follow

# Langfuse logs
aws logs tail /ecs/airex-prod-langfuse --follow

# Filter for errors only
aws logs tail /ecs/airex-prod-api --follow --filter-pattern "ERROR"

# Get last 30 minutes
aws logs tail /ecs/airex-prod-api --since 30m
```

### 13.6 Access Frontend (S3 + CloudFront)

```bash
# Check what's deployed in S3
aws s3 ls s3://airex-prod-frontend-547361935557/

# Download a specific file
aws s3 cp s3://airex-prod-frontend-547361935557/index.html -

# Check CloudFront status
aws cloudfront get-distribution --id <DISTRIBUTION_ID> --query 'Distribution.Status'

# Force cache invalidation
aws cloudfront create-invalidation --distribution-id <DISTRIBUTION_ID> --paths "/*"
```

### 13.7 Read Terraform Outputs

```bash
cd deployment/ecs/terraform/environments/prod

# Show all outputs
terraform output

# Specific outputs
terraform output rds_airex_endpoint
terraform output redis_endpoint
terraform output alb_dns_name
terraform output cloudfront_domain_name
terraform output data_security_group_id
```

### 13.8 Read/Update Secrets

```bash
# Read a secret value
aws secretsmanager get-secret-value --secret-id /airex/prod/backend/database_url \
  --query SecretString --output text

# List all AIREX secrets
aws secretsmanager list-secrets --filters Key=name,Values=/airex/prod \
  --query 'SecretList[].Name' --output table

# Update a secret (CAUTION: services need restart to pick up changes)
aws secretsmanager update-secret --secret-id /airex/prod/backend/secret_key \
  --secret-string "new-value-here"

# After updating a secret, force ECS to restart and pick up the new value:
aws ecs update-service --cluster airex-prod-cluster --service airex-prod-api --force-new-deployment
```

---

## 14. Infrastructure Changes Playbook

When modifying the infrastructure, follow these runbooks. Each section lists **every file you need to touch** and the **exact commands** to apply changes.

### 14.1 Add a New Environment Variable

**Determine type:** Secret (sensitive) or Plaintext (non-sensitive)?

#### If Plaintext:

```
Files to modify:
  1. deployment/ecs/task-definitions/airex-api.json (and/or airex-worker.json)
     → Add to "environment" array: { "name": "NEW_VAR", "value": "__NEW_VAR__" }
  2. deployment/ecs/scripts/render-task-defs.sh
     → Add to required_env array + add sed line: -e "s|__NEW_VAR__|$NEW_VAR|g"
  3. deployment/ecs/.manual-deploy.env.example
     → Add NEW_VAR=<default>
  4. CodeBuild project (AWS Console)
     → Add environment variable to the relevant deploy project

Apply:
  # Manual deploy
  deployment/ecs/scripts/manual-deploy-all.sh --skip-images --skip-migrations --skip-frontend

  # Or via CodePipeline: push to main
```

#### If Secret:

```
Files to modify:
  1. deployment/ecs/terraform/modules/platform/main.tf
     → Add aws_secretsmanager_secret + aws_secretsmanager_secret_version resources
     → Add secret ARN to execution role IAM policy resource list
  2. deployment/ecs/task-definitions/airex-api.json (and/or airex-worker.json)
     → Add to "secrets" array: { "name": "NEW_SECRET", "valueFrom": "__SECRET_NEW_SECRET_ARN__" }
  3. deployment/ecs/scripts/render-task-defs.sh
     → Add SECRET_NEW_SECRET_ARN to required_env + sed line
  4. deployment/ecs/.manual-deploy.env.example
     → Add SECRET_NEW_SECRET_ARN=

Apply:
  # Step 1: Provision the secret
  cd deployment/ecs/terraform/environments/prod
  terraform apply

  # Step 2: Deploy services to pick up the new secret
  deployment/ecs/scripts/manual-deploy-all.sh --skip-images --skip-migrations --skip-frontend
```

### 14.2 Add a New ECS Service

```
Files to create/modify:

  1. services/<name>/Dockerfile        → Create the Dockerfile
  2. services/<name>/requirements.txt   → Dependencies (if Python)

  3. deployment/ecs/terraform/modules/platform/main.tf
     → Add aws_ecr_repository.<name>
     → Add aws_cloudwatch_log_group.<name>
     → Add aws_ecs_task_definition.<name>
     → Add aws_ecs_service.<name> (include enable_execute_command = true)
     → If HTTP: add aws_lb_target_group.<name> + aws_lb_listener_rule.<name>
     → If custom port: add aws_security_group_rule for ecs-sg ingress

  4. deployment/ecs/terraform/modules/platform/variables.tf
     → Add <name>_image, <name>_desired_count variables

  5. deployment/ecs/terraform/modules/platform/outputs.tf
     → Add service name output

  6. deployment/ecs/terraform/environments/prod/main.tf
     → Pass new variables to module

  7. deployment/ecs/task-definitions/airex-<name>.json
     → Create task definition template

  8. deployment/ecs/scripts/render-task-defs.sh
     → Add render_file call for new template

  9. deployment/ecs/scripts/register-task-defs.sh
     → Add register call

  10. deployment/ecs/scripts/deploy-services.sh
      → Add update_service call

  11. deployment/ecs/codebuild/
      → Create buildspec.images.<name>.yml
      → Create buildspec.deploy.<name>.yml

  12. deployment/ecs/codepipeline/pipeline.prod.json
      → Add build + deploy stages

Apply:
  cd deployment/ecs/terraform/environments/prod
  terraform plan -var='<name>_image=...' && terraform apply
```

### 14.3 Add a Custom Domain

```
Steps:
  1. Request ACM certificate in AWS Console (ap-south-1 for ALB, us-east-1 for CloudFront)
  2. Add DNS validation CNAME records in Hostinger
  3. Wait for certificate status = Issued

  4. Apply Terraform:
     cd deployment/ecs/terraform/environments/prod
     terraform apply \
       -var='enable_custom_domains=true' \
       -var='alb_certificate_arn=arn:aws:acm:ap-south-1:...' \
       -var='cloudfront_certificate_arn=arn:aws:acm:us-east-1:...' \
       -var='frontend_domain=airex.ankercloud.com' \
       -var='litellm_domain=airex-litellm.ankercloud.com' \
       -var='langfuse_domain=airex-langfuse.ankercloud.com'

  5. Create DNS records in Hostinger from Terraform outputs:
     terraform output dns_records_to_create
```

### 14.4 Scale a Service

```bash
# Temporary scale (reverts on next deploy):
aws ecs update-service --cluster airex-prod-cluster --service airex-prod-api --desired-count 4

# Permanent scale via Terraform:
cd deployment/ecs/terraform/environments/prod
terraform apply -var='api_desired_count=4'

# Check current task count:
aws ecs describe-services --cluster airex-prod-cluster --services airex-prod-api \
  --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount}'
```

### 14.5 Change RDS or Redis Instance Size

```bash
# RDS: scale up database instance
cd deployment/ecs/terraform/environments/prod
terraform apply -var='database_instance_class=db.t4g.small'
# WARNING: This causes a brief downtime during apply (modify-db-instance).

# Redis: scale up cache node
terraform apply -var='redis_node_type=cache.t4g.small'
# WARNING: ElastiCache may create a new replication group.
```

### 14.6 Modify Security Group Rules

```
File: deployment/ecs/terraform/modules/platform/main.tf

Current security groups:
  - aws_security_group.alb           (alb-sg)
  - aws_security_group.ecs_services  (ecs-sg)
  - aws_security_group.data          (data-sg)

To add a new ingress rule (e.g., allow ECS to reach a new service on port 27017):
  → Add an aws_security_group_rule resource in modules/platform/main.tf
  → terraform apply

To verify current rules:
  aws ec2 describe-security-groups --group-ids <SG_ID> \
    --query 'SecurityGroups[0].IpPermissions'
```

### 14.7 Rotate a Secret

```bash
# Step 1: Update the secret value
aws secretsmanager update-secret --secret-id /airex/prod/backend/secret_key \
  --secret-string "new-secret-value"

# Step 2: Force all affected services to restart (picks up new secret)
aws ecs update-service --cluster airex-prod-cluster --service airex-prod-api --force-new-deployment
aws ecs update-service --cluster airex-prod-cluster --service airex-prod-worker --force-new-deployment

# Step 3: Verify the new value is loaded
TASK=$(aws ecs list-tasks --cluster airex-prod-cluster --service-name airex-prod-api --query 'taskArns[0]' --output text)
aws ecs execute-command --cluster airex-prod-cluster --task $TASK --container api --interactive \
  --command "python -c \"import os; print(os.environ.get('SECRET_KEY', 'NOT SET')[:8] + '...')\""
```

### 14.8 Run Database Migrations Manually

```bash
# Option A: Using the manual deploy script
deployment/ecs/scripts/manual-deploy-all.sh --skip-images --skip-backend --skip-frontend

# Option B: From your machine (must have VPC connectivity, e.g., from CodeBuild)
export DATABASE_URL=$(aws secretsmanager get-secret-value --secret-id /airex/prod/backend/database_url --query SecretString --output text)
export PYTHONPATH=services/airex-core
pip install -e services/airex-core/
pip install -r services/airex-api/requirements.txt
alembic -c database/alembic.ini upgrade heads

# Option C: Trigger via CodePipeline
# The DbMigration stage runs automatically. To re-run manually:
# Go to AWS Console → CodePipeline → airex-prod → Retry the DbMigration stage
```

### 14.9 Update Terraform State After Manual Changes

If you make manual AWS changes (Console or CLI) that conflict with Terraform:

```bash
cd deployment/ecs/terraform/environments/prod

# Import an existing resource into state
terraform import module.platform.aws_security_group.data sg-0abc123def

# Refresh state to match actual AWS
terraform refresh

# See what Terraform thinks has drifted
terraform plan

# Remove a resource from state (without destroying it)
terraform state rm module.platform.aws_some_resource.name
```

---

## 15. AI Agent Deployment via MCP

AI agents with MCP access can execute the full deployment pipeline without leaving the editor. Two MCP servers cover everything:

| MCP Server | Purpose |
| :--- | :--- |
| **terraform** | `init`, `plan`, `validate`, `apply`, `destroy`, Checkov security scans, AWS provider doc lookup |
| **shell** | Any shell command: `aws` CLI, `docker`, deploy scripts, `alembic`, `npm`, logs, ECS Exec |

### 15.1 MCP → Deployment Step Mapping

| Deployment Step | MCP Server | MCP Tool / Command |
| :--- | :--- | :--- |
| Validate Terraform | `terraform` | `ExecuteTerraformCommand(command="validate", working_directory="deployment/ecs/terraform/environments/prod")` |
| Plan infra changes | `terraform` | `ExecuteTerraformCommand(command="plan", ...)` |
| Apply infra changes | `terraform` | `ExecuteTerraformCommand(command="apply", ...)` |
| Security scan | `terraform` | `RunCheckovScan(working_directory="deployment/ecs/terraform/environments/prod")` |
| Look up AWS resource docs | `terraform` | `SearchAwsProviderDocs(asset_name="aws_ecs_service")` |
| ECR login | `shell` | `aws ecr get-login-password --region ap-south-1 \| docker login --username AWS --password-stdin <registry>` |
| Build Docker images | `shell` | `docker build -f services/airex-api/Dockerfile -t <image> .` |
| Push Docker images | `shell` | `docker push <image>` |
| Run DB migrations | `shell` | `alembic -c database/alembic.ini upgrade heads` |
| Render task defs | `shell` | `deployment/ecs/scripts/render-task-defs.sh` |
| Register task defs | `shell` | `deployment/ecs/scripts/register-task-defs.sh` |
| Deploy ECS services | `shell` | `deployment/ecs/scripts/deploy-services.sh` |
| Build frontend | `shell` | `npm ci --prefix apps/web && npm run build --prefix apps/web` |
| Sync frontend to S3 | `shell` | `aws s3 sync apps/web/dist s3://<bucket> --delete` |
| Invalidate CloudFront | `shell` | `aws cloudfront create-invalidation --distribution-id <id> --paths "/*"` |
| Full manual deploy | `shell` | `deployment/ecs/scripts/manual-deploy-all.sh [flags]` |
| View logs | `shell` | `aws logs tail /ecs/airex-prod-api --follow` |
| Read/update secrets | `shell` | `aws secretsmanager get-secret-value --secret-id /airex/prod/...` |
| Exec into container | `shell` | `aws ecs execute-command --cluster airex-prod-cluster --task <id> --container api --interactive --command /bin/bash` |
| Check service status | `shell` | `aws ecs describe-services --cluster airex-prod-cluster --services airex-prod-api` |

### 15.2 Deploy Sequences

#### Infrastructure Only (Terraform Changes)

```
Step 1: terraform MCP → ExecuteTerraformCommand(command="validate")
Step 2: terraform MCP → ExecuteTerraformCommand(command="plan")
        → Review output, confirm with user
Step 3: terraform MCP → ExecuteTerraformCommand(command="apply")
        → REQUIRES user approval — destructive
```

#### Backend Only (Code Changes, No Infra)

```
Step 1: shell MCP → aws ecr get-login-password | docker login
Step 2: shell MCP → docker build -f services/airex-api/Dockerfile -t <image> .
Step 3: shell MCP → docker build -f services/airex-worker/Dockerfile -t <image> .
Step 4: shell MCP → docker push <api_image> && docker push <worker_image>
Step 5: shell MCP → source deployment/ecs/.manual-deploy.env && deployment/ecs/scripts/render-task-defs.sh
Step 6: shell MCP → deployment/ecs/scripts/register-task-defs.sh
Step 7: shell MCP → deployment/ecs/scripts/deploy-services.sh
        → Verify: aws ecs describe-services --cluster airex-prod-cluster --services airex-prod-api
```

#### Frontend Only

```
Step 1: shell MCP → npm ci --prefix apps/web
Step 2: shell MCP → VITE_GOOGLE_CLIENT_ID=<from secrets> npm run build --prefix apps/web
Step 3: shell MCP → aws s3 sync apps/web/dist s3://airex-prod-frontend-547361935557 --delete
Step 4: shell MCP → aws cloudfront create-invalidation --distribution-id <id> --paths "/*"
```

#### Full Deploy (Everything)

```
Step 1: terraform MCP → validate + plan
Step 2: terraform MCP → apply (if infra changes needed)
Step 3: shell MCP → docker build + push (API, Worker, LiteLLM)
Step 4: shell MCP → alembic upgrade heads (DB migrations)
Step 5: shell MCP → render → register → deploy ECS services
Step 6: shell MCP → npm build → S3 sync → CloudFront invalidate

OR single command:
Step 1: shell MCP → deployment/ecs/scripts/manual-deploy-all.sh
```

### 15.3 Safety Rules for AI Agents

- **NEVER auto-run** `terraform apply` or `terraform destroy` without explicit user confirmation
- **NEVER auto-run** `aws secretsmanager update-secret` — always confirm the new value
- **ALWAYS show** the `terraform plan` output to the user before applying
- **ALWAYS show** the image tag being deployed before pushing/deploying
- **OK to auto-run:** `terraform validate`, `terraform plan`, `aws ecs list-tasks`, `aws logs tail`, read-only operations
- **OK to auto-run:** `docker build` (local only, no side effects until push)

---

## 16. Troubleshooting

### ECS → RDS Connection Issues

```bash
# Get a shell inside a running task (see §13.2)
TASK=$(aws ecs list-tasks --cluster airex-prod-cluster --service-name airex-prod-api --query 'taskArns[0]' --output text) && \
aws ecs execute-command --cluster airex-prod-cluster --task $TASK --container api --interactive --command /bin/bash

# Test DB connectivity
python -c "import asyncio; from sqlalchemy.ext.asyncio import create_async_engine; e = create_async_engine('$DATABASE_URL'); asyncio.run(e.dispose())"
```

### ECS → Redis Connection Issues

```bash
# From inside ECS task
python -c "import redis; r = redis.from_url('$REDIS_URL'); print(r.ping())"
```

### ECS Exec Not Working

```bash
# Symptom: "The execute command failed" or session hangs
# Fix checklist:
#  1. Session Manager plugin installed locally? → session-manager-plugin --version
#  2. ECS service has enable_execute_command = true? → check Terraform
#  3. Task Role has ssmmessages permissions? → check IAM policy in Terraform
#  4. Task is RUNNING (not PENDING/STOPPED)? → aws ecs describe-tasks --cluster ... --tasks ...
#  5. Container has /bin/bash? → try /bin/sh instead
```

### Common Pitfalls

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| `Connection refused` to RDS | data-sg missing 5432 ingress from ecs-sg | Check SG rules |
| `Connection timed out` to Redis | Wrong subnet or SG | Verify subnet/SG config |
| `SSL: CERTIFICATE_VERIFY_FAILED` on Redis | Using `redis://` not `rediss://` | Use `rediss://` (double s) |
| `AUTH failed` on Redis | Auth token mismatch | Check Secrets Manager value |
| `password authentication failed` on RDS | Password rotated outside TF | Align Secrets Manager with RDS |
| CodeBuild can't reach RDS | CodeBuild project not in VPC | Configure VPC in project settings |
| Frontend env vars missing | Secrets Manager value wrong | Check `/airex/prod/frontend/google_oauth_client_id` |
| Old image after deploy | ECS service didn't roll | `aws ecs update-service --force-new-deployment` |
| CloudFront serving stale content | Invalidation not triggered | `aws cloudfront create-invalidation --paths "/*"` |
| ECS Exec hangs/fails | Missing SSM plugin or IAM | See "ECS Exec Not Working" above |
| `Unable to start session` | Task Role missing ssmmessages | Check `aws_iam_role_policy.task_role_ecs_exec` in TF |
| Terraform plan shows drift | Manual AWS Console changes | `terraform refresh` then `terraform plan` |
| `Error: No valid credential sources found` in ECS | Task Role not attached | Check task definition `taskRoleArn` |

---

## 17. Security & Isolation

- **Zero-trust:** Worker tasks use short-lived scoped credentials from ECS Task Role. NEVER bake static AWS keys.
- **Network isolation:** RDS and Redis are in private subnets, unreachable from the internet. No bastion host exists.
- **Encryption:** RDS storage encrypted at rest. Redis has at-rest + in-transit (TLS) encryption.
- **Secret management:** All credentials auto-generated by Terraform and stored in Secrets Manager. Injected at container startup via `valueFrom`.
- **VPC design:** NAT Gateways in public subnets enable outbound internet for private subnets. No inbound internet reaches data services.
- **Least privilege:** Execution Role only reads specific secret/parameter ARNs. Task Role is scoped for application needs + ECS Exec SSM permissions.
- **Access model:** The ONLY way to reach RDS/Redis is via ECS Exec into a running task. This is by design — no SSH keys, no bastion, no public endpoints.
- **Observability isolation:** Langfuse runs in its own container with its own database, collecting telemetry offline from user API traffic.
- **Secrets policy:** Secrets are NEVER placed in `terraform.tfvars`, CodeBuild buildspecs, or checked into git.
