"""
Site24x7 REST API client with OAuth2 token management.

Uses the Zoho OAuth2 refresh-token flow to obtain access tokens,
cached in Redis with configurable TTL. All I/O is async (httpx).

API docs: https://www.site24x7.com/help/api/
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
import structlog

from airex_core.core.config import settings

logger = structlog.get_logger()

REDIS_TOKEN_KEY = "airex:site24x7:access_token"
class Site24x7Client:
    """Async Site24x7 REST API client with OAuth2 token caching."""

    def __init__(self, redis=None) -> None:
        self._redis = redis
        self._access_token: str | None = None
        self._token_expiry: float = 0.0

    # ── Token management ─────────────────────────────────────────

    async def _get_access_token(self) -> str:
        """Get a valid access token, refreshing from Zoho if needed."""
        # 1. Check in-memory cache
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token

        # 2. Check Redis cache
        if self._redis is not None:
            try:
                cached = await self._redis.get(REDIS_TOKEN_KEY)
                if cached:
                    data = json.loads(cached)
                    if data.get("expires_at", 0) > time.time():
                        token = data["token"]
                        self._access_token = token
                        self._token_expiry = data["expires_at"]
                        return token
            except Exception as exc:
                logger.warning("site24x7_redis_token_read_failed", error=str(exc))

        # 3. Refresh from Zoho OAuth2
        token = await self._refresh_token()
        return token

    async def _refresh_token(self) -> str:
        """Exchange refresh token for a new access token via Zoho OAuth2."""
        url = f"{settings.SITE24X7_ACCOUNTS_URL}/oauth/v2/token"
        params = {
            "client_id": settings.SITE24X7_CLIENT_ID,
            "client_secret": settings.SITE24X7_CLIENT_SECRET,
            "refresh_token": settings.SITE24X7_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        access_token = data["access_token"]
        expires_at = time.time() + settings.SITE24X7_TOKEN_CACHE_TTL

        self._access_token = access_token
        self._token_expiry = expires_at

        # Cache in Redis
        if self._redis is not None:
            try:
                cache_data = json.dumps(
                    {
                        "token": access_token,
                        "expires_at": expires_at,
                    }
                )
                await self._redis.set(
                    REDIS_TOKEN_KEY,
                    cache_data,
                    ex=settings.SITE24X7_TOKEN_CACHE_TTL,
                )
            except Exception as exc:
                logger.warning("site24x7_redis_token_write_failed", error=str(exc))

        logger.info("site24x7_token_refreshed")
        return access_token

    async def _headers(self) -> dict[str, str]:
        """Build request headers with Authorization."""
        token = await self._get_access_token()
        return {
            "Authorization": f"Zoho-oauthtoken {token}",
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json; version=2.1",
        }

    # ── API methods ──────────────────────────────────────────────

    async def _get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        """Make an authenticated GET request to Site24x7 API."""
        url = f"{settings.SITE24X7_BASE_URL}{path}"
        headers = await self._headers()

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json()

    async def get_monitor(self, monitor_id: str) -> dict[str, Any]:
        """Get monitor details by ID."""
        result = await self._get(f"/monitors/{monitor_id}")
        return result.get("data", {})

    async def get_current_status(self, monitor_id: str) -> dict[str, Any]:
        """Get current status of a monitor."""
        result = await self._get(f"/current_status/{monitor_id}")
        return result.get("data", {})

    async def get_log_report(
        self,
        monitor_id: str,
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """Get log report for a monitor within a date range.

        Dates in format: 2026-02-26T00:00:00+0530
        """
        result = await self._get(
            f"/reports/log_reports/{monitor_id}",
            params={"start_date": start_date, "end_date": end_date},
        )
        return result.get("data", {})

    async def get_performance_report(
        self,
        monitor_id: str,
        period: int = 3,
    ) -> dict[str, Any]:
        """Get performance report for a monitor.

        period: 1=last 24h, 2=last 7d, 3=last 30d
        """
        result = await self._get(
            f"/reports/performance/{monitor_id}",
            params={"period": str(period)},
        )
        return result.get("data", {})

    async def get_outage_report(
        self,
        monitor_id: str,
        period: int = 3,
    ) -> dict[str, Any]:
        """Get outage report for a monitor.

        period: 1=last 24h, 2=last 7d, 3=last 30d
        """
        result = await self._get(
            f"/reports/outage/{monitor_id}",
            params={"period": str(period)},
        )
        return result.get("data", {})

    async def get_availability_summary(
        self,
        monitor_id: str,
        period: int = 3,
    ) -> dict[str, Any]:
        """Get availability summary for a monitor.

        period: 1=last 24h, 2=last 7d, 3=last 30d
        """
        result = await self._get(
            f"/reports/availability_summary/{monitor_id}",
            params={"period": str(period)},
        )
        return result.get("data", {})

    async def get_summary(self, monitor_id: str) -> dict[str, Any]:
        """Get a combined summary: monitor details + current status."""
        monitor = await self.get_monitor(monitor_id)
        status = await self.get_current_status(monitor_id)
        return {
            "monitor": monitor,
            "current_status": status,
        }

    async def list_monitors(self) -> list[dict[str, Any]]:
        """List all monitors with id, name, and type."""
        result = await self._get("/monitors")
        data = result.get("data", [])
        return data if isinstance(data, list) else []

    async def get_all_current_status(self) -> list[dict[str, Any]]:
        """Get current status for all monitors in one call."""
        result = await self._get("/current_status", params={"apm_required": "true"})
        monitors_data = result.get("data", {})
        monitor_groups = monitors_data.get("monitors", [])
        if not monitor_groups and isinstance(monitors_data, list):
            monitor_groups = monitors_data

        flat: list[dict[str, Any]] = []
        if isinstance(monitor_groups, list):
            for item in monitor_groups:
                if isinstance(item, dict) and "monitors" in item:
                    flat.extend(item["monitors"])
                elif isinstance(item, dict) and "monitor_id" in item:
                    flat.append(item)
        return flat
