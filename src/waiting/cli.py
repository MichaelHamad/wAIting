"""Waiting CLI - Notify when Claude Code needs input."""

import glob
import json
import os
import re
import stat
import subprocess
from pathlib import Path

import click

# Hook version - increment when hook logic changes
# This allows us to detect outdated hooks and warn users
HOOK_VERSION = "2.3.0"  # 2.3.0 = aggressive audio killing + cleanup in PreToolUse hook

CONFIG_PATH = Path(os.environ.get("WAITING_CONFIG", Path.home() / ".waiting.json"))
HOOKS_DIR = Path.home() / ".claude" / "hooks"
SETTINGS_PATH = Path.home() / ".claude" / "settings.json"

DEFAULT_CONFIG = {
    "audio": "default",
    "volume": 100,
    "enabled_hooks": ["stop", "idle"],
    "grace_period": 30,
    "interval": 30,
    "max_nags": 0,
}


def get_hook_version_header() -> str:
    """Return version header to embed in generated hooks."""
    return f"# WAITING_HOOK_VERSION={HOOK_VERSION}"


def get_installed_hook_version() -> str | None:
    """Read version from installed hooks, return None if not found or outdated format."""
    for name in ["waiting-notify-permission.sh", "waiting-activity-submit.sh"]:
        hook_path = HOOKS_DIR / name
        if hook_path.exists():
            try:
                content = hook_path.read_text()
                match = re.search(r"WAITING_HOOK_VERSION=(\S+)", content)
                if match:
                    return match.group(1)
            except IOError:
                pass
    return None


def get_running_nags() -> list[tuple[str, str]]:
    """Return list of (pid, session_id) for running nag processes."""
    nags = []
    try:
        result = subprocess.run(
            ["pgrep", "-af", "waiting-nag-"],
            capture_output=True, text=True
        )
        for line in result.stdout.strip().split("\n"):
            if line and "waiting-nag-" in line and "pgrep" not in line:
                parts = line.split()
                if parts:
                    pid = parts[0]
                    # Extract session ID from command line
                    match = re.search(r"waiting-nag-([a-f0-9-]+)", line)
                    session_id = match.group(1) if match else "unknown"
                    nags.append((pid, session_id))
    except (subprocess.SubprocessError, OSError):
        pass
    return nags


def get_orphaned_files() -> dict[str, list[str]]:
    """Return dict of orphaned temp files by category."""
    orphans = {
        "pid_files": [],
        "pending_files": [],
        "stop_signals": [],
        "nag_scripts": [],
    }

    # Get running nag session IDs
    running_sessions = {sid for _, sid in get_running_nags()}

    for pidfile in glob.glob("/tmp/waiting-nag-*.pid"):
        session = pidfile.replace("/tmp/waiting-nag-", "").replace(".pid", "")
        if session not in running_sessions:
            orphans["pid_files"].append(pidfile)

    for f in glob.glob("/tmp/waiting-pending-*"):
        session = f.replace("/tmp/waiting-pending-", "")
        if session not in running_sessions:
            orphans["pending_files"].append(f)

    for f in glob.glob("/tmp/waiting-stop-*"):
        orphans["stop_signals"].append(f)

    for f in glob.glob("/tmp/waiting-nag-*.sh"):
        orphans["nag_scripts"].append(f)

    return orphans


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
    return str(Path(__file__).parent / "Cool_bell_final.wav")


def get_audio_command(audio_path: str, volume: int) -> str:
    """Generate cross-platform audio detection and play command."""
    return f'''play_sound() {{
    AUDIO_PID_FILE="/tmp/waiting-audio-$SESSION_ID.pid"
    if command -v paplay &> /dev/null; then
        paplay --volume={int(65536 * volume / 100)} "{audio_path}" 2>/dev/null &
        echo $! > "$AUDIO_PID_FILE"
    elif command -v pw-play &> /dev/null; then
        pw-play --volume={volume / 100:.2f} "{audio_path}" 2>/dev/null &
        echo $! > "$AUDIO_PID_FILE"
    elif command -v aplay &> /dev/null; then
        aplay -q "{audio_path}" 2>/dev/null &
        echo $! > "$AUDIO_PID_FILE"
    elif command -v afplay &> /dev/null; then
        afplay -v {volume / 100:.2f} "{audio_path}" 2>/dev/null &
        echo $! > "$AUDIO_PID_FILE"
    elif command -v powershell.exe &> /dev/null; then
        # WSL: Copy to Windows temp to avoid UNC path issues with SoundPlayer
        win_temp="/mnt/c/Users/Public/waiting-bell.wav"
        cp "{audio_path}" "$win_temp" 2>/dev/null
        powershell.exe -c "(New-Object Media.SoundPlayer 'C:\\Users\\Public\\waiting-bell.wav').PlaySync()" 2>/dev/null &
        echo $! > "$AUDIO_PID_FILE"
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
    interval = config.get("interval", 30)
    max_nags = config.get("max_nags", 0)
    grace_period = config.get("grace_period", 30)
    volume = config.get("volume", 100)

    return f'''#!/bin/bash
# Waiting - Stop hook with wait-and-see logic
{get_hook_version_header()}

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
STOP_SIGNAL="/tmp/waiting-stop-$SESSION_ID"

