"""add platform_admins table

Creates a completely isolated platform_admins table with no tenant_id,
no RLS, and no foreign keys to any tenant table.
Seeds the default platform admin account.

Default credentials:
  Email:    airex@ankercloud.com
  Password: Airex@2026!Temp  (change immediately after first login)

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6
Create Date: 2026-03-18 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

# Fixed UUIDs so the migration is idempotent / reproducible
_ADMIN_ID = "00000000-0000-0000-0000-000000000002"

# bcrypt hash of "Airex@2026!Temp" (cost=12) — same as existing admin seed
# To regenerate:
#   python3 -c "from passlib.context import CryptContext; \
#               print(CryptContext(schemes=['bcrypt']).hash('YourPassword'))"
_HASHED_PW = "$2b$12$n42sbGW1WHGU5UUCFFFjE.yD7lOnd8j6VPv2s5Y4/xlRQ9adz0Vjm"


def upgrade() -> None:
    op.create_table(
        "platform_admins",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False, server_default="Platform Admin"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("ix_platform_admins_email", "platform_admins", ["email"], unique=True)

    # Seed default platform admin
    conn = op.get_bind()
    existing = conn.execute(
        sa.text("SELECT id FROM platform_admins WHERE email = :email"),
        {"email": "airex@ankercloud.com"},
    ).fetchone()

    if not existing:
        conn.execute(
            sa.text("""
                INSERT INTO platform_admins (id, email, hashed_password, display_name, is_active)
                VALUES (:id, :email, :hashed_password, :display_name, TRUE)
            """),
            {
                "id": _ADMIN_ID,
                "email": "airex@ankercloud.com",
                "hashed_password": _HASHED_PW,
                "display_name": "Platform Admin",
            },
        )


def downgrade() -> None:
    op.drop_index("ix_platform_admins_email", table_name="platform_admins")
    op.drop_table("platform_admins")
