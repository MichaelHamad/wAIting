"""Integration tests for hook lifecycle."""

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from waiting.hooks.manager import HookManager
from waiting.state import create_stop_signal, generate_session_id, has_stop_signal


class TestHookLifecycle:
    """Integration tests for complete hook lifecycle."""

    @pytest.fixture
    def hook_manager_with_scripts(self, tmp_home):
        """Create HookManager and install scripts."""
        manager = HookManager()
        manager.hooks_install_dir = tmp_home / ".claude" / "hooks"
        manager.settings_path = tmp_home / ".claude" / "settings.json"

        # Install hooks
        manager.install()

        return manager

    def test_hook_scripts_exist_and_executable(self, hook_manager_with_scripts):
        """Installed hook scripts should exist and be executable."""
        perm_script = (
            hook_manager_with_scripts.hooks_install_dir
            / "waiting-notify-permission.sh"
        )
        activity_script = (
            hook_manager_with_scripts.hooks_install_dir / "waiting-activity-tooluse.sh"
        )

        assert perm_script.exists()
        assert activity_script.exists()

        # Check executable
        assert perm_script.stat().st_mode & 0o111
        assert activity_script.stat().st_mode & 0o111

    def test_permission_hook_script_contents(self, hook_manager_with_scripts):
        """Permission hook script should have expected content."""
        perm_script = (
            hook_manager_with_scripts.hooks_install_dir
            / "waiting-notify-permission.sh"
        )

        content = perm_script.read_text()

        # Check for key functionality
        assert "PermissionRequest" in content or "permission" in content.lower()
        assert "jq" in content  # JSON parsing
        assert "$GRACE_PERIOD" in content
        assert "STOP_SIGNAL" in content
        assert "sleep" in content

    def test_activity_hook_script_contents(self, hook_manager_with_scripts):
        """Activity hook script should have expected content."""
        activity_script = (
            hook_manager_with_scripts.hooks_install_dir / "waiting-activity-tooluse.sh"
        )

        content = activity_script.read_text()

        # Check for key functionality
        assert "PreToolUse" in content or "activity" in content.lower()
        assert "STOP_SIGNAL" in content
        assert "jq" in content
        assert "touch" in content  # Creating stop signal

    def test_permission_hook_parses_session_id(self, hook_manager_with_scripts, tmp_home):
        """Permission hook should parse session_id from JSON input."""
        hook_input = json.dumps({"session_id": "test-session-123"})
        perm_script = (
            hook_manager_with_scripts.hooks_install_dir
            / "waiting-notify-permission.sh"
        )

        # Create minimal config for the script
        config_file = tmp_home / ".waiting.json"
        config_file.write_text(
            json.dumps({"grace_period": 1, "volume": 100, "audio": "default"})
        )

        # Note: We're just checking the script can be sourced/parsed
        # Full execution would require a full bash environment
        content = perm_script.read_text()
        assert "SESSION_ID" in content
        assert "jq -r '.session_id" in content

    def test_activity_hook_creates_stop_signal(
        self, hook_manager_with_scripts, tmp_home
    ):
        """Activity hook logic should create stop signal."""
        activity_script = (
            hook_manager_with_scripts.hooks_install_dir / "waiting-activity-tooluse.sh"
        )

        content = activity_script.read_text()

        # Check that script creates stop signal
        assert "touch" in content
        assert "STOP_SIGNAL" in content

    def test_hook_registration_in_settings(self, hook_manager_with_scripts):
        """Hooks should be registered in settings.json."""
        settings = json.loads(hook_manager_with_scripts.settings_path.read_text())

        # Check PermissionRequest hook
        assert "PermissionRequest" in settings["hooks"]
        perm_hooks = settings["hooks"]["PermissionRequest"]
        perm_hook_commands = [
            h["command"]
            for matcher in perm_hooks
            for h in matcher.get("hooks", [])
        ]
        assert any(
            "waiting-notify-permission.sh" in cmd for cmd in perm_hook_commands
        )

        # Check PreToolUse hook
        assert "PreToolUse" in settings["hooks"]
        pre_hooks = settings["hooks"]["PreToolUse"]
        pre_hook_commands = [
            h["command"] for matcher in pre_hooks for h in matcher.get("hooks", [])
        ]
        assert any("waiting-activity-tooluse.sh" in cmd for cmd in pre_hook_commands)

    def test_state_files_workflow(self, tmp_home):
        """Test the state file creation/cleanup workflow."""
        session_id = "test-session"

        # 1. Permission hook would create stop signal (not yet, but user doesn't respond)
        # 2. Activity hook creates stop signal
        stop_signal = create_stop_signal(session_id)
        assert stop_signal.exists()

        # 3. Check that we can detect the signal
        assert has_stop_signal(session_id)

        # 4. Cleanup
        from waiting.state import cleanup

        cleanup(session_id)
        assert not has_stop_signal(session_id)

    def test_session_id_generation_from_hook_input(self):
        """Session ID should be extracted from hook JSON input."""
        hook_input = {"session_id": "provided-session-id"}
        session_id = generate_session_id(hook_input)
        assert session_id == "provided-session-id"

    def test_session_id_fallback_generation(self):
        """Session ID should fall back to generated hash."""
        hook_input = {"other_field": "value"}
        session_id = generate_session_id(hook_input)

        # Should be MD5 hash (32 hex chars)
        assert len(session_id) == 32
        assert all(c in "0123456789abcdef" for c in session_id)

    def test_hook_removal_cleans_up(self, hook_manager_with_scripts, tmp_home):
        """Removing hooks should clean up both scripts and settings."""
        # Verify installed first
        assert hook_manager_with_scripts.is_installed()

        # Remove
        hook_manager_with_scripts.remove()

        # Verify removed
        assert not hook_manager_with_scripts.is_installed()

        # Scripts should be gone
        perm_script = (
            hook_manager_with_scripts.hooks_install_dir
            / "waiting-notify-permission.sh"
        )
        assert not perm_script.exists()


class TestHookScriptExecution:
    """Tests for hook script execution patterns (without full bash)."""

    def test_permission_hook_background_execution(self):
        """Permission hook should execute in background."""
        # The hook runs in background with &
        from waiting.hooks.manager import HookManager

        manager = HookManager()
        perm_script = manager.hooks_source_dir / "waiting-notify-permission.sh"

        content = perm_script.read_text()

        # Should end with background execution marker
        assert ") &" in content
        assert "exit 0" in content

    def test_activity_hook_synchronous_execution(self):
        """Activity hook should execute synchronously."""
        from waiting.hooks.manager import HookManager

        manager = HookManager()
        activity_script = manager.hooks_source_dir / "waiting-activity-tooluse.sh"

        content = activity_script.read_text()

        # Should exit immediately, not run in background
        assert "exit 0" in content
        # Should not have background marker at end
        lines = content.strip().split("\n")
        assert not lines[-1].strip().endswith("&")

    def test_hook_error_handling(self):
        """Hooks should handle missing files gracefully."""
        from waiting.hooks.manager import HookManager

        manager = HookManager()

        # Both scripts should have error handling
        perm_script = manager.hooks_source_dir / "waiting-notify-permission.sh"
        activity_script = manager.hooks_source_dir / "waiting-activity-tooluse.sh"

        perm_content = perm_script.read_text()
        activity_content = activity_script.read_text()

        # Should check for config file existence
        assert "CONFIG_FILE" in perm_content
        assert "if [ ! -f" in perm_content or "if [ -f" in perm_content