now=$(date +%s)

# ============================================
# STEP 1: Create stop signal FIRST
# ============================================
touch "$STOP_SIGNAL"
sleep 0.3

# ============================================
# STEP 2: Kill audio EXPLICITLY (SIGKILL prevents cleanup)
# ============================================
for audiopid in /tmp/waiting-audio-*.pid; do
    if [ -f "$audiopid" ]; then
        kill "$(cat "$audiopid")" 2>/dev/null
        kill -9 "$(cat "$audiopid")" 2>/dev/null
        rm -f "$audiopid"
    fi
done
pgrep -f "SoundPlayer.*waiting-bell" | xargs -r kill 2>/dev/null
pgrep -f "powershell.*waiting-bell" | xargs -r kill 2>/dev/null

# ============================================
# STEP 3: Kill nag processes
# ============================================
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$OLD_PID" ]; then
        kill "$OLD_PID" 2>/dev/null
        sleep 0.1
        kill -9 "$OLD_PID" 2>/dev/null
    fi
    rm -f "$PID_FILE"
fi

for pidfile in /tmp/waiting-nag-*.pid; do
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile" 2>/dev/null)
        if [ -n "$pid" ]; then
            kill "$pid" 2>/dev/null
            kill -9 "$pid" 2>/dev/null
        fi
        rm -f "$pidfile"
    fi
done

sleep 0.1

# ============================================
# STEP 4: Remove stop signal for new nag
# ============================================
rm -f "$STOP_SIGNAL"

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
SESSION_ID="$8"

STOP_SIGNAL="/tmp/waiting-stop-$SESSION_ID"

start_time=$(($(cat "$STOP_TIME_FILE" 2>/dev/null || date +%s) + 2))  # +2 to avoid race with activity hooks
nag_count=0
max_lifetime=600  # 10 minute orphan protection
heartbeat_timeout=120  # 2 minute heartbeat timeout

cleanup() {{
    echo "$(date '+%Y-%m-%d %H:%M:%S') [stop-nag] cleanup called" >> /tmp/waiting-activity-debug.log
    # Kill audio by tracked PID
    AUDIO_PID_FILE="/tmp/waiting-audio-$SESSION_ID.pid"
    if [ -f "$AUDIO_PID_FILE" ]; then
        kill $(cat "$AUDIO_PID_FILE") 2>/dev/null
        kill -9 $(cat "$AUDIO_PID_FILE") 2>/dev/null
        rm -f "$AUDIO_PID_FILE"
    fi
    # Kill any powershell audio (WSL)
    pgrep -f "SoundPlayer.*waiting-bell" | xargs -r kill 2>/dev/null
    pgrep -f "powershell.*waiting-bell" | xargs -r kill 2>/dev/null
    rm -f "$PID_FILE"
    rm -f "$STOP_SIGNAL"
    exit 0
}}
trap cleanup SIGTERM SIGINT EXIT

# Check function for all exit conditions
should_exit() {{
    # PRIMARY: Check stop signal file (most reliable)
    [ -f "$STOP_SIGNAL" ] && return 0
    # Secondary checks
    [ ! -f "$PID_FILE" ] && return 0
    if [ -f "$ACTIVITY_FILE" ]; then
        last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
        [ "$last_activity" -ge "$start_time" ] && return 0
    fi
    # Check heartbeat (if Claude is dead, stop nagging)
    if [ -f "$HEARTBEAT_FILE" ]; then
        heartbeat=$(cat "$HEARTBEAT_FILE" 2>/dev/null || echo 0)
        elapsed=$(($(date +%s) - heartbeat))
        [ "$elapsed" -ge "$heartbeat_timeout" ] && return 0
    fi
    return 1
}}

{get_audio_command(audio_path, volume)}

# Grace period - check frequently (every 0.2 seconds)
grace_checks=$((GRACE_PERIOD * 5))
for ((i=0; i<grace_checks; i++)); do
    sleep 0.2
    should_exit && cleanup
done

# Main nag loop
while true; do
    elapsed=$(($(date +%s) - start_time))
    [ "$elapsed" -ge "$max_lifetime" ] && cleanup
    should_exit && cleanup

    play_sound
    nag_count=$((nag_count + 1))

    if [ "$MAX_NAGS" -gt 0 ] && [ "$nag_count" -ge "$MAX_NAGS" ]; then
        cleanup
    fi

    # Sleep in 0.2 second increments for fast response to stop signal
    interval_checks=$((INTERVAL * 5))
    for ((i=0; i<interval_checks; i++)); do
        sleep 0.2
        should_exit && cleanup
    done
done
NAGEOF

chmod +x "$NAG_SCRIPT"

"$NAG_SCRIPT" "$INTERVAL" "$MAX_NAGS" "$GRACE_PERIOD" "$PID_FILE" "$ACTIVITY_FILE" "$STOP_TIME_FILE" "$HEARTBEAT_FILE" "$SESSION_ID" > /dev/null 2>&1 &
echo $! > "$PID_FILE"
'''


def create_permission_script() -> str:
    """Generate the Permission hook script (wait-and-see with pending marker)."""
    config = load_config()
    audio_path = get_audio_path()
    interval = config.get("interval", 30)
    max_nags = config.get("max_nags", 0)
    grace_period = config.get("grace_period", 30)
    volume = config.get("volume", 100)

    return f'''#!/bin/bash
