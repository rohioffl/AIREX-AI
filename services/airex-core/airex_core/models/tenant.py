"""Tenant model — global (non-RLS) table for tenant metadata and credentials.

This table stores the source-of-truth for all tenant configuration that was
previously managed via tenants.yaml.  The ``id`` column IS the ``tenant_id``
referenced by every other table through ``TenantMixin``.

NOT RLS-scoped: only admins interact with this table through the API.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, String, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from airex_core.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(Base):
    """Global tenant registry — stores cloud config, credentials, and contacts."""

    __tablename__ = "tenants"

    # Primary key — this IS the tenant_id used across all other tables
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Identity
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    cloud: Mapped[str] = mapped_column(String(10), nullable=False)  # "aws" / "gcp"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Contacts
    escalation_email: Mapped[str] = mapped_column(String(320), default="", nullable=False)
    slack_channel: Mapped[str] = mapped_column(String(100), default="", nullable=False)

    # SSH defaults
    ssh_user: Mapped[str] = mapped_column(String(100), default="ubuntu", nullable=False)

    # ── Cloud credentials (JSONB for flexibility) ────────────────
    # AWS: {account_id, role_name, role_arn, external_id,
    #       access_key_id, secret_access_key, credentials_file,
    #       region, profile, ssm_document, ssm_timeout, log_group_prefix}
    aws_config: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)

    # GCP: {project_id, service_account_key, zone, os_login_user,
    #       log_explorer_enabled}
    gcp_config: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)

    # ── Server overrides (JSONB list) ────────────────────────────
    # [{name, instance_id, private_ip, cloud, role, ssh_user, ...}]
    servers: Mapped[dict | None] = mapped_column(JSONB, default=list, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=_utcnow,
    )

    def __repr__(self) -> str:
        return (
            "Tenant("
            f"id={self.id!s}, "
            f"name={self.name!r}, "
            f"cloud={self.cloud!r}, "
            f"is_active={self.is_active}"
            ")"
        )
