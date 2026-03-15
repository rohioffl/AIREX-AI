"""Add TOTP/MFA fields to users table.

Revision ID: 009_add_totp_mfa
Revises: 008_add_health_checks
Create Date: 2026-03-15

Schema changes only — no data backfill required.
New columns are nullable / default=False so existing rows are unaffected.
"""

from alembic import op
import sqlalchemy as sa

revision = "009_add_totp_mfa"
down_revision = "008_add_health_checks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("totp_secret_enc", sa.String(512), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "totp_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "totp_enabled")
    op.drop_column("users", "totp_secret_enc")
