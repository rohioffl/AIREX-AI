"""resize_vector_columns_3072_to_1024

Revision ID: e964260b273c
Revises: e24dbe500578
Create Date: 2026-02-26 08:46:35.096051
"""

from typing import Sequence, Union

from alembic import op
from pgvector.sqlalchemy import Vector


# revision identifiers
revision: str = "e964260b273c"
down_revision: Union[str, None] = "e24dbe500578"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Resize vector columns from 3072 (OpenAI text-embedding-3-large)
    # to 1024 (Amazon Titan Text Embeddings v2 max).
    # Both tables are empty so no data loss.
    op.alter_column(
        "runbook_chunks",
        "embedding",
        existing_type=Vector(3072),
        type_=Vector(1024),
        existing_nullable=False,
    )
    op.alter_column(
        "incident_embeddings",
        "embedding",
        existing_type=Vector(3072),
        type_=Vector(1024),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "runbook_chunks",
        "embedding",
        existing_type=Vector(1024),
        type_=Vector(3072),
        existing_nullable=False,
    )
    op.alter_column(
        "incident_embeddings",
        "embedding",
        existing_type=Vector(1024),
        type_=Vector(3072),
        existing_nullable=False,
    )
