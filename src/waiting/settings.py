"""Settings management for Claude Code hook registration."""

import json
from pathlib import Path

from .errors import SettingsError


CLAUDE_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
HOOK_NAME_PERMISSION = "waiting-notify-permission"
HOOK_NAME_ACTIVITY = "waiting-activity-tooluse"


def load_settings(settings_path: Path | None = None) -> dict:
    """
    Load Claude Code settings from file.

    Args:
        settings_path: Path to settings.json. Defaults to ~/.claude/settings.json

    Returns:
        dict: Settings dictionary (empty dict if file doesn't exist)

    Raises:
        SettingsError: If file exists but is invalid JSON
    """
    if settings_path is None:
        settings_path = CLAUDE_SETTINGS_PATH

    if not settings_path.exists():
        return {}

    try:
        with open(settings_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise SettingsError(f"Failed to load settings from {settings_path}: {e}")


def save_settings(settings: dict, settings_path: Path | None = None) -> None:
    """
    Save Claude Code settings to file.

    Args:
        settings: Settings dictionary to save
        settings_path: Path to settings.json. Defaults to ~/.claude/settings.json

    Raises:
        SettingsError: If save fails
    """
    if settings_path is None:
        settings_path = CLAUDE_SETTINGS_PATH

    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2)
    except OSError as e:
        raise SettingsError(f"Failed to save settings to {settings_path}: {e}")


def get_hook_paths() -> dict[str, Path]:
    """
    Get paths to hook scripts.

    Returns:
        dict: Mapping of hook names to their script paths
    """
    hooks_dir = Path.home() / ".claude" / "hooks"
    return {
        HOOK_NAME_PERMISSION: hooks_dir / f"{HOOK_NAME_PERMISSION}.sh",
        HOOK_NAME_ACTIVITY: hooks_dir / f"{HOOK_NAME_ACTIVITY}.sh",
    }


def merge_hooks_into_settings(settings: dict) -> dict:
    """
    Add Waiting hooks to settings without overwriting existing hooks.

    This function:
    1. Preserves all existing hooks
    2. Adds or updates Waiting hooks
    3. Returns modified settings

    Args:
        settings: Existing settings dictionary

    Returns:
        dict: Modified settings with Waiting hooks added
    """
    hook_paths = get_hook_paths()

    # Ensure hooks structure exists
    if "hooks" not in settings:
        settings["hooks"] = {}

    # Add PermissionRequest hook
    if "PermissionRequest" not in settings["hooks"]:
        settings["hooks"]["PermissionRequest"] = []

    # Check if Waiting hook already registered
    perm_request_hooks = settings["hooks"]["PermissionRequest"]
    waiting_hook_exists = any(
        hook.get("matcher") == "*"
        and any(
            h.get("command", "").endswith(f"{HOOK_NAME_PERMISSION}.sh")
            for h in hook.get("hooks", [])
        )
        for hook in perm_request_hooks
        if isinstance(hook, dict)
    )

    if not waiting_hook_exists:
        perm_request_hooks.append(
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": str(hook_paths[HOOK_NAME_PERMISSION]),
                    }
                ],
            }
        )

    # Add PreToolUse hook (for activity detection)
    if "PreToolUse" not in settings["hooks"]:
        settings["hooks"]["PreToolUse"] = []

    pre_tool_use_hooks = settings["hooks"]["PreToolUse"]
    activity_hook_exists = any(
        hook.get("matcher") == "*"
        and any(
            h.get("command", "").endswith(f"{HOOK_NAME_ACTIVITY}.sh")
            for h in hook.get("hooks", [])
        )
        for hook in pre_tool_use_hooks
        if isinstance(hook, dict)
    )

    if not activity_hook_exists:
        pre_tool_use_hooks.append(
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": str(hook_paths[HOOK_NAME_ACTIVITY]),
                    }
                ],
            }
        )

    return settings


def remove_hooks_from_settings(settings: dict) -> dict:
    """
    Remove Waiting hooks from settings.

    Args:
        settings: Settings dictionary

    Returns:
        dict: Modified settings with Waiting hooks removed
    """
    if "hooks" not in settings:
        return settings

    hook_paths = get_hook_paths()
    perm_hook_path = str(hook_paths[HOOK_NAME_PERMISSION])
    activity_hook_path = str(hook_paths[HOOK_NAME_ACTIVITY])

    # Remove from PermissionRequest
    if "PermissionRequest" in settings["hooks"]:
        settings["hooks"]["PermissionRequest"] = [
            hook
            for hook in settings["hooks"]["PermissionRequest"]
            if not (
                isinstance(hook, dict)
                and hook.get("matcher") == "*"
                and any(
                    h.get("command", "") in [perm_hook_path]
                    for h in hook.get("hooks", [])
                )
            )
        ]
        if not settings["hooks"]["PermissionRequest"]:
            del settings["hooks"]["PermissionRequest"]

    # Remove from PreToolUse
    if "PreToolUse" in settings["hooks"]:
        settings["hooks"]["PreToolUse"] = [
            hook
            for hook in settings["hooks"]["PreToolUse"]
            if not (
                isinstance(hook, dict)
                and hook.get("matcher") == "*"
                and any(
                    h.get("command", "") in [activity_hook_path]
                    for h in hook.get("hooks", [])
                )
            )
        ]
        if not settings["hooks"]["PreToolUse"]:
            del settings["hooks"]["PreToolUse"]

    # Clean up empty hooks object
    if not settings["hooks"]:
        del settings["hooks"]

    return settings


def is_installed(settings_path: Path | None = None) -> bool:
    """
    Check if Waiting hooks are registered in settings.

    Args:
        settings_path: Path to settings.json. Defaults to ~/.claude/settings.json

    Returns:
        bool: True if hooks are registered, False otherwise
    """
    try:
        settings = load_settings(settings_path)
        if "hooks" not in settings:
            return False

        hook_paths = get_hook_paths()
        perm_hook_path = str(hook_paths[HOOK_NAME_PERMISSION])
        activity_hook_path = str(hook_paths[HOOK_NAME_ACTIVITY])

        # Check PermissionRequest
        perm_found = False
        if "PermissionRequest" in settings["hooks"]:
            for hook in settings["hooks"]["PermissionRequest"]:
                if isinstance(hook, dict):
                    for h in hook.get("hooks", []):
                        if h.get("command") == perm_hook_path:
                            perm_found = True

        # Check PreToolUse
        activity_found = False
        if "PreToolUse" in settings["hooks"]:
            for hook in settings["hooks"]["PreToolUse"]:
                if isinstance(hook, dict):
                    for h in hook.get("hooks", []):
                        if h.get("command") == activity_hook_path:
                            activity_found = True

        return perm_found and activity_found

    except SettingsError:
        return False
