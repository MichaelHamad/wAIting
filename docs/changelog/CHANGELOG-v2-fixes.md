# v2 Critical Bug Fixes

## Problem Summary

Bells were playing continuously even when:
1. User had just responded to a permission dialog
2. Claude was actively working (not waiting for input)
3. Claude was completely closed

The symptom was double bells playing in a pattern, continuing indefinitely.

---

## Root Cause

**Auto-approved tools were not updating the activity file.**

When Claude worked for 2+ minutes using auto-approved tools (Read, Grep, Bash with allowed commands), the activity timestamp went stale. When a new permission dialog appeared, the nag checked:

```
last_activity (2 minutes ago) < START_TIMESTAMP (now) → "User is AFK" → play bell
```

But the user was right there watching Claude work.

---

## Fixes Applied

### 1. Auto-Approved Tools Now Update Activity (Critical Fix)

**File:** `src/waiting/cli.py` - `create_activity_scripts()` - PreToolUse hook

**Before:**
```bash
# Only update activity if there's a pending permission (user approved, not auto-approved)
if [ -f "$PENDING_FILE" ]; then
    ACTIVITY_TIME=$((NOW + 1))
    echo "$ACTIVITY_TIME" > "$ACTIVITY_FILE"
    rm -f "$PENDING_FILE"
    echo "  User approved permission, updated activity" >> "$DEBUG_LOG"
else
    echo "  Auto-approved tool, no activity update" >> "$DEBUG_LOG"
fi
```

**After:**
```bash
ACTIVITY_TIME=$((NOW + 1))

# ALWAYS update activity when any tool runs - Claude is working, user is present
echo "$ACTIVITY_TIME" > "$ACTIVITY_FILE"

# Clean up pending file if it exists (user manually approved)
if [ -f "$PENDING_FILE" ]; then
    rm -f "$PENDING_FILE"
    echo "  User approved permission, updated activity" >> "$DEBUG_LOG"
else
    echo "  Auto-approved tool, updated activity" >> "$DEBUG_LOG"
fi
```

---

### 2. Fixed Timestamp Equality Bug

**File:** `src/waiting/cli.py` - `create_permission_notify_script()` - nag wrapper script

**Before:**
```bash
if [ "$last_activity" -gt "$START_TIMESTAMP" ]; then
```

**After:**
```bash
if [ "$last_activity" -ge "$START_TIMESTAMP" ]; then
```

**Reason:** When user approves permission A and Claude immediately shows permission B (same second), the timestamps were equal. Using `>` caused the check to fail, triggering a false bell. Changed to `>=` to handle same-second cascading dialogs.

---

### 3. Added Heartbeat Mechanism

**New file:** `/tmp/waiting-heartbeat-$SESSION_ID`

**Changes to all hooks:**

```bash
HEARTBEAT_FILE="/tmp/waiting-heartbeat-$SESSION_ID"
HEARTBEAT_TIMEOUT=120  # 2 minutes

# Update heartbeat (proves Claude is alive)
echo "$(date +%s)" > "$HEARTBEAT_FILE"
```

**Changes to nag loops:**

```bash
# Check if Claude is still alive via heartbeat
if [ -f "$HEARTBEAT_FILE" ]; then
    last_heartbeat=$(cat "$HEARTBEAT_FILE" 2>/dev/null || echo 0)
    heartbeat_age=$((NOW - last_heartbeat))
    if [ "$heartbeat_age" -gt "$HEARTBEAT_TIMEOUT" ]; then
        echo "  Heartbeat stale, Claude appears dead, exiting" >> "$DEBUG_LOG"
        rm -f "$PID_FILE" "$0"
        exit 0
    fi
fi
```

**Reason:** Prevents orphaned nag processes from ringing forever after Claude closes. If no hook fires for 2 minutes, the nag assumes Claude died and exits.

---

### 4. Reduced Max Lifetime

**Before:**
```bash
MAX_LIFETIME=7200  # 2 hours
```

**After:**
```bash
MAX_LIFETIME=600  # 10 minutes
```

**Reason:** Hard safety cap. Even with heartbeat checking, no nag should run longer than 10 minutes.

---

### 5. Improved Cleanup in `_kill_nag_process()`

**Added:**
```python
# Kill any orphaned waiting-notify or waiting-nag processes
for pattern in ["waiting-notify", "waiting-nag"]:
    subprocess.run(["pkill", "-f", pattern], capture_output=True)

# Clean up pending files
for pending_file in tmp_dir.glob("waiting-pending-*"):
    pending_file.unlink(missing_ok=True)

# Clean up nag wrapper scripts
for wrapper_script in tmp_dir.glob("waiting-nag-*.sh"):
    wrapper_script.unlink(missing_ok=True)
```

**Reason:** Ensures all orphaned processes and stale files are cleaned up when running `waiting kill` or `waiting disable`.

---

### 6. Removed Lookback Window Complexity

**Removed from `DEFAULT_CONFIG`:**
```python
"lookback_window": 30,  # REMOVED
```

**Removed from `create_permission_notify_script()`:**
- `lookback_window` parameter
- "Monitoring mode" logic
- `SKIP_FIRST_BELL` variable and related code

**Replaced with:** Simple wait-and-see logic that checks if activity occurred since the dialog opened using `>=` comparison.

---

## Files Changed

- `src/waiting/cli.py`
  - `DEFAULT_CONFIG` - removed `lookback_window`
  - `create_stop_notify_script()` - added heartbeat, reduced max lifetime
  - `create_permission_notify_script()` - added heartbeat, fixed comparison, simplified logic
  - `create_idle_notify_script()` - added heartbeat, reduced max lifetime
  - `create_activity_scripts()` - PreToolUse now always updates activity
  - `_kill_nag_process()` - improved cleanup
  - `cli()` - removed lookback_window references
  - `status()` - removed lookback_window display

---

## Testing

After applying fixes:

1. **Auto-approved tools keep activity fresh** - New permission dialogs see recent activity
2. **Same-second cascading dialogs** - No false bells due to `>=` comparison
3. **Claude closes** - Nag detects stale heartbeat and exits within 2 minutes
4. **Max runtime** - Nag exits after 10 minutes regardless
5. **Manual kill** - `waiting kill` cleans up all processes and files
