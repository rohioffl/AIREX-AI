"""add_knowledge_base_table

Revision ID: 5b759aef255f
Revises: a0abe085396f
Create Date: 2026-03-11 08:09:53.266504
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '5b759aef255f'
down_revision: Union[str, None] = 'a0abe085396f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'knowledge_base',
        sa.Column('tenant_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('incident_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('summary', sa.Text, nullable=False),
        sa.Column('root_cause', sa.Text, nullable=True),
        sa.Column('resolution_steps', sa.Text, nullable=True),
        sa.Column('alert_type', sa.String(255), nullable=False),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('tags', sa.dialects.postgresql.ARRAY(sa.String(100)), nullable=True),
        sa.Column('created_by', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.dialects.postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.dialects.postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('tenant_id', 'id'),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'incident_id'],
            ['incidents.tenant_id', 'incidents.id'],
            ondelete='SET NULL',
            deferrable=True,
            initially='DEFERRED'
        ),
    )
    op.create_index('idx_knowledge_base_tenant', 'knowledge_base', ['tenant_id', 'alert_type'])
    op.create_index('idx_knowledge_base_category', 'knowledge_base', ['tenant_id', 'category'])
    op.execute('ALTER TABLE knowledge_base ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE knowledge_base FORCE ROW LEVEL SECURITY')
    op.execute("""
        CREATE POLICY tenant_isolation_knowledge_base ON knowledge_base
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS tenant_isolation_knowledge_base ON knowledge_base')
    op.execute('ALTER TABLE knowledge_base DISABLE ROW LEVEL SECURITY')
    op.drop_index('idx_knowledge_base_category', table_name='knowledge_base')
    op.drop_index('idx_knowledge_base_tenant', table_name='knowledge_base')
    op.drop_table('knowledge_base')
