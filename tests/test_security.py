"""Tests for JWT token creation and verification."""

import uuid

import pytest

from airex_core.core.security import create_access_token, decode_access_token, TokenData


class TestJWTTokens:
    def test_create_and_decode_roundtrip(self):
        tid = uuid.uuid4()
        token = create_access_token(tid, "user@example.com")
        data = decode_access_token(token)
        assert data.tenant_id == tid
        assert data.sub == "user@example.com"

    def test_invalid_token_raises(self):
        with pytest.raises(ValueError, match="Invalid token"):
            decode_access_token("not.a.valid.token")

    def test_empty_token_raises(self):
        with pytest.raises(ValueError):
            decode_access_token("")

    def test_tampered_token_raises(self):
        tid = uuid.uuid4()
        token = create_access_token(tid, "user@example.com")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(ValueError):
            decode_access_token(tampered)

    def test_different_tenants_different_tokens(self):
        t1 = create_access_token(uuid.uuid4(), "user1")
        t2 = create_access_token(uuid.uuid4(), "user2")
        assert t1 != t2
