#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/../.." && pwd)"

DEPLOY_ENV="${DEPLOY_ENV:-prod}"
ENV_FILE="${MANUAL_DEPLOY_ENV_FILE:-}"
ENV_FILE_EXPLICIT="false"

SKIP_IMAGES="false"
SKIP_MIGRATIONS="false"
SKIP_BACKEND_DEPLOY="false"
SKIP_FRONTEND_DEPLOY="false"
IMAGE_TAG="${IMAGE_TAG:-}"

validate_env() {
  local env_name="$1"

  case "$env_name" in
    dev|prod)
      ;;
    *)
      echo "Unsupported environment: $env_name" >&2
      echo "Expected one of: dev, prod" >&2
      exit 1
      ;;
  esac
}

default_env_file() {
  local env_name="$1"
  local candidate="$ROOT_DIR/.manual-deploy.${env_name}.env"

  if [[ -f "$candidate" ]]; then
    printf '%s\n' "$candidate"
    return
  fi

  if [[ "$env_name" == "prod" ]]; then
    printf '%s\n' "$ROOT_DIR/.manual-deploy.env"
    return
  fi

  printf '%s\n' "$candidate"
}

usage() {
  cat <<'EOF'
Usage: deployment/ecs/scripts/manual-deploy-all.sh [options]

Deploys backend images + ECS services + frontend (S3/CloudFront) manually.

Options:
  --env <dev|prod>       Deployment environment (default: prod)
  --env-file <path>      Path to env file (overrides environment default)
  --image-tag <tag>      Image tag for API/worker/litellm (default: current git sha)
  --skip-images          Skip docker build/push step
  --skip-migrations      Skip alembic migration step
  --skip-backend         Skip task-def register + ECS service deploy step
  --skip-frontend        Skip frontend build + S3 sync + CloudFront invalidation
  -h, --help             Show this help

Required env vars for backend deploy step:
  AWS_REGION ECS_CLUSTER
  EXECUTION_ROLE_ARN TASK_ROLE_ARN
  TASKDEF_FAMILY_API TASKDEF_FAMILY_WORKER TASKDEF_FAMILY_LITELLM TASKDEF_FAMILY_LANGFUSE
  LOG_GROUP_API LOG_GROUP_WORKER LOG_GROUP_LITELLM LOG_GROUP_LANGFUSE
  SECRET_DATABASE_URL_ARN SECRET_REDIS_URL_ARN SECRET_APP_SECRET_KEY_ARN
  SECRET_LITELLM_MASTER_KEY_ARN SECRET_GEMINI_API_KEY_ARN
  SECRET_SITE24X7_CLIENT_SECRET_ARN SECRET_SITE24X7_REFRESH_TOKEN_ARN
  SECRET_LANGFUSE_PUBLIC_KEY_ARN SECRET_LANGFUSE_SECRET_KEY_ARN
  SECRET_LANGFUSE_DATABASE_URL_ARN SECRET_LANGFUSE_NEXTAUTH_SECRET_ARN SECRET_LANGFUSE_SALT_ARN
  LLM_BASE_URL LLM_PRIMARY_MODEL LLM_FALLBACK_MODEL LLM_EMBEDDING_MODEL
  CORS_ORIGINS FRONTEND_URL GOOGLE_OAUTH_CLIENT_ID SITE24X7_ENABLED SITE24X7_CLIENT_ID SITE24X7_BASE_URL SITE24X7_ACCOUNTS_URL EMAIL_FROM LANGFUSE_HOST NEXTAUTH_URL

Required env vars for frontend deploy step:
  CLOUDFRONT_DISTRIBUTION_ID

Optional vars:
  ECR_API_REPO (default: airex-<env>-api)
  ECR_WORKER_REPO (default: airex-<env>-worker)
  ECR_LITELLM_REPO (default: airex-<env>-litellm)
  TASKDEF_FAMILY_API (default: airex-<env>-api)
  TASKDEF_FAMILY_WORKER (default: airex-<env>-worker)
  TASKDEF_FAMILY_LITELLM (default: airex-<env>-litellm)
  TASKDEF_FAMILY_LANGFUSE (default: airex-<env>-langfuse)
  LOG_GROUP_API (default: /ecs/airex-<env>-api)
  LOG_GROUP_WORKER (default: /ecs/airex-<env>-worker)
  LOG_GROUP_LITELLM (default: /ecs/airex-<env>-litellm)
  LOG_GROUP_LANGFUSE (default: /ecs/airex-<env>-langfuse)
  FRONTEND_BUCKET (default: airex-<env>-frontend-<account_id>)
  FRONTEND_GOOGLE_CLIENT_ID_SECRET_ID (default: /airex/<env>/frontend/google_oauth_client_id)
  BACKEND_DATABASE_URL_SECRET_ID (default: /airex/<env>/backend/database_url)
  ECS_CLUSTER (default: airex-<env>-cluster)
  ECS_SERVICE_API (default: airex-<env>-api)
  ECS_SERVICE_WORKER (default: airex-<env>-worker)
  ECS_SERVICE_LITELLM (default: airex-<env>-litellm)
  ECS_SERVICE_LANGFUSE (default: airex-<env>-langfuse)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      DEPLOY_ENV="${2,,}"
      shift 2
      ;;
    --env-file)
      ENV_FILE="$2"
      ENV_FILE_EXPLICIT="true"
      shift 2
      ;;
    --image-tag)
      IMAGE_TAG="$2"
      shift 2
      ;;
    --skip-images)
      SKIP_IMAGES="true"
      shift
      ;;
    --skip-migrations)
      SKIP_MIGRATIONS="true"
      shift
      ;;
    --skip-backend)
      SKIP_BACKEND_DEPLOY="true"
      shift
      ;;
    --skip-frontend)
      SKIP_FRONTEND_DEPLOY="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

