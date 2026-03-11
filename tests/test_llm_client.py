"""Tests for LLM client circuit breaker."""

import pytest

from airex_core.llm.client import CircuitBreaker


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker(threshold=3, cooldown_seconds=300)
        assert cb.can_attempt() is True
        assert cb.is_open is False

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(threshold=3, cooldown_seconds=300)
        cb.record_failure()
        cb.record_failure()
        assert cb.can_attempt() is True
        cb.record_failure()
        assert cb.is_open is True
        assert cb.can_attempt() is False

    def test_success_resets_failures(self):
        cb = CircuitBreaker(threshold=3, cooldown_seconds=300)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.is_open is False

    def test_half_open_after_cooldown(self):
        cb = CircuitBreaker(threshold=1, cooldown_seconds=0)
        cb.record_failure()
        assert cb.is_open is True
        # Cooldown of 0 means it should reopen immediately
        assert cb.can_attempt() is True
        assert cb.is_open is False

    def test_failure_count_tracks_correctly(self):
        cb = CircuitBreaker(threshold=5, cooldown_seconds=300)
        for i in range(4):
            cb.record_failure()
            assert cb.failure_count == i + 1
        assert cb.is_open is False
        cb.record_failure()
        assert cb.is_open is True
