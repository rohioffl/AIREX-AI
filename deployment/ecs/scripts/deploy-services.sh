#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${ECS_CLUSTER:-}" ]]; then
  echo "Missing ECS_CLUSTER" >&2
  exit 1
fi

update_service() {
  local service_name="$1"
  aws ecs update-service \
    --cluster "$ECS_CLUSTER" \
    --service "$service_name" \
    --force-new-deployment >/dev/null
  echo "Triggered deployment: $service_name"
}

update_service "${ECS_SERVICE_API:-airex-prod-api}"
update_service "${ECS_SERVICE_WORKER:-airex-prod-worker}"
update_service "${ECS_SERVICE_LITELLM:-airex-prod-litellm}"
update_service "${ECS_SERVICE_LANGFUSE:-airex-prod-langfuse}"
