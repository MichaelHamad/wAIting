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
    "volume": 100,  # Volume 0-100% (some players may not support this)
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
        content = settings_path.read_text().strip()
        if content:
            return json.loads(content)
    return {}


def save_claude_settings(settings: dict) -> None:
    """Save Claude Code settings."""
    settings_path = get_claude_settings_path()
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)


def create_stop_notify_script(
    audio_path: str,
    interval: int = 30,
    max_nags: int = 0,
    grace_period: int = 300,
    volume: int = 100,
) -> Path:
    """Create the Stop hook notification script with 'wait and see' logic.

    The Stop hook uses delayed checking:
    1. Record when Stop fired
    2. Wait for grace_period
    3. Check if any activity since Stop fired
    4. If no activity → bell (user is AFK)

    Args:
        audio_path: Path to the audio file
        interval: Seconds between repeated notifications (0 = no repeat)
        max_nags: Maximum number of repeats (0 = unlimited)
        grace_period: Seconds to wait before checking for activity
        volume: Volume level 0-100%
    """
    script_path = get_hooks_dir() / "waiting-notify-stop.sh"

    script_content = f"""#!/bin/bash
# Waiting - Stop hook with "wait and see" logic
# Waits for grace period, then checks if user has been active
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
ACTIVITY_FILE="/tmp/waiting-activity-stop-$SESSION_ID"
STOP_TIME_FILE="/tmp/waiting-stop-time-$SESSION_ID"
HEARTBEAT_FILE="/tmp/waiting-heartbeat-$SESSION_ID"
# How long without a heartbeat before we assume Claude is dead (2 minutes)
HEARTBEAT_TIMEOUT=120

# Check if Claude is still running
is_claude_alive() {{
    pgrep -f "claude" > /dev/null 2>&1
}}

# Update heartbeat (proves Claude is alive)
echo "$(date +%s)" > "$HEARTBEAT_FILE"

# Kill any existing wait/nag process for THIS session
if [ -f "$PID_FILE" ]; then
    old_pid=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$old_pid" ]; then
        kill "$old_pid" 2>/dev/null
        pkill -P "$old_pid" 2>/dev/null
    fi
    rm -f "$PID_FILE"
fi

# Record when Stop fired
stop_time=$(date +%s)
echo "$stop_time" > "$STOP_TIME_FILE"

play_sound() {{
    # Volume: {volume}% (paplay uses 0-65536, afplay/pw-play use 0.0-1.0)
    PAPLAY_VOL=$((65536 * {volume} / 100))
    FLOAT_VOL=$(awk "BEGIN {{printf \\"%.2f\\", {volume}/100}}")

    if command -v paplay &> /dev/null; then
        paplay --volume=$PAPLAY_VOL "{audio_path}" 2>/dev/null
    elif command -v pw-play &> /dev/null; then
        pw-play --volume=$FLOAT_VOL "{audio_path}" 2>/dev/null
    elif command -v aplay &> /dev/null; then
        # aplay doesn't support volume control directly
        aplay -q "{audio_path}" 2>/dev/null
    elif command -v afplay &> /dev/null; then
        afplay -v $FLOAT_VOL "{audio_path}" 2>/dev/null
    elif command -v powershell.exe &> /dev/null; then
        win_path=$(wslpath -w "{audio_path}" 2>/dev/null)
        if [ -n "$win_path" ]; then
            powershell.exe -c "(New-Object Media.SoundPlayer '$win_path').PlaySync()" 2>/dev/null
        else
            powershell.exe -c "(New-Object Media.SoundPlayer 'C:\\Windows\\Media\\notify.wav').PlaySync()" 2>/dev/null
        fi
    fi
}}

# Start background "wait and see" process
(
    # Wait for grace period before checking
    sleep "$GRACE_PERIOD"

    # Check if user had any activity since Stop fired
    stop_time=$(cat "$STOP_TIME_FILE" 2>/dev/null || echo 0)
    last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)

    if [ "$last_activity" -gt "$stop_time" ]; then
        # User was active after Stop fired, no bell needed
        rm -f "$STOP_TIME_FILE"
        rm -f "$PID_FILE"
        exit 0
    fi

    # User hasn't done anything since Stop fired - they're AFK
    play_sound

    # Start nag loop if interval > 0
    if [ "$INTERVAL" -gt 0 ]; then
        # Max lifetime: 10 minutes (prevents orphaned nag loops)
        MAX_LIFETIME=600
        START_TIME=$(date +%s)
        count=0
        while true; do
            # Sleep in 1-second increments, checking if Claude dies
            for i in $(seq 1 "$INTERVAL"); do
                sleep 1
                if ! is_claude_alive; then
                    rm -f "$STOP_TIME_FILE" "$PID_FILE"
                    exit 0
                fi
            done

            # Safety: exit if we've been running too long (orphaned process)
            NOW=$(date +%s)
            ELAPSED=$((NOW - START_TIME))
            if [ "$ELAPSED" -ge "$MAX_LIFETIME" ]; then
                break
            fi

            # Check if Claude is still alive via heartbeat
            if [ -f "$HEARTBEAT_FILE" ]; then
                last_heartbeat=$(cat "$HEARTBEAT_FILE" 2>/dev/null || echo 0)
                heartbeat_age=$((NOW - last_heartbeat))
                if [ "$heartbeat_age" -gt "$HEARTBEAT_TIMEOUT" ]; then
                    # Claude appears dead, stop nagging
                    break
                fi
            fi

            # Re-check activity in case user came back
            last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
            stop_time=$(cat "$STOP_TIME_FILE" 2>/dev/null || echo 0)
            if [ "$last_activity" -gt "$stop_time" ]; then
                break
            fi

            play_sound
            count=$((count + 1))
            if [ "$MAX_NAGS" -gt 0 ] && [ "$count" -ge "$MAX_NAGS" ]; then
                break
            fi
        done
    fi

    rm -f "$STOP_TIME_FILE"
    rm -f "$PID_FILE"
) &

# Save PID of background process
echo $! > "$PID_FILE"
"""

    with open(script_path, "w") as f:
        f.write(script_content)

    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return script_path


