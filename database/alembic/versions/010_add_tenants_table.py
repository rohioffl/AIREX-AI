"""add_tenants_table

Revision ID: 010_add_tenants_table
Revises: fcd9217e5222
Create Date: 2026-03-16 06:44:00.000000

Creates a global (non-RLS) ``tenants`` table and seeds it from the
existing ``config/tenants.yaml`` file so that current tenants are
preserved as DB records.
"""

import os
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "010_add_tenants_table"
down_revision: Union[str, None] = "fcd9217e5222"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Create tenants table (global, NOT RLS-scoped) ────────────
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("cloud", sa.String(10), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default="true"
        ),
        # Contacts
        sa.Column(
            "escalation_email", sa.String(320), nullable=False, server_default=""
        ),
        sa.Column(
            "slack_channel", sa.String(100), nullable=False, server_default=""
        ),
        # SSH
        sa.Column(
            "ssh_user", sa.String(100), nullable=False, server_default="ubuntu"
        ),
        # Cloud config (JSONB)
        sa.Column(
            "aws_config",
            sa.dialects.postgresql.JSONB,
            nullable=True,
            server_default="{}",
        ),
        sa.Column(
            "gcp_config",
            sa.dialects.postgresql.JSONB,
            nullable=True,
            server_default="{}",
        ),
        # Server overrides
        sa.Column(
            "servers",
            sa.dialects.postgresql.JSONB,
            nullable=True,
            server_default="[]",
        ),
        # Timestamps
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
    )

    op.create_index("idx_tenants_name", "tenants", ["name"], unique=True)
    op.create_index("idx_tenants_active", "tenants", ["is_active"])

    # ── Seed from tenants.yaml ───────────────────────────────────
    _seed_from_yaml()


def _seed_from_yaml() -> None:
    """Read tenants.yaml and INSERT each tenant into the new table."""
    try:
        import yaml
    except ImportError:
        # yaml not available in migration context — skip seeding
        return

    # Try common locations relative to the alembic directory
    yaml_paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "services", "airex-core", "config", "tenants.yaml"),
        "/home/ubuntu/AIREX-AI/AIREX-AI/services/airex-core/config/tenants.yaml",
    ]

    raw = None
    for p in yaml_paths:
        resolved = os.path.abspath(p)
        if os.path.isfile(resolved):
            with open(resolved) as f:
                raw = yaml.safe_load(f)
            break

    if not raw or "tenants" not in raw:
        return

    connection = op.get_bind()
    tenants_data = raw["tenants"]

    for name, cfg in tenants_data.items():
        cloud = cfg.get("cloud", "aws")

        aws_config = {}
        if "aws" in cfg and isinstance(cfg["aws"], dict):
            aws_config = {
                "region": cfg["aws"].get("region", ""),
                "account_id": cfg["aws"].get("account_id", ""),
                "role_name": cfg["aws"].get("role_name", ""),
                "role_arn": cfg["aws"].get("role_arn", ""),
                "external_id": cfg["aws"].get("external_id", ""),
                "access_key_id": cfg["aws"].get("access_key_id", ""),
                "secret_access_key": cfg["aws"].get("secret_access_key", ""),
                "credentials_file": cfg["aws"].get("credentials_file", ""),
                "profile": cfg["aws"].get("profile", ""),
                "ssm_document": cfg["aws"].get("ssm_document", "AWS-RunShellScript"),
                "ssm_timeout": cfg["aws"].get("ssm_timeout", 30),
                "log_group_prefix": cfg["aws"].get("log_group_prefix", ""),
            }

        gcp_config = {}
        if "gcp" in cfg and isinstance(cfg["gcp"], dict):
            gcp_config = {
                "project_id": cfg["gcp"].get("project_id", ""),
                "service_account_key": cfg["gcp"].get("service_account_key", ""),
                "zone": cfg["gcp"].get("zone", ""),
                "os_login_user": cfg["gcp"].get("os_login_user", ""),
                "log_explorer_enabled": cfg["gcp"].get("log_explorer_enabled", True),
            }

        servers = []
        if "servers" in cfg and isinstance(cfg["servers"], dict):
            for srv_name, srv_cfg in cfg["servers"].items():
                srv = {"name": srv_name}
                if isinstance(srv_cfg, dict):
                    srv.update(srv_cfg)
                servers.append(srv)

        import json

        connection.execute(
            sa.text(
                """
                INSERT INTO tenants (id, name, display_name, cloud, escalation_email,
                                     slack_channel, ssh_user, aws_config, gcp_config, servers)
                VALUES (:id, :name, :display_name, :cloud, :escalation_email,
                        :slack_channel, :ssh_user,
                        CAST(:aws_config AS jsonb),
                        CAST(:gcp_config AS jsonb),
                        CAST(:servers AS jsonb))
                ON CONFLICT (name) DO NOTHING
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "name": name.lower(),
                "display_name": cfg.get("display_name", name),
                "cloud": cloud,
                "escalation_email": cfg.get("escalation_email", ""),
                "slack_channel": cfg.get("slack_channel", ""),
                "ssh_user": cfg.get("ssh_user", raw.get("defaults", {}).get("ssh_user", "ubuntu")),
                "aws_config": json.dumps(aws_config),
                "gcp_config": json.dumps(gcp_config),
                "servers": json.dumps(servers),
            },
        )


def downgrade() -> None:
    op.drop_index("idx_tenants_active", table_name="tenants")
    op.drop_index("idx_tenants_name", table_name="tenants")
    op.drop_table("tenants")
