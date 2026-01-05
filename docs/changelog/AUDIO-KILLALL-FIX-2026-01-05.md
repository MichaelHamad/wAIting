# Audio Kill-All Fix - v2.3.0

**Date:** January 5, 2026
**Version:** 2.3.0
**Status:** Fixed
**Priority:** CRITICAL

---

## Summary

Fixed a critical bug where bell sounds **continue playing after user approves permission dialogs**. The issue was in the PreToolUse hook (called when user responds), which was not aggressively killing all audio processes before killing the nag script.

---

## Issue: Bell Continues After User Approves

### Symptom
- User triggers a permission dialog
- Bell plays (after grace period)
- User approves the permission
- **Bell KEEPS playing** even though the dialog is gone
- User's only option: `waiting kill` to stop it manually

### Root Cause
The PreToolUse hook (v2.2.0) had TWO problems:

**Problem 1: No sleep before audio kill**
```bash
# v2.2.0 (BROKEN)
touch "$STOP_SIGNAL"
# Immediately kill audio
for audiopid in /tmp/waiting-audio-*.pid; do
```

This creates a race condition:
1. PreToolUse creates stop signal
2. PreToolUse immediately kills audio by reading PID file
3. But the nag script may not have called cleanup() yet
4. Even if cleanup() was called, it only kills the LAST audio PID saved
5. **Multiple audio processes could be playing** (new one started every 30s)

**Problem 2: Only killing tracked audio, not all audio**
```bash
# v2.2.0 (PARTIAL)
for audiopid in /tmp/waiting-audio-*.pid; do
    kill "$(cat "$audiopid")" 2>/dev/null
done
```

Issues:
- Only kills audio with PID files
- Orphaned audio processes without PID files survive
- No pgrep to catch audio processes by command name

---

## Solution: v2.3.0 - Aggressive Audio Kill Strategy

### Changes

**1. Sleep 0.3s after stop signal (let nag exit cleanly)**
```bash
# v2.3.0 (FIXED)
touch "$STOP_SIGNAL"
echo "Stop signal created, sleeping 0.3s for nag to exit cleanly"
sleep 0.3  # Give nag time to see signal and exit cleanly via should_exit()
```

This allows the nag script's `should_exit()` function to detect the stop signal and call its own cleanup() before we force kill it.

**2. Aggressive audio killing by BOTH PID file AND process search**
```bash
# Kill audio by tracked PID (primary method)
for audiopid in /tmp/waiting-audio-*.pid; do
    if [ -f "$audiopid" ]; then
        kill "$(cat "$audiopid")" 2>/dev/null
        kill -9 "$(cat "$audiopid")" 2>/dev/null
        rm -f "$audiopid"
    fi
done

# Kill ALL audio processes by command name (belt and suspenders)
pgrep -f "paplay.*(waiting-bell|Cool_bell)" | xargs -r kill -9 2>/dev/null
pgrep -f "pw-play.*(waiting-bell|Cool_bell)" | xargs -r kill -9 2>/dev/null
pgrep -f "aplay.*(waiting-bell|Cool_bell)" | xargs -r kill -9 2>/dev/null
pgrep -f "afplay.*(waiting-bell|Cool_bell)" | xargs -r kill -9 2>/dev/null
```

This ensures:
- All tracked audio PIDs are killed
- All audio processes playing the bell sound are killed by name
- Orphaned processes are caught

**3. Full 4-step cleanup sequence**
```bash
# STEP 1: Create stop signal
touch "$STOP_SIGNAL"
sleep 0.3

# STEP 2: Kill audio EXPLICITLY
for audiopid in /tmp/waiting-audio-*.pid; do
    kill ... kill -9 ...
done
pgrep -f "paplay..." | xargs -r kill -9 ...

# STEP 3: Kill nag processes
kill "$NAG_PID"
kill -9 "$NAG_PID"

# CLEANUP: Remove all temp files
rm -f /tmp/waiting-nag-*.pid
rm -f /tmp/waiting-audio-*.pid
rm -f /tmp/waiting-stop-*
```