def create_permission_notify_script(
    audio_path: str,
    interval: int = 30,
    max_nags: int = 0,
    grace_period: int = 10,
) -> Path:
    """Create the Permission hook notification script with wait-and-see logic.

    The Permission hook creates a pending marker file, then waits grace_period seconds.
    After the delay, it checks if user was active SINCE the dialog opened.
    The pending file helps PreToolUse distinguish user approvals from auto-approved tools.

    Args:
        audio_path: Path to the audio file
        interval: Seconds between repeated notifications (0 = no repeat)
        max_nags: Maximum number of repeats (0 = unlimited)
        grace_period: Seconds to wait before checking activity and playing bell
    """
    script_path = get_hooks_dir() / "waiting-notify-permission.sh"

    script_content = f"""#!/bin/bash
# Waiting - Permission hook with wait-and-see logic
# Waits grace_period, then checks if user responded since dialog opened
# Audio file: {audio_path}

INTERVAL={interval}
MAX_NAGS={max_nags}
DELAY={grace_period}
DEBUG_LOG="/tmp/waiting-debug.log"

# Read hook context from stdin to get session ID
HOOK_INPUT=$(cat)

# Debug: log when hook fires
echo "$(date): PermissionRequest fired" >> "$DEBUG_LOG"

SESSION_ID=$(echo "$HOOK_INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)

# Fall back to a hash of the input if no session_id found
if [ -z "$SESSION_ID" ]; then
    SESSION_ID=$(echo "$HOOK_INPUT" | md5sum | cut -c1-8)
fi

echo "  Session: $SESSION_ID, delay: ${{DELAY}}s" >> "$DEBUG_LOG"

# Use session-specific marker for process identification
NAG_MARKER="waiting-nag-$SESSION_ID"
PID_FILE="/tmp/$NAG_MARKER.pid"
PENDING_FILE="/tmp/waiting-pending-$SESSION_ID"
ACTIVITY_FILE="/tmp/waiting-activity-permission-$SESSION_ID"
HEARTBEAT_FILE="/tmp/waiting-heartbeat-$SESSION_ID"

# Get current time upfront
now=$(date +%s)

# Update heartbeat (proves Claude is alive)
echo "$now" > "$HEARTBEAT_FILE"

# Kill ALL existing nag processes for this session
pkill -f "$NAG_MARKER" 2>/dev/null
rm -f "$PID_FILE"

# Small delay to ensure old processes are dead
sleep 0.2

# Create pending marker (tells PreToolUse this is a user approval, not auto-approved)
echo "$now" > "$PENDING_FILE"
echo "  Created pending marker: $PENDING_FILE" >> "$DEBUG_LOG"

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

# Create wrapper script with session marker in filename (so pkill -f can find it)
NAG_SCRIPT="/tmp/$NAG_MARKER.sh"
AUDIO_PATH="{audio_path}"

cat > "$NAG_SCRIPT" << NAGEOF
#!/bin/bash
DEBUG_LOG="/tmp/waiting-debug.log"
PID_FILE="$PID_FILE"
DELAY=$DELAY
INTERVAL=$INTERVAL
MAX_NAGS=$MAX_NAGS
AUDIO_PATH="$AUDIO_PATH"
ACTIVITY_FILE="$ACTIVITY_FILE"
HEARTBEAT_FILE="$HEARTBEAT_FILE"
START_TIMESTAMP=$now
# How long without a heartbeat before we assume Claude is dead (2 minutes)
HEARTBEAT_TIMEOUT=120

# Check if Claude is still running (any node process with 'claude' in cmdline)
is_claude_alive() {{
    pgrep -f "claude" > /dev/null 2>&1
}}

# Trap SIGTERM for instant kill when PreToolUse runs pkill
# Also kill any background sound processes
trap 'echo "  Nag received SIGTERM, exiting" >> "\\$DEBUG_LOG"; kill \\$(jobs -p) 2>/dev/null; rm -f "\\$PID_FILE" "\\$0"; exit 0' TERM

play_sound() {{
    # Play sound in background (&) so SIGTERM trap can fire immediately during playback
    if command -v paplay &> /dev/null; then
        paplay "\\$AUDIO_PATH" 2>/dev/null &
    elif command -v pw-play &> /dev/null; then
        pw-play "\\$AUDIO_PATH" 2>/dev/null &
    elif command -v aplay &> /dev/null; then
        aplay -q "\\$AUDIO_PATH" 2>/dev/null &
    elif command -v afplay &> /dev/null; then
        afplay "\\$AUDIO_PATH" 2>/dev/null &
    elif command -v powershell.exe &> /dev/null; then
        win_path=\\$(wslpath -w "\\$AUDIO_PATH" 2>/dev/null)
        if [ -n "\\$win_path" ]; then
            powershell.exe -c "(New-Object Media.SoundPlayer '\\$win_path').PlaySync()" 2>/dev/null &
        fi
    fi
}}

echo "  Starting delayed bell (waiting \\${{DELAY}}s)" >> "\\$DEBUG_LOG"

# Sleep in 1-second increments during grace period, checking if Claude dies
for i in \\$(seq 1 "\\$DELAY"); do
    sleep 1
    if ! is_claude_alive; then
        echo "  Claude process not found during delay, exiting" >> "\\$DEBUG_LOG"
        rm -f "\\$PID_FILE" "\\$0"
        exit 0
    fi
done

if [ ! -f "\\$PID_FILE" ]; then
    echo "  PID file removed, exiting" >> "\\$DEBUG_LOG"
    rm -f "\\$0"
    exit 0
fi

# Wait-and-see: check if user was active SINCE the dialog opened
# Use >= to handle same-second cascading dialogs (user approves one, Claude shows another)
echo "  Checking activity since dialog opened (START_TIMESTAMP=\\$START_TIMESTAMP)" >> "\\$DEBUG_LOG"

if [ -f "\\$ACTIVITY_FILE" ]; then
    last_activity=\\$(cat "\\$ACTIVITY_FILE" 2>/dev/null || echo 0)
    echo "  Activity check: last_activity=\\$last_activity" >> "\\$DEBUG_LOG"
    if [ "\\$last_activity" -ge "\\$START_TIMESTAMP" ]; then
        echo "  User responded during grace period (\\$last_activity >= \\$START_TIMESTAMP), exiting" >> "\\$DEBUG_LOG"
        rm -f "\\$PID_FILE" "\\$0"
        exit 0
    fi
    echo "  No activity since dialog opened (\\$last_activity < \\$START_TIMESTAMP)" >> "\\$DEBUG_LOG"
else
    echo "  No activity file found at \\$ACTIVITY_FILE" >> "\\$DEBUG_LOG"
fi

# No activity since dialog - play bell
echo "  Grace period complete, playing bell" >> "\\$DEBUG_LOG"
play_sound

if [ "\\$INTERVAL" -eq 0 ]; then
    rm -f "\\$PID_FILE" "\\$0"
    exit 0
fi

# Max lifetime: 10 minutes (prevents orphaned nag loops)
MAX_LIFETIME=600
LOOP_START=\\$(date +%s)
count=0
while true; do
    # Sleep in 1-second increments, checking if we should exit
    for i in \\$(seq 1 "\\$INTERVAL"); do
        sleep 1
        if [ ! -f "\\$PID_FILE" ]; then
            echo "  PID file removed, stopping nag" >> "\\$DEBUG_LOG"
            rm -f "\\$0"
            exit 0
        fi
        # Check if Claude is still running every second
        if ! is_claude_alive; then
            echo "  Claude process not found, exiting" >> "\\$DEBUG_LOG"
            rm -f "\\$PID_FILE" "\\$0"
            exit 0
        fi
    done

    NOW=\\$(date +%s)
    ELAPSED=\\$((NOW - LOOP_START))
    if [ "\\$ELAPSED" -ge "\\$MAX_LIFETIME" ]; then
        echo "  Nag loop max lifetime reached, exiting" >> "\\$DEBUG_LOG"
        break
    fi

    # Check if Claude is still alive via heartbeat
    # If no hook has fired in HEARTBEAT_TIMEOUT seconds, Claude is probably dead
    if [ -f "\\$HEARTBEAT_FILE" ]; then
        last_heartbeat=\\$(cat "\\$HEARTBEAT_FILE" 2>/dev/null || echo 0)
        heartbeat_age=\\$((NOW - last_heartbeat))
        if [ "\\$heartbeat_age" -gt "\\$HEARTBEAT_TIMEOUT" ]; then
            echo "  Heartbeat stale (\\${{heartbeat_age}}s > \\${{HEARTBEAT_TIMEOUT}}s), Claude appears dead, exiting" >> "\\$DEBUG_LOG"
            rm -f "\\$PID_FILE" "\\$0"
            exit 0
        fi
    fi

    # Check if user responded to THIS dialog (activity at or after dialog appeared)
    if [ -f "\\$ACTIVITY_FILE" ]; then
        last_activity=\\$(cat "\\$ACTIVITY_FILE" 2>/dev/null || echo 0)
        if [ "\\$last_activity" -ge "\\$START_TIMESTAMP" ]; then
            echo "  User responded (activity \\$last_activity >= start \\$START_TIMESTAMP), stopping nag" >> "\\$DEBUG_LOG"
            rm -f "\\$PID_FILE" "\\$0"
            exit 0
        fi
    fi
    echo "  Nag loop: playing bell (iteration \\$count)" >> "\\$DEBUG_LOG"
    play_sound
    count=\\$((count + 1))
    if [ "\\$MAX_NAGS" -gt 0 ] && [ "\\$count" -ge "\\$MAX_NAGS" ]; then
        break
    fi
done
rm -f "\\$PID_FILE" "\\$0"
NAGEOF

chmod +x "$NAG_SCRIPT"

# Run the nag script in background (its path contains the marker for pkill -f)
"$NAG_SCRIPT" &

# Save PID of background process
echo $! > "$PID_FILE"
echo "  Background PID: $!" >> "$DEBUG_LOG"
"""

    with open(script_path, "w") as f:
        f.write(script_content)

    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return script_path


