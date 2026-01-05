# Permission Nag Fix - v2.1.0

**Date:** January 5, 2026
**Version:** 2.1.0
**Status:** Fixed

---

## Summary

Fixed a critical bug where permission dialogs never triggered bell notifications because the activity check was blocking ALL nags from starting.

---

## Issue 1: Nags Never Starting

### Symptom
User triggers a permission dialog but never hears a bell, even after waiting past the grace period.

### Debug Evidence
```
2026-01-05 00:42:23 PreToolUse fired
2026-01-05 00:42:23 [tooluse] Cleanup done
2026-01-05 00:42:23 PermissionRequest fired
2026-01-05 00:42:23 [permission] Skipping nag - recent activity (-1 sec ago)
```

### Root Cause
The permission hook checked for "recent activity" before starting a nag:

```bash
if [ -f "$ACTIVITY_FILE" ]; then
    last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
    elapsed=$((now - last_activity))
    if [ "$elapsed" -lt 3 ]; then
        exit 0  # Skip nag
    fi
fi
```

The problem: `PreToolUse` sets activity timestamp with a +1 second buffer:
```bash
ACTIVITY_TIME=$(($(date +%s) + 1))  # 1 second in the FUTURE
```

When the next `PermissionRequest` fires immediately after:
```
elapsed = now - (now + 1) = -1
-1 < 3 is TRUE → nag is skipped
```

This created a loop where EVERY permission request after the first tool approval was skipped.

### Fix
Removed the activity check from the permission hook startup entirely:

```bash
# NOTE: We removed the "recent activity" check from here.
# The nag script's should_exit() function handles this by checking if activity
# happened AFTER the nag started. This prevents the bug where PreToolUse's +1
# timestamp caused all subsequent permission requests to be skipped.
```

The nag script's own `should_exit()` function already handles checking for activity that happens AFTER the nag starts, which is the correct behavior.

---

## Issue 2: UserPromptSubmit Blocking Permission Nags

### Symptom
After submitting a message, if a permission dialog appears within 3 seconds, no nag starts.

### Root Cause
`UserPromptSubmit` was updating BOTH activity files:
```bash
echo "$ACTIVITY_TIME" > "/tmp/waiting-activity-stop-$SESSION_ID"
echo "$ACTIVITY_TIME" > "/tmp/waiting-activity-permission-$SESSION_ID"
```

When the permission hook checked for recent activity, it saw the timestamp from `UserPromptSubmit` and skipped.

### Fix
`UserPromptSubmit` now only updates the stop activity file:
```bash
# Update stop activity file only (not permission - that's only for PreToolUse)
echo "$ACTIVITY_TIME" > "/tmp/waiting-activity-stop-$SESSION_ID"
# Note: Don't update permission activity here - only PreToolUse should do that
```

Only `PreToolUse` (which fires when user responds to a permission dialog) updates the permission activity file.

---

## Issue 3: Missing Debug Logging

### Symptom
Could not determine if `PermissionRequest` hook was even firing.

### Fix
Added debug logging to permission hook:
```bash
echo "$(date '+%Y-%m-%d %H:%M:%S') PermissionRequest fired" >> /tmp/waiting-activity-debug.log
echo "$(date '+%Y-%m-%d %H:%M:%S') [permission] SESSION_ID=$SESSION_ID" >> /tmp/waiting-activity-debug.log
echo "$(date '+%Y-%m-%d %H:%M:%S') [permission] Starting nag with grace period $GRACE_PERIOD sec" >> /tmp/waiting-activity-debug.log
echo "$(date '+%Y-%m-%d %H:%M:%S') [permission] Nag started with PID $!" >> /tmp/waiting-activity-debug.log
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/waiting/cli.py` | Removed activity check from permission hook, fixed UserPromptSubmit, added debug logging, bumped version to 2.1.0 |
| `~/.claude/hooks/waiting-notify-permission.sh` | Regenerated |
| `~/.claude/hooks/waiting-activity-submit.sh` | Regenerated |

---

## Correct Behavior After Fix

### Timeline
1. User submits message → `UserPromptSubmit` fires (updates stop-activity only)
2. Claude needs permission → `PermissionRequest` fires
3. **Nag starts** with 10-second grace period
4. After 10 seconds without response → **bell plays**
5. User responds → `PreToolUse` fires → nag stops immediately
6. If another permission needed → new nag starts (step 2)

### Key Insight
The activity check at hook startup was wrong. The correct place for activity checking is in the nag script's `should_exit()` function, which checks if activity happened AFTER the nag started (`last_activity >= start_time`).

---

## Testing

After fix, debug log shows:
```
PermissionRequest fired
[permission] SESSION_ID=abc123...
[permission] Starting nag with grace period 10 sec
[permission] Nag started with PID 12345
```

And after 10 seconds, bell plays. When user responds:
```
PreToolUse fired
[tooluse] Created stop signal
[nag] cleanup called
```

---

## Version History

- **2.0.0** - Stop-signal mechanism, rapid-fire prevention (had bug)
- **2.1.0** - Fixed permission hook blocking all nags
