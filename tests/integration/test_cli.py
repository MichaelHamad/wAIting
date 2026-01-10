"""Integration tests for CLI module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from waiting.cli import CLI
from waiting.config import Config, load_config


class TestCLIEnableDisableWorkflow:
    """Tests for enable -> status -> disable workflow."""

    def test_enable_status_workflow(self, tmp_home, capsys):
        """Test enable followed by status shows enabled."""
        config_path = tmp_home / ".waiting.json"
        cli = CLI(config_path=config_path)

        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.is_installed.return_value = True
            mock_manager.get_hook_paths.return_value = {}
            mock_manager_class.return_value = mock_manager

            # Enable
            result1 = cli.enable()
            assert result1 == 0

            # Status
            result2 = cli.status()
            assert result2 == 0

        captured = capsys.readouterr()
        output = captured.out.lower()
        assert "enabled" in output or "installed" in output

    def test_enable_disable_workflow(self, tmp_home, capsys):
        """Test enable followed by disable."""
        config_path = tmp_home / ".waiting.json"
        cli = CLI(config_path=config_path)

        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            # Enable
            result1 = cli.enable()
            assert result1 == 0
            mock_manager.install.assert_called_once()

            # Disable
            result2 = cli.disable()
            assert result2 == 0
            mock_manager.remove.assert_called_once()

    def test_enable_status_disable_status_workflow(self, tmp_home, capsys):
        """Test full workflow: enable -> status -> disable -> status."""
        config_path = tmp_home / ".waiting.json"
        cli = CLI(config_path=config_path)

        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()

            # First: enabled state
            mock_manager.is_installed.return_value = True
            mock_manager.get_hook_paths.return_value = {}
            mock_manager_class.return_value = mock_manager

            cli.enable()
            cli.status()

            # Second: disabled state
            mock_manager.is_installed.return_value = False
            cli.disable()
            cli.status()

        captured = capsys.readouterr()
        assert "enabled" in captured.out.lower() or "disabled" in captured.out.lower()


class TestCLIConfigPersistence:
    """Tests for configuration persistence across commands."""

    def test_config_persists_after_enable(self, tmp_home):
        """Config should persist after enable."""
        config_path = tmp_home / ".waiting.json"
        original_config = {
            "grace_period": 60,
            "volume": 80,
            "audio": "default"
        }
        config_path.write_text(json.dumps(original_config))

        cli = CLI(config_path=config_path)

        with patch("waiting.cli.HookManager"):
            cli.enable()

        # Verify config unchanged
        saved_config = json.loads(config_path.read_text())
        assert saved_config == original_config

    def test_config_persists_after_disable(self, tmp_home):
        """Config should persist after disable."""
        config_path = tmp_home / ".waiting.json"
        original_config = {
            "grace_period": 45,
            "volume": 75,
            "audio": "/custom/sound.wav"
        }
        config_path.write_text(json.dumps(original_config))

        cli = CLI(config_path=config_path)

        with patch("waiting.cli.HookManager"):
            cli.disable()

        # Verify config unchanged
        saved_config = json.loads(config_path.read_text())
        assert saved_config == original_config

    def test_config_changes_reflected_in_status(self, tmp_home, capsys):
        """Status should reflect config changes."""
        config_path = tmp_home / ".waiting.json"

        # Initial config
        config_path.write_text(
            json.dumps({
                "grace_period": 30,
                "volume": 100,
                "audio": "default"
            })
        )

        cli = CLI(config_path=config_path)

        with patch("waiting.cli.HookManager"):
            cli.status()

        captured = capsys.readouterr()
        assert "30" in captured.out
        assert "100" in captured.out

        # Update config
        config_path.write_text(
            json.dumps({
                "grace_period": 60,
                "volume": 50,
                "audio": "/new/sound.wav"
            })
        )

        # Status should show new values
        capsys.readouterr()  # Clear previous output

        with patch("waiting.cli.HookManager"):
            cli.status()

        captured = capsys.readouterr()
        assert "60" in captured.out
        assert "50" in captured.out
        assert "/new/sound.wav" in captured.out

    def test_enable_creates_default_config(self, tmp_home):
        """Enable should create default config if missing."""
        config_path = tmp_home / ".waiting.json"
        assert not config_path.exists()

        cli = CLI(config_path=config_path)

        with patch("waiting.cli.HookManager"):
            cli.enable()

        assert config_path.exists()
        config_data = json.loads(config_path.read_text())

        # Verify default values
        assert "grace_period" in config_data
        assert "volume" in config_data
        assert "audio" in config_data


class TestCLIHookInstallation:
    """Tests for hook installation verification."""

    def test_enable_calls_hook_manager_install(self, tmp_home):
        """Enable should call HookManager.install()."""
        config_path = tmp_home / ".waiting.json"
        cli = CLI(config_path=config_path)

        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            cli.enable()

            mock_manager.install.assert_called_once()

    def test_disable_calls_hook_manager_remove(self, tmp_home):
        """Disable should call HookManager.remove()."""
        cli = CLI()

        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            cli.disable()

            mock_manager.remove.assert_called_once()

    def test_status_checks_hook_installation(self, tmp_home):
        """Status should check if hooks are installed."""
        config_path = tmp_home / ".waiting.json"
        cli = CLI(config_path=config_path)

        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.is_installed.return_value = True
            mock_manager.get_hook_paths.return_value = {}
            mock_manager_class.return_value = mock_manager

            cli.status()

            mock_manager.is_installed.assert_called()


class TestCLIMultipleEnableCalls:
    """Tests for idempotent enable calls."""

    def test_multiple_enable_calls_idempotent(self, tmp_home):
        """Multiple enable calls should be idempotent."""
        config_path = tmp_home / ".waiting.json"
        cli = CLI(config_path=config_path)

        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            # Call enable multiple times
            result1 = cli.enable()
            result2 = cli.enable()
            result3 = cli.enable()

        assert result1 == 0
        assert result2 == 0
        assert result3 == 0
        # install should be called 3 times (HookManager handles idempotency)
        assert mock_manager.install.call_count == 3

    def test_multiple_disable_calls_safe(self, tmp_home):
        """Multiple disable calls should be safe."""
        cli = CLI()

        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            result1 = cli.disable()
            result2 = cli.disable()

        assert result1 == 0
        assert result2 == 0
        assert mock_manager.remove.call_count == 2


class TestCLIStatusVariations:
    """Tests for status command with different states."""

    def test_status_when_hooks_installed(self, tmp_home, capsys):
        """Status should show when hooks are installed."""
        config_path = tmp_home / ".waiting.json"

        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.is_installed.return_value = True
            mock_manager.get_hook_paths.return_value = {
                "waiting-notify-permission": Path("/home/user/.claude/hooks/waiting-notify-permission.sh"),
                "waiting-activity-tooluse": Path("/home/user/.claude/hooks/waiting-activity-tooluse.sh"),
            }
            mock_manager_class.return_value = mock_manager

            cli = CLI(config_path=config_path)
            cli.status()

        captured = capsys.readouterr()
        assert "enabled" in captured.out.lower()

    def test_status_when_hooks_not_installed(self, tmp_home, capsys):
        """Status should show when hooks are not installed."""
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

    def test_status_with_custom_config_values(self, tmp_home, capsys):
        """Status should display custom config values correctly."""
        config_path = tmp_home / ".waiting.json"
        config_path.write_text(
            json.dumps({
                "grace_period": 120,
                "volume": 25,
                "audio": "/usr/share/sounds/custom.wav"
            })
        )

        cli = CLI(config_path=config_path)

        with patch("waiting.cli.HookManager"):
            cli.status()

        captured = capsys.readouterr()
        assert "120" in captured.out
        assert "25" in captured.out
        assert "/usr/share/sounds/custom.wav" in captured.out


class TestCLIErrorScenarios:
    """Tests for error handling in workflows."""

    def test_enable_with_invalid_config_fails(self, tmp_home):
        """Enable should fail gracefully with invalid config."""
        config_path = tmp_home / ".waiting.json"
        config_path.write_text(json.dumps({"grace_period": -10}))

        cli = CLI(config_path=config_path)
        result = cli.enable()

        assert result == 1

    def test_status_with_invalid_config_fails(self, tmp_home):
        """Status should fail gracefully with invalid config."""
        config_path = tmp_home / ".waiting.json"
        config_path.write_text(json.dumps({"grace_period": 0}))

        cli = CLI(config_path=config_path)
        result = cli.status()

        assert result == 1

    def test_hook_manager_error_handled(self, tmp_home):
        """Hook manager errors should be handled gracefully."""
        config_path = tmp_home / ".waiting.json"
        cli = CLI(config_path=config_path)

        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.install.side_effect = Exception("Hook failed")
            mock_manager_class.return_value = mock_manager

            result = cli.enable()

        assert result == 1

    def test_config_file_corrupted_during_status(self, tmp_home):
        """Status should handle corrupted config file."""
        config_path = tmp_home / ".waiting.json"
        config_path.write_text("{ this is not valid json }")

        cli = CLI(config_path=config_path)
        result = cli.status()

        assert result == 1


class TestCLIConfigFileIntegrity:
    """Tests for config file integrity during operations."""

    def test_enable_does_not_modify_config(self, tmp_home):
        """Enable should not modify config file."""
        config_path = tmp_home / ".waiting.json"
        original_config = {
            "grace_period": 30,
            "volume": 100,
            "audio": "default"
        }
        config_path.write_text(json.dumps(original_config))
        original_content = config_path.read_text()

        cli = CLI(config_path=config_path)

        with patch("waiting.cli.HookManager"):
            cli.enable()

        assert config_path.read_text() == original_content

    def test_disable_does_not_modify_config(self, tmp_home):
        """Disable should not modify config file."""
        config_path = tmp_home / ".waiting.json"
        original_config = {
            "grace_period": 45,
            "volume": 80,
            "audio": "/custom.wav"
        }
        config_path.write_text(json.dumps(original_config))
        original_content = config_path.read_text()

        cli = CLI(config_path=config_path)

        with patch("waiting.cli.HookManager"):
            cli.disable()

        assert config_path.read_text() == original_content

    def test_status_does_not_modify_config(self, tmp_home):
        """Status should not modify config file."""
        config_path = tmp_home / ".waiting.json"
        original_config = {
            "grace_period": 60,
            "volume": 50,
            "audio": "default"
        }
        config_path.write_text(json.dumps(original_config))
        original_content = config_path.read_text()

        cli = CLI(config_path=config_path)

        with patch("waiting.cli.HookManager"):
            cli.status()

        assert config_path.read_text() == original_content


class TestCLIMessaging:
    """Tests for user-facing messages."""

    def test_enable_success_messaging(self, tmp_home, capsys):
        """Enable should display success messaging."""
        config_path = tmp_home / ".waiting.json"

        with patch("waiting.cli.HookManager"):
            cli = CLI(config_path=config_path)
            cli.enable()

        captured = capsys.readouterr()
        output = captured.out.lower()
        # Should have success indicators
        assert "install" in output or "enabled" in output

    def test_disable_success_messaging(self, tmp_home, capsys):
        """Disable should display success messaging."""
        with patch("waiting.cli.HookManager"):
            cli = CLI()
            cli.disable()

        captured = capsys.readouterr()
        output = captured.out.lower()
        assert "removed" in output or "disabled" in output

    def test_error_messaging_on_enable_failure(self, tmp_home, capsys):
        """Enable should show error message on failure."""
        config_path = tmp_home / ".waiting.json"

        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.install.side_effect = Exception("Install failed")
            mock_manager_class.return_value = mock_manager

            cli = CLI(config_path=config_path)
            cli.enable()

        captured = capsys.readouterr()
        assert len(captured.err) > 0

    def test_error_messaging_on_disable_failure(self, capsys):
        """Disable should show error message on failure."""
        with patch("waiting.cli.HookManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.remove.side_effect = Exception("Remove failed")
            mock_manager_class.return_value = mock_manager

            cli = CLI()
            cli.disable()

        captured = capsys.readouterr()
        assert len(captured.err) > 0


class TestCLICustomConfigPath:
    """Tests for custom config path functionality."""

    def test_enable_with_custom_config_path(self, tmp_home):
        """Enable should work with custom config path."""
        custom_path = tmp_home / "custom_dir" / "waiting.json"

        cli = CLI(config_path=custom_path)

        with patch("waiting.cli.HookManager"):
            cli.enable()

        assert custom_path.exists()

    def test_status_with_custom_config_path(self, tmp_home):
        """Status should work with custom config path."""
        custom_path = tmp_home / "custom_dir" / "waiting.json"

        cli = CLI(config_path=custom_path)

        with patch("waiting.cli.HookManager"):
            result = cli.status()

        assert result == 0
        assert custom_path.exists()

    def test_multiple_cli_instances_with_different_paths(self, tmp_home):
        """Multiple CLI instances should handle different config paths."""
        path1 = tmp_home / "config1.json"
        path2 = tmp_home / "config2.json"

        cli1 = CLI(config_path=path1)
        cli2 = CLI(config_path=path2)

        with patch("waiting.cli.HookManager"):
            cli1.enable()
            cli2.enable()

        assert path1.exists()
        assert path2.exists()
