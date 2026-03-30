"""seed_default_admin_user (legacy revision — no-op)

Originally inserted a platform admin row into ``users`` with role ``platform_admin``.
That violates ``check_role_valid`` on ``users`` (roles: operator, admin, viewer only).

Platform admin seeding lives in ``f1a2b3c4d5e6_add_platform_admins_table`` via the
``platform_admins`` table. This revision is retained only to preserve the Alembic graph.

Revision ID: 9a2b3c4d5e6f
Revises: 8f3b7c2a91e4
Create Date: 2026-03-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "9a2b3c4d5e6f"
down_revision: Union[str, None] = "8f3b7c2a91e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TENANT_ID = "00000000-0000-0000-0000-000000000000"
_USER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    pass


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"SET LOCAL app.tenant_id = '{_TENANT_ID}'"))
    conn.execute(
        sa.text("DELETE FROM users WHERE id = :id AND tenant_id = :tenant_id"),
        {"id": _USER_ID, "tenant_id": _TENANT_ID},
    )