validate_env "$DEPLOY_ENV"

if [[ "$ENV_FILE_EXPLICIT" != "true" ]]; then
  ENV_FILE="$(default_env_file "$DEPLOY_ENV")"
fi

export DEPLOY_ENV
PROJECT_PREFIX="airex-$DEPLOY_ENV"

if [[ -f "$ENV_FILE" ]]; then
  echo "Loading env from $ENV_FILE"
  # shellcheck disable=SC1090
  source "$ENV_FILE"
else
  echo "Env file not found at $ENV_FILE; using existing process environment"
fi

require_cmd() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "Missing required command: $name" >&2
    exit 1
  fi
}

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required env: $name" >&2
    exit 1
  fi
}

require_cmd aws
require_cmd python3
require_cmd npm

AWS_REGION="${AWS_REGION:-ap-south-1}"
export AWS_REGION

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_REGISTRY="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

ECR_API_REPO="${ECR_API_REPO:-$PROJECT_PREFIX-api}"
ECR_WORKER_REPO="${ECR_WORKER_REPO:-$PROJECT_PREFIX-worker}"
ECR_LITELLM_REPO="${ECR_LITELLM_REPO:-$PROJECT_PREFIX-litellm}"

if [[ -z "$IMAGE_TAG" ]]; then
  IMAGE_TAG="$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
fi

export API_IMAGE="$ECR_REGISTRY/$ECR_API_REPO:$IMAGE_TAG"
export WORKER_IMAGE="$ECR_REGISTRY/$ECR_WORKER_REPO:$IMAGE_TAG"
export LITELLM_IMAGE="$ECR_REGISTRY/$ECR_LITELLM_REPO:$IMAGE_TAG"
export LANGFUSE_IMAGE="${LANGFUSE_IMAGE:-public.ecr.aws/langfuse/langfuse:2}"

export ECS_CLUSTER="${ECS_CLUSTER:-$PROJECT_PREFIX-cluster}"
export ECS_SERVICE_API="${ECS_SERVICE_API:-$PROJECT_PREFIX-api}"
export ECS_SERVICE_WORKER="${ECS_SERVICE_WORKER:-$PROJECT_PREFIX-worker}"
export ECS_SERVICE_LITELLM="${ECS_SERVICE_LITELLM:-$PROJECT_PREFIX-litellm}"
export ECS_SERVICE_LANGFUSE="${ECS_SERVICE_LANGFUSE:-$PROJECT_PREFIX-langfuse}"

