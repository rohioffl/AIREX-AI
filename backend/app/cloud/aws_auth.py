"""
Centralized AWS session/credential builder for per-tenant authentication.

Supports three auth methods (in priority order):
  1. Cross-account Role Assumption (STS AssumeRole) — account_id + role_name
  2. Static Access Key / Secret Key — from credentials_file or inline
  3. Default credential chain — instance role, env vars, CLI profile

Usage:
    from app.cloud.aws_auth import get_aws_session, get_aws_client

    session = get_aws_session(tenant_aws_config)
    ec2 = get_aws_client("ec2", tenant_aws_config)
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

import structlog
from structlog.contextvars import get_contextvars

if TYPE_CHECKING:
    from app.cloud.tenant_config import AWSConfig

logger = structlog.get_logger()


def _get_correlation_id() -> str:
    """Return correlation ID from structlog contextvars, if present."""
    value = get_contextvars().get("correlation_id")
    return str(value) if value is not None else ""


def get_aws_session(
    aws_config: AWSConfig | None = None,
    region: str = "",
) -> Any:  # boto3.Session
    """
    Build a boto3 Session using the tenant's AWS config.

    Auth priority:
      1. Role assumption (account_id + role_name or explicit role_arn)
      2. Static credentials (credentials_file or inline access_key_id)
      3. CLI profile (if set)
      4. Default chain (instance role, env vars, ~/.aws/credentials)

    AWS APIs/permissions used:
      - STS AssumeRole (`sts:AssumeRole`) when role-based auth is configured.
      - Service-specific client credentials inherited from returned session.
    """
    import boto3  # type: ignore[import-not-found]

    from app.core.config import settings

    effective_region = (
        region
        or (aws_config.region if aws_config else "")
        or settings.AWS_REGION
        or "us-east-1"
    )

    if aws_config:
        # Method 1: Role Assumption
        role_arn = aws_config.get_role_arn()
        if role_arn:
            return _assume_role_session(
                role_arn=role_arn,
                external_id=aws_config.external_id,
                region=effective_region,
                base_config=aws_config,
            )

        # Method 2: Static credentials (file or inline)
        access_key, secret_key = _load_static_credentials(aws_config)
        if access_key and secret_key:
            logger.info(
                "aws_auth_static_keys",
                source="file" if aws_config.credentials_file else "inline",
                correlation_id=_get_correlation_id(),
            )
            return boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=effective_region,
            )

        # Method 3: CLI profile
        if aws_config.profile:
            logger.info(
                "aws_auth_profile",
                profile=aws_config.profile,
                correlation_id=_get_correlation_id(),
            )
            return boto3.Session(
                profile_name=aws_config.profile,
                region_name=effective_region,
            )

    # Method 4: Default credential chain
    session_kwargs: dict = {"region_name": effective_region}
    profile = (aws_config.profile if aws_config else "") or settings.AWS_PROFILE or ""
    if profile:
        session_kwargs["profile_name"] = profile

    logger.info(
        "aws_auth_default_chain",
        region=effective_region,
        has_profile=bool(profile),
        correlation_id=_get_correlation_id(),
    )
    return boto3.Session(**session_kwargs)


def get_aws_client(
    service: str,
    aws_config: AWSConfig | None = None,
    region: str = "",
) -> Any:
    """
    Build a boto3 client for a specific AWS service using tenant credentials.

    Examples:
        ec2 = get_aws_client("ec2", tenant.aws)
        ssm = get_aws_client("ssm", tenant.aws)
        logs = get_aws_client("logs", tenant.aws)

    AWS APIs/permissions used:
      - Initializes boto3 service client for caller-owned API operations.
    """
    session = get_aws_session(aws_config, region)
    logger.debug(
        "aws_client_created",
        service=service,
        region=region or (aws_config.region if aws_config else ""),
        correlation_id=_get_correlation_id(),
    )
    return session.client(service)


def _assume_role_session(
    role_arn: str,
    external_id: str = "",
    region: str = "ap-south-1",
    base_config: AWSConfig | None = None,
) -> Any:  # boto3.Session
    """
    Assume an IAM role via STS and return a session with temporary credentials.

    If the tenant also has static keys or a profile, those are used as the
    base credentials for the AssumeRole call (cross-account from a central account).

    AWS APIs/permissions used:
      - STS AssumeRole (`sts:AssumeRole`) to obtain temporary session credentials.
    """
    import boto3  # type: ignore[import-not-found]

    # Build a base session for the STS call
    base_kwargs: dict = {"region_name": region}

    if base_config:
        # Use static keys as base for cross-account assumption
        access_key, secret_key = _load_static_credentials(base_config)
        if access_key and secret_key:
            base_kwargs["aws_access_key_id"] = access_key
            base_kwargs["aws_secret_access_key"] = secret_key
        elif base_config.profile:
            base_kwargs["profile_name"] = base_config.profile

    base_session = boto3.Session(**base_kwargs)
    sts = base_session.client("sts")

    assume_kwargs: dict = {
        "RoleArn": role_arn,
        "RoleSessionName": "airex-investigation",
        "DurationSeconds": 3600,
    }
    if external_id:
        assume_kwargs["ExternalId"] = external_id

    logger.info(
        "aws_auth_assuming_role",
        role_arn=role_arn,
        has_external_id=bool(external_id),
        correlation_id=_get_correlation_id(),
    )

    response = sts.assume_role(**assume_kwargs)
    creds = response["Credentials"]

    return boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
        region_name=region,
    )


def _load_static_credentials(aws_config: AWSConfig) -> tuple[str, str]:
    """
    Load static AWS credentials from a file or inline config.

    Credentials file can be JSON or YAML:
      {
        "access_key_id": "AKIA...",
        "secret_access_key": "wJa..."
      }

    Returns: (access_key_id, secret_access_key) or ("", "")
    """
    # Check inline first
    if aws_config.access_key_id and aws_config.secret_access_key:
        return aws_config.access_key_id, aws_config.secret_access_key

    # Try credentials file
    creds_file = aws_config.credentials_file
    if not creds_file:
        return "", ""

    if not os.path.exists(creds_file):
        logger.warning(
            "aws_credentials_file_not_found",
            path=creds_file,
            correlation_id=_get_correlation_id(),
        )
        return "", ""

    try:
        with open(creds_file, encoding="utf-8") as f:
            content = f.read().strip()

        # Try JSON first
        if content.startswith("{"):
            data = json.loads(content)
        else:
            import yaml  # type: ignore[import-untyped]

            data = yaml.safe_load(content)

        access_key = data.get("access_key_id") or data.get("aws_access_key_id") or ""
        secret_key = (
            data.get("secret_access_key") or data.get("aws_secret_access_key") or ""
        )

        if access_key and secret_key:
            logger.info(
                "aws_credentials_loaded_from_file",
                path=creds_file,
                correlation_id=_get_correlation_id(),
            )
            return access_key, secret_key

        logger.warning(
            "aws_credentials_file_incomplete",
            path=creds_file,
            correlation_id=_get_correlation_id(),
        )
        return "", ""

    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.error(
            "aws_credentials_file_read_failed",
            path=creds_file,
            error=str(exc),
            correlation_id=_get_correlation_id(),
        )
        return "", ""
