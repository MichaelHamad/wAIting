# Audio PID Tracking Fix - January 4, 2026 (22:16)

## Problem

Bell continues playing after user responds to permission dialog. Previous fixes using `pkill -P $$` and `pkill -f "waiting-bell.wav"` were unreliable on WSL.

## Root Cause Analysis

On WSL, killing processes that play audio is unreliable because:

1. **Parent-child relationship breaks**: `pkill -P $$` doesn't work because PowerShell processes spawned with `&` get reparented
2. **Pattern matching may fail**: `pkill -f "waiting-bell.wav"` searches process command lines but WSL interop can be inconsistent
3. **Audio buffering**: Windows audio subsystem buffers audio data, so even killing the process may not stop playback immediately

This is a [known WSL issue](https://github.com/microsoft/WSL/issues/2706) - child processes remain alive when parent exits.

## Solution

Implemented **explicit PID tracking** for audio processes:

1. When `play_sound()` spawns an audio player, save its PID to a file
2. When cleanup is needed, read the PID file and kill that specific process
3. Keep pattern-based pkill as a backup

## Changes Made

### 1. Updated `get_audio_command()` - Track audio PID

```python
def get_audio_command(audio_path: str, volume: int) -> str:
    return f'''play_sound() {{
    AUDIO_PID_FILE="/tmp/waiting-audio-$SESSION_ID.pid"
    if command -v paplay &> /dev/null; then
        paplay --volume=... "{audio_path}" 2>/dev/null &
        echo $! > "$AUDIO_PID_FILE"
    elif command -v powershell.exe &> /dev/null; then
        ...
        powershell.exe -c "..." 2>/dev/null &
        echo $! > "$AUDIO_PID_FILE"
    fi
}}'''
```

All audio players (paplay, pw-play, aplay, afplay, powershell.exe) now save their PID.

### 2. Updated `cleanup()` in all nag scripts

```bash
cleanup() {
    # Kill audio by tracked PID (most reliable)
    AUDIO_PID_FILE="/tmp/waiting-audio-$SESSION_ID.pid"
    if [ -f "$AUDIO_PID_FILE" ]; then
        kill $(cat "$AUDIO_PID_FILE") 2>/dev/null
        rm -f "$AUDIO_PID_FILE"
    fi
    # Backup: kill by pattern
    pkill -f "waiting-bell.wav" 2>/dev/null
    rm -f "$PID_FILE"
    exit 0
}
```

### 3. Updated activity hooks (UserPromptSubmit, PreToolUse)

```bash
# Kill audio by tracked PID first (fastest)
AUDIO_PID_FILE="/tmp/waiting-audio-$SESSION_ID.pid"
if [ -f "$AUDIO_PID_FILE" ]; then
    kill $(cat "$AUDIO_PID_FILE") 2>/dev/null
    rm -f "$AUDIO_PID_FILE"
fi

# Kill nag process
pkill -f "waiting-nag-$SESSION_ID" 2>/dev/null

# Backup: kill audio by pattern
pkill -f "waiting-bell.wav" 2>/dev/null

# Cleanup files
rm -f "/tmp/waiting-nag-$SESSION_ID.pid"
rm -f "$PENDING_FILE"
```

## Files Changed

| File | Functions Modified |
|------|-------------------|
| `src/waiting/cli.py` | `get_audio_command()` |
| `src/waiting/cli.py` | `create_stop_script()` - cleanup() |
| `src/waiting/cli.py` | `create_permission_script()` - cleanup() |
| `src/waiting/cli.py` | `create_idle_script()` - cleanup() |
| `src/waiting/cli.py` | `create_activity_submit_script()` |
| `src/waiting/cli.py` | `create_activity_tooluse_script()` |

## New Temp Files

- `/tmp/waiting-audio-{SESSION_ID}.pid` - Stores the PID of the currently playing audio process

## Why This Should Work Better

1. **Direct PID kill**: Using `kill <PID>` is more reliable than pattern matching
2. **Activity hooks kill first**: When user responds, PreToolUse fires and kills audio immediately
3. **Multiple fallbacks**: PID file -> pkill pattern -> nag cleanup

## Known Limitation

Even with this fix, Windows audio buffering may cause a brief continuation of sound after the process is killed. This is a fundamental WSL/Windows audio limitation. If issues persist, consider using a shorter bell sound (~0.3 seconds).

## Requires

**Restart Claude Code** after running `waiting` for activity hook changes to take effect.
