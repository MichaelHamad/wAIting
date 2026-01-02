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
    "grace_period": 60,
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


def create_notify_script(audio_path: str, interval: int = 30, max_nags: int = 0, grace_period: int = 60) -> Path:
    """Create the notification shell script.

    Args:
        audio_path: Path to the audio file
        interval: Seconds between repeated notifications (0 = no repeat)
        max_nags: Maximum number of repeats (0 = unlimited)
        grace_period: Seconds after user activity to suppress notifications (0 = no grace)
    """
    script_path = get_hooks_dir() / "waiting-notify.sh"

    script_content = f"""#!/bin/bash
# Waiting - Nag user until they respond to Claude Code
# Audio file: {audio_path}

PID_FILE="/tmp/waiting-nag.pid"
ACTIVITY_FILE="/tmp/waiting-last-activity"
INTERVAL={interval}
MAX_NAGS={max_nags}
GRACE_PERIOD={grace_period}

# Check if user was recently active (within grace period)
SKIP_IMMEDIATE=0
if [ "$GRACE_PERIOD" -gt 0 ] && [ -f "$ACTIVITY_FILE" ]; then
    last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
    now=$(date +%s)
    elapsed=$((now - last_activity))
    if [ "$elapsed" -lt "$GRACE_PERIOD" ]; then
        # User was active recently, skip immediate sound but still start nag loop
        SKIP_IMMEDIATE=1
    fi
fi

# Kill any existing nag process
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

# Play immediately (unless within grace period)
if [ "$SKIP_IMMEDIATE" -eq 0 ]; then
    play_sound
fi

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
PID_FILE="/tmp/waiting-nag.pid"
ACTIVITY_FILE="/tmp/waiting-last-activity"

# Record that user was just active
date +%s > "$ACTIVITY_FILE"

# Kill the nag loop if running
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


def setup_hook(script_path: Path) -> None:
    """Add notification hooks to Claude settings for immediate alerts."""
    settings = load_claude_settings()
    stop_script = script_path.parent / "waiting-stop.sh"

    if "hooks" not in settings:
        settings["hooks"] = {}

    notify_config = {
        "type": "command",
        "command": str(script_path),
        "timeout": 10
    }

    stop_config = {
        "type": "command",
        "command": str(stop_script),
        "timeout": 5
    }

    # Set up PermissionRequest hook (fires for all input-blocking scenarios)
    # This covers: tool permissions, AskUserQuestion, and other user prompts
    if "PermissionRequest" not in settings["hooks"]:
        settings["hooks"]["PermissionRequest"] = []
    settings["hooks"]["PermissionRequest"] = [
        h for h in settings["hooks"]["PermissionRequest"]
        if not _is_waiting_hook(h)
    ]
    settings["hooks"]["PermissionRequest"].append({
        "matcher": "",
        "hooks": [notify_config.copy()]
    })

    # Set up PreToolUse hook to stop nagging immediately when user approves
    # (fires before tool runs, so nag stops right away)
    if "PreToolUse" not in settings["hooks"]:
        settings["hooks"]["PreToolUse"] = []
    settings["hooks"]["PreToolUse"] = [
        h for h in settings["hooks"]["PreToolUse"]
        if not _is_waiting_hook(h)
    ]
    settings["hooks"]["PreToolUse"].append({
        "matcher": "",
        "hooks": [stop_config.copy()]
    })

    # Also keep PostToolUse as backup (in case PreToolUse doesn't fire)
    if "PostToolUse" not in settings["hooks"]:
        settings["hooks"]["PostToolUse"] = []
    settings["hooks"]["PostToolUse"] = [
        h for h in settings["hooks"]["PostToolUse"]
        if not _is_waiting_hook(h)
    ]
    settings["hooks"]["PostToolUse"].append({
        "matcher": "",
        "hooks": [stop_config.copy()]
    })

    # Clean up old Notification hooks from previous versions
    if "Notification" in settings["hooks"]:
        settings["hooks"]["Notification"] = [
            h for h in settings["hooks"]["Notification"]
            if not _is_waiting_hook(h)
        ]
        if not settings["hooks"]["Notification"]:
            del settings["hooks"]["Notification"]

    save_claude_settings(settings)


def remove_hook() -> None:
    """Remove all waiting hooks from Claude settings."""
    settings = load_claude_settings()

    if "hooks" not in settings:
        return

    # Remove from all hook types we use
    for hook_type in ["PermissionRequest", "PreToolUse", "PostToolUse", "Notification"]:
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
@click.option("--grace-period", type=int, default=None, help="Seconds after activity to suppress notifications (0 = no grace)")
@click.pass_context
def cli(ctx, audio: str | None, interval: int | None, max_nags: int | None, grace_period: int | None):
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
        if grace_period is None:
            grace_period = config.get("grace_period", DEFAULT_CONFIG["grace_period"])

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
        click.echo(f"  Grace period: {grace_period}s" + (" (disabled)" if grace_period == 0 else ""))

        # Create the notify script
        script_path = create_notify_script(audio_path, interval, max_nags, grace_period)
        click.echo(f"  Script: {script_path}")

        # Add hook to Claude settings
        setup_hook(script_path)
        click.echo(f"  Hooks: {get_claude_settings_path()}")

        click.echo()
        click.echo("Done! Claude Code will nag you when waiting for input.")
        click.echo()
        click.echo("Behavior:")
        if grace_period > 0:
            click.echo(f"  - Waits {grace_period}s after your last response before alerting")
        click.echo("  - Plays sound when Claude needs input")
        if interval > 0:
            click.echo(f"  - Repeats every {interval}s until you respond")
        click.echo("  - Stops automatically when you respond")


@cli.command()
def disable():
    """Disable waiting notifications."""
    remove_hook()

    # Remove scripts
    for script_name in ["waiting-notify.sh", "waiting-stop.sh"]:
        script_path = get_hooks_dir() / script_name
        if script_path.exists():
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
    import signal

    pid_file = Path("/tmp/waiting-nag.pid")
    activity_file = Path("/tmp/waiting-last-activity")
    killed = False

    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            # Kill the process and its children
            os.kill(pid, signal.SIGTERM)
            killed = True
        except (ValueError, ProcessLookupError, PermissionError):
            pass  # Process already dead or invalid PID
        pid_file.unlink(missing_ok=True)

    # Also record activity so grace period kicks in
    if activity_file.exists() or killed:
        import time
        activity_file.write_text(str(int(time.time())))

    return killed


@cli.command()
def status():
    """Show current waiting configuration."""
    settings = load_claude_settings()
    script_path = get_hooks_dir() / "waiting-notify.sh"

    # Check if PermissionRequest hook is configured
    hook_found = False
    if "hooks" in settings:
        if "PermissionRequest" in settings["hooks"]:
            for h in settings["hooks"]["PermissionRequest"]:
                if _is_waiting_hook(h):
                    hook_found = True
                    break

    if hook_found and script_path.exists():
        click.echo("Status: ENABLED")
        click.echo(f"  Script: {script_path}")

        # Parse config from script
        audio = None
        interval = None
        max_nags = None
        grace_period = None
        with open(script_path) as f:
            for line in f:
                if line.startswith("# Audio file:"):
                    audio = line.split(":", 1)[1].strip()
                elif line.startswith("INTERVAL="):
                    interval = line.split("=", 1)[1].strip()
                elif line.startswith("MAX_NAGS="):
                    max_nags = line.split("=", 1)[1].strip()
                elif line.startswith("GRACE_PERIOD="):
                    grace_period = line.split("=", 1)[1].strip()

        if audio:
            click.echo(f"  Audio: {audio}")
        if grace_period:
            click.echo(f"  Grace period: {grace_period}s" + (" (disabled)" if grace_period == "0" else ""))
        if interval:
            click.echo(f"  Interval: {interval}s" + (" (no repeat)" if interval == "0" else ""))
        if max_nags:
            click.echo(f"  Max nags: {'unlimited' if max_nags == '0' else max_nags}")

        # Check if currently nagging
        pid_file = Path("/tmp/waiting-nag.pid")
        if pid_file.exists():
            click.echo(f"  Currently: NAGGING (pid file exists)")
    else:
        click.echo("Status: DISABLED")
        click.echo()
        click.echo("Run: waiting")


@cli.command()
@click.option("--audio", type=click.Path(), help="Default audio file path (use 'default' for bundled sound)")
@click.option("--interval", type=int, help="Default seconds between nags")
@click.option("--max-nags", type=int, help="Default max repeats")
@click.option("--grace-period", type=int, help="Default grace period in seconds")
@click.option("--show", is_flag=True, help="Show current config without modifying")
@click.option("--reset", is_flag=True, help="Reset to default configuration")
def configure(audio: str | None, interval: int | None, max_nags: int | None, grace_period: int | None, show: bool, reset: bool):
    """Configure default settings.

    Examples:
        waiting configure --grace-period 30 --interval 15
        waiting configure --audio /path/to/sound.wav
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

    if show or (audio is None and interval is None and max_nags is None and grace_period is None):
        config = load_config()
        click.echo(f"Config: {config_path}")
        if not config_path.exists():
            click.echo("  (using defaults, no config file)")
        click.echo()
        click.echo("Current settings:")
        audio_display = config['audio'] if config['audio'] != "default" else "default (bundled bell.wav)"
        click.echo(f"  audio:        {audio_display}")
        click.echo(f"  grace_period: {config['grace_period']}s")
        click.echo(f"  interval:     {config['interval']}s")
        click.echo(f"  max_nags:     {config['max_nags'] if config['max_nags'] > 0 else 'unlimited'}")
        return

    # Load existing config and update
    config = load_config()

    if audio is not None:
        if audio.lower() == "default":
            config["audio"] = None
        else:
            audio_path = str(Path(audio).expanduser().resolve())
            if not Path(audio_path).exists():
                raise click.ClickException(f"Audio file not found: {audio_path}")
            config["audio"] = audio_path

    if interval is not None:
        config["interval"] = interval
    if max_nags is not None:
        config["max_nags"] = max_nags
    if grace_period is not None:
        config["grace_period"] = grace_period

    save_config(config)
    click.echo(f"Config saved to: {config_path}")
    click.echo()
    click.echo("Updated settings:")
    audio_display = config['audio'] if config['audio'] != "default" else "default (bundled bell.wav)"
    click.echo(f"  audio:        {audio_display}")
    click.echo(f"  grace_period: {config['grace_period']}s")
    click.echo(f"  interval:     {config['interval']}s")
    click.echo(f"  max_nags:     {config['max_nags'] if config['max_nags'] > 0 else 'unlimited'}")
    click.echo()
    click.echo("Run 'waiting' to apply these settings.")


if __name__ == "__main__":
    cli()
