"""Utility functions for wait detection."""

import re

# ANSI escape sequence pattern
_ANSI_PATTERN = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[()][AB012]')

# Prompt patterns that suggest waiting for input
_PROMPT_PATTERNS = [
    r'\?\s*$',           # ends with ?
    r':\s*$',            # ends with :
    r'>\s*$',            # ends with >
    r'\[Y/n\]',          # [Y/n] style
    r'\[y/N\]',          # [y/N] style
    r'\[yes/no\]',       # [yes/no] style
    r'\(y/n\)',          # (y/n) style
    r'\(yes/no\)',       # (yes/no) style
    r'password',         # password prompts (case insensitive)
    r'enter\s+',         # "Enter something:"
    r'input',            # input prompts
]

_PROMPT_REGEX = re.compile('|'.join(_PROMPT_PATTERNS), re.IGNORECASE)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return _ANSI_PATTERN.sub('', text)


def matches_prompt_pattern(line: str) -> bool:
    """Check if a line matches common prompt patterns."""
    cleaned = strip_ansi(line).strip()
    if not cleaned:
        return False
    return bool(_PROMPT_REGEX.search(cleaned))
