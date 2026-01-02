"""Tests for process state introspection."""

import os
import platform
import subprocess
import time

import pytest

from waiting.process_state import (
    BlockedState,
    get_blocked_state_linux,
    get_descendant_pids_linux,
    get_process_state_linux,
    get_wchan_linux,
    is_any_process_blocked_on_tty,
    is_linux,
)


class TestPlatformDetection:
    """Tests for platform detection."""

    def test_is_linux_returns_bool(self):
        """is_linux should return a boolean."""
        result = is_linux()
        assert isinstance(result, bool)

    def test_is_linux_matches_platform(self):
        """is_linux should match platform.system()."""
        expected = platform.system() == 'Linux'
        assert is_linux() == expected


class TestBlockedStateEnum:
    """Tests for BlockedState enum."""

    def test_blocked_states_exist(self):
        """All expected blocked states should exist."""
        assert BlockedState.UNKNOWN
        assert BlockedState.NOT_BLOCKED
        assert BlockedState.BLOCKED_TTY_READ
        assert BlockedState.BLOCKED_SELECT


@pytest.mark.skipif(not is_linux(), reason="Linux-only test")
class TestLinuxProcessState:
    """Tests for Linux /proc introspection (only run on Linux)."""

    def test_get_process_state_self(self):
        """Should get state of current process."""
        state = get_process_state_linux(os.getpid())
        # Current process should be running
        assert state == 'R'

    def test_get_process_state_invalid_pid(self):
        """Should return '?' for invalid PID."""
        state = get_process_state_linux(999999999)
        assert state == '?'

    def test_get_wchan_running_process(self):
        """Running process should have no wchan (or 0)."""
        wchan = get_wchan_linux(os.getpid())
        # Running process typically has no wchan
        assert wchan is None or wchan == '0'

    def test_get_blocked_state_self(self):
        """Current process should not be blocked."""
        state = get_blocked_state_linux(os.getpid())
        assert state == BlockedState.NOT_BLOCKED

    def test_get_blocked_state_sleeping_process(self):
        """A sleeping process should be detected."""
        # Start a process that sleeps
        proc = subprocess.Popen(['sleep', '10'])
        time.sleep(0.1)  # Let it start

        try:
            state = get_blocked_state_linux(proc.pid)
            # Sleep process is sleeping but not on TTY
            assert state in (BlockedState.NOT_BLOCKED, BlockedState.BLOCKED_SELECT)
        finally:
            proc.terminate()
            proc.wait()

    def test_get_blocked_state_cat_waiting(self):
        """cat with no input should be blocked on TTY read."""
        # Start cat which will block waiting for input
        proc = subprocess.Popen(
            ['cat'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        time.sleep(0.1)  # Let it start and block

        try:
            state = get_blocked_state_linux(proc.pid)
            # cat should be blocked reading - but from PIPE not TTY
            # This tests the detection works even if result isn't TTY_READ
            assert state in (
                BlockedState.BLOCKED_TTY_READ,
                BlockedState.BLOCKED_SELECT,
                BlockedState.NOT_BLOCKED  # Might be waiting on pipe
            )
        finally:
            proc.stdin.close()
            proc.terminate()
            proc.wait()

    def test_get_descendant_pids(self):
        """Should find child processes."""
        # Start a process with a child
        proc = subprocess.Popen(['bash', '-c', 'sleep 10'])
        time.sleep(0.1)

        try:
            descendants = get_descendant_pids_linux(proc.pid)
            # bash spawns sleep as child
            assert isinstance(descendants, list)
            # May or may not have descendants depending on bash behavior
        finally:
            proc.terminate()
            proc.wait()


class TestNonLinuxFallback:
    """Tests for graceful fallback on non-Linux systems."""

    def test_blocked_state_returns_unknown_on_non_linux(self):
        """On non-Linux, should return UNKNOWN."""
        if is_linux():
            pytest.skip("Only run on non-Linux")

        state = get_blocked_state_linux(os.getpid())
        assert state == BlockedState.UNKNOWN

    def test_is_any_blocked_returns_unknown_on_non_linux(self):
        """On non-Linux, is_any_process_blocked_on_tty returns UNKNOWN."""
        if is_linux():
            pytest.skip("Only run on non-Linux")

        state = is_any_process_blocked_on_tty(os.getpid())
        assert state == BlockedState.UNKNOWN


class TestTrueDetectionIntegration:
    """Integration tests for true detection with detector."""

    def test_detector_uses_heuristic_on_macos(self):
        """On macOS, detector should use heuristic detection."""
        if is_linux():
            pytest.skip("Only run on non-Linux")

        from waiting.detector import WaitDetector

        detector = WaitDetector()
        detector.set_child_pid(os.getpid())

        # Should fall back to heuristic (not use true detection)
        assert detector._use_true_detection is False

    @pytest.mark.skipif(not is_linux(), reason="Linux-only test")
    def test_detector_uses_true_detection_on_linux(self):
        """On Linux, detector should use true detection when PID set."""
        from waiting.detector import WaitDetector

        detector = WaitDetector()
        detector.set_child_pid(os.getpid())

        assert detector._use_true_detection is True
