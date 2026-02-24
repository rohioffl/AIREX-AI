"""remove escalated state

Revision ID: dbf34187c3db
Revises: 3503608aa8aa
Create Date: 2026-02-19 11:30:06.318528
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers
revision: str = "dbf34187c3db"
down_revision: Union[str, None] = "3503608aa8aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_STATES = (
    "RECEIVED",
    "INVESTIGATING",
    "RECOMMENDATION_READY",
    "AWAITING_APPROVAL",
    "EXECUTING",
    "VERIFYING",
    "RESOLVED",
    "FAILED_ANALYSIS",
    "FAILED_EXECUTION",
    "FAILED_VERIFICATION",
    "REJECTED",
)

OLD_STATES = NEW_STATES + ("ESCALATED",)


def upgrade() -> None:
    op.execute(
        "UPDATE state_transitions SET from_state='REJECTED' WHERE from_state='ESCALATED'"
    )
    op.execute(
        "UPDATE state_transitions SET to_state='REJECTED' WHERE to_state='ESCALATED'"
    )
    op.execute("UPDATE incidents SET state='REJECTED' WHERE state='ESCALATED'")

    op.execute("DROP INDEX IF EXISTS idx_incidents_tenant_state")
    op.execute("DROP INDEX IF EXISTS idx_incidents_active")
    op.execute("DROP INDEX IF EXISTS idx_incidents_awaiting_approval")
    op.execute(
        "ALTER TABLE incidents DROP CONSTRAINT IF EXISTS ck_incidents_soft_delete"
    )
    op.execute("ALTER TABLE incidents ALTER COLUMN state DROP DEFAULT")
    op.execute("ALTER TYPE incident_state RENAME TO incident_state_old")
    op.execute(
        "CREATE TYPE incident_state AS ENUM ("
        + ", ".join(f"'{state}'" for state in NEW_STATES)
        + ")"
    )

    op.execute(
        "ALTER TABLE incidents ALTER COLUMN state TYPE incident_state USING state::text::incident_state"
    )
    op.execute(
        "ALTER TABLE state_transitions ALTER COLUMN from_state TYPE incident_state USING from_state::text::incident_state"
    )
    op.execute(
        "ALTER TABLE state_transitions ALTER COLUMN to_state TYPE incident_state USING to_state::text::incident_state"
    )

    op.execute("DROP TYPE incident_state_old")
    op.execute("ALTER TABLE incidents ALTER COLUMN state SET DEFAULT 'RECEIVED'")

    op.execute(
        """
        ALTER TABLE incidents
        ADD CONSTRAINT ck_incidents_soft_delete
        CHECK (
            deleted_at IS NULL
            OR state IN (
                'RESOLVED',
                'FAILED_EXECUTION',
                'FAILED_VERIFICATION',
                'REJECTED'
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_incidents_tenant_state ON incidents (tenant_id, state)"
    )
    op.execute(
        "CREATE INDEX idx_incidents_active ON incidents (tenant_id, created_at DESC) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX idx_incidents_awaiting_approval ON incidents (tenant_id, created_at DESC) WHERE state = 'AWAITING_APPROVAL' AND deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_incidents_tenant_state")
    op.execute("DROP INDEX IF EXISTS idx_incidents_active")
    op.execute("DROP INDEX IF EXISTS idx_incidents_awaiting_approval")
    op.execute(
        "ALTER TABLE incidents DROP CONSTRAINT IF EXISTS ck_incidents_soft_delete"
    )
    op.execute("ALTER TABLE incidents ALTER COLUMN state DROP DEFAULT")
    op.execute("ALTER TYPE incident_state RENAME TO incident_state_old")
    op.execute(
        "CREATE TYPE incident_state AS ENUM ("
        + ", ".join(f"'{state}'" for state in OLD_STATES)
        + ")"
    )

    op.execute(
        "ALTER TABLE incidents ALTER COLUMN state TYPE incident_state USING state::text::incident_state"
    )
    op.execute(
        "ALTER TABLE state_transitions ALTER COLUMN from_state TYPE incident_state USING from_state::text::incident_state"
    )
    op.execute(
        "ALTER TABLE state_transitions ALTER COLUMN to_state TYPE incident_state USING to_state::text::incident_state"
    )

    op.execute("DROP TYPE incident_state_old")
    op.execute("ALTER TABLE incidents ALTER COLUMN state SET DEFAULT 'RECEIVED'")

    op.execute(
        """
        ALTER TABLE incidents
        ADD CONSTRAINT ck_incidents_soft_delete
        CHECK (
            deleted_at IS NULL
            OR state IN (
                'RESOLVED',
                'ESCALATED',
                'FAILED_EXECUTION',
                'FAILED_VERIFICATION',
                'REJECTED'
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_incidents_tenant_state ON incidents (tenant_id, state)"
    )
    op.execute(
        "CREATE INDEX idx_incidents_active ON incidents (tenant_id, created_at DESC) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX idx_incidents_awaiting_approval ON incidents (tenant_id, created_at DESC) WHERE state = 'AWAITING_APPROVAL' AND deleted_at IS NULL"
    )
