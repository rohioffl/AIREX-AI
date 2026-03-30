#!/usr/bin/env bash
# Create local directories for OpenClaw gateway persistence (.local/ is gitignored).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CFG="${OPENCLAW_CONFIG_DIR:-$ROOT/.local/openclaw/config}"
WS="${OPENCLAW_WORKSPACE_DIR:-$ROOT/.local/openclaw/workspace}"

mkdir -p "$CFG" "$WS"
echo "Created OpenClaw dirs:"
echo "  OPENCLAW_CONFIG_DIR=$CFG"
echo "  OPENCLAW_WORKSPACE_DIR=$WS"
echo ""
echo "Next steps:"
echo "  1. Read docs/openclaw_local_setup.md and services/openclaw/README.md"
echo "  2. Docker: ./scripts/openclaw-seed-config.sh  (once) then"
echo "     docker compose --env-file .env -f services/openclaw/docker-compose.yml up -d"
echo "  3. Or npm: npm install -g openclaw && openclaw onboard && openclaw gateway --port 18789"
echo ""
if command -v docker >/dev/null 2>&1; then
  echo "If using Docker and you see permission errors on mounted volumes, run:"
  echo "  sudo chown -R 1000:1000 \"$CFG\" \"$WS\""
fi
