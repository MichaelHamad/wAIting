# Bell Notification System - Technical Analysis

**Date:** January 4, 2026
**Status:** Debugging in Progress

---

## 1. The UX Goal

### What Should Happen
1. User runs Claude Code with `waiting` hooks enabled
2. A permission dialog appears (e.g., "Allow tool X?")
3. After a grace period (10 seconds), a bell sound plays to alert the user
4. User responds to the dialog (clicks Allow/Deny or types a response)
5. **Bell stops immediately** - no more sounds
6. Claude continues working
7. If another permission dialog appears, cycle repeats

### What Actually Happens (The Bug)
1. Permission dialog appears
2. Bell plays correctly after grace period
3. User responds to the dialog
4. **Bell continues playing** even though no dialog is open
5. Bells keep going off while Claude is working
6. User hears "stray bells" with no way to stop them

This is a **critical UX failure** - the notification meant to help the user becomes an annoyance that can't be silenced.

---

## 2. System Architecture

### Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        Claude Code                               │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ Permission   │    │ UserPrompt   │    │ PreToolUse   │       │
│  │ Request Hook │    │ Submit Hook  │    │ Hook         │       │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘       │
└─────────┼───────────────────┼───────────────────┼───────────────┘
          │                   │                   │
          ▼                   ▼                   ▼
┌──────────────────┐  ┌─────────────────────────────────┐
│ Permission Hook  │  │      Activity Hooks             │
│ (starts nag)     │  │ (should kill nag + audio)       │
└────────┬─────────┘  └─────────────────────────────────┘
         │
         ▼
┌──────────────────┐
│   Nag Process    │ ◄─── Background bash script
│  (plays bells)   │      Loops: sleep → play_sound()
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Audio Process   │ ◄─── powershell.exe (WSL) or paplay/aplay
│ (actual sound)   │
└──────────────────┘
```

### File System State

```
/tmp/
├── waiting-nag-{SESSION_ID}.pid      # PID of nag process
├── waiting-nag-{SESSION_ID}.sh       # The nag script itself
├── waiting-pending-{SESSION_ID}      # Marker: permission dialog is open
├── waiting-activity-permission-{SESSION_ID}  # Last activity timestamp
├── waiting-activity-stop-{SESSION_ID}        # Last activity timestamp (stop hook)
└── waiting-audio-{SESSION_ID}.pid    # PID of audio process
```

### Process Lifecycle

**On Permission Dialog:**
1. `PermissionRequest` hook fires
2. Creates nag script at `/tmp/waiting-nag-{SESSION_ID}.sh`
3. Launches nag in background: `"$NAG_SCRIPT" ... &`
4. Writes PID to `/tmp/waiting-nag-{SESSION_ID}.pid`
5. Creates pending marker `/tmp/waiting-pending-{SESSION_ID}`

**Nag Loop:**
```bash
while true; do
    # Check exit conditions
    [ ! -f "$PID_FILE" ] && cleanup
    [ ! -f "$PENDING_FILE" ] && cleanup
    if [ "$last_activity" -ge "$start_time" ]; then cleanup; fi

    # Play sound
    play_sound

    # Wait interval
    sleep $INTERVAL
