"""Wait detection state machine."""

import termios
import time
from enum import Enum, auto
from typing import Callable, Optional

from .events import WaitingEntered, WaitingExited
from .utils import matches_prompt_pattern


class State(Enum):
    """Detector states."""
    RUNNING = auto()
    WAITING = auto()


# Detection thresholds
STALL_THRESHOLD = 2.0  # seconds of no output before checking prompt
NAG_INTERVAL = 5.0    # seconds between repeat alerts
MIN_ALERT_GAP = 1.0    # minimum seconds between any alerts


def is_raw_mode(fd: int) -> bool:
    """Check if the terminal is in raw mode (waiting for single keypress)."""
    try:
        attrs = termios.tcgetattr(fd)
        # Check if ICANON (canonical mode) is disabled
        # Raw mode has ICANON off - means input is available immediately
        lflag = attrs[3]  # c_lflag
        return not (lflag & termios.ICANON)
    except (termios.error, OSError):
        return False


class WaitDetector:
    """State machine for detecting when a command is waiting for input."""

    def __init__(self, on_event: Optional[Callable] = None):
        self.state = State.RUNNING
        self.last_output_time = time.monotonic()
        self.last_line = ""
        self.last_alert_time = 0.0
        self.waiting_since: Optional[float] = None
        self.on_event = on_event

    def record_output(self, data: bytes) -> None:
        """Record that output was received from the command."""
        self.last_output_time = time.monotonic()

        # Extract last line from output for prompt detection
        try:
            text = data.decode('utf-8', errors='replace')
            lines = text.split('\n')
            # Get the last non-empty line, or the last line if all empty
            for line in reversed(lines):
                if line.strip():
                    self.last_line = line
                    break
            else:
                if lines:
                    self.last_line = lines[-1]
        except Exception:
            pass

        # Output received - if we were waiting, we're not anymore
        if self.state == State.WAITING:
            self._transition_to_running("output")

    def record_input(self) -> None:
        """Record that user input was detected."""
        if self.state == State.WAITING:
            self._transition_to_running("input")

    def check(self, pty_fd: int) -> bool:
        """
        Check if the command is waiting for input.

        Returns True if we should alert (entered waiting state or nag interval).
        """
        now = time.monotonic()
        is_waiting = self._check_waiting(pty_fd, now)

        if is_waiting and self.state == State.RUNNING:
            # Just entered waiting state
            self._transition_to_waiting(now)
            return self._should_alert(now)

        if is_waiting and self.state == State.WAITING:
            # Still waiting - check if we should nag
            return self._should_alert(now)

        if not is_waiting and self.state == State.WAITING:
            # No longer waiting
            self._transition_to_running("output")

        return False

    def _check_waiting(self, pty_fd: int, now: float) -> bool:
        """Determine if the command is currently waiting for input."""
        # Primary check: raw mode detection
        if is_raw_mode(pty_fd):
            return True

        # Secondary check: output stall + prompt pattern
        stall_duration = now - self.last_output_time
        if stall_duration >= STALL_THRESHOLD:
            if matches_prompt_pattern(self.last_line):
                return True

        return False

    def _transition_to_waiting(self, now: float) -> None:
        """Transition to WAITING state."""
        self.state = State.WAITING
        self.waiting_since = now
        if self.on_event:
            self.on_event(WaitingEntered(timestamp=now))

    def _transition_to_running(self, reason: str) -> None:
        """Transition back to RUNNING state."""
        self.state = State.RUNNING
        now = time.monotonic()
        self.waiting_since = None
        if self.on_event:
            self.on_event(WaitingExited(timestamp=now, reason=reason))

    def _should_alert(self, now: float) -> bool:
        """Determine if we should send an alert now."""
        # Minimum gap between alerts
        if now - self.last_alert_time < MIN_ALERT_GAP:
            return False

        # First alert when entering waiting state
        if self.waiting_since and now - self.waiting_since < 0.1:
            self.last_alert_time = now
            return True

        # Nag interval for repeated alerts
        if now - self.last_alert_time >= NAG_INTERVAL:
            self.last_alert_time = now
            return True

        return False
