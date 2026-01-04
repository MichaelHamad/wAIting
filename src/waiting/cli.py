"""Waiting CLI - Notify when Claude Code needs input."""

import json
import os
import stat
from pathlib import Path

import click

CONFIG_PATH = Path(os.environ.get("WAITING_CONFIG", Path.home() / ".waiting.json"))
HOOKS_DIR = Path.home() / ".claude" / "hooks"
SETTINGS_PATH = Path.home() / ".claude" / "settings.json"

DEFAULT_CONFIG = {
    "audio": "default",
    "interval": 30,
    "max_nags": 0,
    "volume": 100,
    "enabled_hooks": ["stop", "permission", "idle"],
    "grace_period_stop": 300,
    "grace_period_permission": 10,
    "grace_period_idle": 0,
}


def load_config() -> dict:
    """Load config from ~/.waiting.json, merged with defaults."""
    config = DEFAULT_CONFIG.copy()
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                user_config = json.load(f)
                config.update(user_config)
        except (json.JSONDecodeError, IOError):
            pass
    return config


def save_config(config: dict) -> None:
    """Save config to ~/.waiting.json."""
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def get_audio_path() -> str:
    """Get path to audio file (bundled or custom)."""
    config = load_config()
    if config["audio"] != "default" and Path(config["audio"]).exists():
        return str(Path(config["audio"]).resolve())
    return str(Path(__file__).parent / "bell.wav")


def get_audio_command(audio_path: str, volume: int) -> str:
    """Generate cross-platform audio detection and play command."""
    return f'''play_sound() {{
    if command -v paplay &> /dev/null; then
        paplay --volume={int(65536 * volume / 100)} "{audio_path}" 2>/dev/null &
    elif command -v pw-play &> /dev/null; then
        pw-play --volume={volume / 100:.2f} "{audio_path}" 2>/dev/null &
    elif command -v aplay &> /dev/null; then
        aplay -q "{audio_path}" 2>/dev/null &
    elif command -v afplay &> /dev/null; then
        afplay -v {volume / 100:.2f} "{audio_path}" 2>/dev/null &
    elif command -v powershell.exe &> /dev/null; then
        win_path=$(wslpath -w "{audio_path}" 2>/dev/null)
        powershell.exe -c "(New-Object Media.SoundPlayer '$win_path').PlaySync()" 2>/dev/null &
    fi
}}'''


def get_session_id_snippet() -> str:
    """Generate bash snippet for extracting session ID from stdin."""
    return '''# Get session ID from stdin JSON
HOOK_INPUT=$(cat)
SESSION_ID=$(echo "$HOOK_INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)
if [ -z "$SESSION_ID" ]; then
    SESSION_ID=$(echo "$HOOK_INPUT" | md5sum | cut -c1-8)
fi'''


