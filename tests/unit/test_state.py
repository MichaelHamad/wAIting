"""Tests for the state module."""

import hashlib
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from waiting.state import (
    cleanup,
    cleanup_old_files,
    create_stop_signal,
    generate_session_id,
    has_stop_signal,
    read_pid_file,
    write_pid_file,
)


class TestGenerateSessionId:
    """Tests for generate_session_id function."""

    def test_generate_from_hook_input_with_session_id(self):
        """Should use session_id from hook input if present."""
        hook_input = {"session_id": "test-session-123"}
        session_id = generate_session_id(hook_input)
        assert session_id == "test-session-123"

    def test_generate_fallback_without_session_id(self):
        """Should generate MD5 hash if no session_id in input."""
        hook_input = {"other_field": "value"}
        session_id = generate_session_id(hook_input)
        # Should be a valid MD5 hash (32 hex chars)
        assert len(session_id) == 32
        assert all(c in "0123456789abcdef" for c in session_id)

    def test_generate_with_none_input(self):
        """Should generate fallback if input is None."""
        session_id = generate_session_id(None)
        assert len(session_id) == 32
        assert all(c in "0123456789abcdef" for c in session_id)

    def test_generate_with_empty_dict(self):
        """Should generate fallback for empty dict."""
        session_id = generate_session_id({})
        assert len(session_id) == 32

    def test_generate_fallback_unique(self):
        """Generated fallback IDs should be unique (different timestamps)."""
        id1 = generate_session_id(None)
        time.sleep(0.01)  # Small delay to ensure different timestamp
        id2 = generate_session_id(None)
        # Should be different due to different timestamps
        assert id1 != id2

    def test_generate_ignores_non_string_session_id(self):
        """Should ignore non-string session_id values."""
        hook_input = {"session_id": 12345}
        session_id = generate_session_id(hook_input)
        # Should generate fallback, not use the integer
        assert len(session_id) == 32


class TestWritePidFile:
    """Tests for write_pid_file function."""

    def test_write_pid_file_creates_file(self):
        """Should create PID file."""
        session_id = "test-session"
        pid = 12345

        pid_file = write_pid_file(session_id, pid)

        assert pid_file.exists()
        assert pid_file.read_text() == "12345"

    def test_write_pid_file_correct_path(self):
        """Should write to correct temp file path."""
        session_id = "test-session-123"
        pid = 999

        pid_file = write_pid_file(session_id, pid)

        expected_path = Path(f"/tmp/waiting-audio-{session_id}.pid")
        assert pid_file == expected_path

    def test_write_pid_file_overwrites_existing(self):
        """Should overwrite existing PID file."""
        session_id = "test-session"
        pid_file = Path(f"/tmp/waiting-audio-{session_id}.pid")
        pid_file.write_text("99999")

        write_pid_file(session_id, 12345)

        assert pid_file.read_text() == "12345"


class TestReadPidFile:
    """Tests for read_pid_file function."""

    def test_read_pid_file_existing(self):
        """Should read PID from existing file."""
        session_id = "test-session"
        pid_file = Path(f"/tmp/waiting-audio-{session_id}.pid")
        pid_file.write_text("12345")

        pid = read_pid_file(session_id)

        assert pid == 12345

    def test_read_pid_file_missing(self):
        """Should return None if file doesn't exist."""
        session_id = "nonexistent-session"
        pid = read_pid_file(session_id)
        assert pid is None

    def test_read_pid_file_invalid_content(self):
        """Should return None if file contains invalid PID."""
        session_id = "test-session"
        pid_file = Path(f"/tmp/waiting-audio-{session_id}.pid")
        pid_file.write_text("not-a-number")

        pid = read_pid_file(session_id)

        assert pid is None

    def test_read_pid_file_with_whitespace(self):
        """Should handle whitespace in PID file."""
        session_id = "test-session"
        pid_file = Path(f"/tmp/waiting-audio-{session_id}.pid")
        pid_file.write_text("  12345  \n")

        pid = read_pid_file(session_id)

        assert pid == 12345


class TestCreateStopSignal:
    """Tests for create_stop_signal function."""

    def test_create_stop_signal_creates_file(self):
        """Should create stop signal file."""
        session_id = "test-session"
        stop_file = create_stop_signal(session_id)
        assert stop_file.exists()

    def test_create_stop_signal_correct_path(self):
        """Should create file at correct path."""
        session_id = "test-session-123"
        stop_file = create_stop_signal(session_id)
        expected_path = Path(f"/tmp/waiting-stop-{session_id}")
        assert stop_file == expected_path

    def test_create_stop_signal_overwrites_existing(self):
        """Should handle existing stop signal gracefully."""
        session_id = "test-session"
        stop_file = Path(f"/tmp/waiting-stop-{session_id}")
        stop_file.write_text("old content")

        create_stop_signal(session_id)

        # Should succeed (touch won't fail on existing file)
        assert stop_file.exists()


class TestHasStopSignal:
    """Tests for has_stop_signal function."""

    def test_has_stop_signal_exists(self):
        """Should return True if stop signal exists."""
        session_id = "test-session"
        stop_file = Path(f"/tmp/waiting-stop-{session_id}")
        stop_file.touch()

        result = has_stop_signal(session_id)

        assert result is True

    def test_has_stop_signal_missing(self):
        """Should return False if stop signal doesn't exist."""
        session_id = "nonexistent-session"
        result = has_stop_signal(session_id)
        assert result is False


