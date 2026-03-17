"""seed_default_admin_user

Seeds a default platform admin user so the system is usable immediately
after a fresh deployment without running a separate script.

Default credentials:
  Email: airex@ankercloud.com

Change the password immediately after first login.

Revision ID: 9a2b3c4d5e6f
Revises: 8f3b7c2a91e4
Create Date: 2026-03-16
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa

revision: str = "9a2b3c4d5e6f"
down_revision: Union[str, None] = "8f3b7c2a91e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Fixed UUIDs so the migration is idempotent / reproducible
_TENANT_ID = "00000000-0000-0000-0000-000000000000"
_USER_ID   = "00000000-0000-0000-0000-000000000001"

# bcrypt hash of "Airex@2026!Temp"  (cost=12)
# Generate a new hash and replace this if you want a different default password:
#   python3 -c "from passlib.context import CryptContext; \
#               print(CryptContext(schemes=['bcrypt']).hash('YourPassword'))"
_HASHED_PW = "$2b$12$n42sbGW1WHGU5UUCFFFjE.yD7lOnd8j6VPv2s5Y4/xlRQ9adz0Vjm"


def upgrade() -> None:
    conn = op.get_bind()

    # Skip if the user already exists (idempotent re-runs)
    existing = conn.execute(
        sa.text("SELECT id FROM users WHERE email = :email"),
        {"email": "airex@ankercloud.com"},
    ).fetchone()

    # Bypass RLS for this privileged seed operation
    # SET LOCAL does not support bind parameters — value is a hardcoded constant
    conn.execute(sa.text(f"SET LOCAL app.tenant_id = '{_TENANT_ID}'"))

    if existing:
        # User already exists — ensure password, role, and active state are correct
        conn.execute(
            sa.text("""
                UPDATE users
                SET hashed_password = :hashed_password, role = 'platform_admin', is_active = TRUE
                WHERE email = :email
            """),
            {"hashed_password": _HASHED_PW, "email": "airex@ankercloud.com"},
        )
        return

    conn.execute(
        sa.text("""
            INSERT INTO users
                (tenant_id, id, email, hashed_password, display_name, role, is_active)
            VALUES
                (:tenant_id, :id, :email, :hashed_password, :display_name, :role, TRUE)
        """),
        {
            "tenant_id":       _TENANT_ID,
            "id":              _USER_ID,
            "email":           "airex@ankercloud.com",
            "hashed_password": _HASHED_PW,
            "display_name":    "Platform Admin",
            "role":            "platform_admin",
        },
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"SET LOCAL app.tenant_id = '{_TENANT_ID}'"))
    conn.execute(
        sa.text("DELETE FROM users WHERE id = :id AND tenant_id = :tenant_id"),
        {"id": _USER_ID, "tenant_id": _TENANT_ID},
    )
