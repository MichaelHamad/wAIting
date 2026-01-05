# WSL Audio Fix & Bell Configuration - January 4, 2026 (21:16)

## Summary

Fixed two issues preventing reliable audio playback on WSL and causing unexpected bell notifications.

---

## Issue 1: WSL Audio Not Playing

### Symptom
Bell sound would not play when triggered via hooks, but played fine when manually executed.

### Root Cause
Windows `SoundPlayer` API cannot handle WSL UNC paths (`\\wsl.localhost\Ubuntu\...`). The previous code used `wslpath -w` to convert Linux paths to Windows paths, but this produced UNC paths that `SoundPlayer` silently failed to play.

### Fix
Updated `get_audio_command()` in `cli.py` to copy the audio file to a Windows-accessible location before playing:

```python
# Before (broken):
elif command -v powershell.exe &> /dev/null; then
    win_path=$(wslpath -w "{audio_path}" 2>/dev/null)
    powershell.exe -c "(New-Object Media.SoundPlayer '$win_path').PlaySync()" 2>/dev/null &

# After (working):
elif command -v powershell.exe &> /dev/null; then
    # WSL: Copy to Windows temp to avoid UNC path issues with SoundPlayer
    win_temp="/mnt/c/Users/Public/waiting-bell.wav"
    cp "{audio_path}" "$win_temp" 2>/dev/null
    powershell.exe -c "(New-Object Media.SoundPlayer 'C:\\Users\\Public\\waiting-bell.wav').PlaySync()" 2>/dev/null &
```

### Files Changed
- `src/waiting/cli.py` (lines 64-68)

---

## Issue 2: Bell Playing When Claude Is Working

### Symptom
Bell notifications would play while Claude was actively working/thinking, when no permission dialog was open.

### Root Cause
Two issues combined:

1. **Permission grace period was 0 seconds** - The permission hook would fire and immediately start playing without waiting for user response.

2. **Race condition with activity detection** - Activity hooks write timestamps with a `+1` buffer, but nag scripts used `start_time = now`. This could cause the nag to see "future" activity and not properly detect ongoing work.

3. **Stale nag processes** - Old nag processes from previous sessions were still running and playing bells.

### Fix

1. **Restored permission grace period to 10 seconds:**
   ```bash
   waiting configure --grace-permission 10
   ```

2. **Added +2 buffer to Stop hook** (Permission hook already had this fix):
   ```bash
   # In create_stop_script(), the nag script now uses:
   start_time=$(($(cat "$STOP_TIME_FILE" 2>/dev/null || date +%s) + 2))  # +2 to avoid race with activity hooks
   ```

3. **Killed stale nag processes:**
   ```bash
   pkill -f "waiting-nag-"
   ```

### Files Changed
- `src/waiting/cli.py` (line 135)
- `~/.waiting.json` (grace_period_permission: 0 -> 10)

---

## Issue 3: Default Bell Sound Update

### Change
Updated default notification sound from `Cool_bell.wav` to `Cool_bell_final.wav`.

### File Changed
- `src/waiting/cli.py` (line 50)

```python
# Before:
return str(Path(__file__).parent / "Cool_bell.wav")

# After:
return str(Path(__file__).parent / "Cool_bell_final.wav")
```

---

## Current Configuration

After fixes, running `waiting status` shows:

```
Status: enabled
Audio: default
Interval: 30s
Max nags: 0 (0=unlimited)
Volume: 100%
Enabled hooks: stop, permission, idle
Grace periods:
  stop: 300s
  permission: 10s
  idle: 0s
```

---

## Testing

1. **WSL audio test** - Run `waiting` to regenerate hooks, then trigger a permission dialog. Bell should play after 10 seconds.

2. **Manual audio test:**
   ```bash
   cp /path/to/Cool_bell_final.wav /mnt/c/Users/Public/waiting-bell.wav
   powershell.exe -c "(New-Object Media.SoundPlayer 'C:\Users\Public\waiting-bell.wav').PlaySync()"
   ```

---

## Issue 4: Bell Keeps Playing After User Responds (21:25)

### Symptom
After responding to a permission dialog, the bell continues playing on the interval even though Claude is working.

### Root Cause
The `cleanup()` function in nag scripts only removed the PID file and exited - it did NOT kill child processes (PowerShell audio players spawned by `play_sound()`). When the nag script was killed, the orphaned PowerShell processes continued playing.

### Fix
Updated `cleanup()` in all three nag scripts (stop, permission, idle) to kill child processes before exiting:

```bash
cleanup() {
    pkill -P $$ 2>/dev/null  # Kill child processes (e.g., PowerShell audio)
    rm -f "$PID_FILE"
    exit 0
}
```

### Files Changed
- `src/waiting/cli.py` (lines 140-144, 267-271, 381-385)

---

## Notes

- Linux/macOS users are unaffected by the WSL audio copy fix - native audio players are tried first
- After running `waiting` to regenerate hooks, restart Claude Code to pick up settings.json changes
- Stale nag processes can be killed with: `pkill -f "waiting-nag-"`
