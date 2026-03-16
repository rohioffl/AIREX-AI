<!-- Generated: 2026-03-16 | Files scanned: 384 | Token estimate: ~500 -->

# Dependencies & Integrations

## External Services
```
Vertex AI / Gemini    LiteLLM proxy → gemini-2.0-flash (primary)
                                     → gemini-flash-lite (fallback)
                      Circuit breaker: Redis-backed
Langfuse              LLM observability tracing (port 3000 local)
Site24x7              Monitor inventory + alert source
                      Client: airex_core/monitoring/site24x7_client.py
AWS SSM               RunShellScript for remote execution (preferred)
AWS EC2 IC            Instance Connect ephemeral SSH (fallback)
GCP OS Login          SSH to GCP VMs via asyncssh
AWS CloudTrail        Audit log fetch (aws_cloudtrail.py)
AWS VPC Flow Logs     Network investigation (aws_vpc_flows.py)
AWS Auto Scaling      Scale actions (aws_autoscaling.py)
GCP Cloud Logging     Log fetch (gcp_logging.py)
GCP MIG               Managed instance group ops (gcp_mig.py)
Google OAuth          ID token verification (auth/google endpoint)
```

## Infrastructure (AWS ap-south-1)
```
ECS Fargate           4 services: api, worker, litellm, langfuse
RDS PostgreSQL 15     x2 instances
ElastiCache Redis 7   TLS enabled
ALB                   HTTPS termination
ECR                   Container image registry
S3 + CloudFront       Frontend hosting
AWS Secrets Manager   ALL secrets (never tfvars)
SSM Parameter Store   App config
CodeBuild             CI/CD + DB migrations
```

## Python Backend Dependencies (key)
```
fastapi               API framework
uvicorn               ASGI server
sqlalchemy[asyncio]   ORM (async)
asyncpg               PostgreSQL async driver
alembic               DB migrations
arq                   Async Redis Queue (worker)
redis                 Redis client
litellm               LLM abstraction layer
pgvector              Vector similarity (RAG)
boto3                 AWS SDK
asyncssh              GCP/SSH
google-auth           Google OAuth token verification
structlog             Structured logging
pydantic              Schema validation
pytest / pytest-asyncio  Testing
```

## JavaScript Frontend Dependencies (key)
```
react@19              UI framework
vite@7                Build tool
tailwindcss@4         Styling
axios                 HTTP client (centralized in api.js)
react-router-dom@6    Client-side routing
recharts              Charts (analytics/dashboard)
vitest                Unit testing
@testing-library/react  Component testing
playwright            E2E testing (e2e/)
```

## Monitoring Stack (infra/)
```
Prometheus            Metrics scraping (FastAPI /metrics endpoint)
Grafana               Dashboards
Alertmanager          Alert routing
k6                    Load testing
```

## Shared Library
```
services/airex-core/  pip install -e . from api and worker
                      pyproject.toml defines package: airex_core
```

## CI/CD (GitHub Actions)
```
6 jobs: lint, test-backend, test-frontend, build-docker, migrate, deploy-ecs
DB migrations: CodeBuild deploy phase (not ECS task)
```
