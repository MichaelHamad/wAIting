# Fix: Stray Audio from SIGKILL Not Triggering Cleanup

**Date:** 2026-01-05
**Version:** 2.2.0
**Status:** Fixed

## Problem

Users reported hearing bells continue playing even after:
- Responding to a permission dialog
- Claude Code finishing its work
- No permission menu being displayed

The bells were "stray" audio processes that wouldn't stop.

## Root Cause Analysis

When a new permission dialog appears while a previous one is still active (or its nag is running), the permission hook needs to kill the old nag process. The code was:

```bash
kill "$OLD_PID" 2>/dev/null
kill -9 "$OLD_PID" 2>/dev/null  # SIGKILL!
```

**The critical bug:** `SIGKILL` (signal 9) **cannot be caught by a trap**.

The nag script has a cleanup function that kills audio:

```bash
trap cleanup SIGTERM SIGINT EXIT

cleanup() {
    # Kill audio by tracked PID
    kill $(cat "$AUDIO_PID_FILE") 2>/dev/null
    ...
}
```

But when killed with SIGKILL:
1. The trap never runs
2. `cleanup()` is never called
3. The audio process continues playing indefinitely

## The Fix (v2.2.0)

We restructured all notification hooks (permission, stop, idle) to use a 4-step kill sequence:

### Step 1: Create stop signal FIRST
```bash
touch "$STOP_SIGNAL"
sleep 0.3  # Give nag time to see signal and exit cleanly
```

This gives the nag script a chance to exit gracefully via `should_exit()`, which WILL trigger the EXIT trap and run `cleanup()`.

### Step 2: Kill audio EXPLICITLY
```bash
for audiopid in /tmp/waiting-audio-*.pid; do
    if [ -f "$audiopid" ]; then
        kill "$(cat "$audiopid")" 2>/dev/null
        kill -9 "$(cat "$audiopid")" 2>/dev/null
        rm -f "$audiopid"
    fi
done
```

If we have to use SIGKILL, the trap won't run. We must kill audio **manually** before killing the nag. This ensures no orphan audio processes.

### Step 3: Kill nag processes
```bash
kill "$OLD_PID" 2>/dev/null
sleep 0.1
kill -9 "$OLD_PID" 2>/dev/null
```

Now we can safely kill the nag. If SIGTERM worked, great. If not, SIGKILL will finish it - but audio is already dead.

### Step 4: Remove stop signal
```bash
rm -f "$STOP_SIGNAL"
```

Only AFTER all cleanup is done, remove the stop signal so the new nag doesn't exit immediately.

## Why This Was Missed Before

The activity hooks (PreToolUse, UserPromptSubmit) already had audio killing code - they were added in v2.0.0. But the notification hooks (permission, stop, idle) only had nag killing, not audio killing.

The assumption was: "killing the nag will trigger its trap, which kills audio."

This is TRUE for SIGTERM but FALSE for SIGKILL.

## Files Changed

- `src/waiting/cli.py`:
  - `HOOK_VERSION` bumped to `"2.2.0"`
  - `create_permission_script()` - added 4-step kill sequence with audio cleanup
  - `create_stop_script()` - added 4-step kill sequence with audio cleanup
  - `create_idle_script()` - added 4-step kill sequence with audio cleanup

## Testing

1. Enable waiting: `waiting`
2. Restart Claude Code
3. Trigger a permission dialog
4. Wait for the bell to play (10 seconds grace period)
5. Respond to the dialog
6. **Verify:** Bell should stop immediately
7. **Verify:** No stray bells after Claude finishes working

## Related Issues

- Bug 6 (v2.0.0): pkill kills itself before completing cleanup
- Bug 7 (v2.1.0): -1 second activity timestamp blocking all nags
- Bug 8 (v2.2.0): **This fix** - SIGKILL doesn't trigger trap

## Upgrade Instructions

```bash
waiting  # Regenerates hooks with v2.2.0
# Restart Claude Code to apply changes
```

Or:

```bash
waiting doctor --fix
# Restart Claude Code to apply changes
```
