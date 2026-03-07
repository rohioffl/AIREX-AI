#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/.rendered-task-definitions"

if [[ ! -d "$OUT_DIR" ]]; then
  echo "Rendered task definitions not found. Run render-task-defs.sh first." >&2
  exit 1
fi

register() {
  local file="$1"
  aws ecs register-task-definition --cli-input-json "file://$file" >/dev/null
  echo "Registered task definition: $(basename "$file")"
}

register "$OUT_DIR/airex-api.json"
register "$OUT_DIR/airex-worker.json"
register "$OUT_DIR/airex-litellm.json"
register "$OUT_DIR/airex-langfuse.json"
register "$OUT_DIR/airex-migrate.json"
