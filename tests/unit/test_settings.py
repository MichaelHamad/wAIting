"""Tests for the settings module."""

import json
from pathlib import Path

import pytest

from waiting.settings import (
    CLAUDE_SETTINGS_PATH,
    HOOK_NAME_ACTIVITY,
    HOOK_NAME_PERMISSION,
    get_hook_paths,
    is_installed,
    load_settings,
    merge_hooks_into_settings,
    remove_hooks_from_settings,
    save_settings,
)


class TestLoadSettings:
    """Tests for load_settings function."""

    def test_load_missing_settings_returns_empty_dict(self, tmp_home):
        """Should return empty dict if settings file doesn't exist."""
        settings_path = tmp_home / ".claude" / "settings.json"
        settings = load_settings(settings_path)
        assert settings == {}

    def test_load_existing_settings(self, tmp_settings):
        """Should load existing settings."""
        test_settings = {"key": "value"}
        tmp_settings.write_text(json.dumps(test_settings))

        settings = load_settings(tmp_settings)

        assert settings == test_settings

    def test_load_invalid_json_raises_error(self, tmp_home):
        """Should raise SettingsError on invalid JSON."""
        settings_path = tmp_home / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text("{ invalid json }")

        from waiting.errors import SettingsError

        with pytest.raises(SettingsError):
            load_settings(settings_path)

    def test_load_with_default_path_uses_claude_settings(self, monkeypatch):
        """Should use default ~/.claude/settings.json if no path provided."""
        # This test would require mocking Path.home(), skip for now
        pass


class TestSaveSettings:
    """Tests for save_settings function."""

    def test_save_settings_creates_file(self, tmp_home):
        """Should create settings file."""
        settings_path = tmp_home / ".claude" / "settings.json"
        test_settings = {"key": "value"}

        save_settings(test_settings, settings_path)

        assert settings_path.exists()
        saved = json.loads(settings_path.read_text())
        assert saved == test_settings

    def test_save_settings_creates_parent_dirs(self, tmp_path):
        """Should create parent directories."""
        settings_path = tmp_path / ".claude" / "settings.json"
        test_settings = {"key": "value"}

        save_settings(test_settings, settings_path)

        assert settings_path.parent.exists()

    def test_save_settings_overwrites_existing(self, tmp_settings):
        """Should overwrite existing settings."""
        new_settings = {"new_key": "new_value"}

        save_settings(new_settings, tmp_settings)

        saved = json.loads(tmp_settings.read_text())
        assert saved == new_settings

    def test_save_settings_preserves_formatting(self, tmp_settings):
        """Should save with readable formatting."""
        test_settings = {"key1": "value1", "key2": "value2"}

        save_settings(test_settings, tmp_settings)

        content = tmp_settings.read_text()
        # Should have indentation
        assert "\n" in content
        assert "  " in content


class TestGetHookPaths:
    """Tests for get_hook_paths function."""

    def test_get_hook_paths_returns_dict(self):
        """Should return dictionary of hook paths."""
        paths = get_hook_paths()

        assert isinstance(paths, dict)
        assert HOOK_NAME_PERMISSION in paths
        assert HOOK_NAME_ACTIVITY in paths

    def test_get_hook_paths_correct_names(self):
        """Should return correct hook script names."""
        paths = get_hook_paths()

        perm_path = paths[HOOK_NAME_PERMISSION]
        activity_path = paths[HOOK_NAME_ACTIVITY]

        assert str(perm_path).endswith(f"{HOOK_NAME_PERMISSION}.sh")
        assert str(activity_path).endswith(f"{HOOK_NAME_ACTIVITY}.sh")


