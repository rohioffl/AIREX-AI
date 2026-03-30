#!/usr/bin/env bash
# Approve pending OpenClaw Control UI / browser pairing ("pairing required").
# Uses OPENCLAW_GATEWAY_TOKEN from repo-root .env (must match gateway.auth.token).
#
# Usage:
#   ./scripts/openclaw-pairing-approve.sh           # approve latest pending request
#   ./scripts/openclaw-pairing-approve.sh list     # only list pending/paired devices
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TOKEN=$(python3 -c "
from pathlib import Path
p = Path('.env')
if not p.exists():
    raise SystemExit('Missing .env')
for line in p.read_text().splitlines():
    line = line.strip()
    if line.startswith('OPENCLAW_GATEWAY_TOKEN=') and not line.startswith('#'):
        v = line.split('=', 1)[1].strip().strip(chr(34)).strip(chr(39))
        if v:
            print(v)
            raise SystemExit(0)
raise SystemExit('OPENCLAW_GATEWAY_TOKEN missing or empty in .env')
")

COMPOSE=(docker compose --env-file .env -f services/openclaw/docker-compose.yml)
URL=ws://127.0.0.1:18789
CLI=(node dist/index.js devices)

if [[ "${1:-}" == "list" ]]; then
  "${COMPOSE[@]}" exec -T openclaw-gateway "${CLI[@]}" list --token "$TOKEN" --url "$URL"
  exit 0
fi

"${COMPOSE[@]}" exec -T openclaw-gateway "${CLI[@]}" approve --latest --token "$TOKEN" --url "$URL"
echo "Done. Reload the dashboard / reconnect in the browser."
