"""Add cloud_account_bindings table.

Implements §7.1 of the Tenant Credentials AWS Secrets Manager plan.

Creates a first-class ``cloud_account_bindings`` table (tenant → cloud account
is 1:N) and backfills one default binding per active tenant from the existing
``aws_config`` / ``gcp_config`` JSONB columns.

Inline secrets (access_key_id, secret_access_key, service_account_key) are
intentionally **not** copied to the new table.  Operators must migrate those
to AWS Secrets Manager and set ``credentials_secret_arn`` on the binding row.

Merges heads: c1d2e3f4a5b6 (merge_all_heads) and a1b2c3d4e5f6 (saas_multi_org).

Revision ID: b0c1d2e3f4a5
Revises: c1d2e3f4a5b6, a1b2c3d4e5f6
Create Date: 2026-03-27
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = ("c1d2e3f4a5b6", "a1b2c3d4e5f6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── cloud_account_bindings ────────────────────────────────────────────────
    op.create_table(
        "cloud_account_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False, server_default=""),
        sa.Column(
            "external_account_id", sa.String(64), nullable=False, server_default=""
        ),
        sa.Column(
            "config_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("credentials_secret_arn", sa.Text(), nullable=True),
        sa.Column(
            "is_default", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "provider",
            "external_account_id",
            name="uq_cloud_account_binding",
        ),
    )
    op.create_index(
        "ix_cloud_account_bindings_tenant_id",
        "cloud_account_bindings",
        ["tenant_id"],
    )

    # ── Row-Level Security ────────────────────────────────────────────────────
    op.execute("ALTER TABLE cloud_account_bindings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE cloud_account_bindings FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY cloud_account_bindings_tenant_isolation
            ON cloud_account_bindings
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )

    # ── Backfill: one default binding per active tenant ───────────────────────
    # Extract non-secret metadata only from aws_config / gcp_config JSONB.
    # Inline credentials (access_key_id, secret_access_key, service_account_key)
    # are intentionally excluded — migrate those to Secrets Manager manually.
    op.execute(
        """
        INSERT INTO cloud_account_bindings
            (id, tenant_id, provider, display_name, external_account_id,
             config_json, is_default)
        SELECT
            gen_random_uuid(),
            t.id,
            COALESCE(t.cloud, 'aws'),
            COALESCE(t.display_name, t.name, ''),
            CASE
                WHEN COALESCE(t.cloud, 'aws') = 'aws'
                    THEN COALESCE(t.aws_config->>'account_id', '')
                ELSE COALESCE(t.gcp_config->>'project_id', '')
            END,
            CASE
                WHEN COALESCE(t.cloud, 'aws') = 'aws' THEN
                    jsonb_strip_nulls(jsonb_build_object(
                        'region',           NULLIF(COALESCE(t.aws_config->>'region', ''), ''),
                        'role_arn',         NULLIF(COALESCE(t.aws_config->>'role_arn', ''), ''),
                        'role_name',        NULLIF(COALESCE(t.aws_config->>'role_name', ''), ''),
                        'account_id',       NULLIF(COALESCE(t.aws_config->>'account_id', ''), ''),
                        'external_id',      NULLIF(COALESCE(t.aws_config->>'external_id', ''), ''),
                        'ssm_document',     COALESCE(t.aws_config->>'ssm_document', 'AWS-RunShellScript'),
                        'ssm_timeout',      COALESCE((t.aws_config->>'ssm_timeout')::int, 30),
                        'log_group_prefix', NULLIF(COALESCE(t.aws_config->>'log_group_prefix', ''), '')
                    ))
                ELSE
                    jsonb_strip_nulls(jsonb_build_object(
                        'project_id',           NULLIF(COALESCE(t.gcp_config->>'project_id', ''), ''),
                        'zone',                 NULLIF(COALESCE(t.gcp_config->>'zone', ''), ''),
                        'os_login_user',        NULLIF(COALESCE(t.gcp_config->>'os_login_user', ''), ''),
                        'log_explorer_enabled', COALESCE(
                            (t.gcp_config->>'log_explorer_enabled')::boolean, true
                        )
                    ))
            END,
            true  -- is_default
        FROM tenants t
        WHERE t.is_active = true
          AND (t.aws_config IS NOT NULL OR t.gcp_config IS NOT NULL)
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS cloud_account_bindings_tenant_isolation "
        "ON cloud_account_bindings"
    )
    op.drop_index(
        "ix_cloud_account_bindings_tenant_id",
        table_name="cloud_account_bindings",
    )
    op.drop_table("cloud_account_bindings")
