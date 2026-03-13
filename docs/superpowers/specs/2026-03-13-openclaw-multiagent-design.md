# AIREX OpenClaw Multi-Agent System — Design Spec
**Date:** 2026-03-13
**Status:** Approved
**Project:** AIREX-AI (`/home/ubuntu/AIREX-AI/AIREX-AI`)

---

## Overview

Deploy a persistent 8-agent team inside the running OpenClaw gateway to handle all coding, bug fixing, testing, deployment, validation, and monitoring for the AIREX-AI platform. Each agent runs 24/7, has its own isolated workspace directory and model, communicates via OpenClaw's native agent-to-agent protocol, and works on feature branches — never directly on `main`.

---

## Architecture

```
User (Telegram / Discord / WebChat :18789)
              ↓
    OpenClaw Gateway (running, port 18789)
              ↓
    ┌─────────────────────────────────┐
    │   CONTROLLER  [gemini-2.5-pro]  │
    │   Reads full codebase (1M ctx)  │
    │   Routes all tasks              │
    │   Owns git: branch/commit/PR    │
    └────────────────┬────────────────┘
                     │ (agentToAgent — Controller initiates only)
     ┌───────┬───────┼───────┬──────────┬───────────┬──────────┐
     ↓       ↓       ↓       ↓          ↓           ↓          ↓
 Backend  Frontend  Reviewer Tester  Deploy/    Validator  Monitor
 Coder    Coder              (4.1    Infra      (Sonnet)   (Gemini
 (Sonnet) (gpt-4.1)  (Sonnet) Mini)  (Nova Pro)            Flash)
     ↓       ↓       ↓       ↓          ↓           ↓          ↓
 FastAPI  React 19  Reviews pytest   Terraform  Alerts    5-min
 SQLAlch  Tailwind  all code Vitest  ECS        UI flows  cron
 ARQ      Vite      security Playwright Alembic  Patterns  health
              ↓
    /home/ubuntu/AIREX-AI/AIREX-AI
    (each task: isolated feature branch, never write to main)
```

---

## Agent Definitions

### 1. Controller
- **Model:** `google/gemini-2.5-pro`
- **Provider:** Gemini API
- **Cost:** $1.25/$10 per 1M tokens
- **Role:** Receives all user requests. Reads codebase context. Breaks tasks into subtasks. Creates feature branches. Delegates to agents. Aggregates results. Opens PRs. Reports back to user.
- **Git responsibility:** All `git checkout -b`, `git commit`, `git push`, `gh pr create` operations run through Controller. No other agent commits directly.
- **Key capability:** 1M token context — reads entire AIREX codebase before routing.
- **Fallback model:** `google/gemini-2.5-flash`

### 2. Backend Coder
- **Model:** `anthropic/claude-sonnet-4-6` (Bedrock)
- **Provider:** AWS Bedrock
- **Cost:** $3/$15 per 1M tokens
- **Role:** Writes and modifies Python/FastAPI/SQLAlchemy/ARQ code on the feature branch created by Controller. Follows all rules in `CLAUDE.md` and `AGENTS.md`. Uses `transition_state()` for all state changes. Async I/O only. `structlog` on every log line.
- **Fallback model:** `anthropic/claude-haiku-4-5` (Bedrock)

### 3. Frontend Coder
- **Model:** `openai/gpt-4.1`
- **Provider:** OpenAI API
- **Cost:** $2/$8 per 1M tokens
- **Role:** Writes React 19 / Vite / Tailwind v4 components on the feature branch. All API calls via `api.js`. No `dangerouslySetInnerHTML`. SSE state-driven rendering only. Prop types on all components.
- **Fallback model:** `openai/gpt-4.1-mini`

### 4. Reviewer
- **Model:** `anthropic/claude-sonnet-4-6` (Bedrock)
- **Provider:** AWS Bedrock
- **Cost:** $3/$15 per 1M tokens
- **Role:** Reviews every code diff before Controller commits. Enforces explicit checklist (see below). Rejects non-compliant code and returns specific failure reasons to Controller.
- **Review checklist (all must pass):**
  - [ ] No direct `incident.state =` mutation — only `transition_state()`
  - [ ] No action outside `ACTION_REGISTRY`
  - [ ] No bare `except:` — specific exceptions only
  - [ ] All DB/HTTP I/O is `async`
  - [ ] No `dangerouslySetInnerHTML` in frontend
  - [ ] No inline `fetch()` — all calls via `api.js`
  - [ ] No hardcoded secrets or credentials
  - [ ] RLS `tenant_id` filter on all DB queries
  - [ ] `structlog` with `correlation_id` on all log lines
  - [ ] No `nullable=True` on `tenant_id` columns
