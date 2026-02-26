"""Add created_at and updated_at timestamps to users table.

Revision ID: 005_add_user_timestamps
Revises: 004_add_role_constraint
Create Date: 2026-02-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision: str = "005_add_user_timestamps"
down_revision: Union[str, None] = "004_add_role_constraint"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add created_at and updated_at columns
    op.add_column(
        "users",
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    
    # Create index on created_at for sorting
    op.create_index("idx_users_created_at", "users", ["tenant_id", "created_at"])
    
    # Add trigger to auto-update updated_at (if function doesn't exist, create it)
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
        BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trigger_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trigger_users_updated_at ON users")
    op.drop_index("idx_users_created_at", table_name="users")
    op.drop_column("users", "updated_at")
    op.drop_column("users", "created_at")