# Waiting - Permission hook with pending marker
{get_hook_version_header()}

# Debug logging
echo "$(date '+%Y-%m-%d %H:%M:%S') PermissionRequest fired" >> /tmp/waiting-activity-debug.log

INTERVAL={interval}
MAX_NAGS={max_nags}
GRACE_PERIOD={grace_period}

{get_session_id_snippet()}

echo "$(date '+%Y-%m-%d %H:%M:%S') [permission] SESSION_ID=$SESSION_ID" >> /tmp/waiting-activity-debug.log

# Session-specific files
NAG_MARKER="waiting-nag-$SESSION_ID"
PID_FILE="/tmp/$NAG_MARKER.pid"
PENDING_FILE="/tmp/waiting-pending-$SESSION_ID"
ACTIVITY_FILE="/tmp/waiting-activity-permission-$SESSION_ID"
STOP_SIGNAL="/tmp/waiting-stop-$SESSION_ID"

now=$(date +%s)

# NOTE: We removed the "recent activity" check from here.
# The nag script's should_exit() function handles this by checking if activity
# happened AFTER the nag started. This prevents the bug where PreToolUse's +1
# timestamp caused all subsequent permission requests to be skipped.

# ============================================
# STEP 1: Create stop signal FIRST
# This gives the old nag a chance to exit cleanly via should_exit()
# If it exits cleanly, cleanup() will run and kill audio
# ============================================
touch "$STOP_SIGNAL"
sleep 0.3  # Give nag time to see signal and exit cleanly

# ============================================
# STEP 2: Kill audio EXPLICITLY
# CRITICAL: If we have to use SIGKILL, the trap won't run, so cleanup()
# never executes. We must kill audio manually BEFORE killing the nag.
# ============================================
AUDIO_PID_FILE="/tmp/waiting-audio-$SESSION_ID.pid"
if [ -f "$AUDIO_PID_FILE" ]; then
    kill "$(cat "$AUDIO_PID_FILE")" 2>/dev/null
    kill -9 "$(cat "$AUDIO_PID_FILE")" 2>/dev/null
    rm -f "$AUDIO_PID_FILE"
fi

# Kill ALL audio processes (handles orphans from other sessions)
for audiopid in /tmp/waiting-audio-*.pid; do
    if [ -f "$audiopid" ]; then
        kill "$(cat "$audiopid")" 2>/dev/null
        kill -9 "$(cat "$audiopid")" 2>/dev/null
        rm -f "$audiopid"
    fi
done

# Kill any powershell audio processes (WSL)
pgrep -f "SoundPlayer.*waiting-bell" | xargs -r kill 2>/dev/null
pgrep -f "powershell.*waiting-bell" | xargs -r kill 2>/dev/null

# ============================================
# STEP 3: Kill the nag process
# ============================================
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$OLD_PID" ]; then
        kill "$OLD_PID" 2>/dev/null
        sleep 0.1
        kill -9 "$OLD_PID" 2>/dev/null
    fi
    rm -f "$PID_FILE"
fi

# Kill ALL nags by PID files (handles orphans)
for pidfile in /tmp/waiting-nag-*.pid; do
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile" 2>/dev/null)
        if [ -n "$pid" ]; then
            kill "$pid" 2>/dev/null
            kill -9 "$pid" 2>/dev/null
        fi
        rm -f "$pidfile"
    fi
done

sleep 0.1

# Reset activity file so new nag doesn't see stale timestamp from previous response
rm -f "$ACTIVITY_FILE"

# ============================================
# STEP 4: Remove stop signal so new nag doesn't exit immediately
# ============================================
rm -f "$STOP_SIGNAL"

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
SESSION_ID="$7"

STOP_SIGNAL="/tmp/waiting-stop-$SESSION_ID"

start_time=$(($(date +%s) + 2))  # +2 to avoid race with PreToolUse's +1 buffer
nag_count=0
max_lifetime=600  # 10 minute orphan protection

cleanup() {{
    echo "$(date '+%Y-%m-%d %H:%M:%S') [nag] cleanup called" >> /tmp/waiting-activity-debug.log
    # Kill audio by tracked PID
    AUDIO_PID_FILE="/tmp/waiting-audio-$SESSION_ID.pid"
    if [ -f "$AUDIO_PID_FILE" ]; then
        kill $(cat "$AUDIO_PID_FILE") 2>/dev/null
        kill -9 $(cat "$AUDIO_PID_FILE") 2>/dev/null
        rm -f "$AUDIO_PID_FILE"
    fi
    # Kill any powershell audio (WSL)
    pgrep -f "SoundPlayer.*waiting-bell" | xargs -r kill 2>/dev/null
    pgrep -f "powershell.*waiting-bell" | xargs -r kill 2>/dev/null
    rm -f "$PID_FILE"
    rm -f "$STOP_SIGNAL"
    exit 0
}}
trap cleanup SIGTERM SIGINT EXIT

