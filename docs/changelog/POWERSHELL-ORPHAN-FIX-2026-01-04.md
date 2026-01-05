# PowerShell Orphan Process Fix - January 4, 2026 (21:50)

## Problem

Bell continues playing after user responds to permission dialog, even though the nag script is killed.

## Root Cause

The previous fix used `pkill -P $$` to kill child processes:

```bash
cleanup() {
    pkill -P $$ 2>/dev/null  # Kill child processes
    rm -f "$PID_FILE"
    exit 0
}
```

This approach fails on WSL because:
1. PowerShell is spawned with `&` (background)
2. When the nag script is killed via signal, the parent-child relationship isn't reliably tracked
3. PowerShell processes become orphaned (reparented to init) and continue playing

## Fix

Changed cleanup to use pattern matching on the audio file path instead of parent-child relationship:

```bash
cleanup() {
    pkill -f "waiting-bell.wav" 2>/dev/null  # Kill any audio playing our bell
    rm -f "$PID_FILE"
    exit 0
}
```

This matches any process with "waiting-bell.wav" in its command line, which includes:
- `powershell.exe -c "(New-Object Media.SoundPlayer 'C:\Users\Public\waiting-bell.wav').PlaySync()"`

## Files Changed

- `src/waiting/cli.py` (lines 140-144, 266-270, 380-384)

All three nag scripts (stop, permission, idle) updated.

## Why This Works

- `pkill -f` searches the full command line of all processes
- Our bell file has a unique path (`waiting-bell.wav`)
- This kills the PowerShell process regardless of parent-child relationship

## Testing

1. Trigger a permission dialog
2. Wait for bell to start playing
3. Respond to the dialog
4. Bell should stop immediately (no lingering sounds)