class TestCleanup:
    """Tests for cleanup function."""

    def test_cleanup_removes_stop_signal(self):
        """Should remove stop signal file."""
        session_id = "test-session"
        stop_file = Path(f"/tmp/waiting-stop-{session_id}")
        stop_file.touch()

        cleanup(session_id)

        assert not stop_file.exists()

    def test_cleanup_removes_pid_file(self):
        """Should remove PID file."""
        session_id = "test-session"
        pid_file = Path(f"/tmp/waiting-audio-{session_id}.pid")
        pid_file.write_text("12345")

        cleanup(session_id)

        assert not pid_file.exists()

    def test_cleanup_removes_both_files(self):
        """Should remove both stop signal and PID file."""
        session_id = "test-session"
        stop_file = Path(f"/tmp/waiting-stop-{session_id}")
        pid_file = Path(f"/tmp/waiting-audio-{session_id}.pid")

        stop_file.touch()
        pid_file.write_text("12345")

        cleanup(session_id)

        assert not stop_file.exists()
        assert not pid_file.exists()

    def test_cleanup_missing_files_no_error(self):
        """Should not raise error if files don't exist."""
        session_id = "nonexistent-session"
        # Should not raise
        cleanup(session_id)


class TestCleanupOldFiles:
    """Tests for cleanup_old_files function."""

    def test_cleanup_old_files_removes_old(self):
        """Should remove files older than age_hours."""
        session_id = "old-session"
        stop_file = Path(f"/tmp/waiting-stop-{session_id}")
        stop_file.touch()

        # Set modification time to 2 hours ago
        old_time = time.time() - (2 * 3600)
        Path(stop_file).stat()  # Refresh
        import os

        os.utime(stop_file, (old_time, old_time))

        cleanup_old_files(age_hours=1)

        # Should be deleted (older than 1 hour)
        assert not stop_file.exists()

    def test_cleanup_old_files_keeps_recent(self):
        """Should keep files newer than age_hours."""
        session_id = "recent-session"
        stop_file = Path(f"/tmp/waiting-stop-{session_id}")
        stop_file.touch()

        cleanup_old_files(age_hours=1)

        # Should still exist (just created, less than 1 hour old)
        assert stop_file.exists()

    def test_cleanup_old_files_no_waiting_files(self):
        """Should not fail if no waiting files exist."""
        # Should not raise
        cleanup_old_files(age_hours=1)


class TestSessionIdValidation:
    """Tests for session ID validation in generate_session_id."""

    def test_valid_alphanumeric_session_id(self):
        """Should accept alphanumeric session IDs."""
        hook_input = {"session_id": "abc123XYZ"}
        session_id = generate_session_id(hook_input)
        assert session_id == "abc123XYZ"

    def test_valid_session_id_with_hyphens(self):
        """Should accept session IDs with hyphens."""
        hook_input = {"session_id": "session-123-abc"}
        session_id = generate_session_id(hook_input)
        assert session_id == "session-123-abc"

    def test_valid_session_id_with_underscores(self):
        """Should accept session IDs with underscores."""
        hook_input = {"session_id": "session_123_abc"}
        session_id = generate_session_id(hook_input)
        assert session_id == "session_123_abc"

    def test_rejects_path_traversal_attempt(self):
        """Should reject session IDs with path traversal."""
        hook_input = {"session_id": "../../../etc/passwd"}
        session_id = generate_session_id(hook_input)
        # Should generate fallback, not use malicious input
        assert session_id != "../../../etc/passwd"
        assert ".." not in session_id
        assert "/" not in session_id

    def test_rejects_session_id_with_slashes(self):
        """Should reject session IDs containing slashes."""
        hook_input = {"session_id": "test/session"}
        session_id = generate_session_id(hook_input)
        assert "/" not in session_id
        # Should be a fallback MD5 hash
        assert len(session_id) == 32

    def test_rejects_session_id_with_spaces(self):
        """Should reject session IDs containing spaces."""
        hook_input = {"session_id": "test session"}
        session_id = generate_session_id(hook_input)
        assert " " not in session_id
        assert len(session_id) == 32

    def test_rejects_session_id_with_special_chars(self):
        """Should reject session IDs with special characters."""
        hook_input = {"session_id": "test;rm -rf /"}
        session_id = generate_session_id(hook_input)
        assert ";" not in session_id
        assert session_id != "test;rm -rf /"
        assert len(session_id) == 32

    def test_rejects_session_id_with_backslash(self):
        """Should reject session IDs containing backslashes."""
        hook_input = {"session_id": "test\\session"}
        session_id = generate_session_id(hook_input)
        assert "\\" not in session_id
        assert len(session_id) == 32

    def test_rejects_session_id_exceeding_max_length(self):
        """Should reject session IDs exceeding max length."""
        long_id = "a" * 200
        hook_input = {"session_id": long_id}
        session_id = generate_session_id(hook_input)
        # Should generate fallback since input too long
        assert session_id != long_id
        assert len(session_id) == 32

    def test_accepts_session_id_at_max_length(self):
        """Should accept session IDs at exactly max length (128)."""
        valid_id = "a" * 128
        hook_input = {"session_id": valid_id}
        session_id = generate_session_id(hook_input)
        assert session_id == valid_id

    def test_rejects_null_bytes(self):
        """Should reject session IDs containing null bytes."""
        hook_input = {"session_id": "test\x00session"}
        session_id = generate_session_id(hook_input)
        assert "\x00" not in session_id
        assert len(session_id) == 32
