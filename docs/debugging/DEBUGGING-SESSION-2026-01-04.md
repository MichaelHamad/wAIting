# Debugging Session - January 4, 2026

## Problem Statement

The "waiting" CLI tool was not reliably playing notification bells when Claude Code permission dialogs appeared, and sometimes played bells at incorrect times.

## Initial State

- Rewrote `cli.py` from scratch based on `ONE_SHOT_PROMPT.md`
- Implemented 3 hooks: Stop, Permission, Idle
- Only Permission hook enabled for testing

## Issues Discovered & Fixes Applied

### Issue 1: Claude Code Not Loading New Hooks

**Symptom:** After code changes, hooks weren't working.

**Cause:** Claude Code only reads `~/.claude/settings.json` at startup.

**Fix:** Restart Claude Code after making changes to hooks.

---

### Issue 2: Stale Processes and Temp Files

**Symptom:** Random bells, inconsistent behavior.

**Cause:** Old nag processes and temp files from previous implementation versions.

**Fix:** Clean up with:
```bash
pkill -f "waiting-nag"
rm -f /tmp/waiting-*
```

---

### Issue 3: Bell Not Playing When Permission Dialog Open

**Symptom:** User left permission dialog open for 10+ seconds, no bell.

**Cause:** Race condition. `PreToolUse` hook fires in same second as `PermissionRequest`, setting activity timestamp to `now+1`. Nag script starts with `start_time = now`, sees activity >= start_time, and exits immediately.

**Timeline:**
```
T+0: PreToolUse fires → activity = T+1
T+0: PermissionRequest fires → nag starts, start_time = T+0
T+1: Nag checks: activity(T+1) >= start_time(T+0) → TRUE → exits
```

**Fix:** Changed nag script to use `start_time = now + 2`:
```bash
# In waiting-notify-permission.sh, inside the NAGEOF heredoc:
start_time=$(($(date +%s) + 2))
```

This ensures the nag ignores activity that happened before/during its startup.

---

### Issue 4: Extra Bell After User Approves

**Symptom:** User approves permission, Claude starts working, bell plays anyway.

**Cause:** The sound is played by `powershell.exe` as a background child process. When `pkill` kills the nag script, the child powershell process continues playing.

**Attempted Fixes (reverted):**
- Added `pkill -f "bell.wav"` - didn't match Windows path
- Added `pkill -f "SoundPlayer"` - caused more issues

**Current Status:** Reverted to original activity hooks. Issue may still occur occasionally.

---

## Files Modified

### ~/.claude/hooks/waiting-notify-permission.sh

Added `start_time = now + 2` fix inside the nag script:
```bash
# Use now+2 to avoid race with PreToolUse's +1 buffer
start_time=$(($(date +%s) + 2))
```

### ~/.claude/hooks/waiting-activity-tooluse.sh

Reverted to original (no debug logging):
```bash
#!/bin/bash
# Waiting - Activity hook for tool approval

HOOK_INPUT=$(cat)
SESSION_ID=$(echo "$HOOK_INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)
if [ -z "$SESSION_ID" ]; then
    SESSION_ID=$(echo "$HOOK_INPUT" | md5sum | cut -c1-8)
fi

PENDING_FILE="/tmp/waiting-pending-$SESSION_ID"

ACTIVITY_TIME=$(($(date +%s) + 1))
echo "$ACTIVITY_TIME" > "/tmp/waiting-activity-stop-$SESSION_ID"
echo "$ACTIVITY_TIME" > "/tmp/waiting-activity-permission-$SESSION_ID"

pkill -f "waiting-nag-$SESSION_ID" 2>/dev/null
rm -f "/tmp/waiting-nag-$SESSION_ID.pid"
rm -f "$PENDING_FILE"
```

### ~/.claude/hooks/waiting-activity-submit.sh

Reverted to original (no debug logging):
```bash
#!/bin/bash
# Waiting - Activity hook for user message submit

HOOK_INPUT=$(cat)
SESSION_ID=$(echo "$HOOK_INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)
if [ -z "$SESSION_ID" ]; then
    SESSION_ID=$(echo "$HOOK_INPUT" | md5sum | cut -c1-8)
fi

ACTIVITY_TIME=$(($(date +%s) + 1))
echo "$ACTIVITY_TIME" > "/tmp/waiting-activity-stop-$SESSION_ID"
echo "$ACTIVITY_TIME" > "/tmp/waiting-activity-permission-$SESSION_ID"

pkill -f "waiting-nag-$SESSION_ID" 2>/dev/null
rm -f "/tmp/waiting-nag-$SESSION_ID.pid"
rm -f "/tmp/waiting-pending-$SESSION_ID"
```

---

## Debug Logging (Removed)

Temporarily added to `/tmp/waiting-debug.log`:
- "Permission hook fired" with session details
- "PreToolUse fired"
- "UserPromptSubmit fired"
- "Killing nag for session X"

Removed because it may have caused issues.

---

## Key Learnings

1. **Hook Timing:** `PreToolUse` can fire in the same second as `PermissionRequest` for cascading tool calls.

2. **Activity Buffer:** The `+1` buffer on activity timestamps can cause false positives if nag script's `start_time` doesn't account for it.

3. **Child Processes:** Background audio processes (`powershell.exe`) survive parent script termination.

4. **Claude Code Hooks:** Settings are read at startup only; scripts are read on each invocation.

---

## Current Behavior

| Scenario | Behavior |
|----------|----------|
| Permission dialog, user AFK 10s+ | Bell plays ✓ |
| Permission dialog, user approves quickly | No bell ✓ |
| User approves after bell starts | Bell may continue briefly |
| Cascading permissions | Each starts new nag |

---

## Outstanding Issues

1. **Extra bell after approval** - Sound may play once more after user approves because powershell.exe child process isn't killed.

2. **Need to update cli.py** - The `+2` buffer fix is only in the generated hook script, not in `cli.py`. Running `waiting` again will overwrite with old code.

---

## Commands Used for Debugging

```bash
# Watch hook activity
tail -f /tmp/waiting-debug.log

# Check running nag processes
ps aux | grep "waiting-nag" | grep -v grep

# Check temp files
ls -la /tmp/waiting-*

# Kill all nags
pkill -f "waiting-nag"

# Test audio directly
powershell.exe -c "(New-Object Media.SoundPlayer '$(wslpath -w /path/to/bell.wav)').PlaySync()"

# Check hook configuration
cat ~/.claude/settings.json | jq '.hooks'
```