# Check function for all exit conditions
should_exit() {{
    # PRIMARY: Check stop signal file (most reliable)
    [ -f "$STOP_SIGNAL" ] && return 0
    # Secondary checks
    [ ! -f "$PID_FILE" ] && return 0
    [ ! -f "$PENDING_FILE" ] && return 0
    if [ -f "$ACTIVITY_FILE" ]; then
        last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
        [ "$last_activity" -ge "$start_time" ] && return 0
    fi
    return 1
}}

{get_audio_command(audio_path, volume)}

# Grace period - check frequently (every 0.2 seconds)
grace_checks=$((GRACE_PERIOD * 5))
for ((i=0; i<grace_checks; i++)); do
    sleep 0.2
    should_exit && cleanup
done

should_exit && cleanup

# Play once and exit (no repeat for permission hook)
play_sound
cleanup
NAGEOF

chmod +x "$NAG_SCRIPT"

echo "$(date '+%Y-%m-%d %H:%M:%S') [permission] Starting nag with grace period $GRACE_PERIOD sec" >> /tmp/waiting-activity-debug.log
"$NAG_SCRIPT" "$INTERVAL" "$MAX_NAGS" "$GRACE_PERIOD" "$PID_FILE" "$PENDING_FILE" "$ACTIVITY_FILE" "$SESSION_ID" > /dev/null 2>&1 &
echo $! > "$PID_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') [permission] Nag started with PID $!" >> /tmp/waiting-activity-debug.log
'''


def create_idle_script() -> str:
    """Generate the Idle hook script (Claude's idle_prompt has 60s built-in)."""
    config = load_config()
    audio_path = get_audio_path()
    interval = config.get("interval", 30)
    max_nags = config.get("max_nags", 0)
    grace_period = config.get("grace_period", 30)
    volume = config.get("volume", 100)

    return f'''#!/bin/bash
# Waiting - Idle hook (idle_prompt already has 60s built-in delay)
{get_hook_version_header()}

INTERVAL={interval}
MAX_NAGS={max_nags}
GRACE_PERIOD={grace_period}

{get_session_id_snippet()}

# Session-specific files
NAG_MARKER="waiting-nag-$SESSION_ID"
PID_FILE="/tmp/$NAG_MARKER.pid"
ACTIVITY_FILE="/tmp/waiting-activity-stop-$SESSION_ID"
STOP_SIGNAL="/tmp/waiting-stop-$SESSION_ID"

now=$(date +%s)

# ============================================
# STEP 1: Create stop signal FIRST
# ============================================
touch "$STOP_SIGNAL"
sleep 0.3

# ============================================
# STEP 2: Kill audio EXPLICITLY (SIGKILL prevents cleanup)
# ============================================
for audiopid in /tmp/waiting-audio-*.pid; do
    if [ -f "$audiopid" ]; then
        kill "$(cat "$audiopid")" 2>/dev/null
        kill -9 "$(cat "$audiopid")" 2>/dev/null
        rm -f "$audiopid"
    fi
done
pgrep -f "SoundPlayer.*waiting-bell" | xargs -r kill 2>/dev/null
pgrep -f "powershell.*waiting-bell" | xargs -r kill 2>/dev/null

# ============================================
# STEP 3: Kill nag processes
# ============================================
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$OLD_PID" ]; then
        kill "$OLD_PID" 2>/dev/null
        sleep 0.1
        kill -9 "$OLD_PID" 2>/dev/null
    fi
    rm -f "$PID_FILE"
fi

for pidfile in /tmp/waiting-nag-*.pid; do
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile" 2>/dev/null)
        if [ -n "$pid" ]; then
            kill "$pid" 2>/dev/null
            kill -9 "$pid" 2>/dev/null
        fi
        rm -f "$pidfile"
    fi
done

sleep 0.1

# ============================================
# STEP 4: Remove stop signal for new nag
# ============================================
rm -f "$STOP_SIGNAL"

# Create nag script
NAG_SCRIPT="/tmp/$NAG_MARKER.sh"

cat > "$NAG_SCRIPT" << 'NAGEOF'
#!/bin/bash

INTERVAL="$1"
MAX_NAGS="$2"
GRACE_PERIOD="$3"
PID_FILE="$4"
ACTIVITY_FILE="$5"
SESSION_ID="$6"

STOP_SIGNAL="/tmp/waiting-stop-$SESSION_ID"

start_time=$(date +%s)
nag_count=0
max_lifetime=600

cleanup() {{
    echo "$(date '+%Y-%m-%d %H:%M:%S') [idle-nag] cleanup called" >> /tmp/waiting-activity-debug.log
    # Kill audio by tracked PID
    AUDIO_PID_FILE="/tmp/waiting-audio-$SESSION_ID.pid"
    if [ -f "$AUDIO_PID_FILE" ]; then
        kill $(cat "$AUDIO_PID_FILE") 2>/dev/null
        kill -9 $(cat "$AUDIO_PID_FILE") 2>/dev/null
        rm -f "$AUDIO_PID_FILE"
    fi
    # Kill any powershell audio (WSL)
    pgrep -f "SoundPlayer.*waiting-bell" | xargs -r kill 2>/dev/null
    pgrep -f "powershell.*waiting-bell" | xargs -r kill 2>/dev/null
    rm -f "$PID_FILE"
    rm -f "$STOP_SIGNAL"
    exit 0
}}
trap cleanup SIGTERM SIGINT EXIT

