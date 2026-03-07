"""Add correlation_group_id for cross-host incident grouping (Phase 4 ARE).

Revision ID: 007_add_correlation_group
Revises: 006_add_resolution_tracking
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa

revision = "007_add_correlation_group"
down_revision = "006_add_resolution_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("correlation_group_id", sa.String(64), nullable=True),
    )
    # Index for fast group lookups
    op.create_index(
        "idx_incidents_correlation_group",
        "incidents",
        ["tenant_id", "correlation_group_id"],
        postgresql_where=sa.text("correlation_group_id IS NOT NULL AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_incidents_correlation_group", table_name="incidents")
    op.drop_column("incidents", "correlation_group_id")
