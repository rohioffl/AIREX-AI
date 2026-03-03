"""Add health_checks table for proactive monitoring (Phase 6 ARE).

Stores periodic health check results against known infrastructure
(Site24x7 monitors, cloud instances). Threshold violations auto-create
incidents through the existing pipeline.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID, TIMESTAMP

revision = "008_add_health_checks"
down_revision = "007_add_correlation_group"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "health_checks",
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_id", sa.String(255), nullable=False),
        sa.Column("target_name", sa.String(500), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("metrics", JSONB, nullable=True),
        sa.Column("anomalies", JSONB, nullable=True),
        sa.Column("incident_created", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("incident_id", UUID(as_uuid=True), nullable=True),
        sa.Column("checked_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Float, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.PrimaryKeyConstraint("tenant_id", "id"),
    )
    # Index for listing latest checks per tenant
    op.create_index(
        "idx_health_checks_tenant_checked",
        "health_checks",
        ["tenant_id", sa.text("checked_at DESC")],
    )
    # Index for looking up checks by target
    op.create_index(
        "idx_health_checks_target",
        "health_checks",
        ["tenant_id", "target_type", "target_id"],
    )
    # Partial index for anomalous checks only
    op.create_index(
        "idx_health_checks_anomalous",
        "health_checks",
        ["tenant_id", sa.text("checked_at DESC")],
        postgresql_where=sa.text("status IN ('degraded', 'down')"),
    )


def downgrade() -> None:
    op.drop_index("idx_health_checks_anomalous")
    op.drop_index("idx_health_checks_target")
    op.drop_index("idx_health_checks_tenant_checked")
    op.drop_table("health_checks")
