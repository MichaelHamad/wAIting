# Waiting - Product Architecture

## Overview

**Waiting** is a CLI tool that provides audio notifications when Claude Code needs user input. It integrates with Claude Code's hook system to detect idle states and plays a sound to alert users who may have stepped away.

### Problem Statement

When using Claude Code for extended sessions, users often switch to other tasks while Claude is working. When Claude finishes and needs input (a response, permission approval, etc.), the user may not notice for minutes—wasting time and breaking flow.

### Solution

Waiting installs shell script hooks that Claude Code executes at key moments. These scripts detect when the user has been inactive and play an audio notification to bring them back.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              USER                                        │
│                                                                          │
│   $ waiting          Enable notifications                                │
│   $ waiting status   Check current state                                 │
│   $ waiting disable  Turn off                                            │
│   $ waiting configure --interval 30                                      │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         WAITING CLI                                      │
│                       src/waiting/cli.py                                 │
│                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │   enable    │  │  configure  │  │   status    │  │   disable   │    │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │
│         │                │                │                │            │
│         ▼                ▼                ▼                ▼            │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    Configuration Layer                            │  │
│  │                                                                   │  │
│  │  ~/.waiting.json     User preferences (interval, grace periods)  │  │
│  │  load_config()       Read with defaults for missing values       │  │
│  │  save_config()       Persist changes                             │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                 Script Generation Layer                           │  │
│  │                                                                   │  │
│  │  create_permission_notify_script()  →  waiting-notify-permission │  │
│  │  create_stop_notify_script()        →  waiting-notify-stop       │  │
│  │  create_idle_notify_script()        →  waiting-notify-idle       │  │
│  │  create_activity_scripts()          →  waiting-activity-*        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                 Hook Registration Layer                           │  │
│  │                                                                   │  │
│  │  ~/.claude/settings.json   Claude Code configuration             │  │
│  │  setup_hooks()             Register our scripts as hooks         │  │
│  │  remove_hook()             Unregister on disable                 │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ Claude Code reads settings.json
                                   │ at startup (hooks are cached)
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          CLAUDE CODE                                     │
│                                                                          │
│  Executes hooks at specific events:                                     │
│                                                                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │ UserPromptSubmit│  │PermissionRequest│  │      Stop       │         │
│  │  User sends msg │  │  Needs approval │  │  Claude done    │         │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘         │
│           │                    │                    │                   │
│  ┌────────┴────────┐  ┌────────┴────────┐                              │
│  │   PreToolUse    │  │   Notification  │                              │
│  │ User approves   │  │  (idle_prompt)  │                              │
│  └────────┬────────┘  └────────┬────────┘                              │
└───────────┼────────────────────┼────────────────────┼───────────────────┘
            │                    │                    │
            ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    GENERATED SHELL SCRIPTS                               │
│                      ~/.claude/hooks/                                    │
│                                                                          │
│  ┌────────────────────────┐    ┌────────────────────────────────────┐  │
│  │   ACTIVITY SCRIPTS     │    │     NOTIFICATION SCRIPTS           │  │
│  │                        │    │                                     │  │
│  │ waiting-activity-      │    │ waiting-notify-permission.sh       │  │
│  │   submit.sh            │    │   Check grace → bell → nag loop    │  │
│  │   Record user activity │    │                                     │  │
│  │   Kill any nag loop    │    │ waiting-notify-stop.sh             │  │
│  │                        │    │   Wait grace → check AFK → bell    │  │
│  │ waiting-activity-      │    │                                     │  │
│  │   permission.sh        │    │ waiting-notify-idle.sh             │  │
│  │   Record tool approval │    │   Bell after 60s idle              │  │
│  │   Kill any nag loop    │    │                                     │  │
│  └────────────────────────┘    └────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
            │                                          │
            ▼                                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         RUNTIME STATE                                    │
│                            /tmp/                                         │
│                                                                          │
│  waiting-activity-permission-{session}   Last activity timestamp        │
│  waiting-activity-stop-{session}         Last activity timestamp        │
│  waiting-stop-time-{session}             When Stop hook fired           │
│  waiting-nag-{session}.pid               Background nag loop PID        │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         AUDIO OUTPUT                                     │
│                                                                          │
│  Platform detection (in order):                                         │
│    • aplay     (ALSA - Linux)                                           │
│    • paplay    (PulseAudio - Linux)                                     │
│    • pw-play   (PipeWire - Linux)                                       │
│    • afplay    (macOS)                                                  │
│    • powershell.exe (WSL → Windows audio)                               │
│                                                                          │
│                              🔔 bell.wav                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. CLI Interface (`src/waiting/cli.py`)

The single source file containing all application logic. Built with Click framework.

| Command | Function | Purpose |
|---------|----------|---------|
| `waiting` | `cli()` | Enable notifications with current config |
| `waiting disable` | `disable()` | Remove hooks, delete scripts, kill processes |
| `waiting kill` | `kill()` | Stop nag loop without disabling hooks |
| `waiting status` | `status()` | Show current configuration and state |
| `waiting configure` | `configure()` | Modify settings |

