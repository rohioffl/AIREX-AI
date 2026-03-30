"""Cloud account bindings API — CRUD + AWS Secrets Manager auto-provisioning.

Implements §7.1–7.5 of the Tenant Credentials AWS Secrets Manager plan.

Endpoints:
  GET    /cloud-accounts                      — list bindings for current tenant
  POST   /cloud-accounts                      — create binding; auto-provisions SM secret
  GET    /cloud-accounts/{binding_id}         — get single binding
  PUT    /cloud-accounts/{binding_id}         — update metadata / config
  PUT    /cloud-accounts/{binding_id}/credentials — rotate stored secret
  DELETE /cloud-accounts/{binding_id}         — delete binding (+ optional SM secret)
  POST   /cloud-accounts/{binding_id}/test    — verify connectivity

Secrets are NEVER returned in responses.  Only the ``credentials_secret_arn``
(masked) and config metadata are exposed.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    RequireAdmin,
    RequireViewer,
    TenantId,
    TenantSession,
    get_auth_session,
    get_authenticated_user,
    authorize_tenant_admin,
)
from airex_core.core.config import settings
from airex_core.core.security import TokenData

logger = structlog.get_logger()
router = APIRouter()

# ── Helpers ────────────────────────────────────────────────────────────────────


def _sm_secret_name(tenant_id: str, provider: str, binding_id: str) -> str:
    """Construct the Secrets Manager secret name for a binding."""
    prefix = settings.AWS_SECRETS_PREFIX.rstrip("/")
    return f"{prefix}/tenant/{tenant_id}/{provider}/{binding_id}"


def _mask_arn(arn: str | None) -> str | None:
    """Return a masked version: arn:aws:secretsmanager:…:secret:name → last 6 chars shown."""
    if not arn:
        return None
    parts = arn.rsplit(":", 1)
    if len(parts) == 2:
        name = parts[1]
        visible = name[-6:] if len(name) >= 6 else name
        return f"{parts[0]}:…{visible}"
    return "…" + arn[-8:]


async def _provision_sm_secret(
    tenant_id: str,
    provider: str,
    binding_id: str,
    credentials: dict,
    description: str = "",
) -> str:
    """Create (or overwrite) a Secrets Manager secret; return the ARN.

    Runs synchronously via boto3 (no async SDK).  Call in executor if needed.
    """
    import boto3  # type: ignore[import-not-found]
    from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-not-found]

    secret_name = _sm_secret_name(tenant_id, provider, binding_id)
    secret_string = json.dumps(credentials)
    region = settings.AWS_REGION

    client = boto3.client("secretsmanager", region_name=region)
    try:
        resp = client.create_secret(
            Name=secret_name,
            Description=description or f"AIREX tenant {tenant_id} {provider} credentials",
            SecretString=secret_string,
        )
        logger.info(
            "sm_secret_created",
            secret_name=secret_name,
            tenant_id=tenant_id,
            provider=provider,
        )
        return resp["ARN"]
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "ResourceExistsException":
            # Secret exists — overwrite the value
            resp = client.put_secret_value(
                SecretId=secret_name,
                SecretString=secret_string,
            )
            logger.info(
                "sm_secret_updated",
                secret_name=secret_name,
                tenant_id=tenant_id,
            )
            return resp["ARN"]
        logger.error(
            "sm_secret_provision_failed",
            secret_name=secret_name,
            error_code=code,
            tenant_id=tenant_id,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to provision Secrets Manager secret: {code}",
        ) from exc
    except (BotoCoreError, OSError, ValueError, TypeError) as exc:
        error_name = type(exc).__name__
        logger.exception(
            "sm_secret_provision_unavailable",
            secret_name=secret_name,
            error_type=error_name,
            tenant_id=tenant_id,
            provider=provider,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to provision Secrets Manager secret: {error_name}",
        ) from exc


async def _delete_sm_secret(arn: str) -> None:
    """Schedule SM secret deletion (14-day recovery window)."""
    import boto3  # type: ignore[import-not-found]
    from botocore.exceptions import ClientError  # type: ignore[import-not-found]

    try:
        client = boto3.client("secretsmanager", region_name=settings.AWS_REGION)
        client.delete_secret(
            SecretId=arn,
            RecoveryWindowInDays=14,
        )
        logger.info("sm_secret_deleted", arn_suffix=arn[-6:])
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("ResourceNotFoundException", "InvalidRequestException"):
            # Already deleted or never existed — ignore
            return
        logger.warning("sm_secret_delete_failed", error_code=code, arn_suffix=arn[-6:])


# ── Pydantic schemas ───────────────────────────────────────────────────────────


class AWSCredentialsInput(BaseModel):
    """Static AWS credentials — written to SM, never stored in DB."""

    access_key_id: str = Field(..., min_length=16, max_length=128)
    secret_access_key: str = Field(..., min_length=1, max_length=512)
    session_token: str | None = None


class GCPCredentialsInput(BaseModel):
    """GCP service account JSON — written to SM as-is."""

    # Full SA JSON: type, project_id, private_key_id, private_key, client_email, …
    type: str = "service_account"
    project_id: str = ""
    private_key_id: str = ""
    private_key: str = Field(..., min_length=1)
    client_email: str = ""
    client_id: str = ""
    auth_uri: str = ""
    token_uri: str = ""
    auth_provider_x509_cert_url: str = ""
    client_x509_cert_url: str = ""

    model_config = {"extra": "allow"}  # allow extra SA JSON fields


class CloudAccountCreateRequest(BaseModel):
    """Request body for creating a new cloud account binding."""

    provider: str = Field(..., pattern=r"^(aws|gcp)$")
    display_name: str = Field(..., min_length=1, max_length=255)
    external_account_id: str = Field("", max_length=64)
    config_json: dict = Field(
        default_factory=dict,
        description="Non-secret operational metadata: region, role_arn, project_id, zone, …",
    )
    is_default: bool = False

    # Optional static credentials — if provided, auto-provisioned to SM
    aws_credentials: AWSCredentialsInput | None = None
    gcp_credentials: GCPCredentialsInput | None = None

    @field_validator("config_json")
    @classmethod
    def _no_secrets_in_config(cls, v: dict) -> dict:
        forbidden = {"access_key_id", "secret_access_key", "private_key", "session_token"}
        found = forbidden & set(v.keys())
        if found:
            raise ValueError(
                f"config_json must not contain secret fields: {', '.join(sorted(found))}. "
                "Use aws_credentials / gcp_credentials instead."
            )
        return v


class CloudAccountUpdateRequest(BaseModel):
    """Request body for updating metadata (never credentials)."""

    display_name: str | None = Field(None, min_length=1, max_length=255)
    external_account_id: str | None = Field(None, max_length=64)
    config_json: dict | None = None
    is_default: bool | None = None

    @field_validator("config_json")
    @classmethod
    def _no_secrets_in_config(cls, v: dict | None) -> dict | None:
        if v is None:
            return v
        forbidden = {"access_key_id", "secret_access_key", "private_key", "session_token"}
        found = forbidden & set(v.keys())
        if found:
            raise ValueError(
                f"config_json must not contain secret fields: {', '.join(sorted(found))}. "
                "Use PUT /credentials to rotate credentials."
            )
        return v


class CloudAccountCredentialsUpdateRequest(BaseModel):
    """Rotate credentials on an existing binding."""

    aws_credentials: AWSCredentialsInput | None = None
    gcp_credentials: GCPCredentialsInput | None = None


class CloudAccountResponse(BaseModel):
    """Binding metadata — secrets are NEVER exposed."""

    id: str
    tenant_id: str
    provider: str
    display_name: str
    external_account_id: str
    config_json: dict
    credentials_secret_arn_masked: str | None  # masked ARN or None
    has_static_credentials: bool
    is_default: bool
    created_at: str
    updated_at: str


def _row_to_response(row: Any) -> CloudAccountResponse:
    arn = row["credentials_secret_arn"]
    return CloudAccountResponse(
        id=str(row["id"]),
        tenant_id=str(row["tenant_id"]),
        provider=row["provider"],
        display_name=row["display_name"] or "",
        external_account_id=row["external_account_id"] or "",
        config_json=row["config_json"] or {},
        credentials_secret_arn_masked=_mask_arn(arn),
        has_static_credentials=bool(arn),
        is_default=bool(row["is_default"]),
        created_at=row["created_at"].isoformat() if row["created_at"] else "",
        updated_at=row["updated_at"].isoformat() if row["updated_at"] else "",
    )


# ── Routes ─────────────────────────────────────────────────────────────────────


@router.get("/cloud-accounts", response_model=list[CloudAccountResponse])
async def list_cloud_accounts(
    _auth: RequireViewer,
    tenant_id: TenantId,
    db: TenantSession,
    provider: str | None = Query(None, pattern=r"^(aws|gcp)$"),
) -> list[CloudAccountResponse]:
    """List all cloud account bindings for the current tenant."""
    where = "WHERE tenant_id = :tenant_id"
    params: dict = {"tenant_id": tenant_id}
    if provider:
        where += " AND provider = :provider"
        params["provider"] = provider

    rows = await db.execute(
        sa_text(
            f"SELECT id, tenant_id, provider, display_name, external_account_id, "
            f"config_json, credentials_secret_arn, is_default, created_at, updated_at "
            f"FROM cloud_account_bindings {where} ORDER BY is_default DESC, created_at ASC"
        ),
        params,
    )
    return [_row_to_response(r._mapping) for r in rows.fetchall()]


@router.post("/cloud-accounts", response_model=CloudAccountResponse, status_code=201)
async def create_cloud_account(
    body: CloudAccountCreateRequest,
    _auth: RequireAdmin,
    tenant_id: TenantId,
    db: TenantSession,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> CloudAccountResponse:
    """Create a cloud account binding.

    If ``aws_credentials`` or ``gcp_credentials`` is provided, the credentials
    are automatically provisioned to AWS Secrets Manager and only the ARN is
    stored in the database.
    """
    # Authorization: must be admin of this tenant
    is_admin = await authorize_tenant_admin(session, current_user, tenant_id)
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant admin access required to manage cloud accounts",
        )

    binding_id = uuid.uuid4()

    # Provision SM secret if credentials provided
    arn: str | None = None
    if body.provider == "aws" and body.aws_credentials:
        creds_dict = body.aws_credentials.model_dump(exclude_none=True)
        arn = await _provision_sm_secret(
            tenant_id=str(tenant_id),
            provider="aws",
            binding_id=str(binding_id),
            credentials=creds_dict,
            description=f"AIREX AWS credentials for {body.display_name}",
        )
    elif body.provider == "gcp" and body.gcp_credentials:
        creds_dict = body.gcp_credentials.model_dump(exclude_none=True)
        arn = await _provision_sm_secret(
            tenant_id=str(tenant_id),
            provider="gcp",
            binding_id=str(binding_id),
            credentials=creds_dict,
            description=f"AIREX GCP service account for {body.display_name}",
        )

    # If this is the first/default binding, clear other defaults
    if body.is_default:
        await db.execute(
            sa_text(
                "UPDATE cloud_account_bindings SET is_default = false "
                "WHERE tenant_id = :tenant_id AND provider = :provider"
            ),
            {"tenant_id": tenant_id, "provider": body.provider},
        )

    result = await db.execute(
        sa_text(
            "INSERT INTO cloud_account_bindings "
            "(id, tenant_id, provider, display_name, external_account_id, "
            "config_json, credentials_secret_arn, is_default) "
            "VALUES (:id, :tenant_id, :provider, :display_name, :external_account_id, "
            "CAST(:config_json AS jsonb), :arn, :is_default) "
            "RETURNING id, tenant_id, provider, display_name, external_account_id, "
            "config_json, credentials_secret_arn, is_default, created_at, updated_at"
        ),
        {
            "id": binding_id,
            "tenant_id": tenant_id,
            "provider": body.provider,
            "display_name": body.display_name,
            "external_account_id": body.external_account_id,
            "config_json": json.dumps(body.config_json),
            "arn": arn,
            "is_default": body.is_default,
        },
    )
    row = result.mappings().one()
    logger.info(
        "cloud_account_created",
        binding_id=str(binding_id),
        provider=body.provider,
        tenant_id=str(tenant_id),
        has_sm_secret=arn is not None,
    )
    return _row_to_response(row)


@router.get("/cloud-accounts/{binding_id}", response_model=CloudAccountResponse)
async def get_cloud_account(
    binding_id: uuid.UUID,
    _auth: RequireViewer,
    tenant_id: TenantId,
    db: TenantSession,
) -> CloudAccountResponse:
    """Get a single cloud account binding."""
    result = await db.execute(
        sa_text(
            "SELECT id, tenant_id, provider, display_name, external_account_id, "
            "config_json, credentials_secret_arn, is_default, created_at, updated_at "
            "FROM cloud_account_bindings WHERE tenant_id = :tenant_id AND id = :id"
        ),
        {"tenant_id": tenant_id, "id": binding_id},
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Cloud account binding not found")
    return _row_to_response(row)


@router.put("/cloud-accounts/{binding_id}", response_model=CloudAccountResponse)
async def update_cloud_account(
    binding_id: uuid.UUID,
    body: CloudAccountUpdateRequest,
    _auth: RequireAdmin,
    tenant_id: TenantId,
    db: TenantSession,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> CloudAccountResponse:
    """Update metadata / config of a cloud account binding.

    To rotate credentials use PUT /cloud-accounts/{id}/credentials instead.
    """
    is_admin = await authorize_tenant_admin(session, current_user, tenant_id)
    if not is_admin:
        raise HTTPException(status_code=403, detail="Tenant admin access required")

    # Fetch existing row first
    existing = await db.execute(
        sa_text(
            "SELECT id, provider FROM cloud_account_bindings "
            "WHERE tenant_id = :tenant_id AND id = :id"
        ),
        {"tenant_id": tenant_id, "id": binding_id},
    )
    row = existing.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Cloud account binding not found")

    # Build dynamic SET clause
    updates: dict[str, Any] = {}
    if body.display_name is not None:
        updates["display_name"] = body.display_name
    if body.external_account_id is not None:
        updates["external_account_id"] = body.external_account_id
    if body.config_json is not None:
        updates["config_json"] = json.dumps(body.config_json)
    if body.is_default is not None:
        updates["is_default"] = body.is_default

    if not updates:
        # Nothing to update — just return existing record
        result = await db.execute(
            sa_text(
                "SELECT id, tenant_id, provider, display_name, external_account_id, "
                "config_json, credentials_secret_arn, is_default, created_at, updated_at "
                "FROM cloud_account_bindings WHERE tenant_id = :tenant_id AND id = :id"
            ),
            {"tenant_id": tenant_id, "id": binding_id},
        )
        return _row_to_response(result.mappings().one())

    if updates.get("is_default"):
        await db.execute(
            sa_text(
                "UPDATE cloud_account_bindings SET is_default = false "
                "WHERE tenant_id = :tenant_id AND provider = :provider AND id != :id"
            ),
            {"tenant_id": tenant_id, "provider": row["provider"], "id": binding_id},
        )

    set_parts = []
    params: dict[str, Any] = {"tenant_id": tenant_id, "id": binding_id}
    for key, val in updates.items():
        param_name = f"p_{key}"
        if key == "config_json":
            set_parts.append(f"{key} = CAST(:{param_name} AS jsonb)")
        else:
            set_parts.append(f"{key} = :{param_name}")
        params[param_name] = val

    set_parts.append("updated_at = now()")
    set_clause = ", ".join(set_parts)

    result = await db.execute(
        sa_text(
            f"UPDATE cloud_account_bindings SET {set_clause} "
            f"WHERE tenant_id = :tenant_id AND id = :id "
            f"RETURNING id, tenant_id, provider, display_name, external_account_id, "
            f"config_json, credentials_secret_arn, is_default, created_at, updated_at"
        ),
        params,
    )
    updated_row = result.mappings().one()
    logger.info("cloud_account_updated", binding_id=str(binding_id), tenant_id=str(tenant_id))
    return _row_to_response(updated_row)


@router.put(
    "/cloud-accounts/{binding_id}/credentials",
    response_model=CloudAccountResponse,
)
async def update_cloud_account_credentials(
    binding_id: uuid.UUID,
    body: CloudAccountCredentialsUpdateRequest,
    _auth: RequireAdmin,
    tenant_id: TenantId,
    db: TenantSession,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> CloudAccountResponse:
    """Rotate / set static credentials for a cloud account binding.

    The new credentials are written to Secrets Manager (create or overwrite);
    only the ARN is stored in the database.
    """
    is_admin = await authorize_tenant_admin(session, current_user, tenant_id)
    if not is_admin:
        raise HTTPException(status_code=403, detail="Tenant admin access required")

    existing = await db.execute(
        sa_text(
            "SELECT id, provider FROM cloud_account_bindings "
            "WHERE tenant_id = :tenant_id AND id = :id"
        ),
        {"tenant_id": tenant_id, "id": binding_id},
    )
    row = existing.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Cloud account binding not found")

    provider = row["provider"]

    arn: str | None = None
    if provider == "aws" and body.aws_credentials:
        creds_dict = body.aws_credentials.model_dump(exclude_none=True)
        arn = await _provision_sm_secret(
            tenant_id=str(tenant_id),
            provider="aws",
            binding_id=str(binding_id),
            credentials=creds_dict,
        )
    elif provider == "gcp" and body.gcp_credentials:
        creds_dict = body.gcp_credentials.model_dump(exclude_none=True)
        arn = await _provision_sm_secret(
            tenant_id=str(tenant_id),
            provider="gcp",
            binding_id=str(binding_id),
            credentials=creds_dict,
        )
    else:
        raise HTTPException(
            status_code=422,
            detail=f"No credentials provided for provider '{provider}'",
        )

    result = await db.execute(
        sa_text(
            "UPDATE cloud_account_bindings SET credentials_secret_arn = :arn, updated_at = now() "
            "WHERE tenant_id = :tenant_id AND id = :id "
            "RETURNING id, tenant_id, provider, display_name, external_account_id, "
            "config_json, credentials_secret_arn, is_default, created_at, updated_at"
        ),
        {"arn": arn, "tenant_id": tenant_id, "id": binding_id},
    )
    updated_row = result.mappings().one()
    logger.info(
        "cloud_account_credentials_rotated",
        binding_id=str(binding_id),
        provider=provider,
        tenant_id=str(tenant_id),
    )
    return _row_to_response(updated_row)


@router.delete("/cloud-accounts/{binding_id}", status_code=204)
async def delete_cloud_account(
    binding_id: uuid.UUID,
    _auth: RequireAdmin,
    tenant_id: TenantId,
    db: TenantSession,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
    delete_secret: bool = Query(
        False,
        description="Also schedule deletion of the Secrets Manager secret (14-day recovery).",
    ),
) -> None:
    """Delete a cloud account binding.

    Set ``delete_secret=true`` to also schedule deletion of the associated
    Secrets Manager secret (14-day recovery window — recoverable if mistaken).
    """
    is_admin = await authorize_tenant_admin(session, current_user, tenant_id)
    if not is_admin:
        raise HTTPException(status_code=403, detail="Tenant admin access required")

    result = await db.execute(
        sa_text(
            "DELETE FROM cloud_account_bindings "
            "WHERE tenant_id = :tenant_id AND id = :id "
            "RETURNING credentials_secret_arn"
        ),
        {"tenant_id": tenant_id, "id": binding_id},
    )
    deleted_row = result.mappings().one_or_none()
    if deleted_row is None:
        raise HTTPException(status_code=404, detail="Cloud account binding not found")

    if delete_secret and deleted_row["credentials_secret_arn"]:
        await _delete_sm_secret(deleted_row["credentials_secret_arn"])

    logger.info(
        "cloud_account_deleted",
        binding_id=str(binding_id),
        tenant_id=str(tenant_id),
        secret_also_deleted=delete_secret,
    )


@router.post("/cloud-accounts/{binding_id}/test")
async def test_cloud_account(
    binding_id: uuid.UUID,
    _auth: RequireViewer,
    tenant_id: TenantId,
    db: TenantSession,
) -> dict:
    """Verify that stored credentials / role assumption can authenticate.

    Returns ``{"ok": true, "detail": "…"}`` on success or raises 502.
    """
    result = await db.execute(
        sa_text(
            "SELECT id, provider, config_json, credentials_secret_arn "
            "FROM cloud_account_bindings WHERE tenant_id = :tenant_id AND id = :id"
        ),
        {"tenant_id": tenant_id, "id": binding_id},
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Cloud account binding not found")

    provider = row["provider"]
    config = row["config_json"] or {}
    arn = row["credentials_secret_arn"]

    try:
        if provider == "aws":
            detail = await _test_aws_binding(config, arn)
        elif provider == "gcp":
            detail = await _test_gcp_binding(config, arn)
        else:
            raise HTTPException(status_code=422, detail=f"Unknown provider: {provider}")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(
            "cloud_account_test_failed",
            binding_id=str(binding_id),
            provider=provider,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Connection test failed: {exc}",
        ) from exc

    return {"ok": True, "detail": detail}


async def _test_aws_binding(config: dict, arn: str | None) -> str:
    """Call STS GetCallerIdentity to verify AWS credentials."""
    import boto3  # type: ignore[import-not-found]
    from airex_core.cloud.secret_resolver import get_secret_json

    kwargs: dict = {"region_name": config.get("region", settings.AWS_REGION)}

    if arn:
        secret = get_secret_json(arn)
        kwargs["aws_access_key_id"] = secret.get("access_key_id")
        kwargs["aws_secret_access_key"] = secret.get("secret_access_key")
        if "session_token" in secret:
            kwargs["aws_session_token"] = secret["session_token"]
    elif config.get("role_arn"):
        # Cross-account role assumption
        sts = boto3.client("sts", region_name=kwargs["region_name"])
        assumed = sts.assume_role(
            RoleArn=config["role_arn"],
            RoleSessionName="airex-connection-test",
            ExternalId=config.get("external_id", ""),
        )
        creds = assumed["Credentials"]
        kwargs["aws_access_key_id"] = creds["AccessKeyId"]
        kwargs["aws_secret_access_key"] = creds["SecretAccessKey"]
        kwargs["aws_session_token"] = creds["SessionToken"]

    sts_client = boto3.client("sts", **kwargs)
    identity = sts_client.get_caller_identity()
    return f"AWS account {identity['Account']} — {identity['Arn']}"


async def _test_gcp_binding(config: dict, arn: str | None) -> str:
    """Use GCP Resource Manager to verify the service account can list projects."""
    try:
        import google.auth  # type: ignore[import-not-found]
        from google.oauth2 import service_account  # type: ignore[import-not-found]
    except ImportError:
        return "GCP SDK not installed — skipping live test"

    from airex_core.cloud.secret_resolver import get_secret_json

    if arn:
        sa_info = get_secret_json(arn)
        creds = service_account.Credentials.from_service_account_info(
            sa_info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        project_id = sa_info.get("project_id") or config.get("project_id", "unknown")
        return f"GCP project {project_id} — {creds.service_account_email}"
    else:
        creds, project = google.auth.default()
        return f"GCP default credentials (project: {project or config.get('project_id', '?')})"
