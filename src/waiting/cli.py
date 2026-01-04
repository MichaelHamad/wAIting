"""Waiting CLI - Notify when Claude Code needs permission."""

import json
import os
import stat
from pathlib import Path

import click

CONFIG_PATH = Path.home() / ".waiting.json"
HOOKS_DIR = Path.home() / ".claude" / "hooks"
SETTINGS_PATH = Path.home() / ".claude" / "settings.json"

DEFAULT_CONFIG = {
    "audio": "default",
    "interval": 30,
    "max_nags": 0,
    "grace_period": 10,
}


def load_config() -> dict:
    """Load config from ~/.waiting.json or return defaults."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                config = json.load(f)
                return {**DEFAULT_CONFIG, **config}
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """Save config to ~/.waiting.json."""
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def get_audio_path() -> str:
    """Get path to bell.wav bundled with package."""
    config = load_config()
    if config["audio"] != "default" and Path(config["audio"]).exists():
        return str(Path(config["audio"]).resolve())
    # Use bundled bell.wav
    return str(Path(__file__).parent / "bell.wav")


def create_permission_script() -> str:
    """Generate the permission notification script."""
    config = load_config()
    audio_path = get_audio_path()
    interval = config["interval"]
    max_nags = config["max_nags"]
    grace_period = config["grace_period"]

    return f'''#!/bin/bash
# Waiting - Permission hook with wait-and-see logic

INTERVAL={interval}
MAX_NAGS={max_nags}
DELAY={grace_period}
AUDIO_PATH="{audio_path}"

# Get session ID from stdin JSON
HOOK_INPUT=$(cat)
SESSION_ID=$(echo "$HOOK_INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)
if [ -z "$SESSION_ID" ]; then
    SESSION_ID=$(echo "$HOOK_INPUT" | md5sum | cut -c1-8)
fi

# Session-specific files
NAG_MARKER="waiting-nag-$SESSION_ID"
PID_FILE="/tmp/$NAG_MARKER.pid"
PENDING_FILE="/tmp/waiting-pending-$SESSION_ID"
ACTIVITY_FILE="/tmp/waiting-activity-$SESSION_ID"

now=$(date +%s)

# Kill any existing nag for this session
pkill -f "$NAG_MARKER" 2>/dev/null
rm -f "$PID_FILE"
sleep 0.2

# Mark that permission dialog is open
echo "$now" > "$PENDING_FILE"

# Create nag script with session marker in filename (for pkill -f)
NAG_SCRIPT="/tmp/$NAG_MARKER.sh"

cat > "$NAG_SCRIPT" << 'NAGEOF'
#!/bin/bash

INTERVAL="$1"
MAX_NAGS="$2"
AUDIO_PATH="$3"
DELAY="$4"
PID_FILE="$5"
PENDING_FILE="$6"
ACTIVITY_FILE="$7"

start_time=$(date +%s)
nag_count=0
max_lifetime=600  # 10 minute orphan protection

cleanup() {{
    rm -f "$PID_FILE"
    exit 0
}}
trap cleanup SIGTERM SIGINT

play_sound() {{
    if command -v aplay &> /dev/null; then
        aplay -q "$AUDIO_PATH" 2>/dev/null &
    elif command -v paplay &> /dev/null; then
        paplay "$AUDIO_PATH" 2>/dev/null &
    elif command -v afplay &> /dev/null; then
        afplay "$AUDIO_PATH" 2>/dev/null &
    elif command -v powershell.exe &> /dev/null; then
        win_path=$(wslpath -w "$AUDIO_PATH" 2>/dev/null)
        powershell.exe -c "(New-Object Media.SoundPlayer '$win_path').PlaySync()" &
    fi
}}

# Initial grace period - sleep in 1-second increments
for ((i=0; i<DELAY; i++)); do
    sleep 1
    # Check if we should stop
    [ ! -f "$PID_FILE" ] && cleanup

    # Check if user responded
    if [ -f "$ACTIVITY_FILE" ]; then
        last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
        if [ "$last_activity" -ge "$start_time" ]; then
            cleanup
        fi
    fi
done

# Check if pending file still exists (user might have already responded)
[ ! -f "$PENDING_FILE" ] && cleanup

# Main nag loop
while true; do
    # Check max lifetime
    elapsed=$(($(date +%s) - start_time))
    [ "$elapsed" -ge "$max_lifetime" ] && cleanup

    # Check if we should stop
    [ ! -f "$PID_FILE" ] && cleanup

    # Check if user responded
    if [ -f "$ACTIVITY_FILE" ]; then
        last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
        if [ "$last_activity" -ge "$start_time" ]; then
            cleanup
        fi
    fi

    # Play sound
    play_sound
    nag_count=$((nag_count + 1))

    # Check max nags (0 = unlimited)
    if [ "$MAX_NAGS" -gt 0 ] && [ "$nag_count" -ge "$MAX_NAGS" ]; then
        cleanup
    fi

    # Sleep interval in 1-second increments for responsive termination
    for ((i=0; i<INTERVAL; i++)); do
        sleep 1
        [ ! -f "$PID_FILE" ] && cleanup

        if [ -f "$ACTIVITY_FILE" ]; then
            last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
            if [ "$last_activity" -ge "$start_time" ]; then
                cleanup
            fi
        fi
    done
done
NAGEOF

chmod +x "$NAG_SCRIPT"

# Run detached (crucial for hook to return quickly)
nohup "$NAG_SCRIPT" "$INTERVAL" "$MAX_NAGS" "$AUDIO_PATH" "$DELAY" "$PID_FILE" "$PENDING_FILE" "$ACTIVITY_FILE" > /dev/null 2>&1 &
echo $! > "$PID_FILE"
disown
'''


def create_activity_submit_script() -> str:
    """Generate the UserPromptSubmit activity script."""
    return '''#!/bin/bash
# Waiting - Activity hook for user message submit

HOOK_INPUT=$(cat)
SESSION_ID=$(echo "$HOOK_INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)
if [ -z "$SESSION_ID" ]; then
    SESSION_ID=$(echo "$HOOK_INPUT" | md5sum | cut -c1-8)
fi

ACTIVITY_FILE="/tmp/waiting-activity-$SESSION_ID"
PID_FILE="/tmp/waiting-nag-$SESSION_ID.pid"
PENDING_FILE="/tmp/waiting-pending-$SESSION_ID"

# Update activity timestamp (+1 buffer for same-second cascading)
echo "$(($(date +%s) + 1))" > "$ACTIVITY_FILE"

# Kill any nag process
pkill -f "waiting-nag-$SESSION_ID" 2>/dev/null
rm -f "$PID_FILE"
rm -f "$PENDING_FILE"
'''


def create_activity_tooluse_script() -> str:
    """Generate the PreToolUse activity script."""
    return '''#!/bin/bash
# Waiting - Activity hook for tool approval

HOOK_INPUT=$(cat)
SESSION_ID=$(echo "$HOOK_INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)
if [ -z "$SESSION_ID" ]; then
    SESSION_ID=$(echo "$HOOK_INPUT" | md5sum | cut -c1-8)
fi

ACTIVITY_FILE="/tmp/waiting-activity-$SESSION_ID"
PID_FILE="/tmp/waiting-nag-$SESSION_ID.pid"
PENDING_FILE="/tmp/waiting-pending-$SESSION_ID"

# Update activity timestamp (+1 buffer for same-second cascading)
echo "$(($(date +%s) + 1))" > "$ACTIVITY_FILE"

# Kill any nag process
pkill -f "waiting-nag-$SESSION_ID" 2>/dev/null
rm -f "$PID_FILE"
rm -f "$PENDING_FILE"
'''


def setup_hooks() -> None:
    """Install hooks scripts and update Claude settings."""
    # Create hooks directory
    HOOKS_DIR.mkdir(parents=True, exist_ok=True)

    # Write scripts
    scripts = {
        "waiting-notify-permission.sh": create_permission_script(),
        "waiting-activity-submit.sh": create_activity_submit_script(),
        "waiting-activity-tooluse.sh": create_activity_tooluse_script(),
    }

    for name, content in scripts.items():
        script_path = HOOKS_DIR / name
        with open(script_path, "w") as f:
            f.write(content)
        # Make executable
        script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Update Claude settings
    settings = {}
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH) as f:
                settings = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    hooks = settings.get("hooks", {})

    # Add our hooks
    hooks["PermissionRequest"] = [{
        "matcher": "",
        "hooks": [{
            "type": "command",
            "command": str(HOOKS_DIR / "waiting-notify-permission.sh"),
            "timeout": 10
        }]
    }]

    hooks["PreToolUse"] = [{
        "matcher": "",
        "hooks": [{
            "type": "command",
            "command": str(HOOKS_DIR / "waiting-activity-tooluse.sh"),
            "timeout": 5
        }]
    }]

    hooks["UserPromptSubmit"] = [{
        "matcher": "",
        "hooks": [{
            "type": "command",
            "command": str(HOOKS_DIR / "waiting-activity-submit.sh"),
            "timeout": 5
        }]
    }]

    settings["hooks"] = hooks

    # Ensure .claude directory exists
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)


def remove_hooks() -> None:
    """Remove hooks scripts and clean up Claude settings."""
    # Remove scripts
    for name in ["waiting-notify-permission.sh", "waiting-activity-submit.sh", "waiting-activity-tooluse.sh"]:
        script_path = HOOKS_DIR / name
        if script_path.exists():
            script_path.unlink()

    # Clean up Claude settings
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH) as f:
                settings = json.load(f)

            hooks = settings.get("hooks", {})
            for hook_type in ["PermissionRequest", "PreToolUse", "UserPromptSubmit"]:
                if hook_type in hooks:
                    # Remove waiting hooks
                    hooks[hook_type] = [
                        h for h in hooks[hook_type]
                        if not any("waiting-" in str(hook.get("command", ""))
                                   for hook in h.get("hooks", []))
                    ]
                    # Remove empty arrays
                    if not hooks[hook_type]:
                        del hooks[hook_type]

            settings["hooks"] = hooks

            with open(SETTINGS_PATH, "w") as f:
                json.dump(settings, f, indent=2)
        except (json.JSONDecodeError, IOError):
            pass

    # Kill any running nag processes
    os.system("pkill -f 'waiting-nag-' 2>/dev/null")


def is_enabled() -> bool:
    """Check if waiting hooks are installed."""
    script_path = HOOKS_DIR / "waiting-notify-permission.sh"
    return script_path.exists()


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Notify when Claude Code needs permission."""
    if ctx.invoked_subcommand is None:
        # Default command: enable
        setup_hooks()
        click.echo("Waiting notifications enabled.")
        click.echo("Restart Claude Code to activate hooks.")


