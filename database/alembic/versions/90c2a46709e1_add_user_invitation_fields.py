"""add_user_invitation_fields

Revision ID: 90c2a46709e1
Revises: 008_add_health_checks
Create Date: 2026-03-11 06:28:48.679110
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP


# revision identifiers
revision: str = '90c2a46709e1'
down_revision: Union[str, None] = '008_add_health_checks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make hashed_password nullable (for invitation flow)
    op.alter_column('users', 'hashed_password', nullable=True)
    
    # Add invitation fields
    op.add_column(
        'users',
        sa.Column('invitation_token', sa.String(64), nullable=True, unique=True)
    )
    op.add_column(
        'users',
        sa.Column(
            'invitation_expires_at',
            TIMESTAMP(timezone=True),
            nullable=True
        )
    )
    
    # Create index on invitation_token for lookups
    op.create_index('idx_users_invitation_token', 'users', ['invitation_token'], unique=True)


def downgrade() -> None:
    op.drop_index('idx_users_invitation_token', table_name='users')
    op.drop_column('users', 'invitation_expires_at')
    op.drop_column('users', 'invitation_token')
    op.alter_column('users', 'hashed_password', nullable=False)
