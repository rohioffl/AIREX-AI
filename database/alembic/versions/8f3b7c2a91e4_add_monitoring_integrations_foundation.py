"""add_monitoring_integrations_foundation

Revision ID: 8f3b7c2a91e4
Revises: 7c1a9d9f4b10
Create Date: 2026-03-16 13:10:00.000000

Adds the tenant-owned monitoring integration foundation:
- integration_types
- monitoring_integrations
- external_monitors
- project_monitor_bindings
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "8f3b7c2a91e4"
down_revision: Union[str, None] = "7c1a9d9f4b10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "integration_types",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False, server_default="monitoring"),
        sa.Column("supports_webhook", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("supports_polling", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("supports_sync", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("config_schema_json", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.dialects.postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.dialects.postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("key", name="uq_integration_types_key"),
    )
    op.create_index("ix_integration_types_key", "integration_types", ["key"], unique=True)

    bind = op.get_bind()
    seed_rows = [
        {"key": "site24x7", "display_name": "Site24x7", "supports_webhook": True, "supports_sync": True},
        {"key": "prometheus", "display_name": "Prometheus", "supports_webhook": False, "supports_sync": False},
        {"key": "datadog", "display_name": "Datadog", "supports_webhook": True, "supports_sync": True},
        {"key": "cloudwatch", "display_name": "CloudWatch", "supports_webhook": False, "supports_sync": False},
    ]
    for row in seed_rows:
        bind.execute(
            sa.text(
                """
                INSERT INTO integration_types (
                    id, key, display_name, category, supports_webhook,
                    supports_polling, supports_sync, enabled, config_schema_json
                )
                VALUES (
                    gen_random_uuid(), :key, :display_name, 'monitoring', :supports_webhook,
                    false, :supports_sync, true, '{}'::jsonb
                )
                ON CONFLICT (key) DO NOTHING
                """
            ),
            row,
        )

    op.create_table(
        "monitoring_integrations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("integration_type_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("config_json", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("secret_ref", sa.String(length=255), nullable=True),
        sa.Column("webhook_token_ref", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="configured"),
        sa.Column("last_tested_at", sa.dialects.postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.dialects.postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.dialects.postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.dialects.postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["integration_type_id"], ["integration_types.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_monitoring_integrations_tenant_slug"),
    )
    op.create_index("ix_monitoring_integrations_tenant_id", "monitoring_integrations", ["tenant_id"])
    op.create_index("ix_monitoring_integrations_integration_type_id", "monitoring_integrations", ["integration_type_id"])

    op.create_table(
        "external_monitors",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("integration_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_monitor_id", sa.String(length=255), nullable=False),
        sa.Column("external_name", sa.String(length=255), nullable=False),
        sa.Column("monitor_type", sa.String(length=64), nullable=False, server_default="generic"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("metadata_json", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_seen_at", sa.dialects.postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.dialects.postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.dialects.postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["integration_id"], ["monitoring_integrations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("integration_id", "external_monitor_id", name="uq_external_monitors_integration_external_id"),
    )
    op.create_index("ix_external_monitors_integration_id", "external_monitors", ["integration_id"])

    op.create_table(
        "project_monitor_bindings",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_monitor_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("alert_type_override", sa.String(length=64), nullable=True),
        sa.Column("resource_mapping_json", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("routing_tags_json", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.dialects.postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.dialects.postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["external_monitor_id"], ["external_monitors.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "external_monitor_id", name="uq_project_monitor_bindings_project_monitor"),
    )
    op.create_index("ix_project_monitor_bindings_project_id", "project_monitor_bindings", ["project_id"])
    op.create_index("ix_project_monitor_bindings_external_monitor_id", "project_monitor_bindings", ["external_monitor_id"])


def downgrade() -> None:
    op.drop_index("ix_project_monitor_bindings_external_monitor_id", table_name="project_monitor_bindings")
    op.drop_index("ix_project_monitor_bindings_project_id", table_name="project_monitor_bindings")
    op.drop_table("project_monitor_bindings")

    op.drop_index("ix_external_monitors_integration_id", table_name="external_monitors")
    op.drop_table("external_monitors")

    op.drop_index("ix_monitoring_integrations_integration_type_id", table_name="monitoring_integrations")
    op.drop_index("ix_monitoring_integrations_tenant_id", table_name="monitoring_integrations")
    op.drop_table("monitoring_integrations")

    op.drop_index("ix_integration_types_key", table_name="integration_types")
    op.drop_table("integration_types")