@cli.command()
def disable():
    """Remove hooks and scripts."""
    remove_hooks()
    click.echo("Waiting notifications disabled.")


@cli.command()
def status():
    """Show if waiting is enabled."""
    if is_enabled():
        click.echo("Waiting is enabled.")
    else:
        click.echo("Waiting is disabled.")


@cli.command()
@click.option("--show", is_flag=True, help="Show current configuration")
@click.option("--interval", type=int, help="Seconds between nags")
@click.option("--max-nags", type=int, help="Maximum nags (0=unlimited)")
@click.option("--grace-period", type=int, help="Initial delay before first nag")
@click.option("--audio", type=str, help="Path to audio file (or 'default')")
def configure(show, interval, max_nags, grace_period, audio):
    """View or modify configuration."""
    config = load_config()

    if show or (interval is None and max_nags is None and grace_period is None and audio is None):
        click.echo(json.dumps(config, indent=2))
        return

    if interval is not None:
        config["interval"] = interval
    if max_nags is not None:
        config["max_nags"] = max_nags
    if grace_period is not None:
        config["grace_period"] = grace_period
    if audio is not None:
        config["audio"] = audio

    save_config(config)
    click.echo("Configuration updated.")

    # Regenerate scripts if enabled
    if is_enabled():
        setup_hooks()
        click.echo("Hooks updated with new configuration.")


if __name__ == "__main__":
    cli()