def create_stop_script() -> str:
    """Generate the Stop hook script (wait-and-see logic)."""
    config = load_config()
    audio_path = get_audio_path()
    interval = config["interval"]
    max_nags = config["max_nags"]
    grace_period = config["grace_period_stop"]
    volume = config["volume"]

    return f'''#!/bin/bash
# Waiting - Stop hook with wait-and-see logic

INTERVAL={interval}
MAX_NAGS={max_nags}
GRACE_PERIOD={grace_period}

{get_session_id_snippet()}

# Session-specific files
NAG_MARKER="waiting-nag-$SESSION_ID"
PID_FILE="/tmp/$NAG_MARKER.pid"
ACTIVITY_FILE="/tmp/waiting-activity-stop-$SESSION_ID"
STOP_TIME_FILE="/tmp/waiting-stop-time-$SESSION_ID"
HEARTBEAT_FILE="/tmp/waiting-heartbeat-$SESSION_ID"

now=$(date +%s)

# Kill any existing nag for this session
pkill -f "$NAG_MARKER" 2>/dev/null
rm -f "$PID_FILE"
sleep 0.1

# Record when Claude stopped
echo "$now" > "$STOP_TIME_FILE"

# Update heartbeat (proves Claude is alive)
echo "$now" > "$HEARTBEAT_FILE"

# Create nag script
NAG_SCRIPT="/tmp/$NAG_MARKER.sh"

cat > "$NAG_SCRIPT" << 'NAGEOF'
#!/bin/bash

INTERVAL="$1"
MAX_NAGS="$2"
GRACE_PERIOD="$3"
PID_FILE="$4"
ACTIVITY_FILE="$5"
STOP_TIME_FILE="$6"
HEARTBEAT_FILE="$7"

start_time=$(cat "$STOP_TIME_FILE" 2>/dev/null || date +%s)
nag_count=0
max_lifetime=600  # 10 minute orphan protection
heartbeat_timeout=120  # 2 minute heartbeat timeout

cleanup() {{
    rm -f "$PID_FILE"
    exit 0
}}
trap cleanup SIGTERM SIGINT

{get_audio_command(audio_path, volume)}

# Grace period - check for activity
for ((i=0; i<GRACE_PERIOD; i++)); do
    sleep 1
    [ ! -f "$PID_FILE" ] && cleanup

    # Check activity
    if [ -f "$ACTIVITY_FILE" ]; then
        last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
        if [ "$last_activity" -ge "$start_time" ]; then
            cleanup
        fi
    fi

    # Check heartbeat (if Claude is dead, stop nagging)
    if [ -f "$HEARTBEAT_FILE" ]; then
        heartbeat=$(cat "$HEARTBEAT_FILE" 2>/dev/null || echo 0)
        elapsed=$(($(date +%s) - heartbeat))
        if [ "$elapsed" -ge "$heartbeat_timeout" ]; then
            cleanup
        fi
    fi
done

# Main nag loop
while true; do
    elapsed=$(($(date +%s) - start_time))
    [ "$elapsed" -ge "$max_lifetime" ] && cleanup
    [ ! -f "$PID_FILE" ] && cleanup

    # Check activity
    if [ -f "$ACTIVITY_FILE" ]; then
        last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
        if [ "$last_activity" -ge "$start_time" ]; then
            cleanup
        fi
    fi

    play_sound
    nag_count=$((nag_count + 1))

    if [ "$MAX_NAGS" -gt 0 ] && [ "$nag_count" -ge "$MAX_NAGS" ]; then
        cleanup
    fi

    # Sleep in 1-second increments
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

nohup "$NAG_SCRIPT" "$INTERVAL" "$MAX_NAGS" "$GRACE_PERIOD" "$PID_FILE" "$ACTIVITY_FILE" "$STOP_TIME_FILE" "$HEARTBEAT_FILE" > /dev/null 2>&1 &
echo $! > "$PID_FILE"
disown
'''


