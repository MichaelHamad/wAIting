# Waiting - Architecture Guide

## Overview

**Waiting** is a Python CLI tool that provides audio notifications when Claude Code needs user attention. It integrates with Claude Code's hook system to detect waiting states and plays bell sounds to alert users who may be away from their desk.

**Core Purpose:** Notify users when Claude Code is waiting for input (permission dialog, task completion, idle timeout) by playing an audio alert.

---

## Table of Contents

1. [What is Waiting?](#what-is-waiting)
2. [Project Structure](#project-structure)
3. [Core Architecture](#core-architecture)
4. [Technologies](#technologies)
5. [Key Workflows](#key-workflows)
6. [Design Patterns](#design-patterns)
7. [Configuration System](#configuration-system)
8. [Hook System](#hook-system)
9. [State Management](#state-management)
10. [Integration Points](#integration-points)

---

## What is Waiting?

Waiting solves this problem: When you step away from your desk while Claude Code is working, you might miss when it needs your input. This tool automatically plays a bell sound to alert you.

### Use Cases

- **Permission Dialog:** Claude shows a dialog asking permission to execute a tool, but you're away → Waiting plays a bell
- **Task Completion:** Claude finishes a response and is waiting for your next message → Waiting plays a bell
- **Long Idle Period:** Claude has been idle for 60+ seconds → Waiting plays a bell

### Key Features

- 🔔 Customizable bell sound and volume
- ⏱️ Grace periods to avoid false alarms
- 🔁 Configurable repeat intervals and maximum nags
- 🔌 Per-hook enable/disable
- 📊 Multi-session support (multiple Claude Code instances)
- 🔄 Activity detection (stops nagging when user responds)

---

## Project Structure

```
waiting_new/
├── src/waiting/
│   ├── __init__.py              # Package initialization
│   ├── cli.py                   # Main application (767 lines)
│   └── bell.wav                 # Default notification sound
├── docs/
│   ├── reference/               # Technical documentation
│   │   ├── ARCHITECTURE.md      # This file
│   │   ├── ONE_SHOT_PROMPT.md   # Complete specification
│   │   └── MVP_PROMPT.md        # MVP specification
│   ├── debugging/               # Debug logs and investigations
│   ├── progress/                # Progress tracking
│   ├── changelog/               # Version history
│   └── issues/                  # Known issues
├── pyproject.toml               # Build configuration
└── README.md                    # User documentation
```

### Configuration Locations

- **User Config:** `~/.waiting.json`
- **Hook Scripts:** `~/.claude/hooks/`
- **Claude Settings:** `~/.claude/settings.json`
- **Temporary Files:** `/tmp/waiting-*` (session-specific)

---

## Core Architecture

### High-Level Flow

```
User runs: waiting [options]
    ↓
Python CLI loads config from ~/.waiting.json
    ↓
Generates 5 bash hook scripts with embedded config
    ↓
Installs scripts to ~/.claude/hooks/
    ↓
Updates ~/.claude/settings.json with hook references
    ↓
User restarts Claude Code
    ↓
Claude Code loads hooks from settings
    ↓
When Claude Code events occur, it fires the corresponding hook
    ↓
Hook scripts use temp files and background processes to manage notifications
```

### Main Components

#### 1. **Configuration Management** (lines 10-43)

Handles loading and saving user preferences.

**Default Configuration:**
```json
{
  "audio": "default",              // "default" or path to custom .wav
  "interval": 30,                  // Seconds between bell repeats
  "max_nags": 0,                   // Max repeats (0 = unlimited)
  "volume": 100,                   // Volume percentage 1-100
  "enabled_hooks": ["stop", "idle"],  // Most reliable hooks (permission optional)
  "grace_period_stop": 300,        // Seconds before bell (Stop hook)
  "grace_period_permission": 10,   // Seconds before bell (Permission hook)
  "grace_period_idle": 0           // Extra seconds (Idle hook)
}
```

**Key Functions:**
- `load_config()` - Merges user config with defaults
- `save_config()` - Persists config to `~/.waiting.json`

#### 2. **Audio System** (lines 45-68)

Detects available audio players and generates playback commands.

**Cross-Platform Audio Detection:**
1. **Linux:** `paplay` (PulseAudio) → `pw-play` (PipeWire) → `aplay` (ALSA)
2. **macOS:** `afplay`
3. **WSL/Windows:** `powershell.exe` with WSL path conversion

**Key Functions:**
- `get_audio_path()` - Resolves audio file location
- `get_audio_command()` - Returns bash function for platform-specific playback

#### 3. **Hook Script Generator** (lines 71-474)

Generates bash scripts that Claude Code executes on specific events.

**Five Hook Scripts:**

| Hook Name | Trigger | Behavior |
|-----------|---------|----------|
| `waiting-notify-stop.sh` | Claude finishes response | Wait 5 min, then nag until user responds |
| `waiting-notify-permission.sh` | Permission dialog appears | Wait 10 sec, then nag until approved |
| `waiting-notify-idle.sh` | Claude idle for 60 sec | Wait 0 sec (usually), then nag |
| `waiting-activity-submit.sh` | User sends message | Kill any running nag |
| `waiting-activity-tooluse.sh` | User approves tool | Kill any running nag |

**Key Functions:**
- `create_stop_hook_script()` - Generate Stop hook
- `create_permission_hook_script()` - Generate Permission hook
- `create_idle_hook_script()` - Generate Idle hook
- `create_activity_submit_script()` - Generate activity tracking
- `create_activity_tooluse_script()` - Generate tool approval tracking

#### 4. **Hook Installation System** (lines 482-627)

Installs and manages hooks in Claude Code's hook system.

**Key Functions:**
- `setup_hooks()` - Install/update all hooks and update Claude settings
- `remove_hooks()` - Uninstall hooks and clean up
- `is_enabled()` - Check if hooks are installed

**Installation Process:**
1. Kill any existing nag processes
2. Create `~/.claude/hooks/` directory
3. Write 5 bash scripts with executable permissions
4. Load existing `~/.claude/settings.json`
5. Remove old waiting hooks (if any)
6. Add new hooks with event matchers
7. Save updated settings to `~/.claude/settings.json`

#### 5. **CLI Command Interface** (lines 635-764)

Provides user commands to manage the notification system.

**Commands:**
- `waiting` - Enable notifications (default action)
- `waiting disable` - Disable all notifications
- `waiting kill` - Stop current nag without disabling
- `waiting status` - Show current configuration
- `waiting configure` - Modify any configuration option

---

## Technologies

### Language & Runtime
- **Python 3.9+** - Main implementation language
- **Click 8.0.0+** - CLI framework for command parsing and help

### Build System
- **Hatchling** - Modern Python build backend

### System Integration
- **Bash** - Hook script implementation
- **Cross-platform audio** - Platform-specific playback detection
- **File-based state** - Configuration and temporary state files
- **Process management** - PID-based nag process control

---

## Key Workflows

### Workflow 1: User Steps Away During Permission Dialog

```
┌─ Claude shows permission dialog
│  ├─ PermissionRequest hook fires
│  ├─ Script creates /tmp/waiting-pending-{session}
│  └─ Spawns background nag process
│
├─ Grace period (10 seconds default)
│  ├─ Nag process waits
│  ├─ Checks for user activity
│  └─ If no activity after 10s → continues
│
├─ Main nag loop (repeats every 30 seconds)
│  ├─ Play bell sound
│  ├─ Check if permission dialog still open (pending file exists)
│  ├─ Check for user activity
│  ├─ Check repeat limits
│  └─ Sleep and repeat
│
└─ User approves permission
   ├─ PreToolUse hook fires
   ├─ Activity timestamp updated
   ├─ Pending marker removed
   └─ Nag process killed
```

### Workflow 2: Claude Finishes Task

```
┌─ Claude sends response
│  ├─ Stop hook fires
│  ├─ Records stop time in temp files
│  └─ Spawns background nag process
│
├─ Grace period (5 minutes default)
│  ├─ Nag waits while checking for activity
│  ├─ Checks Claude's heartbeat (timeout = 2 min)
│  └─ If no activity after 5 min → continues
│
├─ Main nag loop
│  ├─ Play bell sound
│  ├─ Verify Claude still responsive (heartbeat)
│  ├─ Check for user activity
│  └─ Repeat every 30 seconds
│
└─ User sends new message
   ├─ UserPromptSubmit hook fires
   ├─ Activity timestamp updated
   └─ Nag process killed
```

### Workflow 3: Claude Idle for 60+ Seconds

```
┌─ 60 seconds of inactivity detected
│  ├─ Claude's internal idle_prompt timer fires
│  ├─ Notification hook matches idle_prompt
│  └─ Spawns idle nag process
│
├─ Grace period (0 seconds default)
│  └─ Usually skipped (60s delay already in Claude)
│
├─ Main nag loop
│  ├─ Play bell sound
│  ├─ Check repeat limits
│  └─ Repeat every 30 seconds
│
└─ User responds
   ├─ UserPromptSubmit hook fires
   └─ Nag process killed
```

### Workflow 4: Configuration Change

```
┌─ User runs: waiting --interval 60 --volume 75
│  ├─ Python loads current config
│  ├─ Updates with new values
│  └─ Saves to ~/.waiting.json
│
├─ Python generates new hook scripts
│  ├─ Embeds new values (60s interval, 75% volume)
│  └─ Writes to ~/.claude/hooks/
│
└─ Claude Code restarts or reloads hooks
   └─ New behavior takes effect
```

---

## Design Patterns

### Pattern 1: Script Generation at Installation Time

Rather than storing static scripts, the Python CLI **generates bash scripts with embedded configuration values**.

**Benefits:**
- Fast hook execution (no config file I/O during alerts)
- Configuration immediately takes effect (scripts regenerated)
- Scripts are standalone (work even if Python environment changes)

**Implementation:**
- All `create_*_hook_script()` functions generate complete scripts
- Configuration values embedded directly in bash code
- Scripts written to `~/.claude/hooks/` with `chmod +x`

### Pattern 2: Grace Periods with Activity Checking

Instead of nagging immediately, hooks wait for a "grace period" while monitoring for user activity.

**Why:**
- User may respond immediately after dialog appears
- Reduces false alarms when user is actively working
- Customizable per-hook

**Implementation:**
- Grace period loop checks user activity file every second
- Exits early if activity detected
- If grace period expires, starts main nag loop

### Pattern 3: Session-Scoped State with Temp Files

Uses `/tmp/` files as a simple state machine:

| File | Purpose |
|------|---------|
| `/tmp/waiting-pending-{session}` | Permission dialog is open |
| `/tmp/waiting-activity-stop-{session}` | Last user activity timestamp (Stop hook) |
| `/tmp/waiting-activity-permission-{session}` | Last user activity timestamp (Permission hook) |
| `/tmp/waiting-nag-{session}.pid` | Currently running nag process ID |
| `/tmp/waiting-stop-time-{session}` | When Stop hook fired |
| `/tmp/waiting-heartbeat-{session}` | Proof Claude is still alive |

**Benefits:**
- No database required
- Accessible from bash scripts
- Automatic cleanup (files expire in `/tmp`)
- Inherently multi-session safe

**Session ID:**
- Extracted from Claude's JSON input: `session_id` field
- If not available, generated as MD5 hash of input
- Ensures each Claude session has independent state

### Pattern 4: Activity-Based Kill Switch

Both activity hooks (UserPromptSubmit and PreToolUse) update activity timestamps, which nag processes continuously check.

**Flow:**
1. User action triggers activity hook
2. Hook updates `/tmp/waiting-activity-*-{session}` timestamp
3. Running nag processes see newer activity timestamp
4. Nag processes exit because activity is recent

**Responsive:** Kill switch works within 1 second (nag loops sleep 1 second at a time)

### Pattern 5: Time Buffer for Cascading Events

Activity scripts set `ACTIVITY_TIME=$(($(date +%s) + 1))` (add 1 second).

**Why:**
- Multiple hooks may fire in same second
- Need to distinguish old activity from new
- PreToolUse can override PermissionRequest with +1 buffer
- Avoids race conditions

**Counterpart:** Permission hook sets `start_time = now + 2` to account for this.

### Pattern 6: Granular Sleep Loops

Instead of `sleep 30`, nag loops use `sleep 1` in a loop, checking conditions each iteration.

**Benefits:**
- Responsive termination (within 1 second of activity)
- Can check for process file deletion
- Early exit on limits reached
- Faster response to user actions

### Pattern 7: Hook Identification by Pattern

`_is_waiting_hook()` identifies waiting hooks by checking if command contains "waiting-notify" or "waiting-activity".

**Enables:**
- Removing old waiting hooks when updating
- Distinguishing waiting hooks from other hooks in settings
- Clean installation without duplicates

### Pattern 8: Orphan Process Protection

Multiple safeguards prevent stale nag processes:

| Protection | Mechanism |
|-----------|-----------|
| **Max lifetime** | 10-minute hard limit |
| **Heartbeat timeout** | 2 minutes for Stop hook (Claude still running?) |
| **PID file check** | Stops if PID file deleted |
| **SIGTERM trap** | Clean shutdown on signal |
| **Activity timeout** | Exits after grace period + time limit |

---

## Configuration System

### Loading Configuration

**Priority order:**
1. User config file: `~/.waiting.json`
2. Command-line arguments: `--audio`, `--interval`, etc.
3. Hardcoded defaults (built into source code)

**File Format:**
```json
{
  "audio": "default",
  "interval": 30,
  "max_nags": 0,
  "volume": 100,
  "enabled_hooks": ["stop", "idle"],
  "grace_period_stop": 300,
  "grace_period_permission": 10,
  "grace_period_idle": 0
}
```

### Saving Configuration

- `save_config()` writes merged config to `~/.waiting.json`
- Recreates hook scripts after every change
- Changes take effect after Claude Code restarts

### Configuration Commands

```bash
# Show current config
waiting status

# Enable notifications with defaults
waiting

# Customize during enable
waiting --interval 60 --volume 75

# Modify after installation
waiting configure --volume 50 --interval 45

# Show config without changing
waiting configure --show

# Reset to defaults
waiting configure --reset

# Enable/disable specific hooks
waiting configure --enable-hook stop --disable-hook idle
```

---

## Hook System

### What are Hooks?

Hooks are bash scripts that Claude Code automatically executes when specific events occur. They're stored in `~/.claude/hooks/` and configured in `~/.claude/settings.json`.

### Claude Code Hook Events

| Event | When it Fires |
|-------|---------------|
| `Stop` | Claude finishes responding |
| `PermissionRequest` | Claude shows permission dialog |
| `Notification` (with `idle_prompt` matcher) | Claude idle for 60+ seconds |
| `UserPromptSubmit` | User sends message |
| `PreToolUse` | Tool about to execute (user approved) |

### How Waiting Uses Hooks

Waiting installs scripts that match these events:

```json
{
  "hooks": {
    "Stop": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "/home/user/.claude/hooks/waiting-notify-stop.sh",
        "timeout": 10
      }]
    }],
    "PermissionRequest": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "/home/user/.claude/hooks/waiting-notify-permission.sh",
        "timeout": 10
      }]
    }],
    // ... etc
  }
}
```

### Hook Installation Steps

1. Python reads `~/.claude/settings.json`
2. Removes any existing `waiting-*` hooks
3. Adds new waiting hooks with correct event matchers
4. Writes updated settings back to `~/.claude/settings.json`
5. Generates fresh hook scripts with current config embedded

### Hook Removal Steps

Same process in reverse: removes all waiting hooks from settings and deletes hook scripts.

---

## State Management

### State Files

Waiting manages state entirely through temporary files:

```
/tmp/waiting-pending-{session}
├─ Purpose: Marks permission dialog as open
├─ Created by: Permission hook
├─ Removed by: Activity hooks (when user approves)
└─ Checked by: Permission nag loop (while loop condition)

/tmp/waiting-activity-stop-{session}
├─ Purpose: Timestamp of last user activity for Stop hook
├─ Format: Unix timestamp (seconds since epoch)
├─ Updated by: UserPromptSubmit and PreToolUse hooks (+1 buffer)
└─ Checked by: Stop nag loop (compares to stop_time)

/tmp/waiting-activity-permission-{session}
├─ Purpose: Timestamp of last user activity for Permission hook
├─ Format: Unix timestamp (seconds since epoch)
├─ Updated by: UserPromptSubmit and PreToolUse hooks (+1 buffer)
└─ Checked by: Permission nag loop

/tmp/waiting-nag-{session}.pid
├─ Purpose: PID of currently running nag process
├─ Created by: Hook scripts when spawning nag in background
├─ Removed by: Nag process on exit
└─ Checked by: Activity hooks (to kill existing nag)

/tmp/waiting-stop-time-{session}
├─ Purpose: Timestamp when Stop hook fired
├─ Format: Unix timestamp
├─ Created by: Stop hook
└─ Used by: Stop nag loop (compare with activity timestamp)

/tmp/waiting-heartbeat-{session}
├─ Purpose: Proof that Claude Code is still alive
├─ Format: Unix timestamp (updated when Stop hook fires)
├─ Created by: Stop hook
└─ Used by: Stop nag loop (timeout check: 2 minutes)
```

### State Lifecycle

```
Activity:
  User action → Activity hook fires → Update activity timestamp → Check nag process → Kill if running

Stop Hook:
  Claude finishes → Stop hook fires → Record stop time, heartbeat → Spawn nag process → (grace period) → Main loop

Permission Hook:
  Dialog appears → Permission hook fires → Create pending file → Spawn nag → (grace period) → Main loop

Activity During Main Loop:
  User responds → Activity hook fires → Update timestamp → Running nag checks every 1s → Sees new timestamp → Exits
```

### Process Lifecycle

**Nag Process:**
1. Created when hook fires (background process: `nag_process &`)
2. Records PID to `/tmp/waiting-nag-{session}.pid`
3. Runs grace period (sleep + activity checks)
4. Enters main loop (play sound, check conditions, sleep 1s, repeat)
5. Exits when: activity detected, max_nags reached, timeout, or killed by activity hook
6. Cleans up temp files on exit

---

## Integration Points

### Claude Code Integration

**Settings File:** `~/.claude/settings.json`
- Waiting reads existing hooks
- Removes old waiting hooks
- Adds new waiting hooks
- Writes updated settings

**Hook Input:** Claude passes JSON to hook scripts via stdin:
```json
{
  "session_id": "uuid-or-hash",
  "event": "Stop",
  "timestamp": 1234567890,
  // ... other event data
}
```

**Hook Execution:** Claude Code:
1. Detects event
2. Finds matching hooks in settings
3. Executes hook script with JSON input
4. Waits for completion (with timeout)
5. Continues normal operation

### File System Integration

**Config:** `~/.waiting.json`
- User-editable JSON file
- Loaded on every `waiting` command
- Saved after every configuration change

**Hooks:** `~/.claude/hooks/*.sh`
- Bash scripts generated by Python
- Executed by Claude Code on events
- Updated when config changes or hooks are reinstalled

**Temporary State:** `/tmp/waiting-*`
- Session-specific state files
- Automatically cleaned up by OS
- Readable/writable from bash scripts

### Audio System Integration

**Audio Detection:**
1. On each hook script generation, detect available audio player
2. Embed detection logic in script
3. Script tries players in priority order on execution

**Supported Players:**
- Linux: paplay, pw-play, aplay
- macOS: afplay
- Windows/WSL: powershell.exe

**Volume Control:**
- Supported by: paplay, pw-play, afplay
- Not supported by: aplay (limitation)
- WSL: pass-through to Windows audio

---

## Summary

Waiting is a well-architected notification system that:

- **Integrates cleanly** with Claude Code through its hook mechanism
- **Maintains reliability** through grace periods, activity detection, and orphan process protection
- **Operates independently** in bash with no dependencies on Python during execution
- **Scales to multiple sessions** with session-scoped temporary files
- **Responds quickly** to user actions within 1 second
- **Is configurable** with per-hook and per-setting customization
- **Cross-platform** with automatic audio player detection

The key insight is that waiting uses **generated scripts with embedded configuration** rather than dynamic configuration lookups, which makes hooks fast and reliable while maintaining configurability at the Python level.