def create_idle_notify_script(
    audio_path: str,
    interval: int = 30,
    max_nags: int = 0,
    grace_period: int = 0,
) -> Path:
    """Create the Idle hook notification script.

    The Idle hook (idle_prompt) already has a 60s built-in delay.
    This script adds optional additional grace period checking.
    """
    script_path = get_hooks_dir() / "waiting-notify-idle.sh"

    script_content = f"""#!/bin/bash
# Waiting - Idle hook notification
# idle_prompt already has 60s built-in delay
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

# Use session-specific files (uses permission activity file)
PID_FILE="/tmp/waiting-nag-$SESSION_ID.pid"
ACTIVITY_FILE="/tmp/waiting-activity-permission-$SESSION_ID"
HEARTBEAT_FILE="/tmp/waiting-heartbeat-$SESSION_ID"
# How long without a heartbeat before we assume Claude is dead (2 minutes)
HEARTBEAT_TIMEOUT=120

# Check if Claude is still running
is_claude_alive() {{
    pgrep -f "claude" > /dev/null 2>&1
}}

# Update heartbeat (proves Claude is alive)
echo "$(date +%s)" > "$HEARTBEAT_FILE"

# Check if user was recently active (within grace period)
if [ "$GRACE_PERIOD" -gt 0 ] && [ -f "$ACTIVITY_FILE" ]; then
    last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
    now=$(date +%s)
    elapsed=$((now - last_activity))
    if [ "$elapsed" -lt "$GRACE_PERIOD" ]; then
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

# If interval is 0, just play once and exit
if [ "$INTERVAL" -eq 0 ]; then
    exit 0
fi

# Record when idle notification fired (for activity comparison)
IDLE_TIME=$(date +%s)

# Start background nag loop
(
    # Max lifetime: 10 minutes (prevents orphaned nag loops)
    MAX_LIFETIME=600
    START_TIME=$(date +%s)
    count=0
    while true; do
        # Sleep in 1-second increments, checking if Claude dies
        for i in $(seq 1 "$INTERVAL"); do
            sleep 1
            if ! is_claude_alive; then
                rm -f "$PID_FILE"
                exit 0
            fi
        done

        # Safety: exit if we've been running too long (orphaned process)
        NOW=$(date +%s)
        ELAPSED=$((NOW - START_TIME))
        if [ "$ELAPSED" -ge "$MAX_LIFETIME" ]; then
            break
        fi

        # Check if Claude is still alive via heartbeat
        if [ -f "$HEARTBEAT_FILE" ]; then
            last_heartbeat=$(cat "$HEARTBEAT_FILE" 2>/dev/null || echo 0)
            heartbeat_age=$((NOW - last_heartbeat))
            if [ "$heartbeat_age" -gt "$HEARTBEAT_TIMEOUT" ]; then
                # Claude appears dead, stop nagging
                rm -f "$PID_FILE"
                exit 0
            fi
        fi

        # Check if user was active since idle notification
        last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
        if [ "$last_activity" -gt "$IDLE_TIME" ]; then
            # User responded, stop nagging
            rm -f "$PID_FILE"
            exit 0
        fi

        play_sound
        count=$((count + 1))
        if [ "$MAX_NAGS" -gt 0 ] && [ "$count" -ge "$MAX_NAGS" ]; then
            break
        fi
    done
    rm -f "$PID_FILE"
) &

# Save PID of background process
echo $! > "$PID_FILE"
"""

    with open(script_path, "w") as f:
        f.write(script_content)

    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return script_path


