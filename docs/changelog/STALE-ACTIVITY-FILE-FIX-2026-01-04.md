# Stale Activity File Fix - January 4, 2026 (23:00)

## Problem

Bell plays correctly on the first permission menu, but does NOT play on the second consecutive permission menu.

## Root Cause

Race condition between activity hooks and permission hooks:

1. First permission menu appears → nag starts with `start_time = now + 2`
2. User responds → activity hook writes `ACTIVITY_TIME = now + 1` to activity file
3. Nag checks `last_activity >= start_time` → exits correctly
4. Second permission menu appears IMMEDIATELY
5. New nag starts with `start_time = now + 2`
6. **Activity file still contains the old timestamp from step 2**
7. New nag checks `last_activity >= start_time` → sees stale timestamp → exits immediately!

The activity file wasn't being cleared between permission events, so consecutive permissions would see "recent activity" and skip the bell.

## Fix

Permission hook now resets the activity file before starting a new nag:

```bash
# Kill any existing nag for this session
pkill -f "$NAG_MARKER" 2>/dev/null
rm -f "$PID_FILE"
sleep 0.1

# Reset activity file so new nag doesn't see stale timestamp from previous response
rm -f "$ACTIVITY_FILE"

# Mark that permission dialog is open
echo "$now" > "$PENDING_FILE"
```

## Files Changed

| File | Line | Change |
|------|------|--------|
| `src/waiting/cli.py` | ~259-260 | Added `rm -f "$ACTIVITY_FILE"` in permission hook |

## Why This Works

Each permission event now starts with a clean slate:
- Old activity timestamp is removed
- New nag has no "recent activity" to check against
- Bell plays correctly on every permission menu

## Requires

**Restart Claude Code** for the updated hooks to take effect.