export TASKDEF_FAMILY_API="${TASKDEF_FAMILY_API:-$PROJECT_PREFIX-api}"
export TASKDEF_FAMILY_WORKER="${TASKDEF_FAMILY_WORKER:-$PROJECT_PREFIX-worker}"
export TASKDEF_FAMILY_LITELLM="${TASKDEF_FAMILY_LITELLM:-$PROJECT_PREFIX-litellm}"
export TASKDEF_FAMILY_LANGFUSE="${TASKDEF_FAMILY_LANGFUSE:-$PROJECT_PREFIX-langfuse}"

export LOG_GROUP_API="${LOG_GROUP_API:-/ecs/$PROJECT_PREFIX-api}"
export LOG_GROUP_WORKER="${LOG_GROUP_WORKER:-/ecs/$PROJECT_PREFIX-worker}"
export LOG_GROUP_LITELLM="${LOG_GROUP_LITELLM:-/ecs/$PROJECT_PREFIX-litellm}"
export LOG_GROUP_LANGFUSE="${LOG_GROUP_LANGFUSE:-/ecs/$PROJECT_PREFIX-langfuse}"

FRONTEND_BUCKET="${FRONTEND_BUCKET:-$PROJECT_PREFIX-frontend-$ACCOUNT_ID}"
FRONTEND_GOOGLE_CLIENT_ID_SECRET_ID="${FRONTEND_GOOGLE_CLIENT_ID_SECRET_ID:-/airex/$DEPLOY_ENV/frontend/google_oauth_client_id}"
BACKEND_DATABASE_URL_SECRET_ID="${BACKEND_DATABASE_URL_SECRET_ID:-/airex/$DEPLOY_ENV/backend/database_url}"

echo "Deploy context:"
echo "  DEPLOY_ENV=$DEPLOY_ENV"
echo "  ENV_FILE=$ENV_FILE"
echo "  AWS_REGION=$AWS_REGION"
echo "  ACCOUNT_ID=$ACCOUNT_ID"
echo "  IMAGE_TAG=$IMAGE_TAG"
echo "  API_IMAGE=$API_IMAGE"
echo "  WORKER_IMAGE=$WORKER_IMAGE"
echo "  LITELLM_IMAGE=$LITELLM_IMAGE"

if [[ "$SKIP_IMAGES" != "true" ]]; then
  require_cmd docker
  echo "Logging into ECR..."
  aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"

  echo "Building API image..."
  docker build -f "$REPO_ROOT/services/airex-api/Dockerfile" -t "$API_IMAGE" "$REPO_ROOT"
  echo "Building worker image..."
  docker build -f "$REPO_ROOT/services/airex-worker/Dockerfile" -t "$WORKER_IMAGE" "$REPO_ROOT"
  echo "Building LiteLLM image..."
  docker build -f "$REPO_ROOT/services/litellm/Dockerfile" -t "$LITELLM_IMAGE" "$REPO_ROOT"

  echo "Pushing images..."
  docker push "$API_IMAGE"
  docker push "$WORKER_IMAGE"
  docker push "$LITELLM_IMAGE"
fi

if [[ "$SKIP_MIGRATIONS" != "true" ]]; then
  echo "Running database migrations..."
  export DATABASE_URL="$(aws secretsmanager get-secret-value --region "$AWS_REGION" --secret-id "$BACKEND_DATABASE_URL_SECRET_ID" --query SecretString --output text)"
  export PYTHONPATH="$REPO_ROOT/services/airex-core:${PYTHONPATH:-}"
  VENV_DIR="$ROOT_DIR/.manual-deploy-venv"
  if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
  fi
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  pip install --upgrade pip >/dev/null
  # Install airex-core first (shared models required by Alembic)
  pip install -e "$REPO_ROOT/services/airex-core/" >/dev/null
  # Install API requirements (includes all ORM deps)
  grep -v "^-e " "$REPO_ROOT/services/airex-api/requirements.txt" > /tmp/req.txt
  pip install -r /tmp/req.txt >/dev/null
    (cd "$REPO_ROOT/database" && alembic upgrade head)
  deactivate
