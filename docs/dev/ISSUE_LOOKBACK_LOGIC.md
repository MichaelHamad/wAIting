# Issue: Permission Hook Uses Lookback Instead of Wait-and-See

## Problem

When a permission dialog opens within the lookback window of a previous user action, the bell is skipped even if the user went AFK immediately after their last action.

**Scenario:**
1. T=0: User approves permission dialog → activity updated
2. T=1: User goes AFK
3. T=8: New permission dialog opens
4. Current behavior: Checks "was user active in last 30s?" → YES (T=0 is within window)
5. Result: First bell skipped, user waits 40+ seconds for notification

## Root Cause

The permission hook uses **lookback logic** (was there activity *before* the dialog?) instead of **wait-and-see logic** (was there activity *since* the dialog?).

Current code (cli.py lines 381-396):
```bash
lookback_threshold=$((START_TIMESTAMP - LOOKBACK_WINDOW))
if [ "$last_activity" -gt "$lookback_threshold" ]; then
    SKIP_FIRST_BELL=true  # Activity before dialog = skip
fi
```

## Solution

Change to "wait and see" logic, matching the Stop hook pattern:

1. Wait `grace_period` seconds (give user time to respond)
2. After waiting, check if activity happened **since dialog opened** (`activity > START_TIMESTAMP`)
3. If activity since dialog → user responded, skip bell
4. If no activity since dialog → user AFK, play bell

## Changes Required

### File: `src/waiting/cli.py`

**1. Remove `lookback_window` from DEFAULT_CONFIG** (line 24)
```python
# Remove this line:
"lookback_window": 30,
```

**2. Update `create_permission_notify_script` function signature** (lines 246-265)
- Remove `lookback_window` parameter from signature
- Update docstring to reflect new behavior
- Remove `LOOKBACK_WINDOW` variable from script template (line 276)

**3. Replace the activity check logic in nag script** (lines 380-418)

Remove the SKIP_FIRST_BELL / lookback logic and monitoring mode. Replace with simple "wait and see":

```bash
# After delay, check if user was active SINCE the dialog opened
if [ -f "$ACTIVITY_FILE" ]; then
    last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
    if [ "$last_activity" -gt "$START_TIMESTAMP" ]; then
        echo "  User responded during grace period, exiting" >> "$DEBUG_LOG"
        rm -f "$PID_FILE" "$0"
        exit 0
    fi
fi
# No activity since dialog opened - play bell
echo "  No activity since dialog, playing bell" >> "$DEBUG_LOG"
play_sound
```

**4. Remove monitoring mode block entirely** (lines 405-418)
- The delayed recheck makes this unnecessary

**5. Update `setup_hooks()` call** (line 951)
```python
# Before:
permission_script = create_permission_notify_script(audio_path, interval, max_nags, grace_permission, lookback_window)

# After:
permission_script = create_permission_notify_script(audio_path, interval, max_nags, grace_permission)
```

**6. Update `status` command output** (lines 945 and 1126-1128)
- Remove the "Lookback window" display lines

## Behavior After Fix

**AFK scenario (the bug this fixes):**
1. T=0: User approves dialog → activity=0
2. T=1: User goes AFK
3. T=8: New dialog opens, START_TIMESTAMP=8
4. T=18: After 10s grace period, check: activity(0) > START_TIMESTAMP(8)? NO
5. Result: Bell plays at T=18 (10 seconds after dialog, user AFK for 17s)

**Rapid dialogs scenario (user present):**
1. T=0: User approves dialog → activity=0
2. T=8: New dialog opens, START_TIMESTAMP=8
3. T=10: User approves → activity=10
4. T=18: After grace period, check: activity(10) > START_TIMESTAMP(8)? YES
5. Result: No bell (user already responded)

## Summary

- Simpler logic (matches Stop hook pattern)
- Removes confusing `lookback_window` vs `grace_period` distinction
- Faster notification when user is actually AFK
- Still respects grace period for user to respond naturally
