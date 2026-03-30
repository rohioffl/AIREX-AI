"""Unit tests for airex_core.cloud.secret_resolver.

Mocks boto3 so no real AWS credentials or network access are required.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from airex_core.cloud.secret_resolver import (
    SecretResolverError,
    get_secret_json,
    invalidate,
    invalidate_all,
)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_boto_client(secret_string: str = '{"key": "value"}', error_code: str = ""):
    """Return a mock boto3 secretsmanager client."""
    client = MagicMock()
    if error_code:
        from botocore.exceptions import ClientError  # type: ignore[import-not-found]

        client.get_secret_value.side_effect = ClientError(
            {"Error": {"Code": error_code, "Message": "test error"}},
            "GetSecretValue",
        )
    else:
        client.get_secret_value.return_value = {"SecretString": secret_string}
    return client


def _patched_boto(client):
    """Context manager: patch boto3.client (module-level) to return *client*.

    secret_resolver imports boto3 locally inside _fetch_from_aws, so the patch
    target must be the real boto3.client attribute, not a module-level reference.
    """
    return patch("boto3.client", return_value=client)


# ── get_secret_json ────────────────────────────────────────────────────────────


def test_get_secret_json_basic():
    """Happy-path: fetches and parses a JSON secret."""
    invalidate_all()
    client = _make_boto_client('{"version": 1, "kind": "aws_credentials"}')
    with _patched_boto(client):
        result = get_secret_json("arn:aws:secretsmanager:us-east-1:123456789012:secret:test")
    assert result == {"version": 1, "kind": "aws_credentials"}
    client.get_secret_value.assert_called_once()


def test_get_secret_json_cache_hit():
    """Second call within TTL hits cache, not AWS."""
    invalidate_all()
    client = _make_boto_client('{"cached": true}')
    arn = "arn:aws:secretsmanager:us-east-1:000000000000:secret:cached"
    with _patched_boto(client):
        first = get_secret_json(arn)
        second = get_secret_json(arn)
    assert first == second == {"cached": True}
    # Only one real AWS call despite two get_secret_json calls
    assert client.get_secret_value.call_count == 1


def test_get_secret_json_force_refresh():
    """force_refresh=True bypasses cache."""
    invalidate_all()
    client = _make_boto_client('{"v": 1}')
    arn = "arn:aws:secretsmanager:us-east-1:000000000000:secret:refresh"
    with _patched_boto(client):
        get_secret_json(arn)
        get_secret_json(arn, force_refresh=True)
    assert client.get_secret_value.call_count == 2


def test_get_secret_json_empty_arn_raises():
    """Empty ARN raises ValueError immediately."""
    with pytest.raises(ValueError, match="must not be empty"):
        get_secret_json("")


def test_get_secret_json_aws_client_error():
    """ClientError from AWS is re-raised as SecretResolverError."""
    invalidate_all()
    client = _make_boto_client(error_code="ResourceNotFoundException")
    arn = "arn:aws:secretsmanager:us-east-1:000000000000:secret:missing"
    with _patched_boto(client):
        with pytest.raises(SecretResolverError, match="ResourceNotFoundException"):
            get_secret_json(arn)


def test_get_secret_json_no_secret_string():
    """Absent SecretString raises SecretResolverError."""
    invalidate_all()
    client = MagicMock()
    client.get_secret_value.return_value = {"SecretString": ""}
    arn = "arn:aws:secretsmanager:us-east-1:000000000000:secret:empty"
    with _patched_boto(client):
        with pytest.raises(SecretResolverError, match="no SecretString"):
            get_secret_json(arn)


def test_get_secret_json_invalid_json():
    """Non-JSON SecretString raises SecretResolverError."""
    invalidate_all()
    client = _make_boto_client("not-json{{")
    arn = "arn:aws:secretsmanager:us-east-1:000000000000:secret:badjson"
    with _patched_boto(client):
        with pytest.raises(SecretResolverError, match="not valid JSON"):
            get_secret_json(arn)


def test_get_secret_json_cache_expiry():
    """After TTL expires, a new fetch is performed."""
    invalidate_all()
    client = _make_boto_client('{"v": 1}')
    arn = "arn:aws:secretsmanager:us-east-1:000000000000:secret:ttltest"

    with patch("airex_core.cloud.secret_resolver._get_ttl", return_value=0):
        with _patched_boto(client):
            get_secret_json(arn)
            time.sleep(0.01)  # ensure monotonic clock advances
            get_secret_json(arn)

    # TTL=0 means every call is a miss
    assert client.get_secret_value.call_count == 2


# ── invalidate ─────────────────────────────────────────────────────────────────


def test_invalidate_removes_single_entry():
    """invalidate() removes only the targeted ARN from cache."""
    invalidate_all()
    arn_a = "arn:aws:secretsmanager:us-east-1:000000000000:secret:aaa"
    arn_b = "arn:aws:secretsmanager:us-east-1:000000000000:secret:bbb"

    client_a = _make_boto_client('{"a": 1}')
    client_b = _make_boto_client('{"b": 2}')

    with _patched_boto(client_a):
        get_secret_json(arn_a)
    with _patched_boto(client_b):
        get_secret_json(arn_b)

    invalidate(arn_a)

    # arn_a re-fetches; arn_b stays cached
    with _patched_boto(client_a):
        get_secret_json(arn_a)
    with _patched_boto(client_b):
        get_secret_json(arn_b)

    assert client_a.get_secret_value.call_count == 2  # fetched twice
    assert client_b.get_secret_value.call_count == 1  # still cached


def test_invalidate_all_clears_cache():
    """invalidate_all() forces re-fetch on next call."""
    invalidate_all()
    arn = "arn:aws:secretsmanager:us-east-1:000000000000:secret:clrtest"
    client = _make_boto_client('{"ok": true}')

    with _patched_boto(client):
        get_secret_json(arn)
    invalidate_all()
    with _patched_boto(client):
        get_secret_json(arn)

    assert client.get_secret_value.call_count == 2


# ── Thread safety ──────────────────────────────────────────────────────────────


def test_concurrent_fetches_are_safe():
    """Multiple threads fetching the same ARN do not corrupt cache."""
    invalidate_all()
    arn = "arn:aws:secretsmanager:us-east-1:000000000000:secret:threadtest"
    client = _make_boto_client('{"thread": "safe"}')
    results: list[dict] = []
    errors: list[Exception] = []

    def _fetch():
        try:
            with _patched_boto(client):
                results.append(get_secret_json(arn))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_fetch) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert all(r == {"thread": "safe"} for r in results)
