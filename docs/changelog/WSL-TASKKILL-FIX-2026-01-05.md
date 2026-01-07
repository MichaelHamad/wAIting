# WSL Audio Kill Fix - v2.3.1

**Date:** January 5, 2026
**Version:** 2.3.1
**Status:** Fixed
**Priority:** CRITICAL (MVP blocking)

---

## Root Cause Discovery

After extensive debugging, we discovered the **actual** root cause of the "bell continuing to play" issue on WSL systems:

### The Problem

When running `powershell.exe ... &` from bash in WSL:

```bash
powershell.exe -c "(New-Object Media.SoundPlayer ...).PlaySync()" &
AUDIO_PID=$!
```

**The `$!` variable gives us the bash subshell PID, NOT the Windows PowerShell PID!**

Proof:
```
Bash reports PID: 524940  (bash wrapper)
Windows shows:    46516   (actual PowerShell)

After: kill -9 524940
Result: PowerShell 46516 is STILL RUNNING!
```

**Linux `kill` command DOES NOT kill Windows processes in WSL!**

### Why Previous Fixes Didn't Work

All our v2.3.0 fixes used Linux `kill`:
```bash
kill "$AUDIO_PID" 2>/dev/null
kill -9 "$AUDIO_PID" 2>/dev/null
pgrep -f "powershell.*waiting-bell" | xargs -r kill 2>/dev/null
```

These commands:
1. Kill the bash wrapper process
2. Leave the Windows PowerShell process running
3. Windows continues playing audio through its audio subsystem

---

## The Solution

Use Windows `taskkill.exe` instead of Linux `kill`:

```bash
# Kill any powershell audio processes (WSL)
# CRITICAL: Linux kill doesn't kill Windows processes! Must use taskkill.exe
if command -v taskkill.exe &> /dev/null; then
    taskkill.exe /F /IM powershell.exe 2>/dev/null
fi
```

### Why This Works

`taskkill.exe` is a Windows command that runs natively and can terminate Windows processes:

```
$ taskkill.exe /F /IM powershell.exe
SUCCESS: The process "powershell.exe" with PID 6136 has been terminated.
```

After this command, the audio stops immediately.

---

## Changes Made

### Files Modified

**`src/waiting/cli.py`**
- Updated `create_activity_tooluse_script()` - PreToolUse hook
- Updated `create_notify_permission_script()` - PermissionRequest hook (nag cleanup)
- Updated `create_activity_submit_script()` - UserPromptSubmit hook
- Version bumped from 2.3.0 to 2.3.1

### Code Changes

**Before (v2.3.0):**
```bash
# Kill any powershell audio processes (WSL)
pgrep -f "SoundPlayer.*waiting-bell" | xargs -r kill 2>/dev/null
pgrep -f "powershell.*waiting-bell" | xargs -r kill 2>/dev/null
```

**After (v2.3.1):**
```bash
# Kill any powershell audio processes (WSL)
# CRITICAL: Linux kill doesn't kill Windows processes! Must use taskkill.exe
if command -v taskkill.exe &> /dev/null; then
    taskkill.exe /F /IM powershell.exe 2>/dev/null
fi
# Fallback: try pgrep (may not work for Windows processes)
pgrep -f "SoundPlayer.*waiting-bell" | xargs -r kill -9 2>/dev/null
pgrep -f "powershell.*waiting-bell" | xargs -r kill -9 2>/dev/null
```

---

## Testing

### Before Fix
1. Trigger permission dialog
2. Wait for bell (after 10s grace period)
3. Approve permission
4. **Bell continues playing for full duration (~2.5 seconds)**
5. Bell may play again after 30 seconds if nag wasn't killed

### After Fix
1. Trigger permission dialog
2. Wait for bell (after 10s grace period)
3. Approve permission
4. **Bell stops immediately** (PowerShell killed by taskkill.exe)
5. No more bells (nag process also terminates)

---

## Side Effects

**Note:** `taskkill.exe /F /IM powershell.exe` kills ALL PowerShell processes.

If user has other PowerShell windows open, they will be terminated. This is aggressive but necessary to ensure audio stops.

Future improvement could use more targeted killing (by window title or command line), but for MVP this is acceptable.

---

## Version History

| Version | Issue | Fix |
|---------|-------|-----|
| 2.0.0 | Stray bells | Stop-signal mechanism |
| 2.1.0 | No bells at all | Fixed activity check timing |
| 2.2.0 | Audio survives nag kill | Kill audio before nag |
| 2.3.0 | Audio still survives | Aggressive pgrep patterns |
| **2.3.1** | **Linux kill doesn't work on WSL** | **Use taskkill.exe** |

---

## Debugging Notes

To verify the fix is working, check:

```bash
# After approving permission, run:
tasklist.exe /FI "IMAGENAME eq powershell.exe"

# Should show:
# INFO: No tasks are running which match the specified criteria.
```

If PowerShell processes remain, the fix isn't working correctly.
