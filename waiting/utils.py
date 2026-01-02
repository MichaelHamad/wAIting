"""Utility functions for wait detection."""

import re

# Comprehensive ANSI escape sequence pattern
# Matches:
# - CSI sequences: \x1b[...X (including private mode with ?, >, =)
# - OSC sequences: \x1b]...BEL or \x1b]...\x1b\\
# - Single-char escapes: \x1b followed by single char
# - Character set: \x1b(X or \x1b)X
_ANSI_PATTERN = re.compile(
    r'\x1b'                           # ESC character
    r'(?:'
        r'\[[0-9;?>=]*[a-zA-Z]'       # CSI sequences (includes ?, >, = for private modes)
        r'|\][^\x07\x1b]*(?:\x07|\x1b\\)'  # OSC sequences (BEL or ST terminated)
        r'|[()][AB012]'               # Character set selection
        r'|[@-Z\\^_]'                 # Single-character escapes
    r')'
)

# Prompt patterns that suggest waiting for input
# NOTE: Only high-confidence patterns to avoid false positives
# Removed: `:$`, `>$` (too common in normal output like "file.ts:123", logs)
# Removed: `^\s*\d+\.\s+\w` (matches any numbered list, not just menus)
_PROMPT_PATTERNS = [
    # Yes/No style prompts (very high confidence)
    r'\[Y/n\]',          # [Y/n] style
    r'\[y/N\]',          # [y/N] style
    r'\[yes/no\]',       # [yes/no] style
    r'\(y/n\)',          # (y/n) style
    r'\(yes/no\)',       # (yes/no) style

    # Password prompts (high confidence)
    r'password\s*:?\s*$',  # password prompts at end of line

    # Interactive selection menus (Claude Code, etc.)
    r'❯',                # arrow selector character (very high signal)
    r'◯',                # radio button unselected
    r'◉',                # radio button selected
    r'☐',                # checkbox unselected
    r'☑',                # checkbox selected

    # Explicit prompt keywords (high confidence)
    r'do you want to',   # permission prompts
    r'would you like',   # permission prompts
    r'press enter',      # continue prompts
    r'hit enter',        # continue prompts
    r'type here',        # text input prompts
    r'confirm\?',        # confirmation prompts with ?
    r'approve\?',        # approval prompts with ?
    r'proceed\?',        # proceed prompts with ?
    r'continue\?',       # continue prompts with ?
    r'overwrite\?',      # overwrite prompts with ?

    # Default value prompts (high confidence)
    r'\(default[^)]*\)\s*:?\s*$',  # (default: foo):

    # Shell-style empty prompts (must be the whole line)
    r'^\s*[$#>]\s*$',    # bare shell prompt
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
