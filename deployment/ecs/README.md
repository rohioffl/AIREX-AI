# AIREX ECS Refactor (Production)

This directory contains production deployment scaffolding for:

- ECS Fargate (single cluster, multiple services)
- ALB routing for API/LiteLLM/Langfuse
- Frontend on S3 + CloudFront
- Secrets Manager (secrets) + SSM Parameter Store (non-secrets)

Production rule for this stack:

- secrets are stored in AWS Secrets Manager, not in Terraform tfvars files
- production is the only environment targeted right now; staging can be added later
- ACM certificates and GitHub/CodePipeline wiring are managed manually outside Terraform

## Target Topology

Initial deploy mode can run on AWS default domains first. Custom domains and ACM certificates can be attached later by setting `enable_custom_domains=true`.

- `CloudFront default domain` -> S3 frontend
- `CloudFront default domain/api/*` -> CloudFront -> ALB -> ECS `airex-api`
- Later: `frontend_domain` -> CloudFront custom domain
- Later: `litellm_domain` -> ALB custom domain
- Later: `langfuse_domain` -> ALB custom domain

Frontend is not served from ECS. The SPA is built by CodeBuild, uploaded to the Terraform-managed S3 bucket, and invalidated through the Terraform-managed CloudFront distribution.

## ECS Services and Tasks

Services:

- `airex-api`
- `airex-worker`
- `airex-litellm`
- `airex-langfuse`

The `airex-api` and `airex-worker` images are both built from `services/backend/Dockerfile`
using separate Docker targets so they stay deployable as independent containers while sharing
the same backend source tree in `backend/`.

## Terraform

Active production Terraform root:

- `deployment/ecs/terraform/environments/prod`

Module layout:

- `deployment/ecs/terraform/modules/vpc`
- `deployment/ecs/terraform/modules/platform`
- `deployment/ecs/terraform/modules/frontend`

Archived legacy flat root:

- `deployment/ecs/terraform/_legacy_flat_root`

Bootstrap stack for remote state:

- `deployment/ecs/terraform/bootstrap/`

This baseline creates:

- Optional dedicated VPC, public subnets, private subnets, IGW, NAT gateways, and route tables
- ECS cluster/services/task definitions
- ALB and listener rules
- S3 + CloudFront frontend delivery
- ECR repositories for API/worker/LiteLLM
- RDS (AIREX + Langfuse), ElastiCache Redis
- Secrets/parameters namespace under `/${project}/${environment}/...`

This stack does not create ACM certificates or CodePipeline resources. Provide existing certificate ARNs and wire CI/CD manually when you are ready for custom domains.

### Production remote state

Use the bootstrap stack once to create the Terraform state bucket and lock table:

```bash
cd deployment/ecs/terraform/bootstrap
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform apply
```

Then configure the production root backend:

```bash
cd deployment/ecs/terraform/environments/prod
terraform init -reconfigure -backend-config=backend.hcl
```

The production root uses `backend.hcl` so state settings stay out of hardcoded Terraform files.

### Example usage

```bash
cd deployment/ecs/terraform/environments/prod
terraform init -reconfigure -backend-config=backend.hcl
terraform plan \
  -var='api_image=<acct>.dkr.ecr.ap-south-1.amazonaws.com/airex-prod-api:latest' \
  -var='worker_image=<acct>.dkr.ecr.ap-south-1.amazonaws.com/airex-prod-worker:latest' \
  -var='litellm_image=<acct>.dkr.ecr.ap-south-1.amazonaws.com/airex-prod-litellm:latest'
```

Later, when you want custom domains, set `enable_custom_domains=true` and provide:

```bash
-var='alb_certificate_arn=arn:aws:acm:ap-south-1:123456789012:certificate/replace-me' \
-var='cloudfront_certificate_arn=arn:aws:acm:us-east-1:123456789012:certificate/replace-me'
```

By default, the stack now creates its own VPC and subnets. If you want to reuse an existing network, set `create_vpc=false` and provide `vpc_id`, `public_subnet_ids`, and `private_subnet_ids`.

Because DNS is on Hostinger, Terraform outputs DNS records for manual creation.

Use `deployment/ecs/terraform/README.md` for the module-level Terraform workflow summary.

## Task Definition Templates

Templates: `deployment/ecs/task-definitions/`

Render + register flow:

```bash
./deployment/ecs/scripts/render-task-defs.sh
./deployment/ecs/scripts/register-task-defs.sh
```

## CI/CD

CodePipeline/CodeBuild are handled manually outside this Terraform stack.

Recommended order:

1. Build/push images
2. Run backend migrations in your deployment runner inside the VPC
3. Update ECS services
4. Build frontend and sync to S3
5. Invalidate CloudFront

### Secrets policy

This stack keeps secrets in AWS Secrets Manager and does not place secret values in `terraform.tfvars`.