done
```

**On User Response:**
1. `UserPromptSubmit` or `PreToolUse` hook fires
2. Should kill nag process
3. Should kill audio process
4. Should remove temp files

---

## 3. Bugs Found and Fixed

### Bug 1: WSL Audio Path (Fixed)
**Problem:** Windows `SoundPlayer` cannot handle WSL UNC paths (`\\wsl.localhost\...`)
**Fix:** Copy audio to Windows-accessible path (`C:\Users\Public\waiting-bell.wav`)

### Bug 2: SESSION_ID Not Passed to Nag (Fixed)
**Problem:** Heredoc used quoted delimiter `<< 'NAGEOF'` which prevents variable expansion. `$SESSION_ID` was literal text, not the actual value.
**Fix:** Pass SESSION_ID as positional parameter `$7` to the nag script.

### Bug 3: Orphaned Nags After Restart (Fixed)
**Problem:** When Claude Code restarts, new session ID can't kill old session's nags.
**Fix:** Activity hooks now kill ALL nags, not just session-specific ones.

### Bug 4: Nags Survive Terminal Close (Fixed)
**Problem:** `nohup` and `disown` made nags immune to terminal death.
**Fix:** Removed `nohup` and `disown` so nags die with terminal.

### Bug 5: Stale Activity File (Fixed)
**Problem:** Second permission menu's nag sees old activity timestamp and exits immediately.
**Fix:** Permission hook clears activity file before starting new nag.

### Bug 6: pkill Kills Itself (Current)
**Problem:** `pkill -f "waiting-nag-"` matches its own process and kills the activity hook before cleanup completes.
**Fix (attempted):** Switch from `pkill` to PID-based killing:
```bash
NAG_PID=$(cat "$NAG_PID_FILE")
kill "$NAG_PID"
kill -9 "$NAG_PID"
```

---

## 4. The Core Problem

### Why Is This So Hard?

The fundamental challenge is **cross-process communication in a loosely-coupled hook system**:

1. **No Direct IPC:** Claude Code hooks are independent shell scripts with no shared memory or message passing
2. **Process Isolation:** The nag runs as a separate process tree from the hooks
3. **Race Conditions:** Multiple hooks can fire in rapid succession
4. **Session Management:** Each Claude Code instance has a unique session ID
5. **WSL Complexity:** Audio plays in Windows, processes run in Linux

### The Kill Chain Must Work Perfectly

For the bell to stop, ALL of these must succeed:
1. Activity hook must fire (Claude Code must trigger it)
2. Hook must extract correct SESSION_ID from JSON input
3. Hook must find the PID file
4. PID file must contain valid PID
5. `kill` must successfully terminate the nag
6. Nag's cleanup must kill the audio process
7. All temp files must be removed

**If ANY step fails, bells continue.**

---

## 5. Debugging Evidence

### Debug Log Output
```
2026-01-04 23:34:12 UserPromptSubmit fired
2026-01-04 23:34:12 SESSION_ID=4d8b89d4-8e68-49dc-872c-97ebc2491e9a
2026-01-04 23:37:30 UserPromptSubmit fired
2026-01-04 23:37:30 SESSION_ID=08d616c6-859c-438c-ab0c-a9b3d05d2fd7
2026-01-04 23:37:37 PreToolUse fired
2026-01-04 23:37:37 SESSION_ID=08d616c6-859c-438c-ab0c-a9b3d05d2fd7
```

**Observation:** Hooks ARE firing with correct SESSION_ID, but nag survives.

### Process State After Hook
```
michael  478881  /bin/bash /tmp/waiting-nag-08d616c6-...  # STILL RUNNING
/tmp/waiting-pending-08d616c6-...                         # STILL EXISTS
```

**Conclusion:** The `pkill` command is not killing the nag.

---

## 6. Current Fix Attempt

### Old Code (Broken)
```bash
pkill -f "waiting-nag-$SESSION_ID" 2>/dev/null
pkill -f "waiting-nag-" 2>/dev/null
```

**Problem:** `pkill -f` with a pattern that matches the command line of the process running pkill causes it to kill itself (exit code 144 = killed by signal 16).

### New Code (Testing)
```bash
# Kill nag by PID file (most reliable)
NAG_PID_FILE="/tmp/waiting-nag-$SESSION_ID.pid"
if [ -f "$NAG_PID_FILE" ]; then
    NAG_PID=$(cat "$NAG_PID_FILE")
    kill "$NAG_PID" 2>/dev/null
    kill -9 "$NAG_PID" 2>/dev/null
fi

# Kill ALL nags by PID files (handles orphans)
for pidfile in /tmp/waiting-nag-*.pid; do
    if [ -f "$pidfile" ]; then
        kill $(cat "$pidfile") 2>/dev/null
        kill -9 $(cat "$pidfile") 2>/dev/null
    fi
done
```

---

## 7. Alternative Approaches to Consider

### A. Signal-Based Cleanup
Have the nag script poll a "stop" file instead of relying on being killed:
```bash
while [ ! -f "/tmp/waiting-stop-$SESSION_ID" ]; do
    play_sound
    sleep $INTERVAL
done
```

### B. File Lock Based
Use `flock` to ensure only one nag runs and clean handoff:
```bash
exec 200>/tmp/waiting-nag.lock
flock -n 200 || exit 0
```

### C. Named Pipe / FIFO
Create a control channel for the nag:
```bash
mkfifo /tmp/waiting-control-$SESSION_ID
# Nag listens for "stop" command
```

### D. Systemd User Service (Linux)
Run nag as a user service that can be cleanly stopped:
```bash
systemctl --user stop waiting-nag@$SESSION_ID
```

---

## 8. Lessons Learned

1. **pkill -f is dangerous** - It can match its own invocation
2. **Heredoc quoting matters** - `<< 'EOF'` vs `<< EOF` changes variable expansion
3. **nohup/disown are double-edged** - They help persistence but hurt cleanup
4. **Session IDs must flow correctly** - Any break in the chain causes orphans
5. **Debug logging is essential** - Can't fix what you can't see
6. **Process management is hard** - Especially across WSL boundary

---

## 9. Files Modified

| File | Purpose |
|------|---------|
| `src/waiting/cli.py` | Main CLI with all hook script generators |
| `~/.claude/hooks/waiting-notify-permission.sh` | Generated permission hook |
| `~/.claude/hooks/waiting-activity-submit.sh` | Generated activity hook (UserPromptSubmit) |
| `~/.claude/hooks/waiting-activity-tooluse.sh` | Generated activity hook (PreToolUse) |
| `~/.claude/settings.json` | Claude Code hook configuration |

---

## 10. Next Steps

1. **Test PID-based killing** - Verify the new approach works
2. **Add more debug logging** - Track exact PID being killed
3. **Consider signal-based approach** - More reliable than process killing
4. **Document final solution** - Once working, create clear documentation
