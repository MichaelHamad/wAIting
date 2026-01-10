"""Tests for the hooks module."""

import json
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from waiting.config import Config
from waiting.errors import HookError
from waiting.hooks.manager import HookManager


class TestHookManager:
    """Tests for HookManager class."""

    @pytest.fixture
    def hook_manager(self, tmp_home):
        """Create HookManager with mocked paths."""
        manager = HookManager()
        # Override paths to use temp directory
        manager.hooks_install_dir = tmp_home / ".claude" / "hooks"
        manager.settings_path = tmp_home / ".claude" / "settings.json"
        return manager

    def test_hook_manager_init(self):
        """HookManager should initialize with correct paths."""
        manager = HookManager()
        assert manager.hooks_source_dir.exists()
        assert manager.hooks_source_dir.name == "scripts"

    def test_hook_source_scripts_exist(self):
        """Hook source scripts should exist in project."""
        manager = HookManager()
        perm_script = manager.hooks_source_dir / "waiting-notify-permission.sh"
        activity_script = manager.hooks_source_dir / "waiting-activity-tooluse.sh"

        assert perm_script.exists()
        assert activity_script.exists()

    def test_install_creates_hooks_directory(self, hook_manager, tmp_home):
        """Install should create ~/.claude/hooks directory."""
        assert not hook_manager.hooks_install_dir.exists()

        hook_manager.install()

        assert hook_manager.hooks_install_dir.exists()
        assert hook_manager.hooks_install_dir.is_dir()

    def test_install_copies_hook_scripts(self, hook_manager, tmp_home):
        """Install should copy hook scripts to ~/.claude/hooks/."""
        hook_manager.install()

        perm_script = hook_manager.hooks_install_dir / "waiting-notify-permission.sh"
        activity_script = (
            hook_manager.hooks_install_dir / "waiting-activity-tooluse.sh"
        )

        assert perm_script.exists()
        assert activity_script.exists()

    def test_install_makes_scripts_executable(self, hook_manager, tmp_home):
        """Install should make hook scripts executable."""
        hook_manager.install()

        perm_script = hook_manager.hooks_install_dir / "waiting-notify-permission.sh"
        activity_script = (
            hook_manager.hooks_install_dir / "waiting-activity-tooluse.sh"
        )

        # Check executable bit
        perm_stat = perm_script.stat().st_mode
        activity_stat = activity_script.stat().st_mode

        assert perm_stat & stat.S_IXUSR
        assert activity_stat & stat.S_IXUSR

    def test_install_registers_hooks_in_settings(self, hook_manager, tmp_home):
        """Install should register hooks in settings.json."""
        hook_manager.install()

        settings = json.loads(hook_manager.settings_path.read_text())

        assert "hooks" in settings
        assert "PermissionRequest" in settings["hooks"]
        assert "PreToolUse" in settings["hooks"]

    def test_install_preserves_existing_settings(self, hook_manager, tmp_home):
        """Install should preserve existing settings."""
        existing_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": "echo test"}],
                    }
                ]
            }
        }

        hook_manager.settings_path.parent.mkdir(parents=True, exist_ok=True)
        hook_manager.settings_path.write_text(json.dumps(existing_settings))

        hook_manager.install()

        settings = json.loads(hook_manager.settings_path.read_text())

        # Original Bash hook should still exist
        bash_hooks = [
            h
            for h in settings["hooks"]["PreToolUse"]
            if h.get("matcher") == "Bash"
        ]
        assert len(bash_hooks) == 1

    def test_remove_deletes_hook_scripts(self, hook_manager, tmp_home):
        """Remove should delete hook scripts."""
        hook_manager.install()

        assert hook_manager.hooks_install_dir.exists()

        hook_manager.remove()

        perm_script = hook_manager.hooks_install_dir / "waiting-notify-permission.sh"
        activity_script = (
            hook_manager.hooks_install_dir / "waiting-activity-tooluse.sh"
        )

        assert not perm_script.exists()
        assert not activity_script.exists()

    def test_remove_unregisters_from_settings(self, hook_manager, tmp_home):
        """Remove should unregister hooks from settings.json."""
        hook_manager.install()

        settings_before = json.loads(hook_manager.settings_path.read_text())
        assert len(settings_before["hooks"]["PermissionRequest"]) > 0

        hook_manager.remove()

        settings_after = json.loads(hook_manager.settings_path.read_text())

        # PermissionRequest and PreToolUse should be gone or empty
        if "PermissionRequest" in settings_after.get("hooks", {}):
            assert len(settings_after["hooks"]["PermissionRequest"]) == 0

    def test_remove_preserves_other_hooks(self, hook_manager, tmp_home):
        """Remove should preserve other hooks."""
        existing_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": "echo test"}],
                    }
                ]
            }
        }

        hook_manager.settings_path.parent.mkdir(parents=True, exist_ok=True)
        hook_manager.settings_path.write_text(json.dumps(existing_settings))

        hook_manager.install()
        hook_manager.remove()

        settings = json.loads(hook_manager.settings_path.read_text())

        # Bash hook should still exist
        bash_hooks = [
            h
            for h in settings.get("hooks", {}).get("PreToolUse", [])
            if h.get("matcher") == "Bash"
        ]
        assert len(bash_hooks) == 1

    def test_is_installed_true_when_installed(self, hook_manager, tmp_home):
        """is_installed should return True when hooks are installed."""
        hook_manager.install()

        assert hook_manager.is_installed() is True

    def test_is_installed_false_when_not_installed(self, hook_manager, tmp_home):
        """is_installed should return False when hooks not installed."""
        assert hook_manager.is_installed() is False

    def test_is_installed_false_after_removal(self, hook_manager, tmp_home):
        """is_installed should return False after removal."""
        hook_manager.install()
        assert hook_manager.is_installed() is True

        hook_manager.remove()
        assert hook_manager.is_installed() is False

    def test_get_hook_paths_returns_dict(self, hook_manager):
        """get_hook_paths should return hook path mapping."""
        paths = hook_manager.get_hook_paths()

        assert isinstance(paths, dict)
        assert "waiting-notify-permission" in paths
        assert "waiting-activity-tooluse" in paths

    def test_install_idempotent(self, hook_manager, tmp_home):
        """Multiple installs should be idempotent."""
        hook_manager.install()
        settings1 = json.loads(hook_manager.settings_path.read_text())

        hook_manager.install()
        settings2 = json.loads(hook_manager.settings_path.read_text())

        # Settings should be the same (no duplicate hooks)
        perm_count_1 = len(settings1["hooks"]["PermissionRequest"])
        perm_count_2 = len(settings2["hooks"]["PermissionRequest"])

        assert perm_count_1 == perm_count_2

    def test_install_with_missing_source_raises_error(self, hook_manager, tmp_home):
        """Install should raise error if source script missing."""
        # Mock _copy_hook_scripts to simulate missing file
        with patch.object(
            hook_manager,
            "_copy_hook_scripts",
            side_effect=HookError("Hook script not found"),
        ):
            with pytest.raises(HookError):
                hook_manager.install()

    def test_logger_is_initialized(self, hook_manager):
        """HookManager should have logger initialized."""
        assert hook_manager.logger is not None