- **Fallback model:** `anthropic/claude-haiku-4-5` (Bedrock)

### 5. Tester
- **Model:** `openai/gpt-4.1-mini`
- **Provider:** OpenAI API
- **Cost:** $0.40/$1.60 per 1M tokens
- **Role:** Writes and runs `pytest` (backend), `Vitest` (frontend), `Playwright` (e2e) on the feature branch. Reports pass/fail with specific failure messages to Controller. Generates edge case coverage.
- **Pass criteria:** All existing tests pass + new tests for changed code added.
- **Fallback model:** `openai/gpt-4.1-nano`

### 6. Deploy/Infra
- **Model:** `amazon.nova-pro-v1:0` (Bedrock)
- **Provider:** AWS Bedrock
- **Cost:** $0.80/$3.20 per 1M tokens
- **Role:** Runs `terraform plan/apply` from `deployment/ecs/terraform/environments/prod`. Runs `alembic upgrade head` from `database/`. Updates ECS services. **Never runs `terraform destroy` without explicit double confirmation from user.** Runs rollback on failure (see Rollback Flow).
- **Pre-deploy gates:**
  - Remote state lock check before every operation
  - `terraform plan` output shown to Controller before `apply`
  - Human written confirmation required before `apply`
- **Fallback model:** `amazon.nova-lite-v1:0` (Bedrock)

### 7. Validator
- **Model:** `anthropic/claude-sonnet-4-6` (Bedrock)
- **Provider:** AWS Bedrock
- **Cost:** $3/$15 per 1M tokens
- **Role:** Five validation categories:
  1. **Alert validation** — real vs false positive vs duplicate (checks last 24h history)
  2. **Human pattern analysis** — bulk approvals, unusual timing, role misuse
  3. **Feature validation** — post-deploy end-to-end checklist
  4. **UI validation** — Playwright checks: incident list, SSE updates, approve/reject, SuperAdmin panel
  5. **AI context validation** — recommendation in ACTION_REGISTRY, risk proportionate to alert, confidence justified
- **Receives:** Secondary notification from AIREX *after* HMAC-verified webhook pipeline processes. Never intercepts the primary webhook.
- **Fallback model:** `anthropic/claude-haiku-4-5` (Bedrock)

### 8. Monitor
- **Model:** `google/gemini-2.5-flash`
- **Provider:** Gemini API
- **Cost:** $0.075/$0.30 per 1M tokens
- **Runs:** Every 5 minutes via OpenClaw heartbeat cron
- **Checks and thresholds:**
  - API `/health` — must return 200 within 3s
  - Redis queue depth (ARQ) — alert if > 50 jobs queued
  - DB connection pool — alert if < 2 connections available
  - LiteLLM circuit breaker — alert if state = OPEN
  - Error rate (Prometheus) — alert if > 5% over 5-min window
  - P95 API latency — alert if > 2000ms
- **On breach:** Sends structured alert to Controller with metric + threshold + current value.
- **Fallback model:** `google/gemini-2.0-flash`

---

## OpenClaw Configuration