def create_activity_scripts() -> tuple[Path, Path]:
    """Create activity recording scripts for different hooks.

    Returns:
        Tuple of (submit_script_path, tooluse_script_path)

    UserPromptSubmit: Records activity + kills nag (user typed a message)
    PreToolUse: Records activity + kills nag (user approved permission OR auto-approved tool)

    Simplified approach: Both hooks always update activity and kill nag.
    When permission dialog shows, Claude is blocked - first PreToolUse = user approved.
    """
    hooks_dir = get_hooks_dir()

    # Script for UserPromptSubmit - updates activity files AND kills nag
    submit_script_path = hooks_dir / "waiting-activity-submit.sh"
    submit_content = """#!/bin/bash
# Record user activity when submitting a message
# Updates BOTH Stop and Permission activity files

DEBUG_LOG="/tmp/waiting-debug.log"

# Read hook context from stdin to get session ID
HOOK_INPUT=$(cat)

echo "$(date): UserPromptSubmit fired" >> "$DEBUG_LOG"

SESSION_ID=$(echo "$HOOK_INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)

# Fall back to a hash of the input if no session_id found
if [ -z "$SESSION_ID" ]; then
    SESSION_ID=$(echo "$HOOK_INPUT" | md5sum | cut -c1-8)
fi

echo "  Session: $SESSION_ID" >> "$DEBUG_LOG"

# Use session-specific files
NAG_MARKER="waiting-nag-$SESSION_ID"
PID_FILE="/tmp/$NAG_MARKER.pid"
STOP_ACTIVITY="/tmp/waiting-activity-stop-$SESSION_ID"
PERMISSION_ACTIVITY="/tmp/waiting-activity-permission-$SESSION_ID"
HEARTBEAT_FILE="/tmp/waiting-heartbeat-$SESSION_ID"

# Record activity for both hooks
NOW=$(date +%s)
# Add 1 second buffer to handle same-second cascading dialogs
ACTIVITY_TIME=$((NOW + 1))
echo "$ACTIVITY_TIME" > "$STOP_ACTIVITY"
echo "$ACTIVITY_TIME" > "$PERMISSION_ACTIVITY"
# Update heartbeat (proves Claude is alive)
echo "$NOW" > "$HEARTBEAT_FILE"
echo "  Updated activity: $ACTIVITY_TIME (NOW+1 buffer), heartbeat: $NOW" >> "$DEBUG_LOG"

# Kill ALL nag processes for this session using the marker (more reliable than PID)
if pkill -f "$NAG_MARKER" 2>/dev/null; then
    echo "  Killed nag processes matching: $NAG_MARKER" >> "$DEBUG_LOG"
else
    echo "  No nag processes found for: $NAG_MARKER" >> "$DEBUG_LOG"
fi

# Clean up PID file and wrapper script
rm -f "$PID_FILE" "/tmp/$NAG_MARKER.sh"
"""
    with open(submit_script_path, "w") as f:
        f.write(submit_content)
    submit_script_path.chmod(submit_script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Script for PreToolUse - kills nag and updates activity
    # Only updates activity if pending file exists (user approved vs auto-approved)
    # Rationale: Auto-approved tools fire PreToolUse but shouldn't count as user activity
    tooluse_script_path = hooks_dir / "waiting-activity-tooluse.sh"
    tooluse_content = """#!/bin/bash
# Kill nag loop when tool executes and update activity
# Uses pending file to distinguish user approvals from auto-approved tools

DEBUG_LOG="/tmp/waiting-debug.log"

# Read hook context from stdin to get session ID
HOOK_INPUT=$(cat)

echo "$(date): PreToolUse fired" >> "$DEBUG_LOG"

SESSION_ID=$(echo "$HOOK_INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)

# Fall back to a hash of the input if no session_id found
if [ -z "$SESSION_ID" ]; then
    SESSION_ID=$(echo "$HOOK_INPUT" | md5sum | cut -c1-8)
fi

echo "  Session: $SESSION_ID" >> "$DEBUG_LOG"

NAG_MARKER="waiting-nag-$SESSION_ID"
PID_FILE="/tmp/$NAG_MARKER.pid"
PENDING_FILE="/tmp/waiting-pending-$SESSION_ID"
ACTIVITY_FILE="/tmp/waiting-activity-permission-$SESSION_ID"
HEARTBEAT_FILE="/tmp/waiting-heartbeat-$SESSION_ID"

NOW=$(date +%s)
# Always update heartbeat (proves Claude is alive, regardless of approval type)
echo "$NOW" > "$HEARTBEAT_FILE"

# Add 1 second buffer to handle same-second cascading dialogs
ACTIVITY_TIME=$((NOW + 1))

# ALWAYS update activity when any tool runs - Claude is working, user is present
# This prevents false "AFK" detection when new permission dialogs appear
echo "$ACTIVITY_TIME" > "$ACTIVITY_FILE"

# Clean up pending file if it exists (user manually approved)
if [ -f "$PENDING_FILE" ]; then
    rm -f "$PENDING_FILE"
    echo "  User approved permission, updated activity: $ACTIVITY_TIME, heartbeat: $NOW" >> "$DEBUG_LOG"
else
    echo "  Auto-approved tool, updated activity: $ACTIVITY_TIME, heartbeat: $NOW" >> "$DEBUG_LOG"
fi

# Kill ALL nag processes for this session
if pkill -f "$NAG_MARKER" 2>/dev/null; then
    echo "  Killed nag: $NAG_MARKER" >> "$DEBUG_LOG"
else
    echo "  No nag processes found" >> "$DEBUG_LOG"
fi

# Clean up PID file and wrapper script
rm -f "$PID_FILE" "/tmp/$NAG_MARKER.sh"
"""
    with open(tooluse_script_path, "w") as f:
        f.write(tooluse_content)
    tooluse_script_path.chmod(tooluse_script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return submit_script_path, tooluse_script_path


def _is_waiting_hook(hook_config: dict) -> bool:
    """Check if a hook config is one of ours."""
    for hook in hook_config.get("hooks", []):
        cmd = hook.get("command", "")
        if "waiting-notify" in cmd or "waiting-stop" in cmd or "waiting-activity" in cmd:
            return True
    return False


def setup_hooks(
    stop_script_path: Path,
    permission_script_path: Path,
    idle_script_path: Path,
    submit_activity_script: Path,
    tooluse_script: Path,
    enabled_hooks: list[str]
) -> None:
    """Add notification hooks to Claude settings with per-hook scripts.

    Activity tracking (simplified approach):
    - UserPromptSubmit → updates activity files + kills nag (user typed message)
    - PreToolUse → updates activity files + kills nag (any tool execution)

    Both hooks always update activity and kill nag. When permission dialog shows,
    Claude is blocked, so first PreToolUse after PermissionRequest = user approved.
    """
    settings = load_claude_settings()

    if "hooks" not in settings:
        settings["hooks"] = {}

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

    # UserPromptSubmit - record activity for BOTH hooks (always enabled)
    if "UserPromptSubmit" not in settings["hooks"]:
        settings["hooks"]["UserPromptSubmit"] = []
    settings["hooks"]["UserPromptSubmit"] = [
        h for h in settings["hooks"]["UserPromptSubmit"]
        if not _is_waiting_hook(h)
    ]
    settings["hooks"]["UserPromptSubmit"].append({
        "matcher": "",
        "hooks": [{
            "type": "command",
            "command": str(submit_activity_script),
            "timeout": 5
        }]
    })

    # PreToolUse - kills nag loop when any tool executes (user approved or auto-approved)
    # Does NOT update activity file (that's UserPromptSubmit's job)
    if "PreToolUse" not in settings["hooks"]:
        settings["hooks"]["PreToolUse"] = []
    settings["hooks"]["PreToolUse"] = [
        h for h in settings["hooks"]["PreToolUse"]
        if not _is_waiting_hook(h)
    ]
    settings["hooks"]["PreToolUse"].append({
        "matcher": "",
        "hooks": [{
            "type": "command",
            "command": str(tooluse_script),
            "timeout": 5
        }]
    })

    # Clean up old hooks from previous versions
    for old_hook_type in ["PostToolUse"]:
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

        # Kill any existing nag processes before setting up fresh
        _kill_nag_process()

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
        stop_script = create_stop_notify_script(audio_path, interval, max_nags, grace_stop)
        permission_script = create_permission_notify_script(audio_path, interval, max_nags, grace_permission)
        idle_script = create_idle_notify_script(audio_path, interval, max_nags, grace_idle)

        # Create activity recording scripts
        submit_activity_script, tooluse_script = create_activity_scripts()

        click.echo(f"  Scripts: {get_hooks_dir()}")

        # Add hooks to Claude settings
        setup_hooks(stop_script, permission_script, idle_script, submit_activity_script, tooluse_script, enabled_hooks)
        click.echo(f"  Hooks: {get_claude_settings_path()}")

        click.echo()
        click.echo("Done! Claude Code will nag you when waiting for input.")
        click.echo()
        click.echo("Behavior:")
        if "stop" in enabled_hooks:
            click.echo(f"  - Stop hook: waits {grace_stop}s ({grace_stop // 60}min), then alerts if you haven't typed")
        if "permission" in enabled_hooks:
            click.echo(f"  - Permission hook: alerts immediately if no activity in last {grace_permission}s")
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

    # Remove all scripts (including per-hook variants and activity scripts)
    script_patterns = [
        "waiting-notify.sh",
        "waiting-notify-*.sh",
        "waiting-stop.sh",
        "waiting-activity-*.sh",
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

    # Kill any orphaned waiting-notify or waiting-nag processes that might not have PID files
    for pattern in ["waiting-notify", "waiting-nag"]:
        try:
            result = subprocess.run(
                ["pkill", "-f", pattern],
                capture_output=True
            )
            if result.returncode == 0:
                killed = True
        except Exception:
            pass

    # Update activity files so grace period kicks in
    import time
    now = str(int(time.time()))
    # New format: separate files for stop and permission
    for activity_file in tmp_dir.glob("waiting-activity-stop-*"):
        activity_file.write_text(now)
    for activity_file in tmp_dir.glob("waiting-activity-permission-*"):
        activity_file.write_text(now)
    # Legacy format
    for activity_file in tmp_dir.glob("waiting-activity-*"):
        if "stop" not in activity_file.name and "permission" not in activity_file.name:
            activity_file.write_text(now)
    legacy_activity = tmp_dir / "waiting-last-activity"
    if legacy_activity.exists():
        legacy_activity.write_text(now)

    # Clean up stop-time files
    for stop_time_file in tmp_dir.glob("waiting-stop-time-*"):
        stop_time_file.unlink(missing_ok=True)

    # Clean up pending files
    for pending_file in tmp_dir.glob("waiting-pending-*"):
        pending_file.unlink(missing_ok=True)

    # Clean up nag wrapper scripts
    for wrapper_script in tmp_dir.glob("waiting-nag-*.sh"):
        wrapper_script.unlink(missing_ok=True)

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
