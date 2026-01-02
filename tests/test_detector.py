"""Tests for wait detector."""

import time
from unittest.mock import patch, MagicMock

import pytest

from waiting.detector import (
    WaitDetector,
    State,
    STALL_THRESHOLD,
    NAG_INTERVAL,
    USER_IDLE_THRESHOLD,
    STARTUP_GRACE,
)
from waiting.events import WaitingEntered, WaitingExited


def _bypass_startup_grace(detector: WaitDetector) -> None:
    """Helper to bypass startup grace period in tests."""
    detector.startup_time = time.monotonic() - STARTUP_GRACE - 1


class TestWaitDetector:
    """Tests for WaitDetector class."""

    def test_initial_state(self):
        """Detector should start in RUNNING state."""
        detector = WaitDetector()
        assert detector.state == State.RUNNING
        assert detector.last_visible_line == ""

    def test_record_output_updates_time(self):
        """Recording output should update last_output_time."""
        detector = WaitDetector()
        old_time = detector.last_output_time
        time.sleep(0.01)
        detector.record_output(b"test output")
        assert detector.last_output_time > old_time

    def test_record_output_extracts_last_line(self):
        """Recording output should extract the last non-empty line."""
        detector = WaitDetector()
        detector.record_output(b"line1\nline2\nline3")
        assert detector.last_visible_line == "line3"

    def test_record_output_skips_empty_lines(self):
        """Should use last non-empty line."""
        detector = WaitDetector()
        detector.record_output(b"line1\n\n\n")
        assert detector.last_visible_line == "line1"

    def test_record_input_exits_waiting(self):
        """Input should exit waiting state."""
        events = []
        detector = WaitDetector(on_event=events.append)
        detector.state = State.WAITING
        detector.waiting_since = time.monotonic()

        detector.record_input()

        assert detector.state == State.RUNNING
        assert len(events) == 1
        assert isinstance(events[0], WaitingExited)
        assert events[0].reason == "input"

    def test_record_output_exits_waiting(self):
        """Output should exit waiting state."""
        events = []
        detector = WaitDetector(on_event=events.append)
        detector.state = State.WAITING
        detector.waiting_since = time.monotonic()

        detector.record_output(b"some output")

        assert detector.state == State.RUNNING
        assert len(events) == 1
        assert isinstance(events[0], WaitingExited)
        assert events[0].reason == "output"

    def test_stall_with_prompt_triggers_waiting(self):
        """Stalled output with prompt pattern should trigger waiting."""
        events = []
        detector = WaitDetector(on_event=events.append)
        _bypass_startup_grace(detector)

        # Simulate stalled output with prompt and idle user
        # Use a high-confidence pattern (password at end of line)
        detector.last_output_time = time.monotonic() - STALL_THRESHOLD - 1
        detector.last_input_time = time.monotonic() - USER_IDLE_THRESHOLD - 1
        detector.last_visible_line = "Enter password:"

        result = detector.check(0)

        assert detector.state == State.WAITING
        assert result is True  # Should alert
        assert len(events) == 1
        assert isinstance(events[0], WaitingEntered)

    def test_stall_without_prompt_no_waiting(self):
        """Stalled output without prompt pattern should not trigger waiting."""
        detector = WaitDetector()

        detector.last_output_time = time.monotonic() - STALL_THRESHOLD - 1
        detector.last_input_time = time.monotonic() - USER_IDLE_THRESHOLD - 1
        detector.last_visible_line = "Processing..."

        result = detector.check(0)

        assert detector.state == State.RUNNING
        assert result is False

    def test_nag_interval(self):
        """Should alert again after nag interval."""
        detector = WaitDetector()
        _bypass_startup_grace(detector)
        detector.state = State.WAITING
        detector.waiting_since = time.monotonic() - NAG_INTERVAL - 1
        detector.last_alert_time = time.monotonic() - NAG_INTERVAL - 1
        detector.last_output_time = time.monotonic() - STALL_THRESHOLD - 1
        detector.last_input_time = time.monotonic() - USER_IDLE_THRESHOLD - 1
        detector.last_visible_line = "Continue? [Y/n]"  # High-confidence pattern

        result = detector.check(0)

        assert result is True  # Should nag

    def test_ansi_sequences_stripped_from_output(self):
        """ANSI sequences should be stripped when extracting visible line."""
        detector = WaitDetector()

        # Output with ANSI sequences including private mode sequences
        detector.record_output(b"\x1b[?2026lEnter your name: \x1b[0m")

        # Should extract visible text, not the escape sequences
        assert detector.last_visible_line == "Enter your name:"

    def test_private_mode_sequences_stripped(self):
        """Private mode escape sequences like [?2026l should be stripped."""
        detector = WaitDetector()

        # Simulate what Claude outputs - private mode sequences
        detector.record_output(b"\x1b[?25l\x1b[?2026lDo you want to continue?")

        assert detector.last_visible_line == "Do you want to continue?"


