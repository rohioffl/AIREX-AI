"""add_incident_templates_table

Revision ID: a0abe085396f
Revises: 79c9cadf8b06
Create Date: 2026-03-11 08:09:51.587813
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'a0abe085396f'
down_revision: Union[str, None] = '79c9cadf8b06'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'incident_templates',
        sa.Column('tenant_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('alert_type', sa.String(255), nullable=False),
        sa.Column('severity', sa.String(50), nullable=False),
        sa.Column('default_title', sa.String(500), nullable=True),
        sa.Column('default_meta', sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.dialects.postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.dialects.postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('tenant_id', 'id'),
    )
    op.create_index('idx_incident_templates_tenant', 'incident_templates', ['tenant_id', 'is_active'])
    op.execute('ALTER TABLE incident_templates ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE incident_templates FORCE ROW LEVEL SECURITY')
    op.execute("""
        CREATE POLICY tenant_isolation_incident_templates ON incident_templates
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS tenant_isolation_incident_templates ON incident_templates')
    op.execute('ALTER TABLE incident_templates DISABLE ROW LEVEL SECURITY')
    op.drop_index('idx_incident_templates_tenant', table_name='incident_templates')
    op.drop_table('incident_templates')