fi

if [[ "$SKIP_BACKEND_DEPLOY" != "true" ]]; then
  required_backend_env=(
    AWS_REGION ECS_CLUSTER
    API_IMAGE WORKER_IMAGE LITELLM_IMAGE LANGFUSE_IMAGE
    EXECUTION_ROLE_ARN TASK_ROLE_ARN
    TASKDEF_FAMILY_API TASKDEF_FAMILY_WORKER TASKDEF_FAMILY_LITELLM TASKDEF_FAMILY_LANGFUSE
    LOG_GROUP_API LOG_GROUP_WORKER LOG_GROUP_LITELLM LOG_GROUP_LANGFUSE
    SECRET_DATABASE_URL_ARN SECRET_REDIS_URL_ARN SECRET_APP_SECRET_KEY_ARN
    SECRET_LITELLM_MASTER_KEY_ARN SECRET_GEMINI_API_KEY_ARN
    SECRET_SITE24X7_CLIENT_SECRET_ARN SECRET_SITE24X7_REFRESH_TOKEN_ARN
    SECRET_LANGFUSE_PUBLIC_KEY_ARN SECRET_LANGFUSE_SECRET_KEY_ARN
    SECRET_LANGFUSE_DATABASE_URL_ARN SECRET_LANGFUSE_NEXTAUTH_SECRET_ARN SECRET_LANGFUSE_SALT_ARN
    LLM_BASE_URL LLM_PRIMARY_MODEL LLM_FALLBACK_MODEL LLM_EMBEDDING_MODEL
    CORS_ORIGINS FRONTEND_URL GOOGLE_OAUTH_CLIENT_ID SITE24X7_ENABLED SITE24X7_CLIENT_ID SITE24X7_BASE_URL SITE24X7_ACCOUNTS_URL EMAIL_FROM LANGFUSE_HOST NEXTAUTH_URL
  )
  for name in "${required_backend_env[@]}"; do
    require_env "$name"
  done

  chmod +x "$ROOT_DIR/scripts/"*.sh
  echo "Rendering task definitions..."
  "$ROOT_DIR/scripts/render-task-defs.sh"
  echo "Registering task definitions..."
  "$ROOT_DIR/scripts/register-task-defs.sh"
  echo "Deploying ECS services..."
  "$ROOT_DIR/scripts/deploy-services.sh"
fi

if [[ "$SKIP_FRONTEND_DEPLOY" != "true" ]]; then
  require_env CLOUDFRONT_DISTRIBUTION_ID

  echo "Building frontend..."
  RAW_CLIENT_ID_SECRET="$(aws secretsmanager get-secret-value --region "$AWS_REGION" --secret-id "$FRONTEND_GOOGLE_CLIENT_ID_SECRET_ID" --query SecretString --output text)"
  export VITE_GOOGLE_CLIENT_ID="$(printf '%s' "$RAW_CLIENT_ID_SECRET" | node -e 'const fs=require("fs"); const raw=fs.readFileSync(0,"utf8").trim(); try { const parsed=JSON.parse(raw); process.stdout.write(parsed?.web?.client_id || parsed?.client_id || raw); } catch { process.stdout.write(raw); }')"

  npm ci --prefix "$REPO_ROOT/apps/web"
  npm run build --prefix "$REPO_ROOT/apps/web"

  echo "Syncing frontend artifacts to s3://$FRONTEND_BUCKET"
  aws s3 sync "$REPO_ROOT/apps/web/dist" "s3://$FRONTEND_BUCKET" --delete

  echo "Invalidating CloudFront distribution $CLOUDFRONT_DISTRIBUTION_ID"
  INVALIDATION_ID="$(aws cloudfront create-invalidation --distribution-id "$CLOUDFRONT_DISTRIBUTION_ID" --paths "/*" --query 'Invalidation.Id' --output text)"
  aws cloudfront wait invalidation-completed --distribution-id "$CLOUDFRONT_DISTRIBUTION_ID" --id "$INVALIDATION_ID"
  echo "CloudFront invalidation completed: $INVALIDATION_ID"
fi

echo "Manual deployment complete."
