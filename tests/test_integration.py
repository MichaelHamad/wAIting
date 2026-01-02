"""Integration tests for waiting CLI."""

import subprocess
import sys
import os

import pytest


# Path to the waiting command (use python -m waiting for reliability)
WAITING_CMD = [sys.executable, "-m", "waiting"]


class TestBasicExecution:
    """Test basic command execution."""

    def test_echo_exits_immediately(self):
        """Echo should exit immediately without errors."""
        result = subprocess.run(
            WAITING_CMD + ["echo", "hello"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "hello"

    def test_true_returns_zero(self):
        """true command should return exit code 0."""
        result = subprocess.run(
            WAITING_CMD + ["true"],
            capture_output=True,
            timeout=5,
        )
        assert result.returncode == 0

    def test_false_returns_one(self):
        """false command should return exit code 1."""
        result = subprocess.run(
            WAITING_CMD + ["false"],
            capture_output=True,
            timeout=5,
        )
        assert result.returncode == 1

    def test_exit_code_passthrough(self):
        """Exit codes should be passed through."""
        result = subprocess.run(
            WAITING_CMD + ["sh", "-c", "exit 42"],
            capture_output=True,
            timeout=5,
        )
        assert result.returncode == 42

    def test_command_not_found(self):
        """Non-existent command should return 127."""
        result = subprocess.run(
            WAITING_CMD + ["nonexistent_command_xyz"],
            capture_output=True,
            timeout=5,
        )
        assert result.returncode == 127


class TestOutputPassthrough:
    """Test output passthrough."""

    def test_stdout_passthrough(self):
        """stdout should be passed through."""
        result = subprocess.run(
            WAITING_CMD + ["echo", "test output"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert "test output" in result.stdout

    def test_multiline_output(self):
        """Multiline output should be preserved."""
        result = subprocess.run(
            WAITING_CMD + ["printf", "line1\nline2\nline3"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert "line1" in result.stdout
        assert "line2" in result.stdout
        assert "line3" in result.stdout


class TestHelpAndUsage:
    """Test help and usage messages."""

    def test_help_flag(self):
        """--help should show usage."""
        result = subprocess.run(
            WAITING_CMD + ["--help"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert result.returncode == 0
        assert "waiting" in result.stdout.lower()
        assert "command" in result.stdout.lower()

    def test_no_command_shows_help(self):
        """Running without command should show help."""
        result = subprocess.run(
            WAITING_CMD,
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert result.returncode == 1
        assert "waiting" in result.stdout.lower() or "usage" in result.stdout.lower()


class TestEnvironment:
    """Test environment handling."""

    def test_env_passthrough(self):
        """Environment variables should be passed through."""
        env = os.environ.copy()
        env["TEST_VAR"] = "test_value"
        result = subprocess.run(
            WAITING_CMD + ["sh", "-c", "echo $TEST_VAR"],
            capture_output=True,
            text=True,
            env=env,
            timeout=5,
        )
        assert "test_value" in result.stdout


class TestDashDashSeparator:
    """Test -- separator handling."""

    def test_double_dash_separator(self):
        """-- should work to separate waiting args from command."""
        result = subprocess.run(
            WAITING_CMD + ["--", "echo", "test"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert result.returncode == 0
        assert "test" in result.stdout
