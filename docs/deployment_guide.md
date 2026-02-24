# AIREX Deployment Guide

## Prerequisites
- Docker & Docker Compose v2+
- 4GB+ RAM (8GB recommended for full stack)
- Ports: 5173 (frontend), 8000 (backend), 5432 (postgres), 6379 (redis)

## Quick Start (Development)

```bash
# Clone and configure
git clone <repo> && cd AIREX
cp .env.template .env
# Edit .env with your secrets

# Start all services
docker-compose up -d

# Run migrations
docker-compose exec backend alembic upgrade head

# Verify
curl http://localhost:8000/health
curl http://localhost:5173
```

## Service Architecture

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│   Frontend   │───▶│    Nginx     │───▶│   Backend    │
│  React/Vite  │    │  (reverse    │    │   FastAPI    │
│  Port 5173   │    │   proxy)     │    │  Port 8000   │
└─────────────┘    └──────────────┘    └──────┬───────┘
                                              │
                   ┌──────────────┐    ┌──────▼───────┐
                   │    Redis     │◀──▶│    Worker    │
                   │  Port 6379   │    │    (ARQ)     │
                   └──────────────┘    └──────────────┘
                                              │
                   ┌──────────────┐           │
                   │  PostgreSQL  │◀──────────┘
                   │  Port 5432   │
                   └──────────────┘
```

## Docker Compose Services

| Service | Image | Role |
|---------|-------|------|
| `db` | postgres:15-alpine | Primary database |
| `redis` | redis:7-alpine | Cache, pub/sub, task queue |
| `backend` | Custom (FastAPI) | API server |
| `worker` | Custom (ARQ) | Background task processor |
| `migrate` | Custom (Alembic) | Database migrations |
| `frontend` | Custom (Nginx+React) | Web UI |

## Environment Variables

### Required
```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/airex

# Redis
REDIS_URL=redis://redis:6379/0

# Security (CHANGE IN PRODUCTION!)
SECRET_KEY=your-secure-random-string-here

# AI (optional — system works without it)
LLM_PRIMARY_MODEL=gpt-4
OPENAI_API_KEY=sk-...
```

### Optional
```env
ACCESS_TOKEN_EXPIRE_MINUTES=11520  # 8 days
CORS_ORIGINS=["http://localhost:5173"]
LLM_CIRCUIT_BREAKER_THRESHOLD=3
LLM_CIRCUIT_BREAKER_COOLDOWN=300
MAX_INVESTIGATION_RETRIES=3
MAX_EXECUTION_RETRIES=3
LLM_BASE_URL=http://ai-platform:4000/v1
LLM_API_KEY=proxy-secret
LLM_EMBEDDING_MODEL=text-embedding-3-large
```

## Retrieval-Augmented Generation (RAG) Setup

1. **Apply migrations (pgvector + vector tables)**
   ```bash
   alembic upgrade head
   ```
2. **Ingest runbooks / KB docs per tenant**
   ```bash
   python -m scripts.ingest_runbooks --directory docs/runbooks --tenant-id <tenant-uuid>
   ```
3. **Backfill historical incidents** (optional) so past runs get embeddings and show up in similarity search.

All embedding + completion calls should flow through the LiteLLM proxy; set `LLM_BASE_URL` and `LLM_API_KEY` so both the chat client and embeddings client inherit the same routing and Langfuse tracing.

## AWS investigations (SSM and EC2 Instance Connect)

For AWS targets, AIREX runs diagnostics on the instance in this order:

1. **SSM first** — If the instance is managed by Systems Manager, commands run via `ssm:SendCommand`. No SSH keys required.
2. **EC2 Instance Connect fallback** — If SSM is unavailable (agent not installed / not managed), AIREX uses **EC2 Instance Connect**: a temporary SSH key is pushed via the AWS API (valid 60s), then SSH runs to the instance. **No SSH keys are stored** anywhere; behaviour is similar to GCP OS Login / `gcloud compute ssh`.

**Requirements for EC2 Instance Connect**

- IAM permission: `ec2-instance-connect:SendSSHPublicKey`
- Instance: Amazon Linux 2, Ubuntu 16.04+, or other AMI with EC2 Instance Connect
- Network: AIREX must reach the instance’s **private IP** on port 22 (same VPC, peering, or VPN)

See runbook: [runbooks/aws_ec2_instance_connect.md](runbooks/aws_ec2_instance_connect.md).

## Production Deployment

### 1. Security Checklist
- [ ] Change `SECRET_KEY` to a cryptographically random 64+ char string
- [ ] Set `CORS_ORIGINS` to your actual frontend domain
- [ ] Enable HTTPS via reverse proxy (Nginx/Traefik/CloudFront)
- [ ] Set `ACCESS_TOKEN_EXPIRE_MINUTES` to a shorter value (e.g., 60)
- [ ] Configure PostgreSQL SSL connections
- [ ] Enable Redis AUTH with a password
- [ ] Remove `.env` from Docker images

### 2. Database
```bash
# Use managed PostgreSQL (RDS, Cloud SQL, etc.)
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/airex?ssl=require

# Run migrations
alembic upgrade head

# Validate RLS is active
psql -c "SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname='public';"
```

### 3. Scaling
```bash
# Scale workers independently
docker-compose up -d --scale worker=3

# Backend is stateless — scale behind a load balancer
docker-compose up -d --scale backend=2
```

### 4. Monitoring
- Prometheus scrapes `/metrics` every 10s
- Import `infra/prometheus/alerting_rules.yml` for alerts
- Connect Alertmanager to Slack/PagerDuty for notifications

### 5. Backup
```bash
# Database backup (daily cron)
pg_dump -Fc airex > /backups/airex_$(date +%Y%m%d).dump

# Redis is ephemeral — DLQ contents are the only critical data
docker-compose exec redis redis-cli SAVE
```

## Troubleshooting

### Migrations fail
```bash
# Check current state
alembic current
alembic history

# Reset (DESTROYS DATA!)
alembic downgrade base
alembic upgrade head
```

### SSE not updating
```bash
# Check Redis pub/sub
docker-compose exec redis redis-cli SUBSCRIBE "tenant:*:events"

# Check worker is emitting events
docker-compose logs --tail=20 worker | grep "emit_"
```

### Worker tasks stuck
```bash
# Check DLQ
docker-compose exec redis redis-cli LRANGE airex:dlq 0 -1

# Check ARQ queue
docker-compose exec redis redis-cli KEYS "arq:*"

# Restart workers
docker-compose restart worker
```

### High memory usage
```bash
# Check Redis memory
docker-compose exec redis redis-cli INFO memory

# Check PostgreSQL connections
docker-compose exec db psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"
```