```json
{
  "meta": { "lastTouchedVersion": "2026.3.8" },
  "auth": {
    "profiles": {
      "openai-codex:default": { "provider": "openai-codex", "mode": "oauth" },
      "google:manual": { "provider": "google", "mode": "token" },
      "bedrock:default": {
        "provider": "bedrock",
        "mode": "key",
        "accessKeyId": "${AWS_ACCESS_KEY_ID}",
        "secretAccessKey": "${AWS_SECRET_ACCESS_KEY}",
        "region": "ap-south-1"
      },
      "openai:default": {
        "provider": "openai",
        "mode": "key",
        "apiKey": "${OPENAI_API_KEY}"
      },
      "gemini:default": {
        "provider": "google",
        "mode": "key",
        "apiKey": "${GEMINI_API_KEY}"
      }
    }
  },
  "agents": {
    "defaults": {
      "workspace": "/home/ubuntu/AIREX-AI/AIREX-AI",
      "maxConcurrent": 4,
      "subagents": { "maxConcurrent": 8 },
      "compaction": { "mode": "safeguard" },
      "timeoutSeconds": 600
    },
    "list": [
      {
        "id": "controller",
        "default": true,
        "name": "Controller",
        "workspace": "/home/ubuntu/AIREX-AI/AIREX-AI",
        "agentDir": "/home/ubuntu/.openclaw/agents/controller/agent",
        "model": {
          "primary": "google/gemini-2.5-pro",
          "secondary": "google/gemini-2.5-flash"
        }
      },
      {
        "id": "backend-coder",
        "name": "Backend Coder",
        "workspace": "/home/ubuntu/AIREX-AI/AIREX-AI",
        "agentDir": "/home/ubuntu/.openclaw/agents/backend-coder/agent",
        "model": {
          "primary": "bedrock/anthropic.claude-sonnet-4-6-v1:0",
          "secondary": "bedrock/anthropic.claude-haiku-4-5-20251022-v1:0"
        }
      },
      {
        "id": "frontend-coder",
        "name": "Frontend Coder",
        "workspace": "/home/ubuntu/AIREX-AI/AIREX-AI",
        "agentDir": "/home/ubuntu/.openclaw/agents/frontend-coder/agent",
        "model": {
          "primary": "openai/gpt-4.1",
          "secondary": "openai/gpt-4.1-mini"
        }
      },
      {
        "id": "reviewer",
        "name": "Reviewer",
        "workspace": "/home/ubuntu/AIREX-AI/AIREX-AI",
        "agentDir": "/home/ubuntu/.openclaw/agents/reviewer/agent",
        "model": {
          "primary": "bedrock/anthropic.claude-sonnet-4-6-v1:0",
          "secondary": "bedrock/anthropic.claude-haiku-4-5-20251022-v1:0"
        }
      },
      {
        "id": "tester",
        "name": "Tester",
        "workspace": "/home/ubuntu/AIREX-AI/AIREX-AI",
        "agentDir": "/home/ubuntu/.openclaw/agents/tester/agent",
        "model": {
          "primary": "openai/gpt-4.1-mini",
          "secondary": "openai/gpt-4.1-nano"
        }
      },
      {
        "id": "deploy-infra",
        "name": "Deploy/Infra",
        "workspace": "/home/ubuntu/AIREX-AI/AIREX-AI",
        "agentDir": "/home/ubuntu/.openclaw/agents/deploy-infra/agent",
        "model": {
          "primary": "bedrock/amazon.nova-pro-v1:0",
          "secondary": "bedrock/amazon.nova-lite-v1:0"
        }
      },
      {
        "id": "validator",
        "name": "Validator",
        "workspace": "/home/ubuntu/AIREX-AI/AIREX-AI",
        "agentDir": "/home/ubuntu/.openclaw/agents/validator/agent",
        "model": {
          "primary": "bedrock/anthropic.claude-sonnet-4-6-v1:0",
          "secondary": "bedrock/anthropic.claude-haiku-4-5-20251022-v1:0"
        }
      },
      {
        "id": "monitor",
        "name": "Monitor",
        "workspace": "/home/ubuntu/AIREX-AI/AIREX-AI",
        "agentDir": "/home/ubuntu/.openclaw/agents/monitor/agent",
        "model": {
          "primary": "google/gemini-2.5-flash",
          "secondary": "google/gemini-2.0-flash"
        },
        "heartbeat": { "every": "5m" }
      }
    ]
  },
  "tools": {
    "profile": "coding",
    "agentToAgent": {
      "enabled": true,
      "allow": {
        "controller": ["backend-coder","frontend-coder","reviewer","tester","deploy-infra","validator","monitor"],
        "backend-coder": ["controller"],
        "frontend-coder": ["controller"],
        "reviewer": ["controller"],
        "tester": ["controller"],
        "deploy-infra": ["controller"],
        "validator": ["controller"],
        "monitor": ["controller"]
      }
    },
    "web": {
      "search": { "enabled": true, "provider": "gemini" }
    }
  },
  "subagents": {
    "allowAgents": ["controller"]
  }
}
```

---

## Branch Strategy

**Rule: No agent ever writes to `main` directly.**

```
Every task → Controller creates: feature/<task-slug>-<date>
Coders work on that branch
Reviewer approves on that branch
Tester passes on that branch
Controller opens PR → waits for human approval
Human approves PR → merge to main
Deploy/Infra deploys after merge
```

