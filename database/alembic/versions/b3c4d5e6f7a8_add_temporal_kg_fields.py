"""Add temporal fields to Knowledge Graph tables.

Revision ID: b3c4d5e6f7a8
Revises: b0c1d2e3f4a5
Create Date: 2026-03-27 12:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "b0c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _has_column(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_index(bind, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()

    if _has_table(bind, "kg_nodes"):
        if not _has_column(bind, "kg_nodes", "observed_at"):
            op.add_column(
                "kg_nodes",
                sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=True, server_default=sa.text("now()")),
            )
        if not _has_column(bind, "kg_nodes", "valid_from"):
            op.add_column(
                "kg_nodes",
                sa.Column("valid_from", sa.TIMESTAMP(timezone=True), nullable=True, server_default=sa.text("now()")),
            )
        if not _has_column(bind, "kg_nodes", "valid_to"):
            op.add_column("kg_nodes", sa.Column("valid_to", sa.TIMESTAMP(timezone=True), nullable=True))
        if not _has_column(bind, "kg_nodes", "state_hash"):
            op.add_column(
                "kg_nodes",
                sa.Column("state_hash", sa.String(), nullable=True, server_default="e3b0c44298fc1c14"),
            )
        op.execute("UPDATE kg_nodes SET observed_at = COALESCE(observed_at, last_seen_at, now())")
        op.execute("UPDATE kg_nodes SET valid_from = COALESCE(valid_from, observed_at, now())")
        op.execute("UPDATE kg_nodes SET state_hash = COALESCE(state_hash, 'e3b0c44298fc1c14')")
        op.alter_column("kg_nodes", "observed_at", nullable=False)
        op.alter_column("kg_nodes", "valid_from", nullable=False)
        op.alter_column("kg_nodes", "state_hash", nullable=False, server_default=None)
        if not _has_index(bind, "kg_nodes", "idx_kg_nodes_validity"):
            op.create_index(
                "idx_kg_nodes_validity",
                "kg_nodes",
                ["tenant_id", "entity_type", "valid_to", "last_seen_at"],
                unique=False,
            )

    if _has_table(bind, "kg_edges"):
        if not _has_column(bind, "kg_edges", "causal_confidence"):
            op.add_column(
                "kg_edges",
                sa.Column("causal_confidence", sa.Float(), nullable=True, server_default="0.5"),
            )
        if not _has_column(bind, "kg_edges", "observed_at"):
            op.add_column(
                "kg_edges",
                sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=True, server_default=sa.text("now()")),
            )
        if not _has_column(bind, "kg_edges", "valid_from"):
            op.add_column(
                "kg_edges",
                sa.Column("valid_from", sa.TIMESTAMP(timezone=True), nullable=True, server_default=sa.text("now()")),
            )
        if not _has_column(bind, "kg_edges", "valid_to"):
            op.add_column("kg_edges", sa.Column("valid_to", sa.TIMESTAMP(timezone=True), nullable=True))
        op.execute("UPDATE kg_edges SET causal_confidence = COALESCE(causal_confidence, 0.5)")
        op.execute("UPDATE kg_edges SET observed_at = COALESCE(observed_at, updated_at, now())")
        op.execute("UPDATE kg_edges SET valid_from = COALESCE(valid_from, observed_at, now())")
        op.alter_column("kg_edges", "causal_confidence", nullable=False, server_default=None)
        op.alter_column("kg_edges", "observed_at", nullable=False)
        op.alter_column("kg_edges", "valid_from", nullable=False)
        if not _has_index(bind, "kg_edges", "idx_kg_edges_temporal"):
            op.create_index(
                "idx_kg_edges_temporal",
                "kg_edges",
                ["tenant_id", "relation", "valid_to", "observed_at"],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()

    if _has_table(bind, "kg_edges"):
        if _has_index(bind, "kg_edges", "idx_kg_edges_temporal"):
            op.drop_index("idx_kg_edges_temporal", table_name="kg_edges")
        for column_name in ("valid_to", "valid_from", "observed_at", "causal_confidence"):
            if _has_column(bind, "kg_edges", column_name):
                op.drop_column("kg_edges", column_name)

    if _has_table(bind, "kg_nodes"):
        if _has_index(bind, "kg_nodes", "idx_kg_nodes_validity"):
            op.drop_index("idx_kg_nodes_validity", table_name="kg_nodes")
        for column_name in ("state_hash", "valid_to", "valid_from", "observed_at"):
            if _has_column(bind, "kg_nodes", column_name):
                op.drop_column("kg_nodes", column_name)
