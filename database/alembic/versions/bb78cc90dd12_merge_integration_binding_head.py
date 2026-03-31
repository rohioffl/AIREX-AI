"""Merge integration binding migration with current head.

Revision ID: bb78cc90dd12
Revises: aa12bb34cc56, b3c4d5e6f7a8
Create Date: 2026-03-31
"""

from typing import Sequence, Union


revision: str = "bb78cc90dd12"
down_revision: Union[str, Sequence[str], None] = ("aa12bb34cc56", "b3c4d5e6f7a8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