def create_permission_script() -> str:
    """Generate the Permission hook script (wait-and-see with pending marker)."""
    config = load_config()
    audio_path = get_audio_path()
    interval = config["interval"]
    max_nags = config["max_nags"]
    grace_period = config["grace_period_permission"]
    volume = config["volume"]

    return f'''#!/bin/bash
# Waiting - Permission hook with pending marker

INTERVAL={interval}
MAX_NAGS={max_nags}
GRACE_PERIOD={grace_period}

{get_session_id_snippet()}

# Session-specific files
NAG_MARKER="waiting-nag-$SESSION_ID"
PID_FILE="/tmp/$NAG_MARKER.pid"
PENDING_FILE="/tmp/waiting-pending-$SESSION_ID"
ACTIVITY_FILE="/tmp/waiting-activity-permission-$SESSION_ID"

now=$(date +%s)

# Kill any existing nag for this session
pkill -f "$NAG_MARKER" 2>/dev/null
rm -f "$PID_FILE"
sleep 0.1

# Mark that permission dialog is open
echo "$now" > "$PENDING_FILE"

# Create nag script
NAG_SCRIPT="/tmp/$NAG_MARKER.sh"

cat > "$NAG_SCRIPT" << 'NAGEOF'
#!/bin/bash

INTERVAL="$1"
MAX_NAGS="$2"
GRACE_PERIOD="$3"
PID_FILE="$4"
PENDING_FILE="$5"
ACTIVITY_FILE="$6"

start_time=$(($(date +%s) + 2))  # +2 to avoid race with PreToolUse's +1 buffer
nag_count=0
max_lifetime=600  # 10 minute orphan protection

cleanup() {{
    rm -f "$PID_FILE"
    exit 0
}}
trap cleanup SIGTERM SIGINT

{get_audio_command(audio_path, volume)}

# Grace period
for ((i=0; i<GRACE_PERIOD; i++)); do
    sleep 1
    [ ! -f "$PID_FILE" ] && cleanup
    [ ! -f "$PENDING_FILE" ] && cleanup

    if [ -f "$ACTIVITY_FILE" ]; then
        last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
        if [ "$last_activity" -ge "$start_time" ]; then
            cleanup
        fi
    fi
done

[ ! -f "$PENDING_FILE" ] && cleanup

# Main nag loop
while true; do
    elapsed=$(($(date +%s) - start_time))
    [ "$elapsed" -ge "$max_lifetime" ] && cleanup
    [ ! -f "$PID_FILE" ] && cleanup
    [ ! -f "$PENDING_FILE" ] && cleanup

    if [ -f "$ACTIVITY_FILE" ]; then
        last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
        if [ "$last_activity" -ge "$start_time" ]; then
            cleanup
        fi
    fi

    play_sound
    nag_count=$((nag_count + 1))

    if [ "$MAX_NAGS" -gt 0 ] && [ "$nag_count" -ge "$MAX_NAGS" ]; then
        cleanup
    fi

    for ((i=0; i<INTERVAL; i++)); do
        sleep 1
        [ ! -f "$PID_FILE" ] && cleanup
        [ ! -f "$PENDING_FILE" ] && cleanup
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

nohup "$NAG_SCRIPT" "$INTERVAL" "$MAX_NAGS" "$GRACE_PERIOD" "$PID_FILE" "$PENDING_FILE" "$ACTIVITY_FILE" > /dev/null 2>&1 &
echo $! > "$PID_FILE"
disown
'''


def create_idle_script() -> str:
    """Generate the Idle hook script (Claude's idle_prompt has 60s built-in)."""
    config = load_config()
    audio_path = get_audio_path()
    interval = config["interval"]
    max_nags = config["max_nags"]
    grace_period = config["grace_period_idle"]
    volume = config["volume"]

    return f'''#!/bin/bash
# Waiting - Idle hook (idle_prompt already has 60s built-in delay)

INTERVAL={interval}
MAX_NAGS={max_nags}
GRACE_PERIOD={grace_period}

{get_session_id_snippet()}

# Session-specific files
NAG_MARKER="waiting-nag-$SESSION_ID"
PID_FILE="/tmp/$NAG_MARKER.pid"
ACTIVITY_FILE="/tmp/waiting-activity-stop-$SESSION_ID"

now=$(date +%s)

# Kill any existing nag for this session
pkill -f "$NAG_MARKER" 2>/dev/null
rm -f "$PID_FILE"
sleep 0.1

# Create nag script
NAG_SCRIPT="/tmp/$NAG_MARKER.sh"

cat > "$NAG_SCRIPT" << 'NAGEOF'
#!/bin/bash

INTERVAL="$1"
MAX_NAGS="$2"
GRACE_PERIOD="$3"
PID_FILE="$4"
ACTIVITY_FILE="$5"

start_time=$(date +%s)
nag_count=0
max_lifetime=600

cleanup() {{
    rm -f "$PID_FILE"
    exit 0
}}
trap cleanup SIGTERM SIGINT

{get_audio_command(audio_path, volume)}

# Optional additional grace period
for ((i=0; i<GRACE_PERIOD; i++)); do
    sleep 1
    [ ! -f "$PID_FILE" ] && cleanup
    if [ -f "$ACTIVITY_FILE" ]; then
        last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
        if [ "$last_activity" -ge "$start_time" ]; then
            cleanup
        fi
    fi
done

# Main nag loop
while true; do
    elapsed=$(($(date +%s) - start_time))
    [ "$elapsed" -ge "$max_lifetime" ] && cleanup
    [ ! -f "$PID_FILE" ] && cleanup

    if [ -f "$ACTIVITY_FILE" ]; then
        last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
        if [ "$last_activity" -ge "$start_time" ]; then
            cleanup
        fi
    fi

    play_sound
    nag_count=$((nag_count + 1))

    if [ "$MAX_NAGS" -gt 0 ] && [ "$nag_count" -ge "$MAX_NAGS" ]; then
        cleanup
    fi

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

nohup "$NAG_SCRIPT" "$INTERVAL" "$MAX_NAGS" "$GRACE_PERIOD" "$PID_FILE" "$ACTIVITY_FILE" > /dev/null 2>&1 &
echo $! > "$PID_FILE"
disown
'''


