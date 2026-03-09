#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.registered-task-definitions.env"

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

update_service "${ECS_SERVICE_API:-airex-prod-api}" "$API_TASKDEF_ARN"
update_service "${ECS_SERVICE_WORKER:-airex-prod-worker}" "$WORKER_TASKDEF_ARN"
update_service "${ECS_SERVICE_LITELLM:-airex-prod-litellm}" "$LITELLM_TASKDEF_ARN"
update_service "${ECS_SERVICE_LANGFUSE:-airex-prod-langfuse}" "$LANGFUSE_TASKDEF_ARN"
