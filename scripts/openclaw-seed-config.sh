#!/usr/bin/env bash
# Seed OpenClaw config for Docker + gateway.bind=lan:
#   - Control UI allowedOrigins (required for non-loopback bind)
#   - gateway.auth.token copied from repo-root .env OPENCLAW_GATEWAY_TOKEN (fixes
#     "unauthorized: gateway token missing" for dashboard + API clients)
#
# Requires: OPENCLAW_GATEWAY_TOKEN set in .env (generate: openssl rand -hex 24)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CFG="${OPENCLAW_CONFIG_DIR:-$ROOT/.local/openclaw/config}"
IMAGE="${OPENCLAW_IMAGE:-ghcr.io/openclaw/openclaw:latest}"

mkdir -p "$CFG"
docker pull "$IMAGE" >/dev/null
docker run --rm \
  -v "$CFG:/home/node/.openclaw" \
  -e HOME=/home/node \
  "$IMAGE" \
  node dist/index.js config set gateway.controlUi.allowedOrigins \
  '["http://127.0.0.1:18789","http://localhost:18789"]' --strict-json
echo "Seeded gateway.controlUi.allowedOrigins under $CFG"

python3 << PY
import json, subprocess, sys
from pathlib import Path

def token_from_env_file() -> str | None:
    p = Path("$ROOT") / ".env"
    if not p.exists():
        return None
    for line in p.read_text().splitlines():
        line = line.strip()
        if line.startswith("OPENCLAW_GATEWAY_TOKEN=") and not line.startswith("#"):
            v = line.split("=", 1)[1].strip().strip('"').strip("'")
            return v if v else None
    return None

tok = token_from_env_file()
if not tok:
    print("ERROR: Set OPENCLAW_GATEWAY_TOKEN in .env (e.g. openssl rand -hex 24), then re-run.", file=sys.stderr)
    sys.exit(1)

cfg = Path("$CFG").resolve()
subprocess.run(
    [
        "docker", "run", "--rm",
        "-v", f"{cfg}:/home/node/.openclaw",
        "-e", "HOME=/home/node",
        "$IMAGE",
        "node", "dist/index.js", "config", "set", "gateway.auth.token",
        json.dumps(tok),
        "--strict-json",
    ],
    check=True,
)
print("Synced gateway.auth.token from .env (matches Control UI + AIREX OPENCLAW_GATEWAY_TOKEN).")

# ── Seed Gemini agents + tools (API key: GEMINI_API_KEY in .env → Docker env only, not in JSON) ──
def env_val(key: str) -> str:
    p = Path("$ROOT") / ".env"
    for line in p.read_text().splitlines():
        line = line.strip()
        if line.startswith(f"{key}=") and not line.startswith("#"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""

if not env_val("GEMINI_API_KEY"):
    print(
        "WARN: GEMINI_API_KEY is empty in .env. Set it (Google AI Studio) and recreate the gateway container.",
        file=sys.stderr,
    )

cfg_file = cfg / "openclaw.json"
if cfg_file.exists():
    config = json.loads(cfg_file.read_text())
else:
    config = {}

config.setdefault("gateway", {})
config["gateway"].setdefault("http", {})
config["gateway"]["http"].setdefault("endpoints", {})
config["gateway"]["http"]["endpoints"].setdefault("chatCompletions", {})
config["gateway"]["http"]["endpoints"]["chatCompletions"]["enabled"] = True
config["gateway"]["http"]["endpoints"].setdefault("responses", {})
config["gateway"]["http"]["endpoints"]["responses"]["enabled"] = True

# Native Google provider — no LiteLLM; see https://docs.openclaw.ai/providers/google
config.pop("models", None)
config.setdefault("agents", {})
config["agents"]["defaults"] = {
    "workspace": "/home/node/.openclaw/workspace",
    "model": {
        "primary": "google/gemini-2.0-flash",
        "fallbacks": ["google/gemini-2.0-flash"],
    },
    "models": {"google/gemini-2.0-flash": {"alias": "Gemini 2.0 Flash"}},
    "sandbox": {"mode": "off"},
}
config["agents"]["list"] = [
    {
        "id": "controller",
        "default": True,
        "name": "Investigation Controller",
        "model": "google/gemini-2.0-flash",
        "tools": {
            "profile": "full",
            "allow": [
                "run_host_diagnostics",
                "fetch_log_analysis",
                "fetch_change_context",
                "fetch_infra_state",
                "fetch_k8s_status",
                "read_incident_context",
                "write_evidence_contract",
            ]
        },
    },
    {
        "id": "researcher",
        "name": "SRE Researcher",
        "model": "google/gemini-2.0-flash",
        "tools": {
            "profile": "full",
            "allow": [
                "run_host_diagnostics",
                "fetch_log_analysis",
                "fetch_change_context",
                "fetch_infra_state",
                "fetch_k8s_status",
                "read_incident_context",
            ]
        },
    },
    {
        "id": "validator",
        "name": "Evidence Validator",
        "model": "google/gemini-2.0-flash",
        "tools": {
            "profile": "full",
            "allow": ["fetch_change_context", "fetch_infra_state", "fetch_k8s_status", "read_incident_context"],
        },
    },
    {"id": "reviewer", "name": "Senior Reviewer", "model": "google/gemini-2.0-flash"},
]
config.setdefault("plugins", {})
config["plugins"]["enabled"] = True
config["plugins"]["allow"] = ["airex-tools"]
load_paths = list(config["plugins"].get("load", {}).get("paths", []))
plugin_path = "/home/node/.openclaw/extensions/airex-tools"
if plugin_path not in load_paths:
    load_paths.append(plugin_path)
config["plugins"]["load"] = {"paths": load_paths}
entries = dict(config["plugins"].get("entries", {}))
entry_config = dict(entries.get("airex-tools", {}))
entry_config["enabled"] = True
entries["airex-tools"] = entry_config
config["plugins"]["entries"] = entries
config["tools"] = {
    "profile": "full",
    "deny": ["browser", "canvas"],
}
config.pop("env", None)

cfg_file.write_text(json.dumps(config, indent=2) + "\n")
print("Seeded agents for google/gemini-2.0-flash (set GEMINI_API_KEY in .env for the gateway container).")
print("Recreate gateway: docker compose --env-file .env -f services/openclaw/docker-compose.yml up -d openclaw-gateway")
PY
