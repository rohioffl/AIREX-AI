"""Add host_key to incidents for linking related incidents (same server).

Revision ID: 003_add_incident_host_key
Revises: 002_add_users_table
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_add_incident_host_key"
down_revision: Union[str, None] = "002_add_users_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("host_key", sa.String(512), nullable=True),
    )
    op.create_index(
        "idx_incidents_host_key",
        "incidents",
        ["tenant_id", "host_key"],
        postgresql_where=sa.text("host_key IS NOT NULL AND host_key != ''"),
    )


def downgrade() -> None:
    op.drop_index("idx_incidents_host_key", table_name="incidents")
    op.drop_column("incidents", "host_key")
