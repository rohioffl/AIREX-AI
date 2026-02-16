"""Initial schema — all tables, enums, indexes, RLS, triggers.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-02-16
"""
from typing import Sequence, Union

from alembic import op

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


STATEMENTS = [
    # Enum types
    """CREATE TYPE incident_state AS ENUM (
        'RECEIVED', 'INVESTIGATING', 'RECOMMENDATION_READY',
        'AWAITING_APPROVAL', 'EXECUTING', 'VERIFYING', 'RESOLVED',
        'FAILED_ANALYSIS', 'FAILED_EXECUTION', 'FAILED_VERIFICATION',
        'ESCALATED')""",
    "CREATE TYPE severity_level AS ENUM ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')",
    "CREATE TYPE execution_status AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')",

    # incidents
    """CREATE TABLE incidents (
        tenant_id UUID NOT NULL,
        id UUID NOT NULL DEFAULT gen_random_uuid(),
        alert_type VARCHAR(255) NOT NULL,
        state incident_state NOT NULL DEFAULT 'RECEIVED',
        severity severity_level NOT NULL,
        title VARCHAR(500) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        deleted_at TIMESTAMPTZ,
        investigation_retry_count INTEGER NOT NULL DEFAULT 0,
        execution_retry_count INTEGER NOT NULL DEFAULT 0,
        verification_retry_count INTEGER NOT NULL DEFAULT 0,
        meta JSONB,
        PRIMARY KEY (tenant_id, id),
        CONSTRAINT ck_incidents_soft_delete CHECK (
            deleted_at IS NULL OR state IN ('RESOLVED','ESCALATED','FAILED_EXECUTION','FAILED_VERIFICATION')),
        CONSTRAINT ck_incidents_investigation_retry CHECK (investigation_retry_count BETWEEN 0 AND 3),
        CONSTRAINT ck_incidents_execution_retry CHECK (execution_retry_count BETWEEN 0 AND 3),
        CONSTRAINT ck_incidents_verification_retry CHECK (verification_retry_count BETWEEN 0 AND 3))""",
    "CREATE INDEX idx_incidents_alert_type ON incidents (alert_type)",
    "CREATE INDEX idx_incidents_tenant_state ON incidents (tenant_id, state)",
    "CREATE INDEX idx_incidents_active ON incidents (tenant_id, created_at DESC) WHERE deleted_at IS NULL",
    "CREATE INDEX idx_incidents_awaiting_approval ON incidents (tenant_id, created_at DESC) WHERE state = 'AWAITING_APPROVAL' AND deleted_at IS NULL",

    # evidence
    """CREATE TABLE evidence (
        tenant_id UUID NOT NULL, id UUID NOT NULL DEFAULT gen_random_uuid(),
        incident_id UUID NOT NULL, tool_name VARCHAR(255) NOT NULL,
        raw_output TEXT NOT NULL, timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (tenant_id, id),
        FOREIGN KEY (tenant_id, incident_id) REFERENCES incidents(tenant_id, id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED)""",
    "CREATE INDEX idx_evidence_incident_fk ON evidence (tenant_id, incident_id)",

    # state_transitions
    """CREATE TABLE state_transitions (
        tenant_id UUID NOT NULL, id UUID NOT NULL DEFAULT gen_random_uuid(),
        incident_id UUID NOT NULL,
        from_state incident_state NOT NULL, to_state incident_state NOT NULL,
        reason TEXT, actor VARCHAR(255) NOT NULL DEFAULT 'system',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        previous_hash VARCHAR(64) NOT NULL, hash VARCHAR(64) NOT NULL,
        PRIMARY KEY (tenant_id, id),
        FOREIGN KEY (tenant_id, incident_id) REFERENCES incidents(tenant_id, id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED)""",
    "CREATE INDEX idx_state_transitions_incident_fk ON state_transitions (tenant_id, incident_id)",

    # executions
    """CREATE TABLE executions (
        tenant_id UUID NOT NULL, id UUID NOT NULL DEFAULT gen_random_uuid(),
        incident_id UUID NOT NULL, action_type VARCHAR(255) NOT NULL,
        attempt INTEGER NOT NULL DEFAULT 1,
        status execution_status NOT NULL DEFAULT 'PENDING',
        logs TEXT, started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        completed_at TIMESTAMPTZ,
        duration_seconds NUMERIC GENERATED ALWAYS AS (EXTRACT(EPOCH FROM (completed_at - started_at))) STORED,
        PRIMARY KEY (tenant_id, id),
        FOREIGN KEY (tenant_id, incident_id) REFERENCES incidents(tenant_id, id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
        CONSTRAINT uq_executions_idempotency UNIQUE (tenant_id, incident_id, action_type, attempt))""",
    "CREATE INDEX idx_executions_incident_fk ON executions (tenant_id, incident_id)",

    # incident_locks
    """CREATE TABLE incident_locks (
        tenant_id UUID NOT NULL, incident_id UUID NOT NULL,
        worker_id VARCHAR(255) NOT NULL,
        locked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), expires_at TIMESTAMPTZ NOT NULL,
        PRIMARY KEY (tenant_id, incident_id))""",

    # tenant_limits
    """CREATE TABLE tenant_limits (
        tenant_id UUID NOT NULL PRIMARY KEY,
        max_concurrent_incidents INTEGER NOT NULL DEFAULT 50,
        max_daily_executions INTEGER NOT NULL DEFAULT 200)""",

    # Trigger
    """CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
       BEGIN NEW.updated_at = NOW(); RETURN NEW; END; $$ LANGUAGE plpgsql""",
    "CREATE TRIGGER trigger_incidents_updated_at BEFORE UPDATE ON incidents FOR EACH ROW EXECUTE FUNCTION set_updated_at()",

    # RLS
    "ALTER TABLE incidents ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE incidents FORCE ROW LEVEL SECURITY",
    "CREATE POLICY tenant_isolation_incidents ON incidents USING (tenant_id = current_setting('app.tenant_id')::uuid)",
    "ALTER TABLE evidence ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE evidence FORCE ROW LEVEL SECURITY",
    "CREATE POLICY tenant_isolation_evidence ON evidence USING (tenant_id = current_setting('app.tenant_id')::uuid)",
    "ALTER TABLE state_transitions ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE state_transitions FORCE ROW LEVEL SECURITY",
    "CREATE POLICY tenant_isolation_state_transitions ON state_transitions USING (tenant_id = current_setting('app.tenant_id')::uuid)",
    "ALTER TABLE executions ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE executions FORCE ROW LEVEL SECURITY",
    "CREATE POLICY tenant_isolation_executions ON executions USING (tenant_id = current_setting('app.tenant_id')::uuid)",
    "ALTER TABLE incident_locks ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE incident_locks FORCE ROW LEVEL SECURITY",
    "CREATE POLICY tenant_isolation_incident_locks ON incident_locks USING (tenant_id = current_setting('app.tenant_id')::uuid)",

    # Immutable
    "REVOKE UPDATE, DELETE ON state_transitions FROM PUBLIC",
]


