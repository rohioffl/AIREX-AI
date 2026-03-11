"""add_incident_comments_and_assignment

Revision ID: fc8657236606
Revises: 90c2a46709e1
Create Date: 2026-03-11 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

# revision identifiers
revision: str = 'fc8657236606'
down_revision: Union[str, None] = '90c2a46709e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create comments table
    op.create_table(
        'comments',
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('incident_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('tenant_id', 'id'),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'incident_id'],
            ['incidents.tenant_id', 'incidents.id'],
            ondelete='CASCADE',
            deferrable=True,
            initially='DEFERRED'
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'user_id'],
            ['users.tenant_id', 'users.id'],
            ondelete='CASCADE',
            deferrable=True,
            initially='DEFERRED'
        ),
    )
    
    # Create indexes
    op.create_index('idx_comments_incident', 'comments', ['tenant_id', 'incident_id', 'created_at'])
    op.create_index('idx_comments_user', 'comments', ['tenant_id', 'user_id'])
    
    # Enable RLS
    op.execute('ALTER TABLE comments ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE comments FORCE ROW LEVEL SECURITY')
    op.execute("""
        CREATE POLICY tenant_isolation_comments ON comments
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS tenant_isolation_comments ON comments')
    op.execute('ALTER TABLE comments DISABLE ROW LEVEL SECURITY')
    op.drop_index('idx_comments_user', table_name='comments')
    op.drop_index('idx_comments_incident', table_name='comments')
    op.drop_table('comments')
