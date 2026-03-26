<!-- Generated: 2026-03-16 | Files scanned: 384 | Token estimate: ~600 -->

# Data Architecture

## Database
PostgreSQL 15, asyncpg driver, SQLAlchemy 2.0 async ORM
- Row-Level Security (RLS) on ALL tables
- Composite PKs: `(tenant_id, id)` everywhere
- `state_transitions` is immutable — SHA-256 hash chain, never UPDATE/DELETE

## Core Models (services/airex-core/airex_core/models/)
```
incident.py               id, tenant_id, state, alert_type, host_ip, severity,
                          recommendation_id, meta, created_at, updated_at
state_transition.py       id, incident_id, from_state, to_state, reason, hash,
                          prev_hash, created_at  [IMMUTABLE]
evidence.py               id, incident_id, tenant_id, data (JSONB), created_at
execution.py              id, incident_id, action_name, status, output, created_at
health_check.py           id, tenant_id, host, check_type, status, result, ran_at
organization.py           id, name, slug, status, timestamps (global SaaS customer)
organization_membership.py organization_id, user_id, role
project.py                id, organization_id, name, …
tenant.py                 id (tenant_id), organization_id, name, cloud, aws_config, gcp_config, …
user.py                   id, tenant_id, email, role, hashed_password, totp_secret,
                          invitation_token, invited_at, last_login
tenant_limit.py           tenant_id, max_incidents, max_users, feature_flags
knowledge_base.py         id, tenant_id, title, content, embedding (vector)
runbook.py                id, tenant_id, title, content, alert_type, generated
runbook_chunk.py          id, runbook_id, content, embedding (vector)
incident_embedding.py     id, incident_id, embedding (vector 1024)
comment.py                id, incident_id, tenant_id, author_id, content
related_incident.py       incident_id, related_id, correlation_score
feedback_learning.py      id, incident_id, feedback_type, content
notification_preference.py  user_id, channel, event_types, enabled
incident_template.py      id, tenant_id, name, alert_type, config
report_template.py        id, tenant_id, name, template_content
incident_lock.py          incident_id, locked_by, locked_at, ttl
```

## Migration History (database/alembic/versions/)
```
001_initial_schema              Base schema: incidents, evidence, executions,
                                state_transitions, tenants
002_add_users_table             users + tenant_limits
003_add_incident_host_key       host_ip index
004_add_role_constraint         role enum constraint
005_add_user_timestamps         invited_at, last_login
006_add_resolution_tracking     resolution_outcome, resolution_notes
007_add_correlation_group       correlation_group_id on incidents
008_add_health_checks           health_check_results table
009_add_totp_mfa                totp_secret on users
3503608aa8aa                    REJECTED state added to enum
4a1c0a3f4c2f                    pgvector extension + embeddings tables
5b759aef255f                    knowledge_base table
79c9cadf8b06                    related_incidents table
84b579817c2c                    report_templates table
90c2a46709e1                    user invitation fields
a0abe085396f                    incident_templates table
b1c2d3e4f5a6                    runbooks + pattern_group tables
cecb2f816253                    feedback_learning table
dbf34187c3db                    removed ESCALATED state
e24dbe500578                    merge: user_timestamps + rag_tables heads
e964260b273c                    resize vector columns 3072→1024
fc8657236606                    incident_comments + assignment
fcd9217e5222                    notification_preferences table
```

## Current Migration Head
`009_add_totp_mfa` (merged via `e24dbe500578`)

## Run Migrations
```bash
cd database && alembic upgrade head
# or in Docker:
docker-compose run migrate
```

## Rules
- `nullable=True` on `tenant_id` is banned
- Never auto-generate Alembic migrations without review
- Schema changes and data backfills = separate migration files
- Large FK tables: use `NOT VALID` + `VALIDATE CONSTRAINT`
- Multi-organization SaaS: **`organizations`** → **`tenants`** (each tenant has **`organization_id`**); RLS and incident data remain keyed by **`tenant_id`**
