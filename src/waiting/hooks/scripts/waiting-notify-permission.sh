#!/bin/bash
# Hook for PermissionRequest event
# Triggered when Claude Code shows a permission dialog
# Starts grace period timer, plays audio if user doesn't respond

set -e

# Read hook input from stdin
HOOK_JSON=$(cat)

# Extract session_id from hook JSON input
SESSION_ID=$(echo "$HOOK_JSON" | jq -r '.session_id // empty' 2>/dev/null || echo "")

# Fallback: generate MD5 session ID if not provided
if [ -z "$SESSION_ID" ]; then
    SESSION_ID=$(echo "$(hostname)-$(date +%s%N)" | md5sum | cut -d' ' -f1)
fi

# Load configuration from ~/.waiting.json
CONFIG_FILE="$HOME/.waiting.json"
if [ ! -f "$CONFIG_FILE" ]; then
    # No config file, exit gracefully
    exit 0
fi

GRACE_PERIOD=$(jq -r '.grace_period // 30' "$CONFIG_FILE" 2>/dev/null || echo "30")
AUDIO_FILE=$(jq -r '.audio // "default"' "$CONFIG_FILE" 2>/dev/null || echo "default")
VOLUME=$(jq -r '.volume // 100' "$CONFIG_FILE" 2>/dev/null || echo "100")

# State file paths
STOP_SIGNAL="/tmp/waiting-stop-$SESSION_ID"
PID_FILE="/tmp/waiting-audio-$SESSION_ID.pid"
LOG_FILE="$HOME/.waiting.log"

# Log the permission request
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PermissionRequest - Session: $SESSION_ID, Grace: ${GRACE_PERIOD}s, Volume: ${VOLUME}%" >> "$LOG_FILE"

# Run grace period in background (non-blocking)
(
    # Loop for grace period, checking for stop signal every second
    for ((i=0; i<$GRACE_PERIOD; i++)); do
        if [ -f "$STOP_SIGNAL" ]; then
            # User responded, stop signal detected
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] User responded - Audio canceled. Session: $SESSION_ID" >> "$LOG_FILE"
            rm -f "$STOP_SIGNAL" "$PID_FILE"
            exit 0
        fi
        sleep 1
    done

    # Grace period expired, check one more time if user responded
    if [ -f "$STOP_SIGNAL" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] User responded during final check. Session: $SESSION_ID" >> "$LOG_FILE"
        rm -f "$STOP_SIGNAL" "$PID_FILE"
        exit 0
    fi

    # Grace period elapsed, no user response - play audio
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Grace period expired - Playing audio. Session: $SESSION_ID" >> "$LOG_FILE"

    # Call Python audio player (returns PID via stdout)
    AUDIO_PID=$("$PYTHON_PATH" -m waiting.audio.play "$AUDIO_FILE" "$VOLUME" 2>> "$LOG_FILE" || echo "")

    # Store PID if available
    if [ -n "$AUDIO_PID" ]; then
        echo "$AUDIO_PID" > "$PID_FILE"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Audio started with PID: $AUDIO_PID. Session: $SESSION_ID" >> "$LOG_FILE"

        # Wait for audio process to complete
        wait "$AUDIO_PID" 2>/dev/null || true
    fi

    # Cleanup
    rm -f "$STOP_SIGNAL" "$PID_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Cleanup complete. Session: $SESSION_ID" >> "$LOG_FILE"
) &

# Exit immediately (hook runs in background)
exit 0