def create_activity_submit_script() -> str:
    """Generate the UserPromptSubmit activity script."""
    return f'''#!/bin/bash
# Waiting - Activity hook for user message submit

{get_session_id_snippet()}

# Update both activity files (+1 buffer for cascading dialogs)
ACTIVITY_TIME=$(($(date +%s) + 1))
echo "$ACTIVITY_TIME" > "/tmp/waiting-activity-stop-$SESSION_ID"
echo "$ACTIVITY_TIME" > "/tmp/waiting-activity-permission-$SESSION_ID"

# Kill any nag process
pkill -f "waiting-nag-$SESSION_ID" 2>/dev/null
rm -f "/tmp/waiting-nag-$SESSION_ID.pid"
rm -f "/tmp/waiting-pending-$SESSION_ID"
'''


def create_activity_tooluse_script() -> str:
    """Generate the PreToolUse activity script."""
    return f'''#!/bin/bash
# Waiting - Activity hook for tool approval

{get_session_id_snippet()}

PENDING_FILE="/tmp/waiting-pending-$SESSION_ID"

# Update activity (+1 buffer)
ACTIVITY_TIME=$(($(date +%s) + 1))
echo "$ACTIVITY_TIME" > "/tmp/waiting-activity-stop-$SESSION_ID"
echo "$ACTIVITY_TIME" > "/tmp/waiting-activity-permission-$SESSION_ID"

# Kill nag and clean pending marker
pkill -f "waiting-nag-$SESSION_ID" 2>/dev/null
rm -f "/tmp/waiting-nag-$SESSION_ID.pid"
rm -f "$PENDING_FILE"
'''


def _is_waiting_hook(command: str) -> bool:
    """Check if a command is a waiting hook."""
    return any(marker in command for marker in ["waiting-notify", "waiting-activity"])


