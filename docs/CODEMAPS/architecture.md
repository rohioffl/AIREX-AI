<!-- Generated: 2026-03-16 | Files scanned: 384 | Token estimate: ~700 -->

# AIREX Architecture

## System Type
Monorepo — AI-powered SRE incident response automation platform (multi-organization SaaS: **organizations** → **tenants** → RLS-scoped **`tenant_id`** data)

## Service Boundaries
```
┌─────────────────────────────────────────────────────────────┐
│  Ingress (Nginx / ALB)                                      │
│   /api/* → FastAPI (port 8000)                              │
│   /      → React SPA (port 5173 / S3+CloudFront)           │
└────────────┬──────────────────────────────────────────────┘
             │
     ┌───────▼────────┐     ┌──────────────┐
     │  airex-api     │────▶│  airex-worker │  (ARQ)
     │  FastAPI       │     │  ARQ Worker   │
     └───────┬────────┘     └──────┬───────┘
             │                     │
     ┌───────▼─────────────────────▼───────┐
     │          airex-core (shared lib)     │
     │  models / services / core / llm /    │
     │  actions / cloud / investigations /  │
     │  rag / schemas / monitoring          │
     └───────┬──────────────────┬──────────┘
             │                  │
     ┌───────▼──────┐   ┌───────▼──────┐
     │  PostgreSQL  │   │  Redis 7     │
     │  (RLS + pgv) │   │  (queue+pub) │
     └──────────────┘   └──────────────┘
             │
     ┌───────▼──────────────────────┐
     │  LiteLLM Proxy (port 4000)   │
     │  → Vertex AI Gemini 2.0 Flash │
     │  → Gemini Flash Lite (fallback)│
     └──────────────────────────────┘
```

## Request Flow: Webhook → Resolution
```
POST /webhook/site24x7 or /webhook/generic
  → HMAC verify + rate limit + idempotency check
  → Create Incident (RECEIVED) + enqueue ARQ task
  → Worker: investigate() → Evidence
  → Worker: generate_recommendation() → Recommendation (LiteLLM + RAG)
  → Policy check: auto_approve + risk ≤ max_allowed_risk?
      YES → EXECUTING → VERIFYING → RESOLVED
      NO  → AWAITING_APPROVAL → operator approves → EXECUTING
  → SSE broadcasts state_changed to frontend
```

## State Machine
```
RECEIVED → INVESTIGATING → RECOMMENDATION_READY → AWAITING_APPROVAL → EXECUTING → VERIFYING → RESOLVED
                ↓                    ↓                     ↓               ↓           ↓
          FAILED_ANALYSIS         REJECTED             REJECTED     FAILED_EXECUTION  FAILED_VERIFICATION
```
- Law: `transition_state(incident, new_state, reason)` — never direct mutation
- Terminal: RESOLVED, REJECTED
- Retryable (max 3): FAILED_ANALYSIS, FAILED_EXECUTION, FAILED_VERIFICATION

## Monorepo Layout
```
services/airex-core/    shared lib (pip install -e .)
services/airex-api/     FastAPI runtime + Dockerfile
services/airex-worker/  ARQ worker runtime + Dockerfile
apps/web/               React 19 + Vite 7 + Dockerfile
database/alembic/       migrations (run: cd database && alembic upgrade head)
deployment/ecs/terraform/environments/prod/  ACTIVE Terraform root
infra/                  Prometheus, Grafana, Alertmanager, k6
e2e/                    Playwright tests
```

## Live Deployment
- Domain: `airex.rohitpt.online`
- AWS ECS Fargate (ap-south-1)
- Terraform state: S3 `airex-prod-terraform-state-ap-south-1-547361935557`
