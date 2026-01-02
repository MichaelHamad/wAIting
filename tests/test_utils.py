"""Tests for utility functions."""

import pytest

from waiting.utils import strip_ansi, matches_prompt_pattern


class TestStripAnsi:
    """Tests for strip_ansi function."""

    def test_no_ansi(self):
        """Plain text should be unchanged."""
        assert strip_ansi("hello world") == "hello world"

    def test_color_codes(self):
        """ANSI color codes should be stripped."""
        # Red text
        assert strip_ansi("\x1b[31mred\x1b[0m") == "red"
        # Bold green
        assert strip_ansi("\x1b[1;32mbold green\x1b[0m") == "bold green"

    def test_cursor_movement(self):
        """Cursor movement codes should be stripped."""
        assert strip_ansi("\x1b[2Jcleared") == "cleared"
        assert strip_ansi("\x1b[Hmoved") == "moved"

    def test_osc_sequences(self):
        """OSC sequences (title changes) should be stripped."""
        assert strip_ansi("\x1b]0;title\x07text") == "text"

    def test_empty_string(self):
        """Empty string should return empty."""
        assert strip_ansi("") == ""

    def test_mixed_content(self):
        """Mixed ANSI and plain text."""
        text = "\x1b[32m$ \x1b[0mcommand \x1b[1marg\x1b[0m"
        assert strip_ansi(text) == "$ command arg"

    def test_private_mode_sequences(self):
        """Private mode CSI sequences (like [?2026l) should be stripped."""
        # Synchronized update end - this was causing the bug
        assert strip_ansi("\x1b[?2026l") == ""
        assert strip_ansi("\x1b[?2026ltext") == "text"
        # Cursor hide/show
        assert strip_ansi("\x1b[?25l") == ""
        assert strip_ansi("\x1b[?25h") == ""
        # Alternate screen
        assert strip_ansi("\x1b[?1049h") == ""
        assert strip_ansi("\x1b[?1049l") == ""
        # Multiple private mode sequences
        assert strip_ansi("\x1b[?25l\x1b[?2026lEnter name:") == "Enter name:"

    def test_dec_private_sequences(self):
        """DEC private mode sequences should be stripped."""
        # These are used by terminals for mode switching
        assert strip_ansi("\x1b[?2004h") == ""  # Bracketed paste mode on
        assert strip_ansi("\x1b[?2004l") == ""  # Bracketed paste mode off


class TestMatchesPromptPattern:
    """Tests for matches_prompt_pattern function.

    NOTE: Pattern matching was tightened to reduce false positives.
    Only high-confidence patterns are matched now.
    Removed: generic `?$`, `:$`, `>$` (too common in normal output).
    """

    def test_yes_no_brackets(self):
        """Yes/no prompts in brackets should match (high confidence)."""
        assert matches_prompt_pattern("[Y/n]")
        assert matches_prompt_pattern("[y/N]")
        assert matches_prompt_pattern("Continue? [yes/no]")
        assert matches_prompt_pattern("Proceed (y/n)")
        assert matches_prompt_pattern("Confirm (yes/no)?")

    def test_password_prompt(self):
        """Password prompts should match."""
        assert matches_prompt_pattern("Password:")
        assert matches_prompt_pattern("Enter your password:")
        assert matches_prompt_pattern("sudo password")

    def test_interactive_selectors(self):
        """Interactive menu selectors should match (Claude Code style)."""
        assert matches_prompt_pattern("❯ Yes")
        assert matches_prompt_pattern("  ❯ Accept changes")
        assert matches_prompt_pattern("◯ Option 1")
        assert matches_prompt_pattern("◉ Selected option")

    def test_explicit_prompt_keywords(self):
        """Explicit prompt phrases should match."""
        assert matches_prompt_pattern("Do you want to continue?")
        assert matches_prompt_pattern("Would you like to proceed?")
        assert matches_prompt_pattern("Press Enter to continue")
        assert matches_prompt_pattern("Hit enter to confirm")

    def test_confirmation_prompts(self):
        """Confirmation prompts with ? should match."""
        assert matches_prompt_pattern("Confirm?")
        assert matches_prompt_pattern("Proceed?")
        assert matches_prompt_pattern("Continue?")
        assert matches_prompt_pattern("Overwrite?")

    def test_default_value_prompts(self):
        """Default value prompts should match."""
        assert matches_prompt_pattern("Name (default: foo):")
        assert matches_prompt_pattern("Port (default 8080)")

    def test_shell_prompts(self):
        """Bare shell prompts should match."""
        assert matches_prompt_pattern("$ ")
        assert matches_prompt_pattern("# ")
        assert matches_prompt_pattern("> ")

    def test_non_matching_removed_patterns(self):
        """Previously matched patterns that are now correctly rejected."""
        # These used to match but caused false positives
        assert not matches_prompt_pattern("Building: 45%")  # colon in progress
        assert not matches_prompt_pattern("file.ts:123")    # file:line format
        assert not matches_prompt_pattern("12:34:56")       # timestamp
        assert not matches_prompt_pattern(">>> import os")  # python REPL output
        assert not matches_prompt_pattern("Enter name:")    # generic colon (not password)
        assert not matches_prompt_pattern("1. First item")  # numbered list

    def test_non_matching(self):
        """Regular output should not match."""
        assert not matches_prompt_pattern("Processing...")
        assert not matches_prompt_pattern("Done!")
        assert not matches_prompt_pattern("File saved")
        assert not matches_prompt_pattern("100%")

    def test_empty_string(self):
        """Empty string should not match."""
        assert not matches_prompt_pattern("")
        assert not matches_prompt_pattern("   ")

    def test_with_ansi_codes(self):
        """Should work with ANSI codes present."""
        assert matches_prompt_pattern("\x1b[32mContinue?\x1b[0m")
        assert matches_prompt_pattern("\x1b[1mPassword:\x1b[0m")
