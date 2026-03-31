"""Scope monitoring integration slug uniqueness to tenant account binding.

Revision ID: cc44dd55ee66
Revises: bb78cc90dd12
Create Date: 2026-03-31 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "cc44dd55ee66"
down_revision = "bb78cc90dd12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_monitoring_integrations_tenant_slug",
        "monitoring_integrations",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_monitoring_integrations_tenant_account_slug",
        "monitoring_integrations",
        ["tenant_id", "cloud_account_binding_id", "slug"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_monitoring_integrations_tenant_account_slug",
        "monitoring_integrations",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_monitoring_integrations_tenant_slug",
        "monitoring_integrations",
        ["tenant_id", "slug"],
    )
