# Stop-Signal Fix for Bell Notification System

**Date:** January 5, 2026
**Status:** Implemented and Tested
**Issue:** Nag processes surviving after user responds to permission dialogs

---

## Problem Summary

Bell sounds kept playing after the user responded to permission dialogs. The root cause was that `pkill -f "waiting-nag-"` was unreliable:

1. `pkill -f` can match its own process and kill itself before cleanup completes
2. Process signaling has race conditions with background scripts
3. PID-based killing alone wasn't always reaching the nag process in time

Debug logs showed hooks were firing correctly with the right SESSION_ID, but nag processes survived:
```
2026-01-04 23:37:30 UserPromptSubmit fired
2026-01-04 23:37:30 SESSION_ID=08d616c6-859c-438c-ab0c-a9b3d05d2fd7
# But nag still running with same SESSION_ID
```

---

## Solution: Stop-Signal File Mechanism

Implemented a **file-based signaling system** as the PRIMARY termination method:

### How It Works

1. **Activity hooks create a stop signal file** (`/tmp/waiting-stop-$SESSION_ID`)
2. **Nag scripts poll for this file every 200ms** in their main loop
3. **When stop signal exists, nag self-terminates** via its `cleanup()` function
4. **PID-based killing retained as backup** (belt and suspenders)

### Why This Works

- **File existence is atomic** - no partial states or race conditions
- **Nag controls its own termination** - doesn't depend on external signals being delivered
- **200ms polling** - fast response time (max 200ms delay vs 1s before)
- **Multiple fallbacks** - stop signal + PID kill + activity file timestamp + trap handlers

---

## Changes Made

### 1. Activity Hooks (`create_activity_submit_script()`, `create_activity_tooluse_script()`)

**Added stop signal creation as PRIMARY method:**
```bash
# PRIMARY KILL METHOD: Stop signal file
STOP_SIGNAL="/tmp/waiting-stop-$SESSION_ID"
touch "$STOP_SIGNAL"

# Also create stop signals for ALL sessions (handles orphans)
for pidfile in /tmp/waiting-nag-*.pid; do
    if [ -f "$pidfile" ]; then
        orphan_session=$(basename "$pidfile" | sed 's/waiting-nag-//' | sed 's/.pid//')
        touch "/tmp/waiting-stop-$orphan_session"
    fi
done
```

### 2. Nag Scripts (permission, stop, idle)

**Added `should_exit()` function with stop signal as PRIMARY check:**
```bash
should_exit() {
    # PRIMARY: Check stop signal file (most reliable)
    [ -f "$STOP_SIGNAL" ] && return 0
    # Secondary checks
    [ ! -f "$PID_FILE" ] && return 0
    [ ! -f "$PENDING_FILE" ] && return 0
    if [ -f "$ACTIVITY_FILE" ]; then
        last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
        [ "$last_activity" -ge "$start_time" ] && return 0
    fi
    return 1
}
```

**Changed polling from 1s to 200ms:**
```bash
# Grace period - check frequently (every 0.2 seconds)
grace_checks=$((GRACE_PERIOD * 5))
for ((i=0; i<grace_checks; i++)); do
    sleep 0.2
    should_exit && cleanup
done

# Main nag loop - sleep in 0.2 second increments
interval_checks=$((INTERVAL * 5))
for ((i=0; i<interval_checks; i++)); do
    sleep 0.2
    should_exit && cleanup
done
```

**Added trap for EXIT (not just SIGTERM/SIGINT):**
```bash
trap cleanup SIGTERM SIGINT EXIT
```

**Cleanup removes stop signal file:**
```bash
cleanup() {
    # ... kill audio ...
    rm -f "$PID_FILE"
    rm -f "$STOP_SIGNAL"
    exit 0
}
```

### 3. Permission/Stop/Idle Hook Scripts

**Removed pkill, now use PID-based killing:**
```bash
# OLD (unreliable):
pkill -f "$NAG_MARKER" 2>/dev/null

# NEW (reliable):
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$OLD_PID" ]; then
        kill "$OLD_PID" 2>/dev/null
        kill -9 "$OLD_PID" 2>/dev/null
    fi
    rm -f "$PID_FILE"
fi
```

**Clear old stop signal before starting new nag:**
```bash
# CRITICAL: Remove old stop signal so new nag doesn't exit immediately
rm -f "$STOP_SIGNAL"
```

### 4. Python CLI (`kill_all_nags()` function)

**New centralized function for reliable nag killing:**
```python
def kill_all_nags() -> None:
    """Kill all nag processes reliably using PID files and stop signals."""
    import glob
    import subprocess

    # Create stop signals for all sessions (primary method)
    for pidfile in glob.glob("/tmp/waiting-nag-*.pid"):
        session_id = pidfile.replace("/tmp/waiting-nag-", "").replace(".pid", "")
        stop_signal = f"/tmp/waiting-stop-{session_id}"
        Path(stop_signal).touch()

    # Kill by PID files (backup method)
    for pidfile in glob.glob("/tmp/waiting-nag-*.pid"):
        try:
            with open(pidfile) as f:
                pid = f.read().strip()
                if pid:
                    subprocess.run(["kill", pid], stderr=subprocess.DEVNULL)
                    subprocess.run(["kill", "-9", pid], stderr=subprocess.DEVNULL)
        except (IOError, OSError):
            pass

    # Cleanup temp files
    for pattern in ["/tmp/waiting-nag-*.pid", "/tmp/waiting-pending-*",
                    "/tmp/waiting-audio-*.pid", "/tmp/waiting-stop-*"]:
        for f in glob.glob(pattern):
            try:
                os.remove(f)
            except OSError:
                pass
```

