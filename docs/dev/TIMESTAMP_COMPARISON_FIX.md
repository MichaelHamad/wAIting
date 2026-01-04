# Timestamp Comparison Fix (>= to >)

**Date:** January 3, 2026
**Status:** Implemented, awaiting test after restart

## The Bug

Bell never played when user was truly AFK at a permission dialog.

### Root Cause

The activity check used `>=` (greater than or equal):

```bash
if [ "$last_activity" -ge "$START_TIMESTAMP" ]; then
    # No bell - user was "active"
fi
```

**Problem:** When auto-approved tools fire in the **same second** as PermissionRequest:

```
T=100 - Auto-approved tool runs → PreToolUse updates activity to 100
T=100 - PermissionRequest fires → START_TIMESTAMP = 100 (same second!)
T=110 - Nag checks: 100 >= 100 → TRUE → no bell ❌
```

Because bash's `date +%s` only has 1-second precision, any activity in the same second as PermissionRequest would prevent the bell entirely.

## The Fix

Changed comparison from `>=` to `>` (strict greater than):

```bash
if [ "$last_activity" -gt "$START_TIMESTAMP" ]; then
    # No bell - user was active AFTER permission appeared
fi
```

Now:
```
T=100 - Auto-approved tool runs → activity = 100
T=100 - PermissionRequest fires → START_TIMESTAMP = 100
T=110 - Nag checks: 100 > 100 → FALSE → bell plays! ✓
```

Activity must be in a **later second** to prevent the bell.

## Files Changed

**src/waiting/cli.py** - Two locations in the permission nag script:

### 1. Initial Delay Check (line 369)

**Before:**
```bash
if [ "\\$last_activity" -ge "\\$START_TIMESTAMP" ]; then
    echo "  User was active during delay (\\$last_activity >= \\$START_TIMESTAMP), no bell"
```

**After:**
```bash
if [ "\\$last_activity" -gt "\\$START_TIMESTAMP" ]; then
    echo "  User was active during delay (\\$last_activity > \\$START_TIMESTAMP), no bell"
```

### 2. Nag Loop Check (line 406)

**Before:**
```bash
if [ "\\$last_activity" -ge "\\$START_TIMESTAMP" ]; then
    echo "  User was active, stopping nag"
```

**After:**
```bash
if [ "\\$last_activity" -gt "\\$START_TIMESTAMP" ]; then
    echo "  User was active, stopping nag"
```

## Edge Case Analysis

### Concern: User Approves in Same Second

**Scenario:** User sees permission dialog and approves instantly (<1 second).

```
T=100 - PermissionRequest fires → START_TIMESTAMP = 100
T=100 - User clicks approve → PreToolUse updates activity = 100 (same second!)
T=110 - Nag checks: 100 > 100 → FALSE → bell plays
```

**Impact:** Bell plays once even though user approved.

**Likelihood:** Extremely low
- User needs to see, read, and approve in <1 second
- Humanly impossible for most permission dialogs
- Normal approval takes 2-5+ seconds

**Mitigation:** Even in worst case, user can dismiss and approve again. Nag stops immediately after.

### Normal Case: User Approves in 2+ Seconds

```
T=100 - PermissionRequest fires → START_TIMESTAMP = 100
T=102 - User clicks approve → PreToolUse updates activity = 102
T=110 - Nag checks: 102 > 100 → TRUE → no bell ✓
```

Works perfectly! This is the expected case 99%+ of the time.

### AFK Case: User Doesn't Approve

```
T=100 - PermissionRequest fires → START_TIMESTAMP = 100
T=100 - Auto-approved tools update activity = 100 (same second)
T=110 - Nag checks: 100 > 100 → FALSE → bell plays ✓
T=115 - Still no approval → bell plays again ✓
```

Bell correctly plays because activity was not in a **later** second.

## Tradeoff Summary

| Comparison | Auto-approved tools in same second | User approves in same second |
|------------|-----------------------------------|------------------------------|
| `>=` (old) | ❌ Prevents bell (BUG) | ✓ No bell (correct) |
| `>` (new)  | ✓ Bell plays (FIXED!) | ⚠️ Bell plays (rare edge case) |

**Conclusion:** The `>` fix solves the critical bug (bell never plays) at the cost of a rare edge case (bell plays once if user approves <1s). This is an acceptable tradeoff.

## Testing Plan

After restart:

1. **Test 1: User approves normally (2-5 seconds)**
   - Trigger permission dialog
   - Approve after 3 seconds
   - Expected: No bell (activity > START_TIMESTAMP)

2. **Test 2: User truly AFK (>10 seconds)**
   - Trigger permission dialog
   - Don't approve for 15+ seconds
   - Expected: Bell plays at 10s, repeats every 15s

3. **Test 3: Auto-approved tools while waiting**
   - Trigger permission dialog
   - Auto-approved tools run in background
   - Don't approve for >10s
   - Expected: Bell plays (auto-tools don't prevent it)

## Expected Debug Output

### When User Approves Quickly

```
Sat Jan  3 16:40:00: PermissionRequest fired
  Session: xxxxx, delay: 10s
  Background PID: xxxxx
  Starting delayed bell (waiting 10s)
Sat Jan  3 16:40:02: PreToolUse fired
  Session: xxxxx
  Updated activity: 1767476402
  Killed nag: waiting-nag-xxxxx

(After 10s, nag already killed - no activity check logged)
```

### When User is AFK

```
Sat Jan  3 16:40:00: PermissionRequest fired
  Session: xxxxx, delay: 10s
  Background PID: xxxxx
  Starting delayed bell (waiting 10s)
  Activity check: START_TIMESTAMP=1767476400
  Activity check: last_activity=1767476400 (from /tmp/waiting-activity-permission-xxxxx)
  User was NOT active (1767476400 <= 1767476400)
  Delay complete, playing bell
```

Note: `1767476400 <= 1767476400` is TRUE, so bell plays.

## Rollback Plan

If the fix causes issues, revert by changing `>` back to `>=`:

```bash
cd /home/michael/projects/waiting_new
git diff src/waiting/cli.py  # See the changes
git checkout src/waiting/cli.py  # Revert
pip install -e . && waiting  # Regenerate hooks
# Restart Claude Code
```

## Related Documents

- `docs/dev/NAG_KILL_APPROACHES.md` - Overview of simplified approach
- `DEBUGGING.md` - Full debugging session log
- `src/waiting/cli.py` - Implementation (lines 369, 406)