# Check function for all exit conditions
should_exit() {{
    # PRIMARY: Check stop signal file (most reliable)
    [ -f "$STOP_SIGNAL" ] && return 0
    # Secondary checks
    [ ! -f "$PID_FILE" ] && return 0
    if [ -f "$ACTIVITY_FILE" ]; then
        last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
        [ "$last_activity" -ge "$start_time" ] && return 0
    fi
    return 1
}}

{get_audio_command(audio_path, volume)}

# Optional additional grace period - check frequently (every 0.2 seconds)
grace_checks=$((GRACE_PERIOD * 5))
for ((i=0; i<grace_checks; i++)); do
    sleep 0.2
    should_exit && cleanup
done

# Main nag loop
while true; do
    elapsed=$(($(date +%s) - start_time))
    [ "$elapsed" -ge "$max_lifetime" ] && cleanup
    should_exit && cleanup

    play_sound
    nag_count=$((nag_count + 1))

    if [ "$MAX_NAGS" -gt 0 ] && [ "$nag_count" -ge "$MAX_NAGS" ]; then
        cleanup
    fi

    # Sleep in 0.2 second increments for fast response to stop signal
    interval_checks=$((INTERVAL * 5))
    for ((i=0; i<interval_checks; i++)); do
        sleep 0.2
        should_exit && cleanup
    done
done
NAGEOF

chmod +x "$NAG_SCRIPT"

"$NAG_SCRIPT" "$INTERVAL" "$MAX_NAGS" "$GRACE_PERIOD" "$PID_FILE" "$ACTIVITY_FILE" "$SESSION_ID" > /dev/null 2>&1 &
echo $! > "$PID_FILE"
'''


def create_activity_submit_script() -> str:
    """Generate the UserPromptSubmit activity script."""
    return f'''#!/bin/bash
# Waiting - Activity hook for user message submit
{get_hook_version_header()}

# Debug logging
echo "$(date '+%Y-%m-%d %H:%M:%S') UserPromptSubmit fired" >> /tmp/waiting-activity-debug.log

{get_session_id_snippet()}

echo "$(date '+%Y-%m-%d %H:%M:%S') SESSION_ID=$SESSION_ID" >> /tmp/waiting-activity-debug.log

# ============================================
# PRIMARY KILL METHOD: Stop signal file
# The nag script polls for this file and self-terminates
# This is atomic and reliable - no process signaling needed
# ============================================
STOP_SIGNAL="/tmp/waiting-stop-$SESSION_ID"
touch "$STOP_SIGNAL"
echo "$(date '+%Y-%m-%d %H:%M:%S') Created stop signal: $STOP_SIGNAL" >> /tmp/waiting-activity-debug.log

# Also create stop signals for ALL sessions (handles orphans)
for pidfile in /tmp/waiting-nag-*.pid; do
    if [ -f "$pidfile" ]; then
        orphan_session=$(basename "$pidfile" | sed 's/waiting-nag-//' | sed 's/.pid//')
        touch "/tmp/waiting-stop-$orphan_session"
    fi
done

# Update stop activity file only (not permission - that's only for PreToolUse)
# This ensures permission dialogs can still trigger nags after user submits a message
ACTIVITY_TIME=$(($(date +%s) + 1))
echo "$ACTIVITY_TIME" > "/tmp/waiting-activity-stop-$SESSION_ID"
# Note: Don't update permission activity here - only PreToolUse should do that

# Remove pending file (signals permission dialog closed)
rm -f "/tmp/waiting-pending-$SESSION_ID"

# ============================================
# BACKUP KILL METHOD: Direct PID termination
# Belt and suspenders - also try to kill by PID
# ============================================

# Kill audio by tracked PID
for audiopid in /tmp/waiting-audio-*.pid; do
    if [ -f "$audiopid" ]; then
        kill "$(cat "$audiopid")" 2>/dev/null
        kill -9 "$(cat "$audiopid")" 2>/dev/null
    fi
done