---

## Task Flows

### New Feature
```
User → Controller
  1. git checkout -b feature/<name>
  2. → Backend Coder (implement, on branch)
     → Frontend Coder (implement, on branch, parallel)
  3. → Reviewer (review diff, checklist)
     If FAIL: back to Coder(s) with specific failures
  4. → Tester (write tests, run suite)
     If FAIL: back to Coder(s)
  5. Controller: git push + gh pr create
  6. Controller: ask user to review and approve PR
  7. (After human approves) → Deploy/Infra (terraform plan)
  8. Controller: show plan to user, ask confirmation
  9. (After human confirms) → Deploy/Infra (terraform apply + alembic)
 10. → Validator (post-deploy feature checklist + UI check)
 11. Controller: report complete
```

### Bug Fix
```
User → Controller
  1. git checkout -b fix/<bug-name>
  2. → Backend/Frontend Coder (fix on branch)
  3. → Reviewer (verify fix, checklist)
  4. → Tester (regression + existing suite)
  5. Controller: git push + gh pr create
  6. Controller: ask user to approve PR
  7. (After human approves) → Deploy/Infra (if prod fix needed)
  8. → Validator (verify fix in prod)
  9. Controller: report complete
```

### Deploy
```
User → Controller
  1. → Deploy/Infra: terraform plan
  2. Controller: show full plan output to user
  3. User provides written "CONFIRM DEPLOY"
  4. → Deploy/Infra: terraform apply
  5. → Deploy/Infra: alembic upgrade head
     If migration involves large table:
       Check for NOT VALID + VALIDATE CONSTRAINT pattern
       Check schema change + data backfill are separate files
  6. → Validator: post-deploy feature checklist + Playwright UI
  7. → Monitor: immediate health check (no wait for 5-min cron)
  8. Controller: report complete
```

### Deploy Failed → Rollback
```
Deploy/Infra reports failure →
  If Terraform: terraform state rollback to last known good
  If ECS: aws ecs update-service --task-definition <previous>
  If Alembic: alembic downgrade -1
  → Monitor: health check
  → Controller: report failure + rollback status to user
  (terraform destroy NEVER runs without explicit "CONFIRM DESTROY" from user)
```

### Alert Received (Secondary Notification)
```
AIREX webhook pipeline (HMAC-verified, primary) processes alert normally
  ↓ (AIREX fires secondary notification to OpenClaw after processing)
Validator:
  1. Alert validation: real / false positive / duplicate
  2. If real → Controller
  3. Controller → Backend Coder (investigate + fix if needed)
  4. → Tester (regression)
  5. If hotfix: full Bug Fix flow
  6. Controller: report findings to user
```

### Scheduled Health Check (every 5 min)
```
Monitor (heartbeat cron):
  → Check all 6 metrics against thresholds
  → If all pass: log OK silently
  → If any breach: send structured alert to Controller
  → Controller: route to correct agent or notify user
```

---

## Agent Workspace Files

```
/home/ubuntu/.openclaw/agents/
├── controller/agent/
│   ├── AGENTS.md    ← orchestration rules, git workflow, routing logic
│   └── SOUL.md      ← coordinator personality, concise, decisive
├── backend-coder/agent/
│   ├── AGENTS.md    ← FastAPI/SQLAlchemy/AIREX backend rules from CLAUDE.md
│   └── SOUL.md      ← careful, safety-first, follows rules exactly
├── frontend-coder/agent/
│   ├── AGENTS.md    ← React/Vite/Tailwind/AIREX frontend rules from CLAUDE.md
│   └── SOUL.md      ← clean UI, no hacks, state-driven
├── reviewer/agent/
│   ├── AGENTS.md    ← full reviewer checklist, security rules
│   └── SOUL.md      ← strict, no shortcuts, specific failure messages
├── tester/agent/
│   ├── AGENTS.md    ← pytest/Vitest/Playwright patterns, coverage rules
│   └── SOUL.md      ← thorough, edge cases, clear pass/fail
├── deploy-infra/agent/
│   ├── AGENTS.md    ← Terraform/ECS/Alembic rules, rollback procedures
│   └── SOUL.md      ← cautious, always plan before apply, confirm first
├── validator/agent/
│   ├── AGENTS.md    ← 5 validation categories, alert analysis, Playwright
│   └── SOUL.md      ← analytical, pattern-aware, AIREX domain knowledge
└── monitor/agent/
    ├── AGENTS.md    ← metric thresholds, health check procedure
    ├── SOUL.md      ← silent when healthy, clear when not
    └── HEARTBEAT.md ← every 5m: check all 6 metrics
```