class TestStartupGrace:
    """Tests for startup grace period."""

    def test_no_alert_during_startup_grace(self):
        """Should not alert during the startup grace period."""
        detector = WaitDetector()
        # Do NOT bypass startup grace - we're testing it works

        # Set up conditions that would normally trigger waiting
        detector.last_output_time = time.monotonic() - STALL_THRESHOLD - 1
        detector.last_input_time = time.monotonic() - USER_IDLE_THRESHOLD - 1
        detector.last_visible_line = "Continue? [Y/n]"

        # But startup was recent, so should NOT alert
        result = detector.check(0)

        assert detector.state == State.RUNNING
        assert result is False

    def test_alert_after_startup_grace(self):
        """Should alert after startup grace period expires."""
        detector = WaitDetector()
        _bypass_startup_grace(detector)  # Simulate time passing

        # Set up conditions that trigger waiting
        detector.last_output_time = time.monotonic() - STALL_THRESHOLD - 1
        detector.last_input_time = time.monotonic() - USER_IDLE_THRESHOLD - 1
        detector.last_visible_line = "Continue? [Y/n]"

        result = detector.check(0)

        assert detector.state == State.WAITING
        assert result is True


class TestStateTransitions:
    """Test state machine transitions."""

    def test_running_to_waiting_to_running(self):
        """Full cycle: RUNNING -> WAITING -> RUNNING."""
        events = []
        detector = WaitDetector(on_event=events.append)
        _bypass_startup_grace(detector)

        # Start in RUNNING
        assert detector.state == State.RUNNING

        # Simulate stalled output, idle user, and prompt pattern
        detector.last_output_time = time.monotonic() - STALL_THRESHOLD - 1
        detector.last_input_time = time.monotonic() - USER_IDLE_THRESHOLD - 1
        detector.last_visible_line = "Continue? [Y/n]"  # High-confidence pattern

        # Trigger waiting via prompt pattern
        detector.check(0)

        assert detector.state == State.WAITING
        assert isinstance(events[0], WaitingEntered)

        # Input received - should exit waiting
        detector.record_input()

        assert detector.state == State.RUNNING
        assert isinstance(events[1], WaitingExited)
        assert events[1].reason == "input"

    def test_prompt_detection_cycle(self):
        """Full cycle with prompt pattern detection."""
        events = []
        detector = WaitDetector(on_event=events.append)
        _bypass_startup_grace(detector)

        # Receive output with a prompt (simulating Claude choice dialog)
        # The ❯ selector must be on the last visible line for pattern matching
        # ❯ is U+276F = UTF-8 bytes: \xe2\x9d\xaf
        detector.record_output(b"Do you want to make this edit?\n\xe2\x9d\xaf Yes")

        # Simulate time passing (stall)
        detector.last_output_time = time.monotonic() - STALL_THRESHOLD - 1
        detector.last_input_time = time.monotonic() - USER_IDLE_THRESHOLD - 1

        # Check should detect waiting (prompt pattern matched)
        result = detector.check(0)
        assert detector.state == State.WAITING
        assert result is True

        # User makes choice
        detector.record_input()
        assert detector.state == State.RUNNING