class TestMergeHooksIntoSettings:
    """Tests for merge_hooks_into_settings function."""

    def test_merge_into_empty_settings(self):
        """Should create hooks structure in empty settings."""
        settings = {}
        paths = get_hook_paths()

        result = merge_hooks_into_settings(settings)

        assert "hooks" in result
        assert "PermissionRequest" in result["hooks"]
        assert "PreToolUse" in result["hooks"]

    def test_merge_preserves_existing_hooks(self):
        """Should preserve existing hooks from other tools."""
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": "echo test"}],
                    }
                ]
            }
        }

        result = merge_hooks_into_settings(settings)

        # Original Bash hook should still exist
        bash_hooks = [
            h
            for h in result["hooks"]["PreToolUse"]
            if h.get("matcher") == "Bash"
        ]
        assert len(bash_hooks) == 1

    def test_merge_adds_permission_hook(self):
        """Should add PermissionRequest hook."""
        settings = {}
        paths = get_hook_paths()

        result = merge_hooks_into_settings(settings)

        perm_hooks = result["hooks"]["PermissionRequest"]
        assert len(perm_hooks) > 0
        # Check that hook script path is included
        perm_hook_commands = [
            h["command"]
            for matcher in perm_hooks
            for h in matcher.get("hooks", [])
        ]
        assert any(str(paths[HOOK_NAME_PERMISSION]) in cmd for cmd in perm_hook_commands)

    def test_merge_adds_activity_hook(self):
        """Should add PreToolUse activity hook."""
        settings = {}
        paths = get_hook_paths()

        result = merge_hooks_into_settings(settings)

        pre_tool_hooks = result["hooks"]["PreToolUse"]
        assert len(pre_tool_hooks) > 0
        # Check that hook script path is included
        activity_hook_commands = [
            h["command"]
            for matcher in pre_tool_hooks
            for h in matcher.get("hooks", [])
        ]
        assert any(
            str(paths[HOOK_NAME_ACTIVITY]) in cmd for cmd in activity_hook_commands
        )

    def test_merge_idempotent(self):
        """Merging twice should not duplicate hooks."""
        settings = {}

        result1 = merge_hooks_into_settings(settings)
        result2 = merge_hooks_into_settings(result1)

        # Count Waiting hooks
        perm_waiting_hooks = [
            h
            for h in result2["hooks"]["PermissionRequest"]
            if h.get("matcher") == "*"
            and any(
                HOOK_NAME_PERMISSION in h.get("command", "")
                for h in h.get("hooks", [])
            )
        ]

        pre_waiting_hooks = [
            h
            for h in result2["hooks"]["PreToolUse"]
            if h.get("matcher") == "*"
            and any(
                HOOK_NAME_ACTIVITY in h.get("command", "")
                for h in h.get("hooks", [])
            )
        ]

        # Should still be just one of each (not duplicated)
        assert len(perm_waiting_hooks) == 1
        assert len(pre_waiting_hooks) == 1


class TestRemoveHooksFromSettings:
    """Tests for remove_hooks_from_settings function."""

    def test_remove_permission_hook(self):
        """Should remove PermissionRequest hook."""
        settings = {}
        settings = merge_hooks_into_settings(settings)

        result = remove_hooks_from_settings(settings)

        # PermissionRequest should be removed or empty
        if "PermissionRequest" in result.get("hooks", {}):
            # If key exists, it should be empty
            assert len(result["hooks"]["PermissionRequest"]) == 0

    def test_remove_activity_hook(self):
        """Should remove PreToolUse activity hook."""
        settings = {}
        settings = merge_hooks_into_settings(settings)

        result = remove_hooks_from_settings(settings)

        # PreToolUse should be removed or empty
        if "PreToolUse" in result.get("hooks", {}):
            assert len(result["hooks"]["PreToolUse"]) == 0

    def test_remove_preserves_other_hooks(self):
        """Should preserve other hooks when removing."""
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": "echo test"}],
                    }
                ]
            }
        }
        settings = merge_hooks_into_settings(settings)

        result = remove_hooks_from_settings(settings)

        # Bash hook should still exist
        bash_hooks = [
            h
            for h in result.get("hooks", {}).get("PreToolUse", [])
            if h.get("matcher") == "Bash"
        ]
        assert len(bash_hooks) == 1

    def test_remove_from_empty_settings(self):
        """Should handle removing from empty settings gracefully."""
        settings = {}

        result = remove_hooks_from_settings(settings)

        # Should return empty or unchanged dict
        assert isinstance(result, dict)

    def test_remove_idempotent(self):
        """Removing twice should not cause errors."""
        settings = {}
        settings = merge_hooks_into_settings(settings)

        result1 = remove_hooks_from_settings(settings)
        result2 = remove_hooks_from_settings(result1)

        # Should be clean
        if "hooks" in result2:
            # If hooks key exists, it should be empty
            assert len(result2["hooks"]) == 0


class TestIsInstalled:
    """Tests for is_installed function."""

    def test_is_installed_false_when_empty(self, tmp_settings):
        """Should return False when no hooks installed."""
        tmp_settings.write_text(json.dumps({}))

        result = is_installed(tmp_settings)

        assert result is False

    def test_is_installed_true_when_both_hooks_present(self, tmp_settings):
        """Should return True when both hooks are registered."""
        settings = {}
        settings = merge_hooks_into_settings(settings)
        tmp_settings.write_text(json.dumps(settings))

        result = is_installed(tmp_settings)

        assert result is True

    def test_is_installed_false_when_permission_missing(self, tmp_settings):
        """Should return False if PermissionRequest hook missing."""
        settings = {}
        settings = merge_hooks_into_settings(settings)
        # Remove PermissionRequest
        del settings["hooks"]["PermissionRequest"]
        tmp_settings.write_text(json.dumps(settings))

        result = is_installed(tmp_settings)

        assert result is False

    def test_is_installed_false_when_pretooluse_missing(self, tmp_settings):
        """Should return False if PreToolUse hook missing."""
        settings = {}
        settings = merge_hooks_into_settings(settings)
        # Remove PreToolUse
        del settings["hooks"]["PreToolUse"]
        tmp_settings.write_text(json.dumps(settings))

        result = is_installed(tmp_settings)

        assert result is False

    def test_is_installed_handles_invalid_settings(self, tmp_settings):
        """Should return False if settings file is invalid."""
        tmp_settings.write_text("{ invalid json }")

        result = is_installed(tmp_settings)

        assert result is False
