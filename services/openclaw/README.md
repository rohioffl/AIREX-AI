# OpenClaw gateway (optional)

Sidecar service for **Phase 2 — InvestigationBridge**: dynamic investigation via the [OpenClaw](https://docs.openclaw.ai/gateway) gateway. AIREX calls it over HTTP; this folder holds Docker wiring only (no application code).

## Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | `openclaw-gateway` service (official image `ghcr.io/openclaw/openclaw`) |
| `env.example` | Environment variables for Docker and for repo-root `.env` (API/worker) |
| `plugins/airex-tools/` | Local OpenClaw plugin that exposes AIREX forensic tools to agents |

## Quick start (Docker)

From the **repository root**:

```bash
./scripts/openclaw-setup.sh
./scripts/openclaw-seed-config.sh   # once per machine: Control UI allowedOrigins for LAN bind
# Ensure .env has OPENCLAW_GATEWAY_TOKEN (see env.example); empty token can break auth — set if needed
docker compose --env-file .env -f services/openclaw/docker-compose.yml up -d
curl -fsS http://127.0.0.1:18789/healthz
```

The compose file uses `--allow-unconfigured` so the gateway can start before full `openclaw onboard`; `openclaw-seed-config.sh` writes the minimum config OpenClaw requires when binding on LAN.

Same stack via the thin wrapper at repo root: `docker compose -f docker-compose.openclaw.yml up -d` (includes this file).

## AIREX configuration

Copy `env.example` into the repo-root `.env` and set `OPENCLAW_GATEWAY_URL`:

- API on the host: `http://127.0.0.1:18789`
- API in Docker Compose: `http://openclaw-gateway:18789` (use both compose files together)

Full guide: `docs/openclaw_local_setup.md`.

## AIREX tool plugin

The gateway now mounts a local plugin from `services/openclaw/plugins/airex-tools/`.
It registers these read-only agent tools:

- `run_host_diagnostics`
- `fetch_log_analysis`
- `fetch_change_context`
- `fetch_infra_state`

These call back into AIREX at `/api/v1/internal/tools/*` using the shared
`OPENCLAW_TOOL_SERVER_TOKEN` secret. If `OPENCLAW_TOOL_SERVER_TOKEN` is empty,
the plugin and API both fall back to `OPENCLAW_GATEWAY_TOKEN`.

After plugin or config changes, recreate the gateway:

```bash
./scripts/openclaw-seed-config.sh
docker compose --env-file .env -f services/openclaw/docker-compose.yml up -d openclaw-gateway
```

## Gemini (default models)

Agents use **`google/gemini-2.0-flash`** via OpenClaw’s native Google provider. Set **`GEMINI_API_KEY`** in the repo-root `.env` (Google AI Studio). Compose passes it into the container as `GEMINI_API_KEY` and `GOOGLE_API_KEY`. After changing the key, recreate the gateway: `docker compose --env-file .env -f services/openclaw/docker-compose.yml up -d openclaw-gateway`.

## Control UI: “gateway token missing” / Connect form

On **`/chat`** the Connect form shows **WebSocket URL** + **Gateway Token**. Do one of the following:

### Option A — tokenized URL (easiest)

With the gateway container running:

```bash
chmod +x scripts/openclaw-dashboard-url.sh
./scripts/openclaw-dashboard-url.sh
```

Open the printed URL in your browser (it includes `#token=…` so you do not need to paste anything).

### Option B — paste the shared secret

1. Ensure `.env` has a non-empty `OPENCLAW_GATEWAY_TOKEN` and you ran `./scripts/openclaw-seed-config.sh` so `gateway.auth.token` matches.
2. Copy the **exact** `OPENCLAW_GATEWAY_TOKEN` value from `.env` (the long hex string after `=`).
3. In the Connect form: **WebSocket URL** = `ws://127.0.0.1:18789`, **Gateway Token** = paste that value, then **Connect**.

The placeholder text says “optional” but the gateway is configured to require a token — leave **Password** empty unless you set one.

### AIREX → gateway

`InvestigationBridge` sends the same secret as `Authorization: Bearer …` and `X-OpenClaw-Token`.

## “Pairing required”

OpenClaw may require **device approval** for the browser before the WebSocket connects. After you try to connect once (so a pending request exists), run from the repo root:

```bash
chmod +x scripts/openclaw-pairing-approve.sh
./scripts/openclaw-pairing-approve.sh list   # optional: see pending requests
./scripts/openclaw-pairing-approve.sh        # approve the latest pending device
```

Then refresh the dashboard or click **Connect** again. This uses `openclaw devices approve --latest` with your `.env` token ([OpenClaw devices CLI](https://docs.openclaw.ai/cli/devices)).

## npm alternative

Install and run on the host without Docker: `npm install -g openclaw` then `openclaw onboard` and `openclaw gateway --port 18789`. See the doc above.
