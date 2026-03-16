"""merge_current_heads

Revision ID: d5e7f9a1c3b2
Revises: 009_add_totp_mfa, 010_add_tenants_table, b1c2d3e4f5a6
Create Date: 2026-03-16 07:30:00.000000

Unifies the current schema branches so `alembic upgrade head` is
deterministic again after the tenant-management migration landed.
"""

from typing import Sequence, Union


revision: str = "d5e7f9a1c3b2"
down_revision: Union[str, Sequence[str], None] = (
    "009_add_totp_mfa",
    "010_add_tenants_table",
    "b1c2d3e4f5a6",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
