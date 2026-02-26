"""merge_user_timestamps_and_rag_tables

Revision ID: e24dbe500578
Revises: 005_add_user_timestamps, 4a1c0a3f4c2f
Create Date: 2026-02-24 10:58:50.618976
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'e24dbe500578'
down_revision: Union[str, None] = ('005_add_user_timestamps', '4a1c0a3f4c2f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
