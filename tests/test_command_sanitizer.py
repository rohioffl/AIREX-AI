"""Tests for airex_core.core.command_sanitizer — defense-in-depth input sanitization."""

import pytest

from airex_core.core.command_sanitizer import (
    SanitizationError,
    sanitize_argument,
    sanitize_command,
    sanitize_host,
)

ALLOWED = frozenset({"restart_service", "clear_logs", "check_disk"})


# --- sanitize_host ---

class TestSanitizeHost:
    def test_valid_hostname(self):
        assert sanitize_host("web-01.prod.example.com") == "web-01.prod.example.com"

    def test_valid_ipv4(self):
        assert sanitize_host("10.0.0.1") == "10.0.0.1"

    def test_valid_ipv6(self):
        assert sanitize_host("::1") == "::1"

    def test_strips_whitespace(self):
        assert sanitize_host("  10.0.0.1  ") == "10.0.0.1"

    def test_empty_raises(self):
        with pytest.raises(SanitizationError, match="must not be empty"):
            sanitize_host("")

    def test_whitespace_only_raises(self):
        with pytest.raises(SanitizationError, match="must not be empty"):
            sanitize_host("   ")

    def test_too_long_raises(self):
        with pytest.raises(SanitizationError, match="too long"):
            sanitize_host("a" * 254)

    def test_max_length_allowed(self):
        host = "a" * 253
        assert sanitize_host(host) == host

    @pytest.mark.parametrize("bad", [
        "host;rm -rf /",
        "host|cat /etc/passwd",
        "host`whoami`",
        "host$(id)",
        "host\ninjected",
        "host&bg",
        "host\\escape",
    ])
    def test_shell_injection_rejected(self, bad):
        with pytest.raises(SanitizationError, match="invalid characters"):
            sanitize_host(bad)


# --- sanitize_command ---

class TestSanitizeCommand:
    def test_valid_allowed_command(self):
        assert sanitize_command("restart_service", allowed_commands=ALLOWED) == "restart_service"

    def test_strips_whitespace(self):
        assert sanitize_command("  clear_logs  ", allowed_commands=ALLOWED) == "clear_logs"

    def test_not_in_allowed_set_raises(self):
        with pytest.raises(SanitizationError, match="not in allowed set"):
            sanitize_command("drop_database", allowed_commands=ALLOWED)

    def test_empty_raises(self):
        with pytest.raises(SanitizationError, match="must not be empty"):
            sanitize_command("", allowed_commands=ALLOWED)

    @pytest.mark.parametrize("bad", [
        "restart;rm",
        "cmd|pipe",
        "cmd`inject`",
        "cmd$(sub)",
    ])
    def test_shell_dangerous_rejected(self, bad):
        with pytest.raises(SanitizationError, match="dangerous characters"):
            sanitize_command(bad, allowed_commands=frozenset({bad}))

    def test_invalid_name_chars_rejected(self):
        with pytest.raises(SanitizationError, match="invalid characters"):
            sanitize_command("cmd with spaces", allowed_commands=frozenset({"cmd with spaces"}))


# --- sanitize_argument ---

class TestSanitizeArgument:
    def test_valid_argument(self):
        assert sanitize_argument("nginx") == "nginx"

    def test_strips_whitespace(self):
        assert sanitize_argument("  myservice  ") == "myservice"

    def test_empty_raises(self):
        with pytest.raises(SanitizationError, match="must not be empty"):
            sanitize_argument("")

    def test_too_long_raises(self):
        with pytest.raises(SanitizationError, match="too long"):
            sanitize_argument("a" * 1025)

    def test_custom_max_length(self):
        with pytest.raises(SanitizationError, match="too long"):
            sanitize_argument("abcdef", max_length=5)

    def test_at_max_length_ok(self):
        assert sanitize_argument("abcde", max_length=5) == "abcde"

    @pytest.mark.parametrize("bad", [
        "arg;inject",
        "arg|pipe",
        "arg`tick`",
        "arg$(sub)",
        "arg\nnewline",
    ])
    def test_shell_dangerous_rejected(self, bad):
        with pytest.raises(SanitizationError, match="dangerous characters"):
            sanitize_argument(bad)