### 2. Configuration System

**User Config** (`~/.waiting.json`):
```json
{
  "audio": "default",
  "interval": 15,
  "max_nags": 0,
  "enabled_hooks": ["permission"],
  "grace_period_stop": 300,
  "grace_period_permission": 10,
  "grace_period_idle": 0
}
```

| Setting | Default | Description |
|---------|---------|-------------|
| `audio` | `"default"` | Path to sound file, or "default" for bundled |
| `interval` | `30` | Seconds between repeated nags |
| `max_nags` | `0` | Maximum repeats (0 = unlimited) |
| `enabled_hooks` | `["stop", "permission", "idle"]` | Active hook types |
| `grace_period_stop` | `300` | Seconds before Stop hook alerts |
| `grace_period_permission` | `10` | Seconds before Permission hook alerts |
| `grace_period_idle` | `0` | Seconds before Idle hook alerts |

### 3. Hook Scripts

Generated bash scripts placed in `~/.claude/hooks/`:

#### Notification Scripts

| Script | Trigger | Behavior |
|--------|---------|----------|
| `waiting-notify-permission.sh` | `PermissionRequest` | Immediate check: if inactive > grace period, bell + nag loop |
| `waiting-notify-stop.sh` | `Stop` | Delayed check: wait grace period, then bell if still AFK |
| `waiting-notify-idle.sh` | `Notification` (idle_prompt) | Same as permission, but fires after 60s idle |

#### Activity Scripts

| Script | Trigger | Behavior |
|--------|---------|----------|
| `waiting-activity-submit.sh` | `UserPromptSubmit` | Update both activity files, kill nag loop |
| `waiting-activity-permission.sh` | `PreToolUse` | Update permission activity file, kill nag loop |

### 4. Claude Code Integration

Hooks are registered in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PermissionRequest": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "/home/user/.claude/hooks/waiting-notify-permission.sh",
        "timeout": 10
      }]
    }],
    "UserPromptSubmit": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "/home/user/.claude/hooks/waiting-activity-submit.sh",
        "timeout": 5
      }]
    }],
    "PreToolUse": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "/home/user/.claude/hooks/waiting-activity-permission.sh",
        "timeout": 5
      }]
    }]
  }
}
```

---

## Data Flow

### Permission Request Flow (MVP)

```
┌─────────────┐
│ Claude Code │
│ needs tool  │
│ permission  │
└──────┬──────┘
       │
       │ Fires PermissionRequest hook
       ▼
┌──────────────────────────────────────────────────────────────────┐
│                waiting-notify-permission.sh                       │
│                                                                   │
│  1. Read session_id from stdin (JSON context)                    │
│  2. Check activity file: was user active in last N seconds?      │
│     ├─ YES → exit (user is present)                              │
│     └─ NO  → continue                                            │
│  3. Kill any existing nag loop for this session                  │
│  4. Play bell sound                                              │
│  5. If interval > 0, start background nag loop:                  │
│     └─ Loop: sleep → check activity → play if still inactive    │
│  6. Save nag loop PID to file                                    │
└──────────────────────────────────────────────────────────────────┘
       │
       │ User sees permission dialog, hears bell
       ▼
┌─────────────┐
│ User clicks │
│  "Approve"  │
└──────┬──────┘
       │
       │ Fires PreToolUse hook
       ▼
┌──────────────────────────────────────────────────────────────────┐
│              waiting-activity-permission.sh                       │
│                                                                   │
│  1. Read session_id from stdin                                   │
│  2. Write current timestamp to activity file                     │
│  3. Kill nag loop if running (read PID, send SIGTERM)           │
└──────────────────────────────────────────────────────────────────┘
       │
       │ Meanwhile, nag loop (if still running):
       ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Nag Loop (background)                          │
│                                                                   │
│  while true:                                                      │
│    sleep $INTERVAL                                                │
│    check activity file                                            │
│    if activity_time > permission_request_time:                   │
│      exit  ← User responded, stop nagging                        │
│    play bell                                                      │
└──────────────────────────────────────────────────────────────────┘
```

### Stop Hook Flow

```
┌─────────────┐
│ Claude Code │
│  finishes   │
│  response   │
└──────┬──────┘
       │
       │ Fires Stop hook
       ▼
