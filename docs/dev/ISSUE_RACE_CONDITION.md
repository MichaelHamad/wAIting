# Issue: Bell Rings After User Approves Permission (Race Condition)

## Problem

When user approves a permission dialog, the bell can still ring once due to a race condition between the nag script waking up and PreToolUse killing it.

**Scenario:**
1. T=0: Dialog opens, nag script starts sleeping for grace_period (10s)
2. T=9: User approves permission
3. T=9.001: PreToolUse hook starts (kills nag, updates activity)
4. T=10: Nag script wakes from sleep, checks PID file (still exists!), plays bell
5. T=10.001: PreToolUse completes cleanup

The nag script wakes and plays before PreToolUse finishes killing it.

## Root Cause

There's a gap between when the nag script wakes from sleep and when it plays the sound. During this gap:
1. Script checks `$PID_FILE` exists → passes (PreToolUse hasn't deleted it yet)
2. Script checks activity → passes (PreToolUse hasn't updated it yet)
3. Script plays sound
4. PreToolUse finally completes, but too late

## Solution

Add a final activity check immediately before every `play_sound` call. This catches the race because PreToolUse updates the activity file before the file deletions.

### Changes Required

**File: `src/waiting/cli.py` - `create_permission_notify_script()` function**

Wrap every `play_sound` call with a pre-check:

```bash
check_and_play() {
    # Final check right before playing (catches race with PreToolUse)
    if [ -f "$ACTIVITY_FILE" ]; then
        last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
        if [ "$last_activity" -gt "$START_TIMESTAMP" ]; then
            echo "  Last-second: user responded, aborting" >> "$DEBUG_LOG"
            rm -f "$PID_FILE" "$0"
            exit 0
        fi
    fi
    play_sound
}
```

Then replace all `play_sound` calls with `check_and_play`.

**Locations to update:**
1. First bell after grace period (around line 399-400)
2. Nag loop bell (around line 456)

### Alternative: Add Small Delay

Add a 100ms delay before checking, giving PreToolUse time to complete:

```bash
sleep 0.1  # Let pending PreToolUse complete
if [ ! -f "$PID_FILE" ]; then exit 0; fi
# ... existing checks ...
play_sound
```

This is simpler but adds 100ms latency to every bell.

## Behavior After Fix

**Same scenario:**
1. T=0: Dialog opens, nag script sleeps
2. T=9: User approves
3. T=9.001: PreToolUse updates activity file to T=9
4. T=10: Nag wakes, final check sees activity(9) > START_TIMESTAMP(0)
5. Result: No bell (user responded)

## Summary

- Eliminates race condition where bell rings after user approves
- Minimal code change (wrap play_sound calls)
- No additional latency for legitimate notifications
