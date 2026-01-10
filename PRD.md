# Product Requirements Document - Waiting MVP

## Overview

**Waiting** is an audio notification system for Claude Code that plays a bell sound when Claude shows a permission dialog and the user doesn't respond within a grace period.

## Problem Statement

Users step away from their desk while Claude Code is working. When a permission dialog appears (e.g., "Allow Bash command?"), the user may not notice it and Claude waits indefinitely for input.

## Solution

Play an audible bell notification after a grace period if the user hasn't responded to a permission dialog.

---

## User Flow

```
Permission dialog appears
        ↓
    Grace period (30s default)
        ↓
    User action detected? → Yes → Cancel bell
        ↓ No
    Play bell sound
```

## How It Works

### 1. Installation
```bash
pip install -e .
waiting          # Enable notifications
```
User restarts Claude Code for hooks to take effect.

### 2. Permission Dialog Appears
Claude Code triggers the `PermissionRequest` hook event.

### 3. Grace Period
Hook script waits (default 30 seconds) before playing sound.

### 4. User Takes Action
User approves/denies the dialog → `PreToolUse` hook fires → signal script to cancel bell.

### 5. Play Sound
If grace period elapses without user action, play bell via cross-platform audio player.

---

## Configuration

Stored in `~/.waiting.json`:

| Setting | Default | Description |
|---------|---------|-------------|
| `grace_period` | 30 | Seconds to wait before first bell |
| `volume` | 100 | Volume percentage (1-100) |
| `audio` | "default" | Audio file path or "default" |

### Example Config
```json
{
  "grace_period": 30,
  "volume": 100,
  "audio": "default"
}
```

---

## MVP Commands

```bash
waiting          # Enable notifications (installs hooks)
waiting disable  # Disable notifications (removes hooks)
waiting status   # Show current configuration
```

---

## Technical Implementation

### Hooks
Install bash scripts to `~/.claude/hooks/`:
- `waiting-notify-permission.sh` - Triggered on `PermissionRequest` event
- `waiting-activity-tooluse.sh` - Triggered on `PreToolUse` event (user responds)

### State Management
Use temp files for communication:
- `/tmp/waiting-stop-{session}` - Stop signal file
- `/tmp/waiting-audio-{session}.pid` - Audio process PID

### Audio Playback
Cross-platform detection (try in order):
1. `paplay` (PulseAudio)
2. `pw-play` (PipeWire)
3. `aplay` (ALSA)
4. `afplay` (macOS)
5. `powershell.exe` (WSL)

### Session ID
Extract from Claude's hook JSON input. Falls back to MD5 hash if missing.

---

## MVP Scope

✅ Single notification trigger (permission dialog)
✅ Grace period configurable
✅ Cross-platform audio playback
✅ Stop signal on user response
✅ Configuration via JSON
✅ Enable/disable commands

❌ Multiple hooks (stop, idle) - future enhancement
❌ Nag repeating - permission plays once only
❌ Web UI - CLI only for MVP

---

## Success Criteria

- [x] User can install and enable notifications
- [x] Bell plays after grace period on permission dialog
- [x] Bell stops immediately when user responds
- [x] Configuration changes take effect after Claude Code restart
- [x] Works on Linux, macOS, and WSL
