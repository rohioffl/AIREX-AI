"""Defense-in-depth input sanitization for tool integrations.

AIREX already prohibits LLM-generated shell commands via whitelisted action
templates (SSM / OS Login).  This module adds an **additional layer** for
any future tool integrations that may process user or probe data as inputs.

Usage:
    from airex_core.core.command_sanitizer import sanitize_host, sanitize_command

    safe_host = sanitize_host(untrusted_hostname)
    safe_cmd  = sanitize_command(raw_cmd, allowed_commands=ALLOWED_TOOLS)
"""

from __future__ import annotations

import re

# Characters that could enable shell injection if interpolated into a
# command string.  We reject rather than escape — safety over flexibility.
_SHELL_DANGEROUS = re.compile(r"[;&|`$(){}!\\\n\r]")

# Hostnames / IPs: alphanumeric, dots, hyphens, colons (IPv6).
_HOST_VALID = re.compile(r"^[a-zA-Z0-9.\-:]+$")

# Tool/command names: alphanumeric, hyphens, underscores.
_TOOL_NAME_VALID = re.compile(r"^[a-zA-Z0-9_\-]+$")


class SanitizationError(ValueError):
    """Raised when an input fails sanitization."""


def sanitize_host(value: str) -> str:
    """Validate and return a safe hostname or IP address.

    Raises ``SanitizationError`` if the value contains dangerous characters
    or does not look like a valid host.
    """
    value = value.strip()
    if not value:
        raise SanitizationError("Host value must not be empty")
    if len(value) > 253:
        raise SanitizationError(f"Host value too long: {len(value)} chars")
    if not _HOST_VALID.match(value):
        raise SanitizationError(f"Host contains invalid characters: {value!r}")
    return value


def sanitize_command(
    cmd: str,
    *,
    allowed_commands: frozenset[str],
) -> str:
    """Validate that ``cmd`` is in the allowed set and contains no injection chars.

    Args:
        cmd: The tool/command name to validate.
        allowed_commands: Frozenset of permitted command names.

    Returns:
        The validated command name (stripped).

    Raises:
        SanitizationError: If the command is not allowed or contains
            dangerous characters.
    """
    cmd = cmd.strip()
    if not cmd:
        raise SanitizationError("Command must not be empty")
    if _SHELL_DANGEROUS.search(cmd):
        raise SanitizationError(f"Command contains dangerous characters: {cmd!r}")
    if not _TOOL_NAME_VALID.match(cmd):
        raise SanitizationError(f"Command name contains invalid characters: {cmd!r}")
    if cmd not in allowed_commands:
        raise SanitizationError(
            f"Command {cmd!r} not in allowed set: {sorted(allowed_commands)}"
        )
    return cmd


def sanitize_argument(value: str, *, max_length: int = 1024) -> str:
    """Sanitize a single argument value for safe interpolation.

    Strips whitespace, rejects shell-dangerous characters, and enforces
    a maximum length.

    Returns:
        The sanitized value.

    Raises:
        SanitizationError: If the value is unsafe.
    """
    value = value.strip()
    if not value:
        raise SanitizationError("Argument must not be empty")
    if len(value) > max_length:
        raise SanitizationError(f"Argument too long: {len(value)} chars (max {max_length})")
    if _SHELL_DANGEROUS.search(value):
        raise SanitizationError(f"Argument contains dangerous characters: {value!r}")
    return value
