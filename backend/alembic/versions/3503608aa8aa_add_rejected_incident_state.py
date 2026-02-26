"""add rejected incident state

Revision ID: 3503608aa8aa
Revises: 003_add_incident_host_key
Create Date: 2026-02-19 09:09:14.960857
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = "3503608aa8aa"
down_revision: Union[str, None] = "003_add_incident_host_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the new REJECTED state to the incident_state enum.
    #
    # Important: do not reference the new enum value in constraints here.
    # Postgres (via asyncpg) requires a commit between adding a new enum
    # label and using it in a CHECK constraint. The later migration
    # dbf34187c3db_remove_escalated_state rewrites the enum and updates
    # ck_incidents_soft_delete to include REJECTED in a separate
    # transaction-safe step.
    op.execute("ALTER TYPE incident_state ADD VALUE IF NOT EXISTS 'REJECTED'")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE incidents DROP CONSTRAINT IF EXISTS ck_incidents_soft_delete"
    )
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
                'FAILED_VERIFICATION'
            )
        )
        """
    )

    # Removing values from PostgreSQL enums is not supported without
    # recreating the type, so we intentionally do not attempt to drop
    # the REJECTED value on downgrade.
