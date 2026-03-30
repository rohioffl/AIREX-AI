#!/usr/bin/env bash
# Print a dashboard URL that includes the auth token (avoids manual paste).
# Requires: gateway container running (docker compose ... up -d openclaw-gateway)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
docker compose --env-file .env -f services/openclaw/docker-compose.yml exec -T openclaw-gateway \
  node dist/index.js dashboard --no-open
