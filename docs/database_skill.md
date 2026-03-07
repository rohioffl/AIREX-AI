---
name: database-core
description: Design and implement the PostgreSQL database layer for the Agentic AI Incident Response Platform. Focus on multi-tenancy, strict schema enforcement, and auditability.
license: Private
---

# Database Skill — AIREX

> **Single-tenant mode:** Although the schema still includes `tenant_id` columns for future scalability, the running system now fixes every row to the primary DEV tenant. RLS `SET app.tenant_id` calls always use `00000000-0000-0000-0000-000000000000` until multi-tenancy is reintroduced.

This skill defines the data persistence rules for the autonomous SRE system.

This is NOT a schema-less playground.
This is a **System of Record** for production incidents.

The Database must be:

- **Multi-Tenant**: Strict isolation via `tenant_id` and **Row Level Security (RLS)**.
- **Auditable**: Every status change is immutable and hashed.
- **Performant**: Composite Primary Keys for partitioning.
- **Safe**: Database-level Enums and Constraints.

---

## 1. Tech Stack (Mandatory)

| Component | Choice | Restriction |
| :--- | :--- | :--- |
| **Engine** | PostgreSQL 15+ | **NO** MySQL. **NO** Mongo. |
| **ORM** | SQLAlchemy 2.0 (Async) | Strict typing. Scoped sessions required. |
| **Migrations** | Alembic | **NO** auto-generating migrations without review. |
| **Connection** | Asyncpg | Connection pooling required. |

**Current repo location:** migrations live in `database/`, with Alembic config in `database/alembic.ini` and versions under `database/alembic/versions/`.

---

## 2. Core Architectural Rules

### 2.1 Multi-Tenancy (Strict)
1.  **Composite Primary Keys**: Every table (except reference data) MUST use `(tenant_id, id)` as the Primary Key.
    - *Why?* Enables partitioning and prevents cross-tenant joins.
2.  **ORM Enforcement**: All repository queries must use a scoped session:
    `session = get_session_for_tenant(ctx.tenant_id)`
    - *Metric*: Zero global session usage allowed.
3.  **Row Level Security (RLS)** (Production Target):
    - `ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;`
    - `ALTER TABLE incidents FORCE ROW LEVEL SECURITY;`
    - `ALTER TABLE evidence ENABLE ROW LEVEL SECURITY FORCE ROW LEVEL SECURITY;`
    - `ALTER TABLE state_transitions ENABLE ROW LEVEL SECURITY FORCE ROW LEVEL SECURITY;`
    - `ALTER TABLE executions ENABLE ROW LEVEL SECURITY FORCE ROW LEVEL SECURITY;`
    - `ALTER TABLE incident_locks ENABLE ROW LEVEL SECURITY FORCE ROW LEVEL SECURITY;`
    - **Policy**: Apply `tenant_isolation` policy to **ALL** tables.
    - **Connection Safety**:
      - `SET app.tenant_id` immediately on checkout.
      - **RESET** `app.tenant_id` on return to pool. **Critical** to prevent leakage.

### 2.2 Strict State Management
- **PostgreSQL Enums**: Do NOT rely solely on Python Enums.
  ```sql
CREATE TYPE incident_state AS ENUM (
    'RECEIVED',
    'INVESTIGATING',
    'RECOMMENDATION_READY',
    'AWAITING_APPROVAL',
    'EXECUTING',
    'VERIFYING',
    'RESOLVED',
    'FAILED_ANALYSIS',
    'FAILED_EXECUTION',
    'FAILED_VERIFICATION',
    'REJECTED'
);
  CREATE TYPE severity_level AS ENUM ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW');
  ```
- **Validation**: `state` column must be `incident_state NOT NULL`.

---

## 3. Schema Specifications

### 3.1 Incidents Table
- **PK**: `tenant_id` (UUID), `id` (UUID) - **Composite PK**
- **Columns**:
    - `alert_type` (String, Indexed, NOT NULL)
    - `state` (Enum `incident_state`, Indexed, NOT NULL)
    - `severity` (Enum `severity_level`, NOT NULL)
    - `title` (String, NOT NULL)
    - `created_at` (Timestamp, Default NOW(), Indexed)
    - `updated_at` (Timestamp, Default NOW())
    - `deleted_at` (Timestamp, Nullable) - **Soft Delete**
    - **Constraint**: `CHECK (deleted_at IS NULL OR state IN ('RESOLVED', 'FAILED_EXECUTION', 'FAILED_VERIFICATION', 'REJECTED'))`
    # Retry Logic Split (With Safety Checks)
    - `investigation_retry_count` (Integer, Default 0, CHECK >= 0 AND <= 3)
    - `execution_retry_count` (Integer, Default 0, CHECK >= 0 AND <= 3)
    - `verification_retry_count` (Integer, Default 0, CHECK >= 0 AND <= 3)
    - `meta` (JSONB)
- **Index**: 
    - `(tenant_id, state)`
    - `(tenant_id, created_at DESC)` (Dashboard optimized)

