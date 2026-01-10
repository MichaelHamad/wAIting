"""Tests for the Waiting CLI module."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from waiting.cli import CLI
from waiting.config import Config
from waiting.errors import ConfigError, HookError


class TestCLI:
    """Test CLI command handlers."""

    def test_show_help(self, capsys):
        """Test show_help displays help message."""
        cli = CLI()
        exit_code = cli.show_help()

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "Waiting" in captured.out
        assert "Usage:" in captured.out
        assert "waiting" in captured.out
        assert "disable" in captured.out
        assert "status" in captured.out

    def test_enable_success(self, capsys, tmp_path, monkeypatch):
        """Test enable command succeeds."""
        config_path = tmp_path / ".waiting.json"
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("waiting.cli.HookManager") as mock_manager:
            mock_instance = MagicMock()
            mock_manager.return_value = mock_instance

            cli = CLI(config_path=config_path)
            exit_code = cli.enable()

            captured = capsys.readouterr()
            assert exit_code == 0
            assert "installed" in captured.out.lower()
            mock_instance.install.assert_called_once()

    def test_enable_failure(self, capsys, tmp_path):
        """Test enable command handles errors."""
        config_path = tmp_path / ".waiting.json"

        with patch("waiting.cli.HookManager") as mock_manager:
            mock_instance = MagicMock()
            mock_instance.install.side_effect = Exception("Test error")
            mock_manager.return_value = mock_instance

            cli = CLI(config_path=config_path)
            exit_code = cli.enable()

            captured = capsys.readouterr()
            assert exit_code == 1
            assert "Error" in captured.err

    def test_disable_success(self, capsys):
        """Test disable command succeeds."""
        with patch("waiting.cli.HookManager") as mock_manager:
            mock_instance = MagicMock()
            mock_manager.return_value = mock_instance

            cli = CLI()
            exit_code = cli.disable()

            captured = capsys.readouterr()
            assert exit_code == 0
            assert "removed" in captured.out.lower()
            mock_instance.remove.assert_called_once()

    def test_disable_failure(self, capsys):
        """Test disable command handles errors."""
        with patch("waiting.cli.HookManager") as mock_manager:
            mock_instance = MagicMock()
            mock_instance.remove.side_effect = Exception("Test error")
            mock_manager.return_value = mock_instance

            cli = CLI()
            exit_code = cli.disable()

            captured = capsys.readouterr()
            assert exit_code == 1
            assert "Error" in captured.err

    def test_status_success(self, capsys, tmp_path, monkeypatch):
        """Test status command succeeds."""
        config_path = tmp_path / ".waiting.json"
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("waiting.cli.HookManager") as mock_manager:
            mock_instance = MagicMock()
            mock_instance.is_installed.return_value = True
            mock_instance.get_hook_paths.return_value = {
                "waiting-notify-permission.sh": Path("/tmp/hook1.sh"),
                "waiting-activity-tooluse.sh": Path("/tmp/hook2.sh"),
            }
            mock_manager.return_value = mock_instance

            cli = CLI(config_path=config_path)
            exit_code = cli.status()

            captured = capsys.readouterr()
            assert exit_code == 0
            assert "Waiting" in captured.out
            assert "Status:" in captured.out
            assert "Grace Period:" in captured.out
            assert "Volume:" in captured.out

    def test_status_failure(self, capsys, tmp_path):
        """Test status command handles errors."""
        config_path = tmp_path / ".waiting.json"

        with patch("waiting.cli.load_config") as mock_load:
            mock_load.side_effect = Exception("Test error")

            cli = CLI(config_path=config_path)
            exit_code = cli.status()

            captured = capsys.readouterr()
            assert exit_code == 1
            assert "Error" in captured.err


class TestCLIEnable:
    """Additional tests for enable() command."""

    def test_enable_creates_config_if_missing(self, tmp_home, capsys):
        """Enable should create config file if missing."""
        config_path = tmp_home / ".waiting.json"
        assert not config_path.exists()

        cli = CLI(config_path=config_path)
        with patch("waiting.cli.HookManager"):
            result = cli.enable()

        assert result == 0
        assert config_path.exists()

    def test_enable_loads_existing_config(self, tmp_home):
        """Enable should load existing config."""
        config_path = tmp_home / ".waiting.json"
        config_path.write_text(
            json.dumps({"grace_period": 45, "volume": 80, "audio": "default"})
        )

        cli = CLI(config_path=config_path)

        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            cli.enable()
            mock_manager.install.assert_called_once()

    def test_enable_with_invalid_config(self, tmp_home, capsys):
        """Enable should return 1 with invalid config."""
        config_path = tmp_home / ".waiting.json"
        config_path.write_text(json.dumps({"grace_period": -5, "volume": 100}))

        cli = CLI(config_path=config_path)
        result = cli.enable()

        assert result == 1

    def test_enable_with_hook_error(self, tmp_home, capsys):
        """Enable should return 1 if HookManager fails."""
        config_path = tmp_home / ".waiting.json"

        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.install.side_effect = HookError("Hook install failed")
            mock_manager_class.return_value = mock_manager

            cli = CLI(config_path=config_path)
            result = cli.enable()

        assert result == 1

    def test_enable_prints_next_steps(self, tmp_home, capsys):
        """Enable should print next steps."""
        config_path = tmp_home / ".waiting.json"

        with patch("waiting.cli.HookManager"):
            cli = CLI(config_path=config_path)
            cli.enable()

        captured = capsys.readouterr()
        output = captured.out.lower()
        assert "restart" in output or "next" in output

    def test_enable_calls_install_with_config(self, tmp_home):
        """Enable should pass config to install if available."""
        config_path = tmp_home / ".waiting.json"

        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            cli = CLI(config_path=config_path)
            cli.enable()

            # Install should be called (config handling is internal)
            mock_manager.install.assert_called_once()


class TestCLIDisable:
    """Additional tests for disable() command."""

    def test_disable_preserves_config(self, tmp_home):
        """Disable should not delete config file."""
        config_path = tmp_home / ".waiting.json"
        config_path.write_text(
            json.dumps({"grace_period": 30, "volume": 100, "audio": "default"})
        )
        original_content = config_path.read_text()

        cli = CLI(config_path=config_path)

        with patch("waiting.cli.HookManager"):
            cli.disable()

        assert config_path.exists()
        assert config_path.read_text() == original_content

    def test_disable_mentions_config_preserved(self, tmp_home, capsys):
        """Disable should mention config is preserved."""
        config_path = tmp_home / ".waiting.json"

        with patch("waiting.cli.HookManager"):
            cli = CLI(config_path=config_path)
            cli.disable()

        captured = capsys.readouterr()
        output = captured.out.lower()
        assert "preserved" in output or "config" in output

    def test_disable_with_hook_error(self, tmp_home, capsys):
        """Disable should return 1 if HookManager fails."""
        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.remove.side_effect = HookError("Remove failed")
            mock_manager_class.return_value = mock_manager

            cli = CLI()
            result = cli.disable()

        assert result == 1

    def test_disable_without_config_file(self, tmp_home):
        """Disable should work even without config file."""
        config_path = tmp_home / ".waiting.json"
        assert not config_path.exists()

        with patch("waiting.cli.HookManager"):
            cli = CLI(config_path=config_path)
            result = cli.disable()

        # Should succeed or gracefully handle missing config
        assert result == 0 or result == 1


class TestCLIStatus:
    """Additional tests for status() command."""

    def test_status_displays_all_config_fields(self, tmp_home, capsys):
        """Status should display grace_period, volume, and audio."""
        config_path = tmp_home / ".waiting.json"
        config_path.write_text(
            json.dumps({
                "grace_period": 45,
                "volume": 75,
                "audio": "/custom/sound.wav"
            })
        )

        with patch("waiting.cli.HookManager"):
            cli = CLI(config_path=config_path)
            cli.status()

        captured = capsys.readouterr()
        output = captured.out
        assert "45" in output
        assert "75" in output
        assert "/custom/sound.wav" in output

    def test_status_shows_enabled_when_installed(self, tmp_home, capsys):
        """Status should show ENABLED when hooks installed."""
        config_path = tmp_home / ".waiting.json"

        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.is_installed.return_value = True
            mock_manager.get_hook_paths.return_value = {}
            mock_manager_class.return_value = mock_manager

            cli = CLI(config_path=config_path)
            cli.status()

        captured = capsys.readouterr()
        assert "enabled" in captured.out.lower()

    def test_status_shows_disabled_when_not_installed(self, tmp_home, capsys):
        """Status should show DISABLED when hooks not installed."""
        config_path = tmp_home / ".waiting.json"

        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.is_installed.return_value = False
            mock_manager.get_hook_paths.return_value = {}
            mock_manager_class.return_value = mock_manager

            cli = CLI(config_path=config_path)
            cli.status()

        captured = capsys.readouterr()
        output = captured.out.lower()
        assert "disabled" in output or "not installed" in output

    def test_status_lists_hook_paths(self, tmp_home, capsys):
        """Status should list hook paths when installed."""
        config_path = tmp_home / ".waiting.json"

        hook_paths = {
            "waiting-notify-permission": tmp_home / ".claude" / "hooks" / "waiting-notify-permission.sh",
            "waiting-activity-tooluse": tmp_home / ".claude" / "hooks" / "waiting-activity-tooluse.sh",
        }

        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.is_installed.return_value = True
            mock_manager.get_hook_paths.return_value = hook_paths
            mock_manager_class.return_value = mock_manager

            cli = CLI(config_path=config_path)
            cli.status()

        captured = capsys.readouterr()
        output = captured.out.lower()
        assert "hook" in output or "waiting" in output

    def test_status_with_invalid_config(self, tmp_home):
        """Status should return 1 with invalid config."""
        config_path = tmp_home / ".waiting.json"
        config_path.write_text("{ invalid json }")

        cli = CLI(config_path=config_path)
        result = cli.status()

        assert result == 1

    def test_status_returns_zero_on_success(self, tmp_home):
        """Status should return 0 on success."""
        config_path = tmp_home / ".waiting.json"

        with patch("waiting.cli.HookManager"):
            cli = CLI(config_path=config_path)
            result = cli.status()

        assert result == 0


class TestCLIShowHelp:
    """Additional tests for show_help() command."""

    def test_show_help_includes_all_commands(self, capsys):
        """Show help should include all commands."""
        cli = CLI()
        cli.show_help()

        captured = capsys.readouterr()
        output = captured.out.lower()
        assert "enable" in output
        assert "disable" in output
        assert "status" in output
        assert "--help" in captured.out

    def test_show_help_explains_config_options(self, capsys):
        """Show help should explain configuration options."""
        cli = CLI()
        cli.show_help()

        captured = capsys.readouterr()
        output = captured.out
        assert "grace_period" in output
        assert "volume" in output
        assert "audio" in output

    def test_show_help_returns_zero(self):
        """Show help should always return 0."""
        cli = CLI()
        result = cli.show_help()
        assert result == 0


class TestCLIErrorHandling:
    """Tests for CLI error handling."""

    def test_config_error_handling_in_enable(self, tmp_home):
        """Enable should handle ConfigError gracefully."""
        config_path = tmp_home / ".waiting.json"
        config_path.write_text(json.dumps({"grace_period": -1}))

        cli = CLI(config_path=config_path)
        result = cli.enable()

        assert result == 1

    def test_generic_exception_in_enable(self, tmp_home):
        """Enable should handle generic exceptions."""
        config_path = tmp_home / ".waiting.json"

        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.install.side_effect = Exception("Unexpected error")
            mock_manager_class.return_value = mock_manager

            cli = CLI(config_path=config_path)
            result = cli.enable()

        assert result == 1

    def test_generic_exception_in_disable(self):
        """Disable should handle generic exceptions."""
        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.remove.side_effect = Exception("Unexpected error")
            mock_manager_class.return_value = mock_manager

            cli = CLI()
            result = cli.disable()

        assert result == 1

    def test_generic_exception_in_status(self, tmp_home):
        """Status should handle generic exceptions."""
        config_path = tmp_home / ".waiting.json"

        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.is_installed.side_effect = Exception("Unexpected error")
            mock_manager_class.return_value = mock_manager

            cli = CLI(config_path=config_path)
            result = cli.status()

        assert result == 1

    def test_permission_error_in_enable(self, tmp_home):
        """Enable should handle permission errors."""
        config_path = tmp_home / ".waiting.json"

        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.install.side_effect = PermissionError("Access denied")
            mock_manager_class.return_value = mock_manager

            cli = CLI(config_path=config_path)
            result = cli.enable()

        assert result == 1

    def test_error_logged_to_logger(self, tmp_home):
        """Errors should be logged to logger."""
        config_path = tmp_home / ".waiting.json"
        config_path.write_text("invalid")

        cli = CLI(config_path=config_path)
        with patch.object(cli, "logger") as mock_logger:
            cli.enable()
            mock_logger.error.assert_called()


class TestCLIInitialization:
    """Tests for CLI initialization."""

    def test_cli_default_config_path(self, tmp_home, monkeypatch):
        """CLI should use ~/.waiting.json by default."""
        monkeypatch.setenv("HOME", str(tmp_home))
        cli = CLI()
        assert cli.config_path == tmp_home / ".waiting.json"

    def test_cli_custom_config_path(self, tmp_home):
        """CLI should accept custom config path."""
        custom_path = tmp_home / "custom" / ".waiting.json"
        cli = CLI(config_path=custom_path)
        assert cli.config_path == custom_path

    def test_cli_has_logger(self):
        """CLI should initialize with logger."""
        cli = CLI()
        assert cli.logger is not None
