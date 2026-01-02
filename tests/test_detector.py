"""Tests for wait detector."""

import time
from unittest.mock import patch, MagicMock

import pytest

from waiting.detector import (
    WaitDetector,
    State,
    is_raw_mode,
    STALL_THRESHOLD,
    NAG_INTERVAL,
)
from waiting.events import WaitingEntered, WaitingExited


class TestIsRawMode:
    """Tests for is_raw_mode function."""

    def test_raw_mode_detected(self):
        """Should detect raw mode when ICANON is off."""
        with patch('waiting.detector.termios') as mock_termios:
            mock_termios.ICANON = 0x2
            mock_termios.tcgetattr.return_value = [0, 0, 0, 0, 0, 0, []]  # ICANON off
            assert is_raw_mode(0) is True

    def test_canonical_mode_detected(self):
        """Should detect canonical mode when ICANON is on."""
        with patch('waiting.detector.termios') as mock_termios:
            mock_termios.ICANON = 0x2
            mock_termios.tcgetattr.return_value = [0, 0, 0, 0x2, 0, 0, []]  # ICANON on
            assert is_raw_mode(0) is False

    def test_error_handling(self):
        """Should return False on errors."""
        with patch('waiting.detector.termios.tcgetattr', side_effect=OSError("Not a tty")):
            assert is_raw_mode(0) is False


class TestWaitDetector:
    """Tests for WaitDetector class."""

    def test_initial_state(self):
        """Detector should start in RUNNING state."""
        detector = WaitDetector()
        assert detector.state == State.RUNNING

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
        assert detector.last_line == "line3"

    def test_record_output_skips_empty_lines(self):
        """Should use last non-empty line."""
        detector = WaitDetector()
        detector.record_output(b"line1\n\n\n")
        assert detector.last_line == "line1"

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

        # Simulate stalled output with prompt
        detector.last_output_time = time.monotonic() - STALL_THRESHOLD - 1
        detector.last_line = "Enter password:"

        with patch('waiting.detector.is_raw_mode', return_value=False):
            result = detector.check(0)

        assert detector.state == State.WAITING
        assert result is True  # Should alert
        assert len(events) == 1
        assert isinstance(events[0], WaitingEntered)

    def test_stall_without_prompt_no_waiting(self):
        """Stalled output without prompt pattern should not trigger waiting."""
        detector = WaitDetector()

        detector.last_output_time = time.monotonic() - STALL_THRESHOLD - 1
        detector.last_line = "Processing..."

        with patch('waiting.detector.is_raw_mode', return_value=False):
            result = detector.check(0)

        assert detector.state == State.RUNNING
        assert result is False

    def test_raw_mode_triggers_waiting(self):
        """Raw mode should trigger waiting state."""
        events = []
        detector = WaitDetector(on_event=events.append)

        with patch('waiting.detector.is_raw_mode', return_value=True):
            result = detector.check(0)

        assert detector.state == State.WAITING
        assert result is True
        assert isinstance(events[0], WaitingEntered)

    def test_nag_interval(self):
        """Should alert again after nag interval."""
        detector = WaitDetector()
        detector.state = State.WAITING
        detector.waiting_since = time.monotonic() - NAG_INTERVAL - 1
        detector.last_alert_time = time.monotonic() - NAG_INTERVAL - 1

        with patch('waiting.detector.is_raw_mode', return_value=True):
            result = detector.check(0)

        assert result is True  # Should nag


class TestStateTransitions:
    """Test state machine transitions."""

    def test_running_to_waiting_to_running(self):
        """Full cycle: RUNNING -> WAITING -> RUNNING."""
        events = []
        detector = WaitDetector(on_event=events.append)

        # Start in RUNNING
        assert detector.state == State.RUNNING

        # Trigger waiting via raw mode
        with patch('waiting.detector.is_raw_mode', return_value=True):
            detector.check(0)

        assert detector.state == State.WAITING
        assert isinstance(events[0], WaitingEntered)

        # Input received - should exit waiting
        detector.record_input()

        assert detector.state == State.RUNNING
        assert isinstance(events[1], WaitingExited)
        assert events[1].reason == "input"
