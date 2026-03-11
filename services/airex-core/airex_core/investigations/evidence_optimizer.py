"""
Evidence output optimizer.

Cleans and optimizes investigation evidence to make it more readable
and remove unnecessary verbosity while preserving critical information.
"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# Maximum length for a single line before truncation
_MAX_LINE_LENGTH = 200

# Patterns to identify and clean up
_LONG_COMMAND_PATTERN = re.compile(r'^.*?/bin/bash.*?--\s+(.+)$', re.MULTILINE)
_PYTHON_COMMAND_PATTERN = re.compile(r'^.*?python.*?-c\s+"\s*(.+?)\s*"\s*$', re.MULTILINE | re.DOTALL)


def optimize_evidence_output(raw_output: str, alert_type: str = "") -> str:
    """
    Optimize evidence output by:
    1. Truncating extremely long lines
    2. Removing redundant sections
    3. Cleaning up command outputs
    4. Preserving critical information
    """
    if not raw_output:
        return raw_output

    lines = raw_output.split('\n')
    optimized_lines: list[str] = []
    skip_next_empty = False

    for i, line in enumerate(lines):
        # Skip redundant empty lines
        if not line.strip():
            if skip_next_empty:
                continue
            skip_next_empty = True
            optimized_lines.append('')
            continue

        skip_next_empty = False

        # Truncate extremely long lines (likely command outputs or errors)
        if len(line) > _MAX_LINE_LENGTH:
            # Preserve the beginning and end of long lines
            truncated = line[:150] + ' ... [truncated] ... ' + line[-50:]
            optimized_lines.append(truncated)
            continue

        # Clean up long bash/python command invocations in process lists
        # Only process lines that are in process list format (have PID, CPU%, MEM% columns)
        if len(line) > _MAX_LINE_LENGTH and ('/bin/bash' in line or ('python' in line and '-c' in line)):
            # Check if this looks like a process list line (has numbers that could be PID, CPU%, MEM%)
            parts = line.split()
            if len(parts) >= 4:
                try:
                    # Try to parse as process list: USER PID %CPU %MEM ...
                    float(parts[2])  # %CPU should be a number
                    float(parts[3])  # %MEM should be a number
                    # This is a process list line - simplify it
                    if '/bin/bash' in line:
                        # Keep: USER PID %CPU %MEM VSZ RSS TTY STAT START TIME
                        # Simplify the command part
                        cmd_start_idx = 10 if len(parts) > 10 else len(parts)
                        simplified = ' '.join(parts[:cmd_start_idx])
                        if len(line) > _MAX_LINE_LENGTH:
                            simplified += ' [bash command - truncated]'
                        optimized_lines.append(simplified)
                        continue
                    elif 'python' in line and '-c' in line:
                        cmd_start_idx = 10 if len(parts) > 10 else len(parts)
                        simplified = ' '.join(parts[:cmd_start_idx])
                        if len(line) > _MAX_LINE_LENGTH:
                            simplified += ' [python script - truncated]'
                        optimized_lines.append(simplified)
                        continue
                except (ValueError, IndexError):
                    # Not a process list line, fall through to normal truncation
                    pass

        optimized_lines.append(line)

    # Remove trailing empty lines
    while optimized_lines and not optimized_lines[-1].strip():
        optimized_lines.pop()

    return '\n'.join(optimized_lines)


def summarize_evidence(raw_output: str, max_length: int = 5000) -> str:
    """
    Create a summary of evidence, truncating if too long while preserving structure.
    """
    if len(raw_output) <= max_length:
        return raw_output

    # Try to preserve important sections
    sections = raw_output.split('\n\n')
    summary_sections: list[str] = []
    current_length = 0

    for section in sections:
        section_length = len(section) + 2  # +2 for \n\n
        if current_length + section_length > max_length:
            # Add a truncation notice
            summary_sections.append(f'\n... [Output truncated: {len(raw_output) - current_length} more characters] ...')
            break
        summary_sections.append(section)
        current_length += section_length

    return '\n\n'.join(summary_sections)
