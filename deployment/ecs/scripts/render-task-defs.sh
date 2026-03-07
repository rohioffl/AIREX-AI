#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE_DIR="$ROOT_DIR/task-definitions"
OUT_DIR="$ROOT_DIR/.rendered-task-definitions"

mkdir -p "$OUT_DIR"

required_env=(
  API_IMAGE
  WORKER_IMAGE
  LITELLM_IMAGE
  EXECUTION_ROLE_ARN
  TASK_ROLE_ARN
  SECRET_DATABASE_URL_ARN
  SECRET_REDIS_URL_ARN
  SECRET_APP_SECRET_KEY_ARN
  SECRET_LITELLM_MASTER_KEY_ARN
  SECRET_LANGFUSE_PUBLIC_KEY_ARN
  SECRET_LANGFUSE_SECRET_KEY_ARN
  SECRET_OPENAI_KEY_ARN
  SECRET_GEMINI_KEY_ARN
  SECRET_LANGFUSE_DATABASE_URL_ARN
  SECRET_LANGFUSE_NEXTAUTH_SECRET_ARN
  SECRET_LANGFUSE_SALT_ARN
  LLM_BASE_URL
  LLM_PRIMARY_MODEL
  LLM_FALLBACK_MODEL
  LLM_EMBEDDING_MODEL
  CORS_ORIGINS
  LANGFUSE_HOST
  NEXTAUTH_URL
)

for name in "${required_env[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required env: $name" >&2
    exit 1
  fi
done

render_file() {
  local input_file="$1"
  local output_file="$2"

  sed \
    -e "s|__API_IMAGE__|$API_IMAGE|g" \
    -e "s|__WORKER_IMAGE__|$WORKER_IMAGE|g" \
    -e "s|__LITELLM_IMAGE__|$LITELLM_IMAGE|g" \
    -e "s|__EXECUTION_ROLE_ARN__|$EXECUTION_ROLE_ARN|g" \
    -e "s|__TASK_ROLE_ARN__|$TASK_ROLE_ARN|g" \
    -e "s|__SECRET_DATABASE_URL_ARN__|$SECRET_DATABASE_URL_ARN|g" \
    -e "s|__SECRET_REDIS_URL_ARN__|$SECRET_REDIS_URL_ARN|g" \
    -e "s|__SECRET_APP_SECRET_KEY_ARN__|$SECRET_APP_SECRET_KEY_ARN|g" \
    -e "s|__SECRET_LITELLM_MASTER_KEY_ARN__|$SECRET_LITELLM_MASTER_KEY_ARN|g" \
    -e "s|__SECRET_LANGFUSE_PUBLIC_KEY_ARN__|$SECRET_LANGFUSE_PUBLIC_KEY_ARN|g" \
    -e "s|__SECRET_LANGFUSE_SECRET_KEY_ARN__|$SECRET_LANGFUSE_SECRET_KEY_ARN|g" \
    -e "s|__SECRET_OPENAI_KEY_ARN__|$SECRET_OPENAI_KEY_ARN|g" \
    -e "s|__SECRET_GEMINI_KEY_ARN__|$SECRET_GEMINI_KEY_ARN|g" \
    -e "s|__SECRET_LANGFUSE_DATABASE_URL_ARN__|$SECRET_LANGFUSE_DATABASE_URL_ARN|g" \
    -e "s|__SECRET_LANGFUSE_NEXTAUTH_SECRET_ARN__|$SECRET_LANGFUSE_NEXTAUTH_SECRET_ARN|g" \
    -e "s|__SECRET_LANGFUSE_SALT_ARN__|$SECRET_LANGFUSE_SALT_ARN|g" \
    -e "s|__LLM_BASE_URL__|$LLM_BASE_URL|g" \
    -e "s|__LLM_PRIMARY_MODEL__|$LLM_PRIMARY_MODEL|g" \
    -e "s|__LLM_FALLBACK_MODEL__|$LLM_FALLBACK_MODEL|g" \
    -e "s|__LLM_EMBEDDING_MODEL__|$LLM_EMBEDDING_MODEL|g" \
    -e "s|__CORS_ORIGINS__|$CORS_ORIGINS|g" \
    -e "s|__LANGFUSE_HOST__|$LANGFUSE_HOST|g" \
    -e "s|__NEXTAUTH_URL__|$NEXTAUTH_URL|g" \
    "$input_file" >"$output_file"
}

render_file "$TEMPLATE_DIR/airex-api.json" "$OUT_DIR/airex-api.json"
render_file "$TEMPLATE_DIR/airex-worker.json" "$OUT_DIR/airex-worker.json"
render_file "$TEMPLATE_DIR/airex-litellm.json" "$OUT_DIR/airex-litellm.json"
render_file "$TEMPLATE_DIR/airex-langfuse.json" "$OUT_DIR/airex-langfuse.json"
render_file "$TEMPLATE_DIR/airex-migrate.json" "$OUT_DIR/airex-migrate.json"

echo "Rendered task definitions in: $OUT_DIR"
