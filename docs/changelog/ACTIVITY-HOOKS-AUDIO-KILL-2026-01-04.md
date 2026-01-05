# Activity Hooks Audio Kill Fix - January 4, 2026 (22:04)

## Problem

Bell continues playing after user responds to permission dialog, even after previous fixes to the nag script cleanup function.

## Root Cause

The **activity hooks** (PreToolUse, UserPromptSubmit) were only killing the nag script process, not the PowerShell audio process:

```bash
# Old activity hook code
pkill -f "waiting-nag-$SESSION_ID" 2>/dev/null
rm -f "/tmp/waiting-nag-$SESSION_ID.pid"
rm -f "$PENDING_FILE"
```

When user responds:
1. Activity hook fires (PreToolUse)
2. Nag script is killed
3. But PowerShell audio process is already running and continues playing

## Fix

Added `pkill -f "waiting-bell.wav"` to both activity scripts:

### waiting-activity-submit.sh
```bash
# Kill nag and any playing audio
pkill -f "waiting-nag-$SESSION_ID" 2>/dev/null
pkill -f "waiting-bell.wav" 2>/dev/null
rm -f "/tmp/waiting-nag-$SESSION_ID.pid"
rm -f "/tmp/waiting-pending-$SESSION_ID"
```

### waiting-activity-tooluse.sh
```bash
# Kill nag, audio, and clean pending marker
pkill -f "waiting-nag-$SESSION_ID" 2>/dev/null
pkill -f "waiting-bell.wav" 2>/dev/null
rm -f "/tmp/waiting-nag-$SESSION_ID.pid"
rm -f "$PENDING_FILE"
```

## Files Changed

- `src/waiting/cli.py`
  - `create_activity_submit_script()` (lines 449-453)
  - `create_activity_tooluse_script()` (lines 470-474)

## Why Previous Fix Was Incomplete

The previous fix added `pkill -f "waiting-bell.wav"` to the nag script's `cleanup()` function. This works when:
- Nag script receives SIGTERM and trap fires

But it doesn't work when:
- Nag script is killed by `pkill -f "waiting-nag-$SESSION_ID"` from activity hook
- The activity hook kills the nag before cleanup() can run
- Or the nag script is in the middle of `play_sound()` when killed

The fix ensures the activity hooks directly kill the audio process, regardless of nag script state.

## Requires

**Restart Claude Code** for the new activity hooks to take effect.