┌──────────────────────────────────────────────────────────────────┐
│                  waiting-notify-stop.sh                           │
│                                                                   │
│  1. Read session_id from stdin                                   │
│  2. Kill any existing nag loop                                   │
│  3. Record current time as "stop_time"                           │
│  4. Start background process:                                    │
│     ├─ Sleep for grace_period (e.g., 5 minutes)                 │
│     ├─ Check: was there activity after stop_time?               │
│     │   ├─ YES → exit (user responded)                          │
│     │   └─ NO  → user is AFK, play bell                         │
│     └─ Start nag loop with activity checks                      │
└──────────────────────────────────────────────────────────────────┘
```

---

## Session Management

Each Claude Code session is tracked independently using session IDs:

```
Session ID extraction (from hook JSON context):
  SESSION_ID=$(echo "$HOOK_INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)

  Fallback if not found:
  SESSION_ID=$(echo "$HOOK_INPUT" | md5sum | cut -c1-8)
```

**Per-session files:**
- `/tmp/waiting-nag-{session}.pid` - Background process ID
- `/tmp/waiting-activity-permission-{session}` - Last activity timestamp
- `/tmp/waiting-activity-stop-{session}` - Last activity timestamp
- `/tmp/waiting-stop-time-{session}` - When Stop hook fired

This enables multiple terminals running Claude Code simultaneously without interference.

---

## File Structure

```
waiting/
├── src/waiting/
│   ├── __init__.py              # Package marker (empty)
│   ├── cli.py                   # All application code (~1100 lines)
│   └── bell.wav                 # Bundled notification sound
│
├── pyproject.toml               # Package metadata, dependencies, build config
├── README.md                    # User documentation
├── CLAUDE.md                    # Developer documentation (for Claude Code)
└── ARCHITECTURE.md              # This document

Generated at runtime:
~/.waiting.json                  # User configuration
~/.claude/settings.json          # Claude Code hook registration
~/.claude/hooks/
├── waiting-notify-permission.sh
├── waiting-notify-stop.sh
├── waiting-notify-idle.sh
├── waiting-activity-submit.sh
└── waiting-activity-permission.sh

/tmp/
├── waiting-nag-{session}.pid
├── waiting-activity-permission-{session}
├── waiting-activity-stop-{session}
└── waiting-stop-time-{session}
```

---

## CLI Code Organization

`src/waiting/cli.py` is organized into logical sections:

| Lines | Section | Functions |
|-------|---------|-----------|
| 12-22 | Constants | `DEFAULT_CONFIG` |
| 25-55 | Config I/O | `get_config_path()`, `load_config()`, `save_config()` |
| 57-89 | Claude Settings | `get_claude_settings_path()`, `get_hooks_dir()`, `load_claude_settings()`, `save_claude_settings()` |
| 92-223 | Stop Script | `create_stop_notify_script()` |
| 225-349 | Permission Script | `create_permission_notify_script()` |
| 352-468 | Idle Script | `create_idle_notify_script()` |
| 471-545 | Activity Scripts | `create_activity_scripts()` |
| 548-555 | Hook Detection | `_is_waiting_hook()` |
| 557-679 | Hook Setup | `setup_hooks()` |
| 682-704 | Hook Removal | `remove_hook()` |
| 706-799 | Main Command | `cli()` |
| 801-821 | Disable Command | `disable()` |
| 824-831 | Kill Command | `kill()` |
| 833-897 | Process Mgmt | `_kill_nag_process()` |
| 899-962 | Status Command | `status()` |
| 964-1093 | Configure Command | `configure()` |

---

## Cross-Platform Audio

Scripts detect available audio players at runtime:

```bash
play_sound() {
    if command -v aplay &> /dev/null; then
        aplay -q "$AUDIO_PATH" 2>/dev/null
    elif command -v paplay &> /dev/null; then
        paplay "$AUDIO_PATH" 2>/dev/null
    elif command -v pw-play &> /dev/null; then
        pw-play "$AUDIO_PATH" 2>/dev/null
    elif command -v afplay &> /dev/null; then
        afplay "$AUDIO_PATH" 2>/dev/null
    elif command -v powershell.exe &> /dev/null; then
        # WSL: convert path and use Windows audio
        win_path=$(wslpath -w "$AUDIO_PATH" 2>/dev/null)
        powershell.exe -c "(New-Object Media.SoundPlayer '$win_path').PlaySync()"
    fi
}
```

| Platform | Player | Notes |
|----------|--------|-------|
| Linux (ALSA) | `aplay` | Most common |
| Linux (PulseAudio) | `paplay` | |
| Linux (PipeWire) | `pw-play` | |
| macOS | `afplay` | Built-in |
| WSL | `powershell.exe` | Routes to Windows audio |

---

## MVP Scope

For initial release, only the **Permission hook** is enabled:

```bash
waiting configure --hooks permission
```

This provides:
- Immediate notification when Claude needs tool approval
- Nag loop until user responds
- Automatic stop when user approves

Future additions (Stop, Idle hooks) are implemented but disabled by default.

---

## Limitations & Considerations

1. **Hook Caching**: Claude Code caches hooks at startup. Users must restart Claude after running `waiting` or `waiting disable`.

2. **Process Cleanup**: Background nag loops may become orphaned if Claude Code crashes. `waiting kill` and `waiting disable` clean these up.

3. **No Windows Native Support**: Requires WSL on Windows.

4. **Single Audio Format**: Only WAV files supported (platform audio player limitation).

5. **No Visual Notification**: Audio only—no desktop notifications or visual alerts.
