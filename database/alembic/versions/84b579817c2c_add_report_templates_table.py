"""Add report_template table

Revision ID: 84b579817c2c
Revises: 
Create Date: 2026-03-11 09:32:58

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '84b579817c2c'
down_revision = 'cecb2f816253'  # Update this with the latest migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'report_templates',
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('schedule_type', sa.String(length=50), nullable=False),
        sa.Column('schedule_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('filters', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('format', sa.String(length=20), nullable=False, server_default='json'),
        sa.Column('recipients', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('tenant_id', 'id'),
    )
    
    # Create indexes
    op.create_index('ix_report_templates_tenant_id', 'report_templates', ['tenant_id'])
    op.create_index('ix_report_templates_created_by', 'report_templates', ['created_by'])
    op.create_index('ix_report_templates_schedule_type', 'report_templates', ['schedule_type'])
    
    # RLS policies
    op.execute(
        "ALTER TABLE report_templates ENABLE ROW LEVEL SECURITY;"
    )
    op.execute(
        "CREATE POLICY report_templates_tenant_isolation ON report_templates FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);"
    )


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS report_templates_tenant_isolation ON report_templates')
    op.drop_index('ix_report_templates_schedule_type', table_name='report_templates')
    op.drop_index('ix_report_templates_created_by', table_name='report_templates')
    op.drop_index('ix_report_templates_tenant_id', table_name='report_templates')
    op.drop_table('report_templates')
