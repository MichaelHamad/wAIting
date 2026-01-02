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


class TestMatchesPromptPattern:
    """Tests for matches_prompt_pattern function."""

    def test_question_mark_suffix(self):
        """Lines ending with ? should match."""
        assert matches_prompt_pattern("Continue?")
        assert matches_prompt_pattern("Are you sure? ")

    def test_colon_suffix(self):
        """Lines ending with : should match."""
        assert matches_prompt_pattern("Enter name:")
        assert matches_prompt_pattern("Password: ")

    def test_greater_than_suffix(self):
        """Lines ending with > should match."""
        assert matches_prompt_pattern(">>> ")
        assert matches_prompt_pattern("> ")

    def test_yes_no_brackets(self):
        """Yes/no prompts in brackets should match."""
        assert matches_prompt_pattern("[Y/n]")
        assert matches_prompt_pattern("[y/N]")
        assert matches_prompt_pattern("Continue? [yes/no]")
        assert matches_prompt_pattern("Proceed (y/n)")
        assert matches_prompt_pattern("Confirm (yes/no)?")

    def test_password_prompt(self):
        """Password prompts should match."""
        assert matches_prompt_pattern("Password:")
        assert matches_prompt_pattern("Enter password")
        assert matches_prompt_pattern("sudo password for user:")

    def test_input_prompt(self):
        """Input prompts should match."""
        assert matches_prompt_pattern("Enter input:")
        assert matches_prompt_pattern("Input required")

    def test_enter_prompt(self):
        """Enter prompts should match."""
        assert matches_prompt_pattern("Enter your name:")
        assert matches_prompt_pattern("Please enter a value")

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
