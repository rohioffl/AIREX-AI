"""Add Knowledge Graph tables (kg_nodes, kg_edges) — Phase 4 ARE.

Revision ID: 009_add_knowledge_graph_tables
Revises: fcd9217e5222
Create Date: 2026-03-19
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "009_add_knowledge_graph_tables"
down_revision: Union[str, None] = "fcd9217e5222"
branch_labels = None
depends_on = None

EMBEDDING_DIM = 1024


def upgrade() -> None:
    # ── kg_nodes ──────────────────────────────────────────────────
    op.create_table(
        "kg_nodes",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column(
            "last_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("tenant_id", "id"),
        sa.UniqueConstraint("tenant_id", "entity_id", name="uq_kg_node_entity"),
    )
    op.create_index("idx_kg_nodes_tenant_entity", "kg_nodes", ["tenant_id", "entity_id"])
    op.create_index("idx_kg_nodes_tenant_type", "kg_nodes", ["tenant_id", "entity_type"])

    # ── kg_edges ──────────────────────────────────────────────────
    op.create_table(
        "kg_edges",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("src_entity_id", sa.String(), nullable=False),
        sa.Column("relation", sa.String(), nullable=False),
        sa.Column("dst_entity_id", sa.String(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("tenant_id", "id"),
        sa.UniqueConstraint(
            "tenant_id",
            "src_entity_id",
            "relation",
            "dst_entity_id",
            name="uq_kg_edge_triple",
        ),
    )
    op.create_index("idx_kg_edges_tenant_src", "kg_edges", ["tenant_id", "src_entity_id"])
    op.create_index("idx_kg_edges_tenant_dst", "kg_edges", ["tenant_id", "dst_entity_id"])
    op.create_index("idx_kg_edges_relation", "kg_edges", ["tenant_id", "relation"])


def downgrade() -> None:
    op.drop_index("idx_kg_edges_relation", table_name="kg_edges")
    op.drop_index("idx_kg_edges_tenant_dst", table_name="kg_edges")
    op.drop_index("idx_kg_edges_tenant_src", table_name="kg_edges")
    op.drop_table("kg_edges")

    op.drop_index("idx_kg_nodes_tenant_type", table_name="kg_nodes")
    op.drop_index("idx_kg_nodes_tenant_entity", table_name="kg_nodes")
    op.drop_table("kg_nodes")
