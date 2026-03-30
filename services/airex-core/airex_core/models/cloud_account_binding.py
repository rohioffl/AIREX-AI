"""Cloud account binding model — one row per linked AWS account or GCP project.

Implements §7.1 of the Tenant Credentials AWS Secrets Manager plan.

Non-secret metadata (account IDs, role names, regions) lives in ``config_json``.
Sensitive material lives in AWS Secrets Manager; only the ARN is stored here.

Table is RLS-scoped by ``tenant_id`` — same pattern as all per-tenant tables.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from airex_core.models.base import Base


class CloudAccountBinding(Base):
    """One linked cloud account (AWS) or project (GCP) for a tenant.

    Cardinality: tenant → bindings is 1:N.
    The ``is_default`` flag identifies the binding used when an incident
    does not specify a ``cloud_account_id``.

    Secret resolution order (§7.4 of the plan):
      1. ``credentials_secret_arn`` set → fetch JSON from Secrets Manager.
      2. ``credentials_secret_arn`` null + ``config_json`` has role ARN →
         cross-account STS assume role (no stored secret needed).
      3. Legacy: fall back to ``tenants.aws_config`` / ``gcp_config``.
      4. ECS task role / environment credential chain.
    """

    __tablename__ = "cloud_account_bindings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # "aws" or "gcp" — extend with more providers if needed
    provider: Mapped[str] = mapped_column(String(16), nullable=False)

    # Human-readable label shown in admin UI: e.g. "Production AWS", "Staging GCP"
    display_name: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default=""
    )

    # AWS account id (12-digit) or GCP project id — non-secret, used for UX + routing
    external_account_id: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=""
    )

    # Non-secret operational metadata.
    # AWS keys: region, role_arn, role_name, account_id, external_id,
    #           ssm_document, ssm_timeout, log_group_prefix, profile
    # GCP keys: project_id, zone, os_login_user, log_explorer_enabled
    config_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    # Secrets Manager ARN for static credentials.
    # Null means rely on cross-account role assumption or ECS task role (preferred).
    credentials_secret_arn: Mapped[str | None] = mapped_column(Text, nullable=True)

    # One binding per tenant is the default for incidents without explicit account.
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
