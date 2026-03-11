"""add_feedback_learning_table

Revision ID: cecb2f816253
Revises: 5b759aef255f
Create Date: 2026-03-11 08:09:54.922299
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'cecb2f816253'
down_revision: Union[str, None] = '5b759aef255f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'feedback_learning',
        sa.Column('tenant_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('incident_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('recommendation_id', sa.String(255), nullable=True),
        sa.Column('action_taken', sa.String(50), nullable=False),  # 'approved', 'rejected', 'modified'
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('confidence_before', sa.Float, nullable=True),
        sa.Column('confidence_after', sa.Float, nullable=True),
        sa.Column('feedback_note', sa.Text, nullable=True),
        sa.Column('created_at', sa.dialects.postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('tenant_id', 'id'),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'incident_id'],
            ['incidents.tenant_id', 'incidents.id'],
            ondelete='CASCADE',
            deferrable=True,
            initially='DEFERRED'
        ),
    )
    op.create_index('idx_feedback_learning_incident', 'feedback_learning', ['tenant_id', 'incident_id'])
    op.create_index('idx_feedback_learning_action', 'feedback_learning', ['tenant_id', 'action_taken'])
    op.execute('ALTER TABLE feedback_learning ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE feedback_learning FORCE ROW LEVEL SECURITY')
    op.execute("""
        CREATE POLICY tenant_isolation_feedback_learning ON feedback_learning
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS tenant_isolation_feedback_learning ON feedback_learning')
    op.execute('ALTER TABLE feedback_learning DISABLE ROW LEVEL SECURITY')
    op.drop_index('idx_feedback_learning_action', table_name='feedback_learning')
    op.drop_index('idx_feedback_learning_incident', table_name='feedback_learning')
    op.drop_table('feedback_learning')
