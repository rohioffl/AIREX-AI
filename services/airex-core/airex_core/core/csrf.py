"""
Double-submit cookie CSRF protection.

For state-changing requests (POST/PUT/PATCH/DELETE) from browser clients,
validates that the X-CSRF-Token header matches the airex_csrf cookie.

Skipped for:
  - GET/HEAD/OPTIONS requests
  - Requests with no cookies (API clients)
  - Webhook endpoints (use signature verification instead)
"""

import secrets

import structlog
from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = structlog.get_logger()

CSRF_COOKIE_NAME = "airex_csrf"
CSRF_HEADER_NAME = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
EXEMPT_PATHS = {
    "/api/v1/webhooks/",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/set-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/google",
    "/api/v1/auth/accept-invitation-with-google",
    "/health",
    "/metrics",
}


def _get_correlation_id(request: Request) -> str | None:
    """Return correlation id from request headers when present."""
    return request.headers.get("x-correlation-id")


class CSRFMiddleware(BaseHTTPMiddleware):
    """Double-submit cookie CSRF protection middleware."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Validate CSRF token for state-changing browser requests."""
        # Set CSRF cookie if not present
        csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
        correlation_id = _get_correlation_id(request)

        if request.method not in SAFE_METHODS:
            # Skip exempted paths
            path = request.url.path
            if not any(path.startswith(exempt) for exempt in EXEMPT_PATHS):
                # Only enforce for browser requests (those that send cookies)
                if csrf_cookie:
                    csrf_header = request.headers.get(CSRF_HEADER_NAME)
                    if not csrf_header or csrf_header != csrf_cookie:
                        logger.warning(
                            "csrf_validation_failed",
                            correlation_id=correlation_id,
                            path=path,
                            has_cookie=bool(csrf_cookie),
                            has_header=bool(csrf_header),
                        )
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="CSRF validation failed",
                        )

        response = await call_next(request)

        # Set CSRF cookie on every response if not present
        if not csrf_cookie:
            token = secrets.token_hex(32)
            response.set_cookie(
                CSRF_COOKIE_NAME,
                token,
                httponly=False,  # Must be readable by JS
                samesite="strict",
                secure=False,  # Set True in production with HTTPS
                max_age=86400,
                path="/",
            )

        return response