---

## Implementation Phases (Correct Order)

### Phase 1 — API Keys + Auth Profiles (45 mins)
User provides 3 sets of credentials. Added to `~/.openclaw/openclaw.json` auth profiles:
- Bedrock: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, region `ap-south-1`
  - Verify IAM: `bedrock:InvokeModel` permissions for `claude-sonnet-4-6`, `nova-pro`, `claude-haiku-4-5`
- OpenAI: `OPENAI_API_KEY`
  - Verify: `gpt-4.1` and `gpt-4.1-mini` accessible
- Gemini: `GEMINI_API_KEY`
  - Verify: `gemini-2.5-pro` and `gemini-2.5-flash` accessible

### Phase 2 — Agent Workspace Files (45 mins)
**Must run before gateway restart.**
- Create all 8 agent directories under `/home/ubuntu/.openclaw/agents/`
- Write `AGENTS.md` for each agent (role-specific rules derived from `CLAUDE.md`)
- Write `SOUL.md` for each agent
- Write `HEARTBEAT.md` for Monitor

### Phase 3 — OpenClaw Config (30 mins)
- Merge `agents.list` (all 8 agents) into `~/.openclaw/openclaw.json`
- Add `tools.agentToAgent` with asymmetric allow rules
- Add `subagents.allowAgents: ["controller"]`
- Validate JSON: `openclaw doctor`

### Phase 4 — Gateway Restart + Verify (15 mins)
- `openclaw restart`
- `openclaw agents list --bindings` — verify all 8 agents registered
- `openclaw health` — verify gateway healthy
- Verify each agent loads its `agentDir` without errors

### Phase 5 — End-to-End Test (30 mins)
**Pass criteria:**
1. Send via WebChat: "Fix the typo in the login page button text"
   → Controller creates branch `fix/login-button-typo-<date>`
   → Frontend Coder makes change
   → Reviewer returns PASS
   → Tester runs `npm run test` — all pass
   → PR created in GitHub
   → Result: PR URL returned to user ✅
2. Send: "Check application health"
   → Monitor fires immediately
   → Returns structured JSON with all 6 metric values ✅
3. Trigger Monitor cron manually
   → Verify it fires and returns silently on healthy system ✅

### Phase 6 — Mission Control (Optional, later)
- Deploy `openclaw-mission-control` via Docker
- Connect to gateway for task boards + audit trail
- Add when team grows or audit requirements increase

---

## Cost Projection

**Assumptions:** 20 coding tasks/day, avg 5K tokens input + 2K output per agent call, Monitor 288 calls/day at 500 tokens each.

| Agent | Calls/day | Tokens/call | Daily cost |
|---|---|---|---|
| Controller | 20 | 50K in / 2K out | ~$2.10 |
| Backend Coder | 15 | 8K in / 4K out | ~$0.96 |
| Frontend Coder | 10 | 6K in / 3K out | ~$0.36 |
| Reviewer | 25 | 10K in / 2K out | ~$1.35 |
| Tester | 20 | 5K in / 3K out | ~$0.18 |
| Deploy/Infra | 2 | 5K in / 2K out | ~$0.02 |
| Validator | 10 | 8K in / 3K out | ~$1.26 |
| Monitor | 288 | 0.5K in / 0.2K out | ~$0.02 |
| **Total** | | | **~$6.25/day** |

**Current:** ~$100/day (single agent, all tasks routed through expensive model)
**After:** ~$6–10/day
**Monthly saving:** ~$2,700

---

## Security Notes

- API keys stored in `~/.openclaw/openclaw.json` using env var references (`${VAR}`) — actual values in system environment, not in file
- `terraform destroy` requires explicit "CONFIRM DESTROY" from user — never auto-executed
- Human approval required before any PR merges to `main`
- Human written "CONFIRM DEPLOY" required before every `terraform apply`
- AIREX webhook HMAC pipeline never bypassed — Validator receives secondary notification only
- All agent actions logged via OpenClaw's built-in command-logger hook (already enabled)
