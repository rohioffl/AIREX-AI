# AIREX ECS Refactor (Production)

This directory contains production deployment scaffolding for:

- ECS Fargate (single cluster, multiple services)
- ALB host-based routing
- Frontend on S3 + CloudFront
- Secrets Manager (secrets) + SSM Parameter Store (non-secrets)

## Target Topology

- `airex.rohitpt.online` -> CloudFront -> S3 frontend
- `airex.rohitpt.online/api/*` -> CloudFront -> ALB -> ECS `airex-api`
- `litellm.rohitpt.online` -> ALB -> ECS `litellm`
- `langfuse.rohitpt.online` -> ALB -> ECS `langfuse`

## ECS Services and Tasks

Services:

- `airex-api`
- `airex-worker`
- `airex-litellm`
- `airex-langfuse`

One-off task:

- `airex-migrate` (runs `alembic upgrade head`)

## Terraform

Terraform root: `deployment/ecs/terraform/`

This baseline creates:

- ECS cluster/services/task definitions
- ALB and host-based listener rules
- S3 + CloudFront frontend delivery
- ECR repositories for API/worker/LiteLLM
- RDS (AIREX + Langfuse), ElastiCache Redis
- Secrets/parameters namespace under `/${project}/${environment}/...`

### Example usage

```bash
cd deployment/ecs/terraform
terraform init
terraform plan \
  -var='vpc_id=vpc-xxxx' \
  -var='public_subnet_ids=["subnet-a","subnet-b"]' \
  -var='private_subnet_ids=["subnet-c","subnet-d"]' \
  -var='api_image=<acct>.dkr.ecr.ap-south-1.amazonaws.com/airex-prod-api:latest' \
  -var='worker_image=<acct>.dkr.ecr.ap-south-1.amazonaws.com/airex-prod-worker:latest' \
  -var='litellm_image=<acct>.dkr.ecr.ap-south-1.amazonaws.com/airex-prod-litellm:latest'
```

Because DNS is on Hostinger, Terraform outputs DNS records for manual creation.

## Task Definition Templates

Templates: `deployment/ecs/task-definitions/`

Render + register flow:

```bash
./deployment/ecs/scripts/render-task-defs.sh
./deployment/ecs/scripts/register-task-defs.sh
```

## CI/CD

Starter buildspecs:

- `deployment/ecs/codebuild/buildspec.images.yml`
- `deployment/ecs/codebuild/buildspec.deploy.yml`
- `deployment/ecs/codebuild/buildspec.frontend.yml`

Pipeline order:

1. Build/push images
2. Render/register task defs
3. Run migrate task
4. Force ECS service deployments
5. Build frontend and sync to S3
6. Invalidate CloudFront
