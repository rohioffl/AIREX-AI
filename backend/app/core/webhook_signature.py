"""
Webhook HMAC signature verification.

Validates incoming webhook payloads using HMAC-SHA256 signatures.
If WEBHOOK_SECRET is not configured, verification is skipped (dev mode).
"""

import hashlib
import hmac

import structlog
from fastapi import HTTPException, Header, Request, status

from app.core.config import settings

logger = structlog.get_logger()


async def verify_webhook_signature(
    request: Request,
    x_webhook_signature: str | None = Header(None),
    x_hub_signature_256: str | None = Header(None),
) -> None:
    """
    Verify webhook signature from X-Webhook-Signature or X-Hub-Signature-256.

    Supports two formats:
      - X-Webhook-Signature: sha256=<hex>
      - X-Hub-Signature-256: sha256=<hex> (GitHub-style)

    If WEBHOOK_SECRET is empty, verification is skipped (dev/test mode).
    """
    secret = getattr(settings, "WEBHOOK_SECRET", "")
    if not secret:
        return

    sig_header = x_webhook_signature or x_hub_signature_256
    if sig_header is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing webhook signature header",
        )

    # Parse "sha256=<hex>" format
    if sig_header.startswith("sha256="):
        expected_sig = sig_header[7:]
    else:
        expected_sig = sig_header

    body = await request.body()
    computed = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(computed, expected_sig):
        logger.warning(
            "webhook_signature_invalid",
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )
