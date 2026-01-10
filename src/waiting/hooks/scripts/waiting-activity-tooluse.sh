#!/bin/bash
# Hook for PreToolUse event
# Triggered when user takes an action (uses a tool)
# Signals the permission hook to stop audio playback

set -e

# Read hook input from stdin
HOOK_JSON=$(cat)

# Extract session_id from hook JSON input
SESSION_ID=$(echo "$HOOK_JSON" | jq -r '.session_id // empty' 2>/dev/null || echo "")

# Validate session ID (alphanumeric, hyphens, underscores only, max 128 chars)
validate_session_id() {
    local id="$1"
    if [[ "$id" =~ ^[a-zA-Z0-9_-]+$ ]] && [ ${#id} -le 128 ]; then
        return 0
    fi
    return 1
}

# Validate or regenerate session ID
if [ -z "$SESSION_ID" ] || ! validate_session_id "$SESSION_ID"; then
    SESSION_ID=$(echo "$(hostname)-$(date +%s%N)" | md5sum | cut -d' ' -f1)
fi

# State file paths
STOP_SIGNAL="/tmp/waiting-stop-$SESSION_ID"
PID_FILE="/tmp/waiting-audio-$SESSION_ID.pid"
LOG_FILE="$HOME/.waiting.log"

# Create stop signal to indicate user responded
touch "$STOP_SIGNAL"

# Kill audio process if running
if [ -f "$PID_FILE" ]; then
    AUDIO_PID=$(cat "$PID_FILE" 2>/dev/null || echo "")
    if [ -n "$AUDIO_PID" ]; then
        kill "$AUDIO_PID" 2>/dev/null || true
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Killed audio process PID: $AUDIO_PID. Session: $SESSION_ID" >> "$LOG_FILE"
        rm -f "$PID_FILE"
    fi
fi

# Log the activity
echo "[$(date '+%Y-%m-%d %H:%M:%S')] User activity detected (PreToolUse). Stopped audio. Session: $SESSION_ID" >> "$LOG_FILE"

# Exit successfully
exit 0