### 3.2 Evidence Table
- **PK**: `tenant_id` (UUID), `id` (UUID)
- **FK**: `(tenant_id, incident_id)` -> `incidents(tenant_id, id)`
- **Columns**:
    - `tool_name` (String)
    - `raw_output` (Text)
    - `timestamp` (Timestamp)
- **Constraint**: `ON DELETE CASCADE`.

### 3.3 State Transitions (Audit Log)
- **PK**: `tenant_id` (UUID), `id` (UUID)
- **FK**: `(tenant_id, incident_id)` -> `incidents(tenant_id, id)`
- **Columns**:
    - `from_state` (Enum, NOT NULL)
    - `to_state` (Enum, NOT NULL)
    - `reason` (Text)
    - `actor` (String)
    - `created_at` (Timestamp, Default NOW())
    - `previous_hash` (String, NOT NULL) - Chain link. **Genesis Rule**: First entry = `'GENESIS'`.
    - `hash` (String) - **Hash Chain**: `SHA256(prev_hash + output)`. Tamper-evident.
- **Rule**: **IMMUTABLE**.
    - `REVOKE UPDATE, DELETE ON state_transitions FROM app_user;`

### 3.4 Executions Table
- **PK**: `tenant_id` (UUID), `id` (UUID)
- **FK**: `(tenant_id, incident_id)` -> `incidents(tenant_id, id)`
- **Columns**:
    - `action_type` (String, NOT NULL)
    - `attempt` (Integer, Default 1)
    - `status` (Enum `execution_status`, NOT NULL)
    - `logs` (Text)
    - `started_at` (Timestamp, NOT NULL, Default NOW())
    - `completed_at` (Timestamp, Nullable)
    - `duration_seconds` - **Generated**: `GENERATED ALWAYS AS (EXTRACT(EPOCH FROM (completed_at - started_at))) STORED`
- **Enum**:
  ```sql
  CREATE TYPE execution_status AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED');
  ```
- **Constraint**: `UNIQUE (tenant_id, incident_id, action_type, attempt)` - **Idempotency**.

### 3.5 Incident Locks (DB Level)
- **PK**: `tenant_id` (UUID), `incident_id` (UUID)
- **Columns**:
    - `worker_id` (String)
    - `locked_at` (Timestamp)
    - `expires_at` (Timestamp)
- **Use**: Observability Only. **Primary Lock is Redis**.
- **Constraint**: No contention on this table. It is write-only for audit.

### 3.6 Tenant Limits (SaaS Future)
- **Table**: `tenant_limits`
- **PK**: `tenant_id` (UUID)
- **Columns**: `max_concurrent_incidents` (Int), `max_daily_executions` (Int).
- **Rule**: Enforce at application layer before DB insert.

---

## 4. STRICT PROHIBITIONS

1.  **NO Nullable Tenants**: `nullable=True` on `tenant_id` is **BANNED**.
2.  **NO Generic Strings for State**: Use DB Enums.
3.  **NO Single Integer Retry**: Must be split by phase.
4.  **NO Business Logic in DB**: No stored procedures (Exception: Infrastructure triggers like `updated_at`).
5.  **NO Global Queries**: `select * from incidents` without tenant filter is **BANNED**.

---

## 5. Performance & Migrations

- **Indexes**: 
    - **Dashboard Guarantee**:
      ```sql
      CREATE INDEX idx_incidents_active 
      ON incidents (tenant_id, created_at DESC) 
      WHERE deleted_at IS NULL;
      ```
    - **Hot Path**:
      ```sql
      CREATE INDEX idx_incidents_awaiting_approval 
      ON incidents (tenant_id, created_at DESC) 
      WHERE state = 'AWAITING_APPROVAL' AND deleted_at IS NULL;
      ```
    - **FK Performance** (Critical):
      - `CREATE INDEX idx_evidence_incident_fk ON evidence (tenant_id, incident_id);`
      - `CREATE INDEX idx_state_transitions_incident_fk ON state_transitions (tenant_id, incident_id);`
      - `CREATE INDEX idx_executions_incident_fk ON executions (tenant_id, incident_id);`
    - **Query Pattern**:
      ```sql
      SELECT * FROM incidents 
      WHERE tenant_id = ? AND deleted_at IS NULL
      ORDER BY created_at DESC 
      LIMIT 50;
      ```
- **Infrastructure Triggers** (Exception to "No Logic"):
    - **Auto-Update**: `updated_at` must use a `BEFORE UPDATE` trigger (`set_updated_at`).
- **Migrations (High Scale)**:
    - **Safe FKs**: Use `NOT VALID` then `VALIDATE CONSTRAINT` to avoid locking.
    - `alembic` revisions must handle Enum creation explicitly.
    - Data backfills separate from Schema changes.
    - The migration pipeline must keep `database/` independent from app deployment pipelines while importing shared models from `backend/`.

## 6. Acceptance Criteria

- [ ] **Multi-Tenant**: Composite PKs used everywhere. RLS verifiable.
- [ ] **Type Safe**: DB rejects invalid state strings.
- [ ] **Resilient**: Retry counters are granular per phase.
- [ ] **Idempotent**: Impossible to insert duplicate execution attempts.
- [ ] **Auditable**: State history is hashed and verifiable.
