"""Add optional cloud_account_binding_id to monitoring integrations.

Revision ID: aa12bb34cc56
Revises: d5e7f9a1c3b2
Create Date: 2026-03-31
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "aa12bb34cc56"
down_revision: Union[str, Sequence[str], None] = "d5e7f9a1c3b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "monitoring_integrations",
        sa.Column(
            "cloud_account_binding_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_monitoring_integrations_cloud_account_binding_id",
        "monitoring_integrations",
        ["cloud_account_binding_id"],
    )
    op.create_foreign_key(
        "fk_monitoring_integrations_cloud_account_binding_id",
        "monitoring_integrations",
        "cloud_account_bindings",
        ["cloud_account_binding_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Backfill existing integrations to the tenant's default cloud account binding
    # when one exists so current data remains associated to a concrete account.
    op.execute(
        """
        UPDATE monitoring_integrations mi
        SET cloud_account_binding_id = cab.id,
            updated_at = CURRENT_TIMESTAMP
        FROM cloud_account_bindings cab
        WHERE cab.tenant_id = mi.tenant_id
          AND cab.is_default = true
          AND mi.cloud_account_binding_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_monitoring_integrations_cloud_account_binding_id",
        "monitoring_integrations",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_monitoring_integrations_cloud_account_binding_id",
        table_name="monitoring_integrations",
    )
    op.drop_column("monitoring_integrations", "cloud_account_binding_id")