---

## Why This Works

### Before (v2.2.0)
1. Permission dialog appears → PermissionRequest fires → starts nag
2. Grace period passes → nag plays audio #1 (PID=9999)
3. 30 seconds later → nag plays audio #2 (PID=8888, overwrites file)
4. User approves → PreToolUse fires
5. PreToolUse kills PID 8888 (only one in file)
6. **But PID 9999 is still playing!**

### After (v2.3.0)
1. Permission dialog appears → PermissionRequest fires → starts nag
2. Grace period passes → nag plays audio #1 (PID=9999)
3. 30 seconds later → nag plays audio #2 (PID=8888)
4. User approves → PreToolUse fires
5. PreToolUse:
   - Creates stop signal
   - Sleep 0.3s (gives nag time to exit via signal)
   - Kill PID 8888 (by PID file)
   - Kill ALL paplay/aplay processes (by name)
   - Kills nag PID (to be safe)
6. **All audio stops, including PID 9999**

---

## Files Changed

| File | Change |
|------|--------|
| `src/waiting/cli.py` | Rewrote PreToolUse hook generation with aggressive audio cleanup, bumped version to 2.3.0 |
| `~/.claude/hooks/waiting-activity-tooluse.sh` | Regenerated with v2.3.0 logic |

---

## Correct Behavior After Fix

### Timeline
1. User submits message → UserPromptSubmit fires
2. Claude needs permission → PermissionRequest fires
3. **Nag starts** with 10-second grace period
4. After 10 seconds → **bell plays**
5. User responds (approves) → PreToolUse fires
6. **Bell stops immediately** (within 300ms max)
7. All audio processes killed (both by PID and by name)
8. Nag terminates cleanly (via stop signal)
9. All temp files cleaned

---

## Testing Notes

### What Changed
- PreToolUse hook now has 0.3s sleep after creating stop signal
- PreToolUse hook now kills audio by BOTH PID file AND pgrep search
- PreToolUse hook now explicitly removes all stop signals in cleanup

### What Should Work Now
- Permission dialog appears → bell plays (after grace period)
- User approves permission → bell stops **immediately**
- No stray audio processes continuing
- No manual `waiting kill` needed
- Multiple permissions in sequence work correctly

### Debug Output (tail -20 /tmp/waiting-activity-debug.log)
```
PermissionRequest fired
[permission] SESSION_ID=abc123...
[permission] Starting nag with grace period 10 sec
[permission] Nag started with PID 12345
...
(10+ seconds pass)
...
PreToolUse fired
SESSION_ID=abc123...
[tooluse] Created stop signal
[tooluse] Stop signal created, sleeping 0.3s for nag to exit cleanly
[tooluse] Killing nag PID 12345
[nag] cleanup called
[tooluse] Cleanup done
```

---

## Version History

- **2.0.0** - Stop-signal mechanism, rapid-fire prevention
- **2.1.0** - Fixed permission hook blocking all nags (issue from activity check)
- **2.2.0** - Added audio kill before nag kill in PermissionRequest hook
- **2.3.0** - **[THIS FIX]** Extended aggressive audio cleanup to PreToolUse hook

---

## Migration Notes

**For Users:**
- Run `waiting` or restart Claude Code to update hooks
- No configuration changes needed
- No changes to usage

**What's Different:**
- Audio kills now more reliable (happens within 300ms of approval)
- Multiple kill methods ensure all audio stops
- Debug log shows aggressive audio killing attempt

---

## Remaining Considerations

If users still experience audio issues:
1. Check system audio levels: `alsamixer` or `pavucontrol`
2. Verify audio device: `pactl list cards`
3. Check for stray audio processes: `pgrep -f paplay`
4. Run diagnostic: `waiting doctor`
5. Nuclear option: `waiting kill` then `waiting`
