"""Wait detection state machine."""

import os
import time
from enum import Enum, auto
from typing import Callable, Optional

from .events import WaitingEntered, WaitingExited
from .process_state import BlockedState, is_any_process_blocked_on_tty, is_linux
from .utils import matches_prompt_pattern


class State(Enum):
    """Detector states."""
    RUNNING = auto()
    WAITING = auto()


# Detection thresholds (tuned for LLM CLI use case)
# LLMs routinely pause 10-30s while generating; 30s avoids false positives
STALL_THRESHOLD = float(os.environ.get('WAITING_STALL', '30.0'))
NAG_INTERVAL = float(os.environ.get('WAITING_NAG', '60.0'))
MIN_ALERT_GAP = 1.0     # minimum seconds between any alerts
USER_IDLE_THRESHOLD = 2.0  # seconds of no typing before alerting
STARTUP_GRACE = 3.0     # seconds to ignore alerts after startup

# On Linux with true detection, we can use a much shorter stall threshold
# since we definitively know when the process is blocked on TTY read
TRUE_DETECT_STALL = float(os.environ.get('WAITING_TRUE_STALL', '2.0'))


class WaitDetector:
    """State machine for detecting when a command is waiting for input.

    On Linux, uses true detection via /proc to determine if the child
    process is blocked waiting for TTY input. On other platforms, falls
    back to heuristic detection (output stall + prompt pattern matching).
    """

    def __init__(
        self,
        on_event: Optional[Callable] = None,
        child_pid: Optional[int] = None
    ):
        self.state = State.RUNNING
        now = time.monotonic()
        self.last_output_time = now
        self.last_input_time = now
        self.startup_time = now  # Track when detector was created
        self.last_visible_line = ""  # Last line with actual visible content
        self.last_alert_time = 0.0
        self.waiting_since: Optional[float] = None
        self.on_event = on_event
        self.child_pid = child_pid
        self._use_true_detection = is_linux() and child_pid is not None

    def set_child_pid(self, pid: int) -> None:
        """Set the child PID for true detection (Linux only).

        Called by runner after fork, since we don't know the PID at init time.
        """
        self.child_pid = pid
        self._use_true_detection = is_linux() and pid is not None

    def record_output(self, data: bytes) -> None:
        """Record that output was received from the command."""
        self.last_output_time = time.monotonic()

        # Extract last visible line for prompt detection
        try:
            text = data.decode('utf-8', errors='replace')
            from .utils import strip_ansi

            # Split into lines and find the last one with visible content
            lines = text.split('\n')
            for line in reversed(lines):
                # Strip ANSI codes first, then whitespace
                visible = strip_ansi(line).strip()
                # Only update if there's meaningful visible content
                if visible and len(visible) > 1:
                    self.last_visible_line = visible
                    break
        except Exception:
            pass

        # Output received - if we were waiting, we're not anymore
        if self.state == State.WAITING:
            self._transition_to_running("output")

    def record_input(self) -> None:
        """Record that user input was detected."""
        self.last_input_time = time.monotonic()
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
        """Determine if the command is currently waiting for input.

        On Linux with child_pid set, uses true detection via /proc.
        Otherwise falls back to heuristic detection.
        """
        # Don't alert during startup grace period (terminal initialization)
        if now - self.startup_time < STARTUP_GRACE:
            return False

        stall_duration = now - self.last_output_time

        # TRUE DETECTION (Linux only)
        # Check if child process is definitively blocked on TTY read
        if self._use_true_detection and self.child_pid:
            blocked_state = is_any_process_blocked_on_tty(self.child_pid)

            if blocked_state == BlockedState.BLOCKED_TTY_READ:
                # Definitively blocked on TTY read - only need short stall
                if stall_duration >= TRUE_DETECT_STALL:
                    return True
                return False

            elif blocked_state == BlockedState.NOT_BLOCKED:
                # Definitively NOT blocked - no alert
                return False

            elif blocked_state == BlockedState.BLOCKED_SELECT:
                # Might be blocked on TTY via select - use pattern matching
                if stall_duration >= TRUE_DETECT_STALL:
                    if matches_prompt_pattern(self.last_visible_line):
                        return True
                return False

            # UNKNOWN - fall through to heuristic

        # HEURISTIC DETECTION (macOS, or Linux fallback)
        # Must have output stall before considering waiting
        if stall_duration < STALL_THRESHOLD:
            return False

        # Check if last visible line matches a prompt pattern
        if matches_prompt_pattern(self.last_visible_line):
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
        # Don't alert if user recently typed
        if now - self.last_input_time < USER_IDLE_THRESHOLD:
            return False

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
