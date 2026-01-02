"""CLI interface for waiting - hook-based notification setup."""

import json
import os
import stat
import sys
from pathlib import Path

import click

# Default configuration values
DEFAULT_CONFIG = {
    "audio": "default",  # "default" = bundled bell.wav, or path to custom .wav
    "interval": 30,
    "max_nags": 0,
    # Which hooks are enabled (stop, permission, idle)
    "enabled_hooks": ["stop", "permission", "idle"],
    # Per-hook grace periods (seconds of inactivity before bell plays)
    "grace_period_stop": 300,         # 5 min - after Claude finishes responding
    "grace_period_permission": 10,    # 10s - when permission dialog shown
    "grace_period_idle": 0,           # 0 - idle_prompt already has 60s delay built in
}


def get_config_path() -> Path:
    """Get the waiting config file path.

    Can be overridden with WAITING_CONFIG environment variable.
    """
    if "WAITING_CONFIG" in os.environ:
        return Path(os.environ["WAITING_CONFIG"]).expanduser()
    return Path.home() / ".waiting.json"


def load_config() -> dict:
    """Load user config, returning defaults for missing values."""
    config_path = get_config_path()
    config = DEFAULT_CONFIG.copy()

    if config_path.exists():
        with open(config_path) as f:
            user_config = json.load(f)
            config.update(user_config)

    return config


def save_config(config: dict) -> None:
    """Save user config."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def get_default_audio() -> str:
    """Get path to bundled bell.wav."""
    return str(Path(__file__).parent / "bell.wav")


def get_claude_settings_path() -> Path:
    """Get the Claude Code user settings path."""
    return Path.home() / ".claude" / "settings.json"


def get_hooks_dir() -> Path:
    """Get the hooks directory path."""
    hooks_dir = Path.home() / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    return hooks_dir


def load_claude_settings() -> dict:
    """Load Claude Code settings, creating if needed."""
    settings_path = get_claude_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    if settings_path.exists():
        with open(settings_path) as f:
            return json.load(f)
    return {}


def save_claude_settings(settings: dict) -> None:
    """Save Claude Code settings."""
    settings_path = get_claude_settings_path()
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)


def create_notify_script(
    audio_path: str,
    interval: int = 30,
    max_nags: int = 0,
    grace_period: int = 60,
    hook_type: str = "default"
) -> Path:
    """Create the notification shell script for a specific hook type.

    Args:
        audio_path: Path to the audio file
        interval: Seconds between repeated notifications (0 = no repeat)
        max_nags: Maximum number of repeats (0 = unlimited)
        grace_period: Seconds after user activity to suppress notifications (0 = no grace)
        hook_type: The hook type (stop, permission, idle, default)
    """
    script_name = f"waiting-notify-{hook_type}.sh" if hook_type != "default" else "waiting-notify.sh"
    script_path = get_hooks_dir() / script_name

    script_content = f"""#!/bin/bash
# Waiting - Nag user until they respond to Claude Code
# Audio file: {audio_path}

INTERVAL={interval}
MAX_NAGS={max_nags}
GRACE_PERIOD={grace_period}