DOWNGRADE_STATEMENTS = [
    "DROP POLICY IF EXISTS tenant_isolation_incident_locks ON incident_locks",
    "DROP POLICY IF EXISTS tenant_isolation_executions ON executions",
    "DROP POLICY IF EXISTS tenant_isolation_state_transitions ON state_transitions",
    "DROP POLICY IF EXISTS tenant_isolation_evidence ON evidence",
    "DROP POLICY IF EXISTS tenant_isolation_incidents ON incidents",
    "ALTER TABLE incident_locks DISABLE ROW LEVEL SECURITY",
    "ALTER TABLE executions DISABLE ROW LEVEL SECURITY",
    "ALTER TABLE state_transitions DISABLE ROW LEVEL SECURITY",
    "ALTER TABLE evidence DISABLE ROW LEVEL SECURITY",
    "ALTER TABLE incidents DISABLE ROW LEVEL SECURITY",
    "GRANT UPDATE, DELETE ON state_transitions TO PUBLIC",
    "DROP TRIGGER IF EXISTS trigger_incidents_updated_at ON incidents",
    "DROP FUNCTION IF EXISTS set_updated_at()",
    "DROP TABLE IF EXISTS tenant_limits",
    "DROP TABLE IF EXISTS incident_locks",
    "DROP TABLE IF EXISTS executions",
    "DROP TABLE IF EXISTS state_transitions",
    "DROP TABLE IF EXISTS evidence",
    "DROP TABLE IF EXISTS incidents",
    "DROP TYPE IF EXISTS execution_status",
    "DROP TYPE IF EXISTS severity_level",
    "DROP TYPE IF EXISTS incident_state",
]


def upgrade() -> None:
    for stmt in STATEMENTS:
        op.execute(stmt)


def downgrade() -> None:
    for stmt in DOWNGRADE_STATEMENTS:
        op.execute(stmt)
