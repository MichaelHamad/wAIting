#!/bin/bash
# Diagnostic script to capture audio process state during permission dialog

echo "=== AUDIO STATE DIAGNOSTIC ==="
echo "Run this script WHILE the bell is playing during a permission dialog"
echo "This will help identify why audio isn't stopping"
echo ""

# Get most recent SESSION_ID from temp files
SESSION_ID=$(ls -t /tmp/waiting-nag-*.pid 2>/dev/null | head -1 | sed 's/.*waiting-nag-//;s/\.pid//')

if [ -z "$SESSION_ID" ]; then
    echo "ERROR: No active nag process found!"
    echo "Make sure a permission dialog is open and the bell is playing."
    exit 1
fi

echo "Found SESSION_ID: $SESSION_ID"
echo ""

# === STEP 1: Show all processes ===
echo "=== ALL BASH PROCESSES ==="
pgrep -af "bash|timeout|powershell" | sort
echo ""

# === STEP 2: Show processes matching current session ===
echo "=== PROCESSES FOR SESSION $SESSION_ID ==="
pgrep -af "waiting-nag-$SESSION_ID"
echo ""

# === STEP 3: Show all audio-related processes ===
echo "=== ALL AUDIO PROCESSES ==="
pgrep -af "paplay|aplay|afplay|pw-play|powershell|timeout|SoundPlayer|Media.SoundPlayer" | sort
echo ""

# === STEP 4: Test each pgrep pattern used by PreToolUse hook ===
echo "=== TESTING PGREP PATTERNS (from PreToolUse hook) ==="
echo ""

echo "Pattern 1: pgrep -f \"SoundPlayer.*waiting-bell|SoundPlayer.*Cool_bell\""
pgrep -f "SoundPlayer.*waiting-bell|SoundPlayer.*Cool_bell" && echo "  ✓ MATCHES" || echo "  ✗ NO MATCH"
echo ""

echo "Pattern 2: pgrep -f \"timeout.*powershell\""
pgrep -f "timeout.*powershell" && echo "  ✓ MATCHES" || echo "  ✗ NO MATCH"
echo ""

echo "Pattern 3: pgrep -f \"paplay.*(waiting-bell|Cool_bell)\""
pgrep -f "paplay.*(waiting-bell|Cool_bell)" && echo "  ✓ MATCHES" || echo "  ✗ NO MATCH"
echo ""

echo "Pattern 4: pgrep -f \"pw-play.*(waiting-bell|Cool_bell)\""
pgrep -f "pw-play.*(waiting-bell|Cool_bell)" && echo "  ✓ MATCHES" || echo "  ✗ NO MATCH"
echo ""

echo "Pattern 5: pgrep -f \"aplay.*(waiting-bell|Cool_bell)\""
pgrep -f "aplay.*(waiting-bell|Cool_bell)" && echo "  ✓ MATCHES" || echo "  ✗ NO MATCH"
echo ""

# === STEP 5: Show full command lines ===
echo "=== FULL COMMAND LINES FOR POWERSHELL PROCESSES ==="
ps auxww | grep -i powershell | grep -v grep
echo ""

# === STEP 6: Show temp files ===
echo "=== TEMP FILES FOR SESSION $SESSION_ID ==="
ls -la /tmp/waiting-* 2>/dev/null | grep "$SESSION_ID" || echo "No temp files found"
echo ""

echo "=== AUDIO PID FILE CONTENTS ==="
if [ -f "/tmp/waiting-audio-$SESSION_ID.pid" ]; then
    PID=$(cat "/tmp/waiting-audio-$SESSION_ID.pid")
    echo "Audio PID: $PID"
    if kill -0 "$PID" 2>/dev/null; then
        echo "Status: RUNNING"
        ps auxww | grep "^ *[^ ]* *$PID "
    else
        echo "Status: NOT RUNNING (PID is dead)"
    fi
else
    echo "No audio PID file found"
fi
echo ""

# === STEP 7: Show nag PID file ===
echo "=== NAG PID FILE CONTENTS ==="
if [ -f "/tmp/waiting-nag-$SESSION_ID.pid" ]; then
    NAG_PID=$(cat "/tmp/waiting-nag-$SESSION_ID.pid")
    echo "Nag PID: $NAG_PID"
    if kill -0 "$NAG_PID" 2>/dev/null; then
        echo "Status: RUNNING"
        ps auxww | grep "^ *[^ ]* *$NAG_PID "
    else
        echo "Status: NOT RUNNING (PID is dead)"
    fi
else
    echo "No nag PID file found"
fi
echo ""

# === STEP 8: Show debug log ===
echo "=== RECENT DEBUG LOG ENTRIES (last 10) ==="
tail -10 /tmp/waiting-activity-debug.log 2>/dev/null || echo "No debug log found"