def setup_hooks() -> None:
    """Install hook scripts and update Claude settings."""
    config = load_config()
    enabled = config["enabled_hooks"]

    # Kill existing nag processes
    os.system("pkill -f 'waiting-nag-' 2>/dev/null")

    # Create hooks directory
    HOOKS_DIR.mkdir(parents=True, exist_ok=True)

    # Define all scripts
    all_scripts = {
        "waiting-notify-stop.sh": ("stop", create_stop_script),
        "waiting-notify-permission.sh": ("permission", create_permission_script),
        "waiting-notify-idle.sh": ("idle", create_idle_script),
        "waiting-activity-submit.sh": (None, create_activity_submit_script),
        "waiting-activity-tooluse.sh": (None, create_activity_tooluse_script),
    }

    # Write scripts
    for name, (hook_type, generator) in all_scripts.items():
        # Activity scripts always written; notify scripts only if enabled
        if hook_type is None or hook_type in enabled:
            script_path = HOOKS_DIR / name
            with open(script_path, "w") as f:
                f.write(generator())
            script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Load current settings
    settings = {}
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH) as f:
                settings = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    hooks = settings.get("hooks", {})

    # Remove old waiting hooks first
    for hook_type in list(hooks.keys()):
        if hook_type in hooks:
            hooks[hook_type] = [
                h for h in hooks[hook_type]
                if not any(_is_waiting_hook(str(hook.get("command", "")))
                           for hook in h.get("hooks", []))
            ]
            if not hooks[hook_type]:
                del hooks[hook_type]

    # Add Stop hook
    if "stop" in enabled:
        hooks["Stop"] = [{
            "matcher": "",
            "hooks": [{
                "type": "command",
                "command": str(HOOKS_DIR / "waiting-notify-stop.sh"),
                "timeout": 10
            }]
        }]

    # Add Permission hook
    if "permission" in enabled:
        hooks["PermissionRequest"] = [{
            "matcher": "",
            "hooks": [{
                "type": "command",
                "command": str(HOOKS_DIR / "waiting-notify-permission.sh"),
                "timeout": 10
            }]
        }]

    # Add Idle hook (Notification with idle_prompt matcher)
    if "idle" in enabled:
        hooks["Notification"] = [{
            "matcher": "idle_prompt",
            "hooks": [{
                "type": "command",
                "command": str(HOOKS_DIR / "waiting-notify-idle.sh"),
                "timeout": 10
            }]
        }]

    # Activity hooks always installed
    hooks["UserPromptSubmit"] = [{
        "matcher": "",
        "hooks": [{
            "type": "command",
            "command": str(HOOKS_DIR / "waiting-activity-submit.sh"),
            "timeout": 5
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

    settings["hooks"] = hooks
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)


def remove_hooks() -> None:
    """Remove hook scripts and clean up Claude settings."""
    # Remove all waiting scripts
    for name in ["waiting-notify-stop.sh", "waiting-notify-permission.sh",
                 "waiting-notify-idle.sh", "waiting-activity-submit.sh",
                 "waiting-activity-tooluse.sh"]:
        script_path = HOOKS_DIR / name
        if script_path.exists():
            script_path.unlink()

    # Clean up settings
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH) as f:
                settings = json.load(f)

            hooks = settings.get("hooks", {})
            for hook_type in list(hooks.keys()):
                hooks[hook_type] = [
                    h for h in hooks[hook_type]
                    if not any(_is_waiting_hook(str(hook.get("command", "")))
                               for hook in h.get("hooks", []))
                ]
                if not hooks[hook_type]:
                    del hooks[hook_type]

            settings["hooks"] = hooks

            with open(SETTINGS_PATH, "w") as f:
                json.dump(settings, f, indent=2)
        except (json.JSONDecodeError, IOError):
            pass

    # Kill nag processes
    os.system("pkill -f 'waiting-nag-' 2>/dev/null")


def is_enabled() -> bool:
    """Check if waiting hooks are installed."""
    return any((HOOKS_DIR / name).exists() for name in
               ["waiting-notify-stop.sh", "waiting-notify-permission.sh", "waiting-notify-idle.sh"])


@click.group(invoke_without_command=True)
@click.option("--audio", type=str, help="Custom audio file path")
@click.option("--interval", type=int, help="Seconds between nags")
@click.option("--max-nags", type=int, help="Maximum nags (0=unlimited)")
@click.pass_context
def cli(ctx, audio, interval, max_nags):
    """Notify when Claude Code needs input."""
    if ctx.invoked_subcommand is None:
        # Apply any options to config temporarily
        if audio or interval is not None or max_nags is not None:
            config = load_config()
            if audio:
                config["audio"] = audio
            if interval is not None:
                config["interval"] = interval
            if max_nags is not None:
                config["max_nags"] = max_nags
            save_config(config)

        setup_hooks()
        click.echo("Waiting notifications enabled.")
        click.echo("Restart Claude Code to activate hooks.")


@cli.command()
def disable():
    """Remove all hooks and scripts."""
    remove_hooks()
    click.echo("Waiting notifications disabled.")


@cli.command()
def kill():
    """Stop current nag loop without disabling hooks."""
    os.system("pkill -f 'waiting-nag-' 2>/dev/null")
    click.echo("Nag processes killed.")


@cli.command()
def status():
    """Show current configuration and active hooks."""
    config = load_config()
    enabled = is_enabled()

    click.echo(f"Status: {'enabled' if enabled else 'disabled'}")
    click.echo(f"Audio: {config['audio']}")
    click.echo(f"Interval: {config['interval']}s")
    click.echo(f"Max nags: {config['max_nags']} (0=unlimited)")
    click.echo(f"Volume: {config['volume']}%")
    click.echo(f"Enabled hooks: {', '.join(config['enabled_hooks'])}")
    click.echo(f"Grace periods:")
    click.echo(f"  stop: {config['grace_period_stop']}s")
    click.echo(f"  permission: {config['grace_period_permission']}s")
    click.echo(f"  idle: {config['grace_period_idle']}s")


@cli.command()
@click.option("--audio", type=str, help="Audio file path ('default' for bundled)")
@click.option("--interval", type=int, help="Seconds between nags")
@click.option("--max-nags", type=int, help="Maximum nags (0=unlimited)")
@click.option("--volume", type=int, help="Volume percentage (1-100)")
@click.option("--grace-stop", type=int, help="Stop hook grace period")
@click.option("--grace-permission", type=int, help="Permission hook grace period")
@click.option("--grace-idle", type=int, help="Idle hook grace period")
@click.option("--enable-hook", type=click.Choice(["stop", "permission", "idle"]), help="Enable a hook")
@click.option("--disable-hook", type=click.Choice(["stop", "permission", "idle"]), help="Disable a hook")
@click.option("--hooks", type=str, help="Set enabled hooks (comma-separated)")
@click.option("--show", is_flag=True, help="Show config without modifying")
@click.option("--reset", is_flag=True, help="Reset to defaults")
def configure(audio, interval, max_nags, volume, grace_stop, grace_permission,
              grace_idle, enable_hook, disable_hook, hooks, show, reset):
    """View or modify configuration."""
    if reset:
        save_config(DEFAULT_CONFIG.copy())
        click.echo("Configuration reset to defaults.")
        if is_enabled():
            setup_hooks()
            click.echo("Hooks updated.")
        return

    config = load_config()

    if show:
        click.echo(json.dumps(config, indent=2))
        return

    modified = False

    if audio is not None:
        config["audio"] = audio
        modified = True
    if interval is not None:
        config["interval"] = interval
        modified = True
    if max_nags is not None:
        config["max_nags"] = max_nags
        modified = True
    if volume is not None:
        config["volume"] = max(1, min(100, volume))
        modified = True
    if grace_stop is not None:
        config["grace_period_stop"] = grace_stop
        modified = True
    if grace_permission is not None:
        config["grace_period_permission"] = grace_permission
        modified = True
    if grace_idle is not None:
        config["grace_period_idle"] = grace_idle
        modified = True
    if enable_hook:
        if enable_hook not in config["enabled_hooks"]:
            config["enabled_hooks"].append(enable_hook)
            modified = True
    if disable_hook:
        if disable_hook in config["enabled_hooks"]:
            config["enabled_hooks"].remove(disable_hook)
            modified = True
    if hooks:
        config["enabled_hooks"] = [h.strip() for h in hooks.split(",") if h.strip() in ["stop", "permission", "idle"]]
        modified = True

    if modified:
        save_config(config)
        click.echo("Configuration updated.")
        if is_enabled():
            setup_hooks()
            click.echo("Hooks regenerated with new configuration.")
    else:
        click.echo(json.dumps(config, indent=2))


if __name__ == "__main__":
    cli()