# Kill nag by PID file
NAG_PID_FILE="/tmp/waiting-nag-$SESSION_ID.pid"
if [ -f "$NAG_PID_FILE" ]; then
    NAG_PID=$(cat "$NAG_PID_FILE")
    if [ -n "$NAG_PID" ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') Killing nag PID $NAG_PID" >> /tmp/waiting-activity-debug.log
        kill "$NAG_PID" 2>/dev/null
        sleep 0.1
        kill -9 "$NAG_PID" 2>/dev/null
    fi
fi

# Kill ALL nags by PID files (handles orphans)
for pidfile in /tmp/waiting-nag-*.pid; do
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile" 2>/dev/null)
        if [ -n "$pid" ]; then
            kill "$pid" 2>/dev/null
            kill -9 "$pid" 2>/dev/null
        fi
    fi
done

# Kill any powershell audio processes (WSL)
pgrep -f "SoundPlayer.*waiting-bell" | xargs -r kill 2>/dev/null
pgrep -f "powershell.*waiting-bell" | xargs -r kill 2>/dev/null

# Cleanup temp files (after kills complete)
sleep 0.2
rm -f /tmp/waiting-nag-*.pid
rm -f /tmp/waiting-pending-*
rm -f /tmp/waiting-audio-*.pid
# Note: Don't remove stop signals - nag needs to see them to exit

echo "$(date '+%Y-%m-%d %H:%M:%S') Cleanup done" >> /tmp/waiting-activity-debug.log
'''


def create_activity_tooluse_script() -> str:
    """Generate the PreToolUse activity script."""
    return f'''#!/bin/bash
# Waiting - Activity hook for tool approval
{get_hook_version_header()}

# Debug logging
echo "$(date '+%Y-%m-%d %H:%M:%S') PreToolUse fired" >> /tmp/waiting-activity-debug.log

{get_session_id_snippet()}

echo "$(date '+%Y-%m-%d %H:%M:%S') SESSION_ID=$SESSION_ID" >> /tmp/waiting-activity-debug.log

# ============================================
# PRIMARY KILL METHOD: Stop signal file
# The nag script polls for this file and self-terminates
# ============================================
STOP_SIGNAL="/tmp/waiting-stop-$SESSION_ID"
touch "$STOP_SIGNAL"
echo "$(date '+%Y-%m-%d %H:%M:%S') [tooluse] Created stop signal: $STOP_SIGNAL" >> /tmp/waiting-activity-debug.log

# Also create stop signals for ALL sessions (handles orphans)
for pidfile in /tmp/waiting-nag-*.pid; do
    if [ -f "$pidfile" ]; then
        orphan_session=$(basename "$pidfile" | sed 's/waiting-nag-//' | sed 's/.pid//')
        touch "/tmp/waiting-stop-$orphan_session"
    fi
done

echo "$(date '+%Y-%m-%d %H:%M:%S') [tooluse] Stop signal created, sleeping 0.3s for nag to exit cleanly" >> /tmp/waiting-activity-debug.log
sleep 0.3  # Give nag time to see signal and exit cleanly via should_exit()

# Update activity (+1 buffer)
ACTIVITY_TIME=$(($(date +%s) + 1))
echo "$ACTIVITY_TIME" > "/tmp/waiting-activity-stop-$SESSION_ID"
echo "$ACTIVITY_TIME" > "/tmp/waiting-activity-permission-$SESSION_ID"

# Remove pending file (signals permission dialog closed)
rm -f "/tmp/waiting-pending-$SESSION_ID"

# ============================================
# STEP 2: Kill audio EXPLICITLY
# CRITICAL: If we have to use SIGKILL, the trap won't run, so cleanup()
# never executes. We must kill audio manually BEFORE killing the nag.
# ============================================

# Kill audio by tracked PID
for audiopid in /tmp/waiting-audio-*.pid; do
    if [ -f "$audiopid" ]; then
        kill "$(cat "$audiopid")" 2>/dev/null
        kill -9 "$(cat "$audiopid")" 2>/dev/null
        rm -f "$audiopid"
    fi
done

# Kill ALL audio processes (handles orphans from other sessions)
for audiopid in /tmp/waiting-audio-*.pid; do
    if [ -f "$audiopid" ]; then
        kill "$(cat "$audiopid")" 2>/dev/null
        kill -9 "$(cat "$audiopid")" 2>/dev/null
        rm -f "$audiopid"
    fi
done

# Kill ALL paplay/pw-play/aplay processes that might be playing the bell
pgrep -f "paplay.*(waiting-bell|Cool_bell)" | xargs -r kill -9 2>/dev/null
pgrep -f "pw-play.*(waiting-bell|Cool_bell)" | xargs -r kill -9 2>/dev/null
pgrep -f "aplay.*(waiting-bell|Cool_bell)" | xargs -r kill -9 2>/dev/null
pgrep -f "afplay.*(waiting-bell|Cool_bell)" | xargs -r kill -9 2>/dev/null

# Kill any powershell audio processes (WSL)
pgrep -f "SoundPlayer.*waiting-bell" | xargs -r kill 2>/dev/null
pgrep -f "powershell.*waiting-bell" | xargs -r kill 2>/dev/null

# ============================================
# STEP 3: Kill the nag processes
# ============================================
NAG_PID_FILE="/tmp/waiting-nag-$SESSION_ID.pid"
if [ -f "$NAG_PID_FILE" ]; then
    NAG_PID=$(cat "$NAG_PID_FILE")
    if [ -n "$NAG_PID" ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') [tooluse] Killing nag PID $NAG_PID" >> /tmp/waiting-activity-debug.log
        kill "$NAG_PID" 2>/dev/null
        sleep 0.1
        kill -9 "$NAG_PID" 2>/dev/null
    fi
fi

# Kill ALL nags by PID files (handles orphans)
for pidfile in /tmp/waiting-nag-*.pid; do
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile" 2>/dev/null)
        if [ -n "$pid" ]; then
            kill "$pid" 2>/dev/null
            kill -9 "$pid" 2>/dev/null
        fi
    fi
done

sleep 0.1

# ============================================
# CLEANUP: Remove all temp files for this session
# ============================================
rm -f /tmp/waiting-nag-*.pid
rm -f /tmp/waiting-pending-*
rm -f /tmp/waiting-audio-*.pid
rm -f /tmp/waiting-stop-*

echo "$(date '+%Y-%m-%d %H:%M:%S') [tooluse] Cleanup done" >> /tmp/waiting-activity-debug.log
'''


def _is_waiting_hook(command: str) -> bool:
    """Check if a command is a waiting hook."""
    return any(marker in command for marker in ["waiting-notify", "waiting-activity"])


def kill_all_nags() -> None:
    """Kill all nag processes reliably using PID files and stop signals."""
    # Create stop signals for all sessions (primary method)
    for pidfile in glob.glob("/tmp/waiting-nag-*.pid"):
        session_id = pidfile.replace("/tmp/waiting-nag-", "").replace(".pid", "")
        stop_signal = f"/tmp/waiting-stop-{session_id}"
        Path(stop_signal).touch()

    # Kill by PID files (backup method)
    for pidfile in glob.glob("/tmp/waiting-nag-*.pid"):
        try:
            with open(pidfile) as f:
                pid = f.read().strip()
                if pid:
                    subprocess.run(["kill", pid], stderr=subprocess.DEVNULL)
                    subprocess.run(["kill", "-9", pid], stderr=subprocess.DEVNULL)
        except (IOError, OSError):
            pass

    # Kill audio processes
    for audiopid in glob.glob("/tmp/waiting-audio-*.pid"):
        try:
            with open(audiopid) as f:
                pid = f.read().strip()
                if pid:
                    subprocess.run(["kill", pid], stderr=subprocess.DEVNULL)
                    subprocess.run(["kill", "-9", pid], stderr=subprocess.DEVNULL)
        except (IOError, OSError):
            pass

    # Cleanup temp files
    for pattern in ["/tmp/waiting-nag-*.pid", "/tmp/waiting-pending-*",
                    "/tmp/waiting-audio-*.pid", "/tmp/waiting-stop-*"]:
        for f in glob.glob(pattern):
            try:
                os.remove(f)
            except OSError:
                pass


def setup_hooks() -> None:
    """Install hook scripts and update Claude settings."""
    config = load_config()
    enabled = config["enabled_hooks"]

    # Kill existing nag processes (using reliable method)
    kill_all_nags()

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

    # Kill nag processes (using reliable method)
    kill_all_nags()


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
    # Check for outdated hooks when running subcommands (not main enable command)
    if ctx.invoked_subcommand is not None and ctx.invoked_subcommand not in ["doctor", "disable"]:
        installed_version = get_installed_hook_version()
        if installed_version and installed_version != HOOK_VERSION:
            click.echo(f"Warning: Hooks outdated ({installed_version} -> {HOOK_VERSION})")
            click.echo("Run 'waiting' or 'waiting doctor --fix' to update.\n")

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
        config = load_config()

        click.echo("Waiting notifications enabled.")
        click.echo("")
        click.echo("Current settings:")
        click.echo(f"  Enabled hooks: {', '.join(config.get('enabled_hooks', ['stop', 'idle']))}")
        click.echo(f"  Grace period: {config.get('grace_period', 30)}s")
        click.echo(f"  Interval: {config.get('interval', 30)}s")
        click.echo(f"  Volume: {config.get('volume', 100)}%")
        click.echo("")
        click.echo("Configure with:")
        click.echo("  waiting configure --grace-period 60")
        click.echo("  waiting configure --interval 45")
        click.echo("  waiting configure --enable-hook permission")
        click.echo("  waiting configure --disable-hook idle")
        click.echo("  waiting configure --show    (view all settings)")
        click.echo("")
        click.echo("Restart Claude Code to activate hooks.")


@cli.command()
def disable():
    """Remove all hooks and scripts."""
    remove_hooks()
    click.echo("Waiting notifications disabled.")


@cli.command()
def kill():
    """Stop current nag loop without disabling hooks."""
    kill_all_nags()
    click.echo("Nag processes killed.")


@cli.command()
@click.option("--fix", is_flag=True, help="Automatically fix issues")
def doctor(fix):
    """Diagnose and fix common issues with waiting notifications."""
    issues = []
    fixes_applied = []

    click.echo("Checking waiting notification health...\n")

    # Check 1: Hook version
    installed_version = get_installed_hook_version()
    if installed_version is None:
        issues.append("Hooks not installed or pre-2.0 version (no version tracking)")
        if fix:
            setup_hooks()
            fixes_applied.append("Regenerated hooks with latest version")
    elif installed_version != HOOK_VERSION:
        issues.append(f"Hooks outdated: {installed_version} -> {HOOK_VERSION}")
        if fix:
            setup_hooks()
            fixes_applied.append("Updated hooks to latest version")
    else:
        click.echo(f"[OK] Hook version: {installed_version}")

    # Check 2: Running nags
    nags = get_running_nags()
    if nags:
        issues.append(f"{len(nags)} nag process(es) running")
        if fix:
            kill_all_nags()
            fixes_applied.append(f"Killed {len(nags)} nag process(es)")
    else:
        click.echo("[OK] No stray nag processes")

    # Check 3: Orphaned files
    orphans = get_orphaned_files()
    orphan_count = sum(len(v) for v in orphans.values())
    if orphan_count > 0:
        issues.append(f"{orphan_count} orphaned temp file(s)")
        if fix:
            for category, files in orphans.items():
                for f in files:
                    try:
                        os.remove(f)
                    except OSError:
                        pass
            fixes_applied.append(f"Cleaned up {orphan_count} orphaned file(s)")
    else:
        click.echo("[OK] No orphaned temp files")

    # Check 4: Claude settings
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH) as f:
                settings = json.load(f)
            hooks = settings.get("hooks", {})
            waiting_hooks = []
            for hook_type, matchers in hooks.items():
                for matcher in matchers:
                    for hook in matcher.get("hooks", []):
                        cmd = hook.get("command", "")
                        if "waiting-" in cmd:
                            waiting_hooks.append(hook_type)
            if waiting_hooks:
                click.echo(f"[OK] Claude settings configured: {', '.join(set(waiting_hooks))}")
            else:
                issues.append("No waiting hooks in Claude settings")
                if fix:
                    setup_hooks()
                    fixes_applied.append("Added hooks to Claude settings")
        except (json.JSONDecodeError, IOError) as e:
            issues.append(f"Could not read Claude settings: {e}")
    else:
        issues.append("Claude settings file not found")

    # Check 5: Hook scripts exist
    hook_scripts = [
        "waiting-notify-permission.sh",
        "waiting-activity-submit.sh",
        "waiting-activity-tooluse.sh",
    ]
    missing_scripts = [s for s in hook_scripts if not (HOOKS_DIR / s).exists()]
    if missing_scripts:
        issues.append(f"Missing hook scripts: {', '.join(missing_scripts)}")
        if fix:
            setup_hooks()
            fixes_applied.append("Regenerated missing hook scripts")
    else:
        click.echo(f"[OK] All required hook scripts present")

    # Summary
    click.echo("")
    if issues:
        click.echo(f"Found {len(issues)} issue(s):")
        for issue in issues:
            click.echo(f"  - {issue}")

        if fix:
            click.echo(f"\nApplied {len(fixes_applied)} fix(es):")
            for applied in fixes_applied:
                click.echo(f"  - {applied}")
            click.echo("\nRestart Claude Code to apply hook changes.")
        else:
            click.echo("\nRun 'waiting doctor --fix' to automatically fix these issues.")
    else:
        click.echo("All checks passed! Waiting notifications are healthy.")


@cli.command()
def status():
    """Show current configuration, hook health, and active processes."""
    config = load_config()
    enabled = is_enabled()

    # Basic status
    click.echo(f"Status: {'enabled' if enabled else 'disabled'}")

    # Version info
    installed_version = get_installed_hook_version()
    if installed_version:
        version_match = installed_version == HOOK_VERSION
        version_status = "current" if version_match else f"OUTDATED (run 'waiting' to update)"
        click.echo(f"Hook version: {installed_version} ({version_status})")
    else:
        click.echo(f"Hook version: unknown (pre-2.0 or not installed)")

    click.echo(f"Latest version: {HOOK_VERSION}")

    # Running nags
    nags = get_running_nags()
    if nags:
        click.echo(f"\nRunning nags: {len(nags)}")
        for pid, session_id in nags:
            click.echo(f"  PID {pid}: session {session_id[:8]}...")
    else:
        click.echo(f"\nRunning nags: 0")

    # Orphaned files
    orphans = get_orphaned_files()
    orphan_count = sum(len(v) for v in orphans.values())
    if orphan_count > 0:
        click.echo(f"Orphaned files: {orphan_count} (run 'waiting doctor' to clean)")

    # Config
    click.echo(f"\nConfiguration:")
    click.echo(f"  Audio: {config.get('audio', 'default')}")
    click.echo(f"  Grace period: {config.get('grace_period', 30)}s")
    click.echo(f"  Interval: {config.get('interval', 30)}s")
    click.echo(f"  Max nags: {config.get('max_nags', 0)} (0=unlimited)")
    click.echo(f"  Volume: {config.get('volume', 100)}%")
    click.echo(f"  Enabled hooks: {', '.join(config.get('enabled_hooks', ['stop', 'idle']))}")


@cli.command()
@click.option("--audio", type=str, help="Audio file path ('default' for bundled)")
@click.option("--interval", type=int, help="Seconds between bell repeats")
@click.option("--max-nags", type=int, help="Maximum bell repeats (0=unlimited)")
@click.option("--volume", type=int, help="Volume percentage (1-100)")
@click.option("--grace-period", type=int, help="Seconds to wait before first bell")
@click.option("--enable-hook", type=click.Choice(["stop", "permission", "idle"]), help="Enable a hook")
@click.option("--disable-hook", type=click.Choice(["stop", "permission", "idle"]), help="Disable a hook")
@click.option("--hooks", type=str, help="Set enabled hooks (comma-separated)")
@click.option("--show", is_flag=True, help="Show config without modifying")
@click.option("--reset", is_flag=True, help="Reset to defaults")
def configure(audio, interval, max_nags, volume, grace_period, enable_hook, disable_hook, hooks, show, reset):
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
    if grace_period is not None:
        config["grace_period"] = grace_period
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
