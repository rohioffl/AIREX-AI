<!-- Generated: 2026-03-16 | Files scanned: 384 | Token estimate: ~900 -->

# Backend Architecture

## Entry Points
- API: `services/airex-api/app/main.py` — FastAPI app factory, lifespan, middleware
- Worker: `services/airex-worker/app/core/worker.py` — ARQ WorkerSettings, task registry

## API Routes (services/airex-api/app/api/routes/)
```
auth.py            POST /auth/login, /auth/logout, /auth/refresh, /auth/google
                   POST /auth/set-password, /auth/totp/setup, /auth/totp/verify
incidents.py       GET/POST /incidents
                   GET/PATCH/DELETE /incidents/{id}
                   POST /incidents/{id}/approve, /reject, /retry, /feedback
                   GET /incidents/{id}/runbook, /execution-logs, /timeline
webhooks.py        POST /webhook/site24x7, /webhook/generic
                   GET /webhook/deliveries, /webhook/stats
sse.py             GET /events/stream  (SSE fan-out via Redis pub/sub)
health_checks.py   GET /health-checks/dashboard, /history, /monitors
                   POST /health-checks/run
metrics.py         GET /metrics/summary, /alert-history, /system
analytics.py       GET /analytics/incidents, /trends, /resolution-time, /mttr
runbooks.py        GET/POST /runbooks, GET/PUT/DELETE /runbooks/{id}
                   POST /runbooks/ingest, /runbooks/search
knowledge_base.py  GET/POST /knowledge-base, GET/DELETE /knowledge-base/{id}
templates.py       GET/POST /incident-templates
reports.py         GET/POST /reports, GET /reports/{id}, POST /reports/generate
users.py           GET/POST /users, GET/PUT/DELETE /users/{id}
tenants.py         GET/POST /tenants, GET/PUT /tenants/{id}
chat.py            POST /incidents/{id}/chat
dlq.py             GET /dlq/messages, POST /dlq/retry, /dlq/purge
grafana_dashboards.py  GET /grafana/dashboards
settings.py        GET/PUT /settings
site24x7.py        GET /site24x7/monitors, /site24x7/status
anomalies.py       GET /anomalies
patterns.py        GET /patterns
predictions.py     GET /predictions
root_causes.py     GET /root-causes
notification_preferences.py  GET/PUT /notification-preferences
```

## Middleware Chain (main.py)
```
CORSMiddleware → CSRFMiddleware → RateLimitMiddleware → JWT auth (per-route dep)
```

## Dependencies (services/airex-api/app/api/dependencies.py)
```
get_db()                    → AsyncSession
get_current_user()          → User (JWT decode)
require_permission(Perm.X)  → RBAC gate
RequireViewer               → alias for Permission.INCIDENT_VIEW
```

## ARQ Worker Tasks (services/airex-worker/app/core/worker.py)
```
investigate_task             → InvestigationService.run()
generate_recommendation_task → RecommendationService.generate()
execute_action_task          → ExecutionService.run() + distributed Redis lock
verify_resolution_task       → VerificationService.run()
generate_runbook_task        → RunbookGenerator.generate()
health_check_task            → HealthCheckService.run_checks()
retry_failed_task            → RetryScheduler.schedule()
```

## Core Services (services/airex-core/airex_core/services/)
```
incident_service.py          CRUD, state transitions
investigation_service.py     Runs probe plugins, stores Evidence
recommendation_service.py    LLM call + RAG context injection
execution_service.py         Dispatches ACTION_REGISTRY action
verification_service.py      Re-runs health probes after action
runbook_generator.py         Auto-generates runbooks post-resolution
health_check_service.py      Proactive scheduled health checks
correlation_service.py       Cross-host incident grouping
pattern_detection_service.py Recurring alert pattern detection
anomaly_detection_service.py Statistical anomaly scoring
rag_context.py               pgvector similarity search for context
chat_service.py              Conversational AI on incident context
notification_service.py      Email/webhook notification dispatch
report_service.py            Incident report generation
```

## Action Registry (airex_core/actions/registry.py)
```
restart_service     RestartServiceAction    auto_approve=False  risk=HIGH
clear_logs          ClearLogsAction         auto_approve=True   risk=MED
scale_instances     ScaleInstancesAction    auto_approve=False  requires_senior=True
flush_cache         FlushCacheAction
kill_process        KillProcessAction
block_ip            BlockIpAction
drain_node          DrainNodeAction
resize_disk         ResizeDiskAction
restart_container   RestartContainerAction
rollback_deployment RollbackDeploymentAction
rotate_credentials  RotateCredentialsAction
toggle_feature_flag ToggleFeatureFlagAction
```

## Cloud Execution (airex_core/cloud/)
```
aws_ssm.py         SSM RunShellScript (preferred)
aws_ssh.py         EC2 Instance Connect ephemeral SSH (fallback)
gcp_ssh.py         OS Login + asyncssh
discovery.py       Instance lookup by IP via AWS/GCP APIs (Redis-cached)
tenant_config.py   Per-tenant cloud credentials
```

## Key Files
```
airex_core/core/state_machine.py          transition_state() — law of state changes
airex_core/core/policy.py                 auto-approval + risk gate
airex_core/core/rbac.py                   Role/Permission enum + enforcement
airex_core/core/security.py               JWT, CSRF, password hashing
airex_core/llm/client.py                  LiteLLM + Redis circuit breaker
airex_core/rag/vector_store.py            pgvector similarity search
airex_core/monitoring/site24x7_client.py  Site24x7 API client
```
