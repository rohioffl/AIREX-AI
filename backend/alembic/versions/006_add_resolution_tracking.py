"""Add resolution tracking columns to incidents.

Revision ID: 006_add_resolution_tracking
Revises: e964260b273c
Create Date: 2026-03-03

Adds structured outcome tracking fields:
  - resolution_type: how the incident was resolved (auto/manual/rejected/timeout)
  - resolution_summary: LLM-generated or operator-provided summary
  - resolution_duration_seconds: total time from RECEIVED to terminal state
  - feedback_score: operator rating (-1 to 5, NULL = not rated)
  - feedback_note: optional operator feedback text
  - resolved_at: timestamp of terminal state transition
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006_add_resolution_tracking"
down_revision: Union[str, None] = "e964260b273c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("resolution_type", sa.String(50), nullable=True),
    )
    op.add_column(
        "incidents",
        sa.Column("resolution_summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "incidents",
        sa.Column(
            "resolution_duration_seconds",
            sa.Float(),
            nullable=True,
        ),
    )
    op.add_column(
        "incidents",
        sa.Column("feedback_score", sa.Integer(), nullable=True),
    )
    op.add_column(
        "incidents",
        sa.Column("feedback_note", sa.Text(), nullable=True),
    )
    op.add_column(
        "incidents",
        sa.Column(
            "resolved_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    # Partial index for unrated resolved incidents (feedback funnel)
    op.create_index(
        "idx_incidents_needs_feedback",
        "incidents",
        ["tenant_id", "resolved_at"],
        postgresql_where=sa.text(
            "feedback_score IS NULL AND state IN ('RESOLVED', 'REJECTED') "
            "AND deleted_at IS NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("idx_incidents_needs_feedback", table_name="incidents")
    op.drop_column("incidents", "resolved_at")
    op.drop_column("incidents", "feedback_note")
    op.drop_column("incidents", "feedback_score")
    op.drop_column("incidents", "resolution_duration_seconds")
    op.drop_column("incidents", "resolution_summary")
    op.drop_column("incidents", "resolution_type")
