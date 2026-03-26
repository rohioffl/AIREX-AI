"""merge_all_heads

Merges all current schema heads into a single head so that
`alembic upgrade head` is deterministic.

Revision ID: c1d2e3f4a5b6
Revises: 009_add_knowledge_graph_tables, 9a2b3c4d5e6f, b2c3d4e5f6a1, f1a2b3c4d5e6
Create Date: 2026-03-26 10:00:00.000000
"""

from typing import Sequence, Union


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = (
    "009_add_knowledge_graph_tables",
    "9a2b3c4d5e6f",
    "b2c3d4e5f6a1",
    "f1a2b3c4d5e6",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
