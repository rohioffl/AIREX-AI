#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.registered-task-definitions.env"
SKIP_LITELLM="${SKIP_LITELLM:-false}"
DEPLOY_ENV="${DEPLOY_ENV:-prod}"
PROJECT_PREFIX="airex-$DEPLOY_ENV"

if [[ -z "${ECS_CLUSTER:-}" ]]; then
  echo "Missing ECS_CLUSTER" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Registered task definitions not found. Run register-task-defs.sh first." >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

update_service() {
  local service_name="$1"
  local taskdef_arn="$2"
  aws ecs update-service \
    --cluster "$ECS_CLUSTER" \
    --service "$service_name" \
    --task-definition "$taskdef_arn" \
    --force-new-deployment >/dev/null
  echo "Triggered deployment: $service_name -> $taskdef_arn"
}

update_service "${ECS_SERVICE_API:-$PROJECT_PREFIX-api}" "$API_TASKDEF_ARN"
update_service "${ECS_SERVICE_WORKER:-$PROJECT_PREFIX-worker}" "$WORKER_TASKDEF_ARN"
if [[ "$SKIP_LITELLM" != "true" ]]; then
  update_service "${ECS_SERVICE_LITELLM:-$PROJECT_PREFIX-litellm}" "$LITELLM_TASKDEF_ARN"
fi
update_service "${ECS_SERVICE_LANGFUSE:-$PROJECT_PREFIX-langfuse}" "$LANGFUSE_TASKDEF_ARN"
