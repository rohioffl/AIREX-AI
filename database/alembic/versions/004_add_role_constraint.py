"""Add role enum constraint to users table.

Revision ID: 004_add_role_constraint
Revises: 003_add_incident_host_key
Create Date: 2026-02-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004_add_role_constraint"
down_revision: Union[str, None] = "003_add_incident_host_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add CHECK constraint to enforce valid role values
    op.execute("""
        ALTER TABLE users
        ADD CONSTRAINT check_role_valid
        CHECK (role IN ('operator', 'admin', 'viewer'))
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS check_role_valid")
