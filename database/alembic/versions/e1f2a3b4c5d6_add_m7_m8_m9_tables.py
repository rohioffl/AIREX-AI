"""add m7 m8 m9 tables: notification_delivery_log, webhook_events, runbook_versions,
runbook_executions, runbook_step_executions

Revision ID: e1f2a3b4c5d6
Revises: a1b2c3d4e5f6, fcd9217e5222
Create Date: 2026-03-17 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: tuple[str, str] = ("a1b2c3d4e5f6", "fcd9217e5222")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── notification_delivery_log ─────────────────────────────────────────────
    op.create_table(
        "notification_delivery_log",
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("incident_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("state_transition", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.String(1024), nullable=True),
        sa.Column(
            "delivered_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("tenant_id", "id"),
    )
    op.create_index(
        "ix_notification_delivery_log_tenant_user",
        "notification_delivery_log",
        ["tenant_id", "user_id", "delivered_at"],
    )
    op.execute(
        "ALTER TABLE notification_delivery_log ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE notification_delivery_log FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_notification_delivery_log
        ON notification_delivery_log
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )

    # ── webhook_events ────────────────────────────────────────────────────────
    op.create_table(
        "webhook_events",
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("integration_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=True),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column("headers", JSONB, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="received"),
        sa.Column("incident_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("dedup_key", sa.String(255), nullable=True),
        sa.Column("is_replay", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("original_event_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "received_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("tenant_id", "id"),
    )
    op.create_index(
        "ix_webhook_events_tenant_integration_received",
        "webhook_events",
        ["tenant_id", "integration_id", sa.text("received_at DESC")],
    )
    op.execute("ALTER TABLE webhook_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE webhook_events FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_webhook_events
        ON webhook_events
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )

    # ── runbook_versions ──────────────────────────────────────────────────────
    op.create_table(
        "runbook_versions",
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("runbook_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("steps", JSONB, nullable=True),
        sa.Column("updated_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("tenant_id", "id"),
    )
    op.create_index(
        "ix_runbook_versions_tenant_runbook",
        "runbook_versions",
        ["tenant_id", "runbook_id", "version"],
    )
    op.execute("ALTER TABLE runbook_versions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE runbook_versions FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_runbook_versions
        ON runbook_versions
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )

    # ── runbook_executions ────────────────────────────────────────────────────
    op.create_table(
        "runbook_executions",
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("runbook_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("runbook_version", sa.Integer, nullable=False),
        sa.Column("runbook_steps_snapshot", JSONB, nullable=True),
        sa.Column("incident_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("started_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("tenant_id", "id"),
    )
    op.create_index(
        "ix_runbook_executions_tenant_incident",
        "runbook_executions",
        ["tenant_id", "incident_id", "status"],
    )
    op.execute("ALTER TABLE runbook_executions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE runbook_executions FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_runbook_executions
        ON runbook_executions
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )

    # ── runbook_step_executions ───────────────────────────────────────────────
    op.create_table(
        "runbook_step_executions",
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("execution_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_order", sa.Integer, nullable=False),
        sa.Column("step_title", sa.String(255), nullable=True),
        sa.Column("step_action_type", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("actor_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.String(2048), nullable=True),
        sa.Column("output", JSONB, nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("tenant_id", "id"),
    )
    op.create_index(
        "ix_runbook_step_executions_tenant_execution",
        "runbook_step_executions",
        ["tenant_id", "execution_id", "step_order"],
    )
    op.execute("ALTER TABLE runbook_step_executions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE runbook_step_executions FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_runbook_step_executions
        ON runbook_step_executions
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_runbook_step_executions ON runbook_step_executions")
    op.drop_table("runbook_step_executions")

    op.execute("DROP POLICY IF EXISTS tenant_isolation_runbook_executions ON runbook_executions")
    op.drop_table("runbook_executions")

    op.execute("DROP POLICY IF EXISTS tenant_isolation_runbook_versions ON runbook_versions")
    op.drop_table("runbook_versions")

    op.execute("DROP POLICY IF EXISTS tenant_isolation_webhook_events ON webhook_events")
    op.drop_table("webhook_events")

    op.execute("DROP POLICY IF EXISTS tenant_isolation_notification_delivery_log ON notification_delivery_log")
    op.drop_table("notification_delivery_log")
