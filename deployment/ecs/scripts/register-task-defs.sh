#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/.rendered-task-definitions"
ENV_FILE="$ROOT_DIR/.registered-task-definitions.env"

if [[ ! -d "$OUT_DIR" ]]; then
  echo "Rendered task definitions not found. Run render-task-defs.sh first." >&2
  exit 1
fi

register() {
  local file="$1"
  local var_name="$2"
  local taskdef_arn

  taskdef_arn="$(aws ecs register-task-definition --cli-input-json "file://$file" --query 'taskDefinition.taskDefinitionArn' --output text)"
  printf '%s=%q\n' "$var_name" "$taskdef_arn" >>"$ENV_FILE"
  echo "Registered task definition: $(basename "$file") -> $taskdef_arn"
}

: >"$ENV_FILE"

register "$OUT_DIR/airex-api.json" "API_TASKDEF_ARN"
register "$OUT_DIR/airex-worker.json" "WORKER_TASKDEF_ARN"
register "$OUT_DIR/airex-litellm.json" "LITELLM_TASKDEF_ARN"
register "$OUT_DIR/airex-langfuse.json" "LANGFUSE_TASKDEF_ARN"

echo "Wrote task definition ARNs to: $ENV_FILE"
