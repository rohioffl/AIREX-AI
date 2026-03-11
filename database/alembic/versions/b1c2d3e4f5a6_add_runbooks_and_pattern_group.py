"""Add runbooks table and pattern_group_id to incidents

Revision ID: b1c2d3e4f5a6
Revises: 84b579817c2c
Create Date: 2026-03-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP

revision = "b1c2d3e4f5a6"
down_revision = "84b579817c2c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add pattern_group_id to incidents
    op.add_column(
        "incidents",
        sa.Column("pattern_group_id", sa.String(64), nullable=True),
    )
    op.create_index(
        "idx_incidents_pattern_group",
        "incidents",
        ["tenant_id", "pattern_group_id"],
        postgresql_where=sa.text("pattern_group_id IS NOT NULL"),
    )

    # Create runbooks table
    op.create_table(
        "runbooks",
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("alert_type", sa.String(255), nullable=False),
        sa.Column("severity", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("steps", JSONB(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("tags", JSONB(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("tenant_id", "id"),
    )
    op.create_index(
        "idx_runbooks_alert_type",
        "runbooks",
        ["tenant_id", "alert_type"],
    )
    op.create_index(
        "idx_runbooks_active",
        "runbooks",
        ["tenant_id"],
        postgresql_where=sa.text("is_active = true"),
    )

    # RLS policies for runbooks
    op.execute(
        "ALTER TABLE runbooks ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "CREATE POLICY tenant_isolation_runbooks ON runbooks "
        "USING (tenant_id = current_setting('app.current_tenant_id')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_runbooks ON runbooks")
    op.execute("ALTER TABLE runbooks DISABLE ROW LEVEL SECURITY")
    op.drop_index("idx_runbooks_active", table_name="runbooks")
    op.drop_index("idx_runbooks_alert_type", table_name="runbooks")
    op.drop_table("runbooks")
    op.drop_index("idx_incidents_pattern_group", table_name="incidents")
    op.drop_column("incidents", "pattern_group_id")
