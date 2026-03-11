"""add_related_incidents_table

Revision ID: 79c9cadf8b06
Revises: fcd9217e5222
Create Date: 2026-03-11 08:05:28.657041
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '79c9cadf8b06'
down_revision: Union[str, None] = 'fcd9217e5222'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create related_incidents table
    op.create_table(
        'related_incidents',
        sa.Column('tenant_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('incident_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('related_incident_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('relationship_type', sa.String(50), nullable=False, server_default='related'),
        sa.Column('note', sa.String(500), nullable=True),
        sa.Column('created_by', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.dialects.postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('tenant_id', 'incident_id', 'related_incident_id'),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'incident_id'],
            ['incidents.tenant_id', 'incidents.id'],
            ondelete='CASCADE',
            deferrable=True,
            initially='DEFERRED'
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'related_incident_id'],
            ['incidents.tenant_id', 'incidents.id'],
            ondelete='CASCADE',
            deferrable=True,
            initially='DEFERRED'
        ),
        sa.CheckConstraint(
            'incident_id != related_incident_id',
            name='ck_related_incidents_no_self_link'
        ),
    )
    
    # Create indexes
    op.create_index('idx_related_incidents_incident', 'related_incidents', ['tenant_id', 'incident_id'])
    op.create_index('idx_related_incidents_related', 'related_incidents', ['tenant_id', 'related_incident_id'])
    
    # Enable RLS
    op.execute('ALTER TABLE related_incidents ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE related_incidents FORCE ROW LEVEL SECURITY')
    op.execute("""
        CREATE POLICY tenant_isolation_related_incidents ON related_incidents
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS tenant_isolation_related_incidents ON related_incidents')
    op.execute('ALTER TABLE related_incidents DISABLE ROW LEVEL SECURITY')
    op.drop_index('idx_related_incidents_related', table_name='related_incidents')
    op.drop_index('idx_related_incidents_incident', table_name='related_incidents')
    op.drop_table('related_incidents')