# Read hook context from stdin to get session ID
HOOK_INPUT=$(cat)
SESSION_ID=$(echo "$HOOK_INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)

# Fall back to a hash of the input if no session_id found
if [ -z "$SESSION_ID" ]; then
    SESSION_ID=$(echo "$HOOK_INPUT" | md5sum | cut -c1-8)
fi

# Use session-specific files
PID_FILE="/tmp/waiting-nag-$SESSION_ID.pid"
ACTIVITY_FILE="/tmp/waiting-activity-$SESSION_ID"

# Check if user was recently active (within grace period)
if [ "$GRACE_PERIOD" -gt 0 ] && [ -f "$ACTIVITY_FILE" ]; then
    last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
    now=$(date +%s)
    elapsed=$((now - last_activity))
    if [ "$elapsed" -lt "$GRACE_PERIOD" ]; then
        # User was active recently, skip everything - don't annoy them
        exit 0
    fi
fi

# Kill any existing nag process for THIS session
if [ -f "$PID_FILE" ]; then
    old_pid=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$old_pid" ]; then
        kill "$old_pid" 2>/dev/null
        pkill -P "$old_pid" 2>/dev/null
    fi
    rm -f "$PID_FILE"
fi

play_sound() {{
    if command -v aplay &> /dev/null; then
        aplay -q "{audio_path}" 2>/dev/null
    elif command -v paplay &> /dev/null; then
        paplay "{audio_path}" 2>/dev/null
    elif command -v pw-play &> /dev/null; then
        pw-play "{audio_path}" 2>/dev/null
    elif command -v afplay &> /dev/null; then
        afplay "{audio_path}" 2>/dev/null
    elif command -v powershell.exe &> /dev/null; then
        win_path=$(wslpath -w "{audio_path}" 2>/dev/null)
        if [ -n "$win_path" ]; then
            powershell.exe -c "(New-Object Media.SoundPlayer '$win_path').PlaySync()" 2>/dev/null
        else
            powershell.exe -c "(New-Object Media.SoundPlayer 'C:\\Windows\\Media\\notify.wav').PlaySync()" 2>/dev/null
        fi
    fi
}}

# Play immediately
play_sound

# If interval is 0, just play once and exit (but only if we played)
if [ "$INTERVAL" -eq 0 ]; then
    exit 0
fi

# Start background nag loop
(
    count=0
    while true; do
        sleep "$INTERVAL"
        play_sound
        count=$((count + 1))
        if [ "$MAX_NAGS" -gt 0 ] && [ "$count" -ge "$MAX_NAGS" ]; then
            break
        fi
    done
) &

# Save PID of background process
echo $! > "$PID_FILE"
"""

    with open(script_path, "w") as f:
        f.write(script_content)

    # Make executable
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Create stop script (kills the nag loop and records activity)
    stop_script_path = get_hooks_dir() / "waiting-stop.sh"
    stop_content = """#!/bin/bash
# Stop the waiting nag loop and record user activity

# Read hook context from stdin to get session ID
HOOK_INPUT=$(cat)
SESSION_ID=$(echo "$HOOK_INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)

# Fall back to a hash of the input if no session_id found
if [ -z "$SESSION_ID" ]; then
    SESSION_ID=$(echo "$HOOK_INPUT" | md5sum | cut -c1-8)
fi

# Use session-specific files
PID_FILE="/tmp/waiting-nag-$SESSION_ID.pid"
ACTIVITY_FILE="/tmp/waiting-activity-$SESSION_ID"

# Record that user was just active
date +%s > "$ACTIVITY_FILE"

# Kill the nag loop if running for THIS session
if [ -f "$PID_FILE" ]; then
    pid=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$pid" ]; then
        kill "$pid" 2>/dev/null
        pkill -P "$pid" 2>/dev/null
    fi
    rm -f "$PID_FILE"
fi
"""
    with open(stop_script_path, "w") as f:
        f.write(stop_content)
    stop_script_path.chmod(stop_script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return script_path


def _is_waiting_hook(hook_config: dict) -> bool:
    """Check if a hook config is one of ours."""
    for hook in hook_config.get("hooks", []):
        cmd = hook.get("command", "")
        if "waiting-notify" in cmd or "waiting-stop" in cmd:
            return True
    return False


def setup_hooks(
    stop_script_path: Path,
    permission_script_path: Path,
    idle_script_path: Path,
    user_stop_script: Path,
    enabled_hooks: list[str]
) -> None:
    """Add notification hooks to Claude settings with per-hook scripts."""
    settings = load_claude_settings()

    if "hooks" not in settings:
        settings["hooks"] = {}

    stop_config = {
        "type": "command",
        "command": str(user_stop_script),
        "timeout": 5
    }

    # PermissionRequest - fires when Claude shows a permission dialog
    if "PermissionRequest" not in settings["hooks"]:
        settings["hooks"]["PermissionRequest"] = []
    settings["hooks"]["PermissionRequest"] = [
        h for h in settings["hooks"]["PermissionRequest"]
        if not _is_waiting_hook(h)
    ]
    if "permission" in enabled_hooks:
        settings["hooks"]["PermissionRequest"].append({
            "matcher": "",
            "hooks": [{
                "type": "command",
                "command": str(permission_script_path),
                "timeout": 10
            }]
        })
    if not settings["hooks"]["PermissionRequest"]:
        del settings["hooks"]["PermissionRequest"]

    # Stop - fires when Claude finishes responding
    if "Stop" not in settings["hooks"]:
        settings["hooks"]["Stop"] = []
    settings["hooks"]["Stop"] = [
        h for h in settings["hooks"]["Stop"]
        if not _is_waiting_hook(h)
    ]
    if "stop" in enabled_hooks:
        settings["hooks"]["Stop"].append({
            "matcher": "",
            "hooks": [{
                "type": "command",
                "command": str(stop_script_path),
                "timeout": 10
            }]
        })
    if not settings["hooks"]["Stop"]:
        del settings["hooks"]["Stop"]

    # Notification with idle_prompt - backup for long waits
    if "Notification" not in settings["hooks"]:
        settings["hooks"]["Notification"] = []
    settings["hooks"]["Notification"] = [
        h for h in settings["hooks"]["Notification"]
        if not _is_waiting_hook(h)
    ]
    if "idle" in enabled_hooks:
        settings["hooks"]["Notification"].append({
            "matcher": "idle_prompt",
            "hooks": [{
                "type": "command",
                "command": str(idle_script_path),
                "timeout": 10
            }]
        })
    if not settings["hooks"]["Notification"]:
        del settings["hooks"]["Notification"]

    # Stop nagging when user submits a prompt (always enabled)
    if "UserPromptSubmit" not in settings["hooks"]:
        settings["hooks"]["UserPromptSubmit"] = []
    settings["hooks"]["UserPromptSubmit"] = [
        h for h in settings["hooks"]["UserPromptSubmit"]
        if not _is_waiting_hook(h)
    ]
    settings["hooks"]["UserPromptSubmit"].append({
        "matcher": "",
        "hooks": [stop_config.copy()]
    })

    # Clean up old PreToolUse/PostToolUse hooks from previous versions
    for old_hook_type in ["PreToolUse", "PostToolUse"]:
        if old_hook_type in settings["hooks"]:
            settings["hooks"][old_hook_type] = [
                h for h in settings["hooks"][old_hook_type]
                if not _is_waiting_hook(h)
            ]
            if not settings["hooks"][old_hook_type]:
                del settings["hooks"][old_hook_type]

    save_claude_settings(settings)


def remove_hook() -> None:
    """Remove all waiting hooks from Claude settings."""
    settings = load_claude_settings()

    if "hooks" not in settings:
        return

    # Remove from all hook types we use (current and legacy)
    for hook_type in ["Stop", "Notification", "UserPromptSubmit", "PermissionRequest", "PreToolUse", "PostToolUse"]:
        if hook_type in settings["hooks"]:
            settings["hooks"][hook_type] = [
                h for h in settings["hooks"][hook_type]
                if not _is_waiting_hook(h)
            ]
            if not settings["hooks"][hook_type]:
                del settings["hooks"][hook_type]

    # Clean up empty hooks object
    if not settings["hooks"]:
        del settings["hooks"]

    save_claude_settings(settings)


@click.group(invoke_without_command=True)
@click.version_option()
@click.option("--audio", type=click.Path(exists=True), help="Custom audio file path")
@click.option("--interval", type=int, default=None, help="Seconds between nags (0 = no repeat)")
@click.option("--max-nags", type=int, default=None, help="Max repeats (0 = unlimited)")
@click.pass_context
def cli(ctx, audio: str | None, interval: int | None, max_nags: int | None):
    """Waiting - Nag you until you respond to Claude Code.

    Run without arguments to enable with defaults from config file.

    Config: ~/.waiting.json (override with WAITING_CONFIG env var)
    """
    if ctx.invoked_subcommand is None:
        # Load config and apply CLI overrides
        config = load_config()

        if audio is None:
            audio = config.get("audio", "default")
        if interval is None:
            interval = config.get("interval", DEFAULT_CONFIG["interval"])
        if max_nags is None:
            max_nags = config.get("max_nags", DEFAULT_CONFIG["max_nags"])

        # Per-hook grace periods
        grace_stop = config.get("grace_period_stop", DEFAULT_CONFIG["grace_period_stop"])
        grace_permission = config.get("grace_period_permission", DEFAULT_CONFIG["grace_period_permission"])
        grace_idle = config.get("grace_period_idle", DEFAULT_CONFIG["grace_period_idle"])

        # Enabled hooks
        enabled_hooks = config.get("enabled_hooks", DEFAULT_CONFIG["enabled_hooks"])

        # Resolve audio path
        if audio is None or audio == "default":
            audio_path = get_default_audio()
        else:
            audio_path = str(Path(audio).expanduser().resolve())

        if not Path(audio_path).exists():
            raise click.ClickException(f"Audio file not found: {audio_path}")

        click.echo(f"Setting up waiting notification...")
        click.echo(f"  Audio: {audio_path}")
        click.echo(f"  Interval: {interval}s" + (" (no repeat)" if interval == 0 else ""))
        click.echo(f"  Max nags: {max_nags if max_nags > 0 else 'unlimited'}")
        click.echo(f"  Enabled hooks: {', '.join(enabled_hooks)}")
        click.echo(f"  Grace periods:")
        if "stop" in enabled_hooks:
            click.echo(f"    Stop hook: {grace_stop}s ({grace_stop // 60}min)")
        if "permission" in enabled_hooks:
            click.echo(f"    Permission hook: {grace_permission}s")
        if "idle" in enabled_hooks:
            click.echo(f"    Idle hook: {grace_idle}s")

        # Create per-hook notify scripts
        stop_script = create_notify_script(audio_path, interval, max_nags, grace_stop, "stop")
        permission_script = create_notify_script(audio_path, interval, max_nags, grace_permission, "permission")
        idle_script = create_notify_script(audio_path, interval, max_nags, grace_idle, "idle")

        # The user stop script is created by create_notify_script as a side effect
        user_stop_script = get_hooks_dir() / "waiting-stop.sh"

        click.echo(f"  Scripts: {get_hooks_dir()}")

        # Add hooks to Claude settings
        setup_hooks(stop_script, permission_script, idle_script, user_stop_script, enabled_hooks)
        click.echo(f"  Hooks: {get_claude_settings_path()}")

        click.echo()
        click.echo("Done! Claude Code will nag you when waiting for input.")
        click.echo()
        click.echo("Behavior:")
        if "stop" in enabled_hooks:
            click.echo(f"  - Stop hook: alerts after {grace_stop}s ({grace_stop // 60}min) of inactivity")
        if "permission" in enabled_hooks:
            click.echo(f"  - Permission hook: alerts after {grace_permission}s of inactivity")
        if "idle" in enabled_hooks:
            click.echo(f"  - Idle hook: alerts after 60s idle (built-in)")
        click.echo("  - Plays sound when Claude needs input")
        if interval > 0:
            click.echo(f"  - Repeats every {interval}s until you respond")
        click.echo("  - Stops automatically when you respond")


@cli.command()
def disable():
    """Disable waiting notifications."""
    remove_hook()

    # Remove all scripts (including per-hook variants)
    script_patterns = [
        "waiting-notify.sh",
        "waiting-notify-*.sh",
        "waiting-stop.sh",
    ]
    hooks_dir = get_hooks_dir()
    for pattern in script_patterns:
        for script_path in hooks_dir.glob(pattern):
            script_path.unlink()

    # Kill any running nag process
    _kill_nag_process()

    click.echo("Waiting notifications disabled.")


@cli.command()
def kill():
    """Stop the current nag loop without disabling hooks."""
    killed = _kill_nag_process()
    if killed:
        click.echo("Nag loop stopped.")
    else:
        click.echo("No nag loop running.")


def _kill_nag_process() -> bool:
    """Kill any running nag process. Returns True if a process was killed."""
    import subprocess
    import signal

    killed = False
    tmp_dir = Path("/tmp")

    # Find all session-specific PID files (new format)
    for pid_file in tmp_dir.glob("waiting-nag-*.pid"):
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            # Also kill child processes
            subprocess.run(["pkill", "-P", str(pid)], capture_output=True)
            killed = True
        except (ValueError, ProcessLookupError, PermissionError):
            pass
        pid_file.unlink(missing_ok=True)

    # Also handle legacy single PID file
    legacy_pid_file = tmp_dir / "waiting-nag.pid"
    if legacy_pid_file.exists():
        try:
            pid = int(legacy_pid_file.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            subprocess.run(["pkill", "-P", str(pid)], capture_output=True)
            killed = True
        except (ValueError, ProcessLookupError, PermissionError):
            pass
        legacy_pid_file.unlink(missing_ok=True)

    # Kill any orphaned waiting-notify processes that might not have PID files
    try:
        result = subprocess.run(
            ["pkill", "-f", "waiting-notify.sh"],
            capture_output=True
        )
        if result.returncode == 0:
            killed = True
    except Exception:
        pass

    # Update activity files so grace period kicks in
    import time
    now = str(int(time.time()))
    for activity_file in tmp_dir.glob("waiting-activity-*"):
        activity_file.write_text(now)
    # Legacy activity file
    legacy_activity = tmp_dir / "waiting-last-activity"
    if legacy_activity.exists():
        legacy_activity.write_text(now)

    return killed


@cli.command()
def status():
    """Show current waiting configuration."""
    settings = load_claude_settings()
    config = load_config()

    # Check which hooks are currently registered
    active_hooks = []
    if "hooks" in settings:
        if "Stop" in settings["hooks"]:
            for h in settings["hooks"]["Stop"]:
                if _is_waiting_hook(h):
                    active_hooks.append("stop")
                    break
        if "PermissionRequest" in settings["hooks"]:
            for h in settings["hooks"]["PermissionRequest"]:
                if _is_waiting_hook(h):
                    active_hooks.append("permission")
                    break
        if "Notification" in settings["hooks"]:
            for h in settings["hooks"]["Notification"]:
                if _is_waiting_hook(h):
                    active_hooks.append("idle")
                    break

    if active_hooks:
        click.echo("Status: ENABLED")
        click.echo(f"  Active hooks: {', '.join(active_hooks)}")
        click.echo(f"  Scripts: {get_hooks_dir()}")

        # Show config
        click.echo()
        click.echo("Configuration:")
        audio = config.get('audio', 'default')
        if audio == 'default':
            audio = get_default_audio()
        click.echo(f"  Audio: {audio}")
        click.echo(f"  Interval: {config.get('interval', DEFAULT_CONFIG['interval'])}s")
        max_nags = config.get('max_nags', DEFAULT_CONFIG['max_nags'])
        click.echo(f"  Max nags: {'unlimited' if max_nags == 0 else max_nags}")

        click.echo()
        click.echo("Grace periods:")
        if "stop" in active_hooks:
            gs = config.get('grace_period_stop', DEFAULT_CONFIG['grace_period_stop'])
            click.echo(f"  Stop: {gs}s ({gs // 60}min)")
        if "permission" in active_hooks:
            gp = config.get('grace_period_permission', DEFAULT_CONFIG['grace_period_permission'])
            click.echo(f"  Permission: {gp}s")
        if "idle" in active_hooks:
            gi = config.get('grace_period_idle', DEFAULT_CONFIG['grace_period_idle'])
            click.echo(f"  Idle: {gi}s (+ 60s built-in)")

        # Check if currently nagging
        tmp_dir = Path("/tmp")
        nag_pids = list(tmp_dir.glob("waiting-nag-*.pid"))
        if nag_pids:
            click.echo()
            click.echo(f"  Currently: NAGGING ({len(nag_pids)} session(s))")
    else:
        click.echo("Status: DISABLED")
        click.echo()
        click.echo("Run: waiting")


@cli.command()
@click.option("--audio", type=click.Path(), help="Default audio file path (use 'default' for bundled sound)")
@click.option("--interval", type=int, help="Default seconds between nags")
@click.option("--max-nags", type=int, help="Default max repeats")
@click.option("--grace-stop", type=int, help="Grace period for Stop hook (seconds)")
@click.option("--grace-permission", type=int, help="Grace period for Permission hook (seconds)")
@click.option("--grace-idle", type=int, help="Grace period for Idle hook (seconds)")
@click.option("--enable-hook", type=click.Choice(["stop", "permission", "idle"]), help="Enable a hook")
@click.option("--disable-hook", type=click.Choice(["stop", "permission", "idle"]), help="Disable a hook")
@click.option("--hooks", type=str, help="Set enabled hooks (comma-separated: stop,permission,idle)")
@click.option("--show", is_flag=True, help="Show current config without modifying")
@click.option("--reset", is_flag=True, help="Reset to default configuration")
def configure(
    audio: str | None,
    interval: int | None,
    max_nags: int | None,
    grace_stop: int | None,
    grace_permission: int | None,
    grace_idle: int | None,
    enable_hook: str | None,
    disable_hook: str | None,
    hooks: str | None,
    show: bool,
    reset: bool
):
    """Configure default settings.

    Examples:
        waiting configure --grace-stop 300 --grace-permission 10
        waiting configure --audio /path/to/sound.wav
        waiting configure --disable-hook idle
        waiting configure --hooks stop,permission
        waiting configure --show
        waiting configure --reset
    """
    config_path = get_config_path()

    if reset:
        if config_path.exists():
            config_path.unlink()
        click.echo("Config reset to defaults.")
        click.echo()
        show = True  # Show defaults after reset

    has_changes = any([audio, interval, max_nags, grace_stop, grace_permission, grace_idle, enable_hook, disable_hook, hooks])
    if show or not has_changes:
        config = load_config()
        click.echo(f"Config: {config_path}")
        if not config_path.exists():
            click.echo("  (using defaults, no config file)")
        click.echo()
        click.echo("Current settings:")
        audio_display = config.get('audio', 'default')
        if audio_display == "default" or audio_display is None:
            audio_display = "default (bundled bell.wav)"
        click.echo(f"  audio:             {audio_display}")
        click.echo(f"  interval:          {config.get('interval', DEFAULT_CONFIG['interval'])}s")
        max_nags_val = config.get('max_nags', DEFAULT_CONFIG['max_nags'])
        click.echo(f"  max_nags:          {max_nags_val if max_nags_val > 0 else 'unlimited'}")
        click.echo()
        enabled = config.get('enabled_hooks', DEFAULT_CONFIG['enabled_hooks'])
        click.echo(f"Enabled hooks: {', '.join(enabled)}")
        click.echo()
        click.echo("Grace periods (seconds of inactivity before bell):")
        gs = config.get('grace_period_stop', DEFAULT_CONFIG['grace_period_stop'])
        gp = config.get('grace_period_permission', DEFAULT_CONFIG['grace_period_permission'])
        gi = config.get('grace_period_idle', DEFAULT_CONFIG['grace_period_idle'])
        click.echo(f"  grace_period_stop:       {gs}s ({gs // 60}min)")
        click.echo(f"  grace_period_permission: {gp}s")
        click.echo(f"  grace_period_idle:       {gi}s")
        return

    # Load existing config and update
    config = load_config()

    if audio is not None:
        if audio.lower() == "default":
            config["audio"] = "default"
        else:
            audio_path = str(Path(audio).expanduser().resolve())
            if not Path(audio_path).exists():
                raise click.ClickException(f"Audio file not found: {audio_path}")
            config["audio"] = audio_path

    if interval is not None:
        config["interval"] = interval
    if max_nags is not None:
        config["max_nags"] = max_nags
    if grace_stop is not None:
        config["grace_period_stop"] = grace_stop
    if grace_permission is not None:
        config["grace_period_permission"] = grace_permission
    if grace_idle is not None:
        config["grace_period_idle"] = grace_idle

    # Handle hook enable/disable
    enabled_hooks = config.get("enabled_hooks", DEFAULT_CONFIG["enabled_hooks"]).copy()
    if hooks is not None:
        # Set exact list
        enabled_hooks = [h.strip() for h in hooks.split(",") if h.strip() in ["stop", "permission", "idle"]]
    if enable_hook is not None and enable_hook not in enabled_hooks:
        enabled_hooks.append(enable_hook)
    if disable_hook is not None and disable_hook in enabled_hooks:
        enabled_hooks.remove(disable_hook)
    config["enabled_hooks"] = enabled_hooks

    save_config(config)
    click.echo(f"Config saved to: {config_path}")
    click.echo()
    click.echo("Updated settings:")
    audio_display = config.get('audio', 'default')
    if audio_display == "default" or audio_display is None:
        audio_display = "default (bundled bell.wav)"
    click.echo(f"  audio:             {audio_display}")
    click.echo(f"  interval:          {config.get('interval', DEFAULT_CONFIG['interval'])}s")
    max_nags_val = config.get('max_nags', DEFAULT_CONFIG['max_nags'])
    click.echo(f"  max_nags:          {max_nags_val if max_nags_val > 0 else 'unlimited'}")
    click.echo()
    click.echo(f"Enabled hooks: {', '.join(config['enabled_hooks'])}")
    click.echo()
    click.echo("Grace periods:")
    gs = config.get('grace_period_stop', DEFAULT_CONFIG['grace_period_stop'])
    gp = config.get('grace_period_permission', DEFAULT_CONFIG['grace_period_permission'])
    gi = config.get('grace_period_idle', DEFAULT_CONFIG['grace_period_idle'])
    click.echo(f"  grace_period_stop:       {gs}s ({gs // 60}min)")
    click.echo(f"  grace_period_permission: {gp}s")
    click.echo(f"  grace_period_idle:       {gi}s")
    click.echo()
    click.echo("Run 'waiting' to apply these settings.")


if __name__ == "__main__":
    cli()
