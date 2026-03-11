"""add_notification_preferences_table

Revision ID: fcd9217e5222
Revises: fc8657236606
Create Date: 2026-03-11 07:53:22.872645
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'fcd9217e5222'
down_revision: Union[str, None] = 'fc8657236606'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create notification_preferences table
    op.create_table(
        'notification_preferences',
        sa.Column('tenant_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('email_critical_only', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('slack_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('slack_webhook_url', sa.String(512), nullable=True),
        sa.Column('slack_critical_only', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notify_on_received', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notify_on_investigating', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notify_on_recommendation_ready', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notify_on_awaiting_approval', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notify_on_executing', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notify_on_verifying', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notify_on_resolved', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notify_on_rejected', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notify_on_failed', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notification_metadata', sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.dialects.postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.dialects.postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('tenant_id', 'user_id'),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'user_id'],
            ['users.tenant_id', 'users.id'],
            ondelete='CASCADE',
            deferrable=True,
            initially='DEFERRED'
        ),
    )
    
    # Create index
    op.create_index('idx_notification_preferences_user', 'notification_preferences', ['tenant_id', 'user_id'], unique=True)
    
    # Enable RLS
    op.execute('ALTER TABLE notification_preferences ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE notification_preferences FORCE ROW LEVEL SECURITY')
    op.execute("""
        CREATE POLICY tenant_isolation_notification_preferences ON notification_preferences
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS tenant_isolation_notification_preferences ON notification_preferences')
    op.execute('ALTER TABLE notification_preferences DISABLE ROW LEVEL SECURITY')
    op.drop_index('idx_notification_preferences_user', table_name='notification_preferences')
    op.drop_table('notification_preferences')
