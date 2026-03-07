"""add RAG vector tables

Revision ID: 4a1c0a3f4c2f
Revises: dbf34187c3db
Create Date: 2026-02-24 10:15:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = "4a1c0a3f4c2f"
down_revision: Union[str, None] = "dbf34187c3db"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


EMBEDDING_DIMENSION = 3072


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "runbook_chunks",
        sa.Column(
            "tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source_type", sa.String(length=128), nullable=False),
        sa.Column(
            "source_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("meta", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSION), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("tenant_id", "id"),
        sa.UniqueConstraint(
            "tenant_id",
            "source_type",
            "source_id",
            "chunk_index",
            name="uq_runbook_chunk_source",
        ),
        sa.CheckConstraint(
            "chunk_index >= 0", name="ck_runbook_chunk_index_non_negative"
        ),
    )
    op.create_index(
        "idx_runbook_chunks_tenant_source",
        "runbook_chunks",
        ["tenant_id", "source_type", "source_id"],
    )

    op.create_table(
        "incident_embeddings",
        sa.Column(
            "tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "incident_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSION), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("tenant_id", "id"),
        sa.UniqueConstraint(
            "tenant_id", "incident_id", name="uq_incident_embedding_incident"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "incident_id"],
            ["incidents.tenant_id", "incidents.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "idx_incident_embeddings_incident_fk",
        "incident_embeddings",
        ["tenant_id", "incident_id"],
    )

    # RLS policies
    op.execute("ALTER TABLE runbook_chunks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE runbook_chunks FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_runbook_chunks ON runbook_chunks "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )

    op.execute("ALTER TABLE incident_embeddings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE incident_embeddings FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_incident_embeddings ON incident_embeddings "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_incident_embeddings ON incident_embeddings"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_runbook_chunks ON runbook_chunks"
    )
    op.execute("ALTER TABLE incident_embeddings DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE runbook_chunks DISABLE ROW LEVEL SECURITY")

    op.drop_index(
        "idx_incident_embeddings_incident_fk", table_name="incident_embeddings"
    )
    op.drop_table("incident_embeddings")

    op.drop_index("idx_runbook_chunks_tenant_source", table_name="runbook_chunks")
    op.drop_table("runbook_chunks")

    op.execute("DROP EXTENSION IF EXISTS vector")