**Updated all callers to use `kill_all_nags()`:**
- `setup_hooks()`
- `remove_hooks()`
- `kill` CLI command

---

## Test Results

### Unit Test: Stop Signal Detection
```
=== Creating stop signal ===
-rw-r--r-- 1 michael michael 0 Jan  4 23:59 /tmp/waiting-stop-test-session-123

=== Nag process after stop signal? ===
SUCCESS: Nag exited after stop signal
```

### Integration Test: Permission → Activity Flow
```
=== STEP 2: Start permission hook (spawns nag) ===
NAG PID: 484904
Nag running: 1

=== STEP 3: Trigger activity hook (should kill nag) ===

=== STEP 4: Verify nag is dead ===
SUCCESS: Nag was killed by activity hook
```

### Debug Log Showing Full Flow
```
2026-01-05 00:01:22 UserPromptSubmit fired
2026-01-05 00:01:22 SESSION_ID=integration-test-456
2026-01-05 00:01:22 Created stop signal: /tmp/waiting-stop-integration-test-456
2026-01-05 00:01:22 Killing nag PID 484904
2026-01-05 00:01:22 [nag] cleanup called
2026-01-05 00:01:23 Cleanup done
```

---

## Files Modified

| File | Changes |
|------|---------|
| `src/waiting/cli.py` | Added `kill_all_nags()`, updated all nag scripts with stop-signal mechanism, 200ms polling, removed pkill |
| `~/.claude/hooks/waiting-notify-permission.sh` | Regenerated with fix |
| `~/.claude/hooks/waiting-notify-stop.sh` | Regenerated with fix |
| `~/.claude/hooks/waiting-notify-idle.sh` | Regenerated with fix |
| `~/.claude/hooks/waiting-activity-submit.sh` | Regenerated with fix |
| `~/.claude/hooks/waiting-activity-tooluse.sh` | Regenerated with fix |

---

## Lessons Learned

1. **File-based IPC is more reliable than process signals** for loosely-coupled shell scripts
2. **Polling at 200ms intervals** provides good responsiveness without excessive CPU usage
3. **Multiple fallback mechanisms** (stop signal + PID kill + activity timestamp) ensure reliability
4. **`pkill -f` is dangerous** in scripts that match their own command line
5. **Self-termination is more reliable than external killing** - the process knows when it's safe to exit

---

## Additional Fix: Rapid-Fire Nag Prevention

**Issue Discovered:** After initial fix, nags were still appearing because each `PermissionRequest` hook was spawning a new nag faster than the activity hooks could kill them.

**Root Cause:** The permission hook was unconditionally starting nags without checking if there was recent user activity.

**Fix:** Added activity check at the START of the permission hook:

```bash
# CRITICAL: Check if there was recent activity (within last 3 seconds)
# If so, don't start a nag - user is actively working
if [ -f "$ACTIVITY_FILE" ]; then
    last_activity=$(cat "$ACTIVITY_FILE" 2>/dev/null || echo 0)
    elapsed=$((now - last_activity))
    if [ "$elapsed" -lt 3 ]; then
        # Recent activity detected - skip nag, just mark pending
        echo "$now" > "$PENDING_FILE"
        exit 0
    fi
fi

# Also check stop signal activity file (covers both hooks)
STOP_ACTIVITY_FILE="/tmp/waiting-activity-stop-$SESSION_ID"
if [ -f "$STOP_ACTIVITY_FILE" ]; then
    last_activity=$(cat "$STOP_ACTIVITY_FILE" 2>/dev/null || echo 0)
    elapsed=$((now - last_activity))
    if [ "$elapsed" -lt 3 ]; then
        echo "$now" > "$PENDING_FILE"
        exit 0
    fi
fi
```

**Effect:** When Claude is actively processing tools (PermissionRequest → PreToolUse → PermissionRequest → ...), no nags are started because each request sees recent activity from the previous tool approval.

---

## User Safeguards Added

To prevent users from experiencing these issues, we added several safeguards:

### 1. Hook Version Tracking
- Each generated hook now includes `# WAITING_HOOK_VERSION=2.0.0`
- Allows detection of outdated hooks

### 2. Enhanced Status Command (`waiting status`)
```
Status: enabled
Hook version: 2.0.0 (current)
Latest version: 2.0.0

Running nags: 0
Orphaned files: 0

Configuration:
  Audio: default
  Interval: 30s
  ...
```

### 3. Doctor Command (`waiting doctor`)
Diagnoses common issues:
- Outdated hooks
- Stray nag processes
- Orphaned temp files
- Missing hook scripts
- Claude settings misconfiguration

Auto-fix with `waiting doctor --fix`

### 4. Auto-Warning for Outdated Hooks
When running any subcommand with outdated hooks:
```
Warning: Hooks outdated (1.0.0 -> 2.0.0)
Run 'waiting' or 'waiting doctor --fix' to update.
```

---

## Next Steps

1. Monitor in production for any edge cases
2. Consider adding metrics/telemetry for nag lifecycle
3. Document the stop-signal protocol for future maintainers
