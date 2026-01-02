# Waiting v2 - Recent Changes

## Overview

This document describes the major changes made to the `waiting` notification system, transforming it from a simple bell trigger into a sophisticated, multi-hook notification system with per-hook grace periods and multi-terminal support.

---

## Problems Solved

### 1. Constant Bell Triggering
**Problem:** The bell was firing constantly, even when the user wasn't being presented with a choice.

**Root Cause:** The original `PermissionRequest` hook was being used, but it was unclear when it actually fired. Investigation revealed that `PermissionRequest` only fires when a permission dialog is actually shown (not for auto-approved tools).

**Solution:** Switched to a multi-hook approach using `Stop`, `PermissionRequest`, and `Notification` (idle_prompt) hooks, each serving a specific purpose.

### 2. Cross-Terminal Interference
**Problem:** Multiple Claude Code sessions (terminals) were interfering with each other's nag loops because they shared a single PID file (`/tmp/waiting-nag.pid`).

**Solution:** Made PID and activity files session-specific by extracting the `session_id` from the hook context (passed via stdin as JSON):
- PID files: `/tmp/waiting-nag-<session_id>.pid`
- Activity files: `/tmp/waiting-activity-<session_id>`

### 3. Annoying Alerts After Recent Activity
**Problem:** Users were getting bell notifications seconds after they had just responded, which was annoying.

**Solution:** Implemented per-hook grace periods. Each hook type now has its own configurable grace period that suppresses notifications if the user was recently active.

---

## Architecture

### Hooks Used

| Hook | Purpose | Script | Default Grace |
|------|---------|--------|---------------|
| `PermissionRequest` | Fires when Claude shows a permission dialog | `waiting-notify-permission.sh` | 10s |
| `Stop` | Fires when Claude finishes responding | `waiting-notify-stop.sh` | 300s (5min) |
| `Notification` (idle_prompt) | Fires after 60s of idle (built-in) | `waiting-notify-idle.sh` | 0s |
| `UserPromptSubmit` | Fires when user submits a message | `waiting-stop.sh` | N/A (stop only) |

### How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER SUBMITS MESSAGE                      │
│                               │                                  │
│                               ▼                                  │
│                    UserPromptSubmit fires                        │
│                               │                                  │
│                               ▼                                  │
│               waiting-stop.sh runs:                              │
│               • Records timestamp to activity file               │
│               • Kills any running nag loop                       │
│                               │                                  │
│                               ▼                                  │
│                      CLAUDE WORKS...                             │
│                               │                                  │
│              ┌────────────────┼────────────────┐                │
│              ▼                ▼                ▼                │
│      Permission needed?   Claude done?    60s idle?             │
│              │                │                │                │
│              ▼                ▼                ▼                │
│      PermissionRequest    Stop hook     Notification            │
│         fires              fires       (idle_prompt)            │
│              │                │                │                │
│              ▼                ▼                ▼                │
│      Check grace:       Check grace:    Check grace:            │
│      10s elapsed?       300s elapsed?   0s elapsed?             │
│              │                │                │                │
│         If YES:          If YES:         If YES:                │
│              │                │                │                │
│              └────────────────┼────────────────┘                │
│                               ▼                                  │
│                    Play bell immediately                         │
│                               │                                  │
│                               ▼                                  │
│                    Start nag loop (every 15s)                   │
│                               │                                  │
│                               ▼                                  │
│                    User responds → back to top                   │
└─────────────────────────────────────────────────────────────────┘
```

### Session Isolation

Each script reads the hook context from stdin to extract the session ID:

```bash
HOOK_INPUT=$(cat)
SESSION_ID=$(echo "$HOOK_INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)

# Fallback to hash if no session_id
if [ -z "$SESSION_ID" ]; then
    SESSION_ID=$(echo "$HOOK_INPUT" | md5sum | cut -c1-8)
fi

# Session-specific files
PID_FILE="/tmp/waiting-nag-$SESSION_ID.pid"
ACTIVITY_FILE="/tmp/waiting-activity-$SESSION_ID"
```

This ensures:
- Each terminal's nag loop is independent
- Stopping one terminal's nag doesn't affect others
- Activity tracking is per-session

---

## Configuration

### Config File
Location: `~/.waiting.json` (override with `WAITING_CONFIG` env var)

### Default Values
```json
{
  "audio": "default",
  "interval": 30,
  "max_nags": 0,
  "grace_period_stop": 300,
  "grace_period_permission": 10,
  "grace_period_idle": 0
}
```

### CLI Commands

```bash
# Enable with defaults
waiting

# Show current config
waiting configure --show

# Set grace periods
waiting configure --grace-stop 600        # 10 minutes
waiting configure --grace-permission 30   # 30 seconds
waiting configure --grace-idle 0          # No extra grace

# Other settings
waiting configure --interval 20           # Nag every 20s
waiting configure --max-nags 5            # Stop after 5 nags
waiting configure --audio /path/to/sound.wav

# Reset to defaults
waiting configure --reset

# Disable completely
waiting disable

# Stop current nag (all sessions)
waiting kill

# Check status
waiting status
```

---

## Files Generated

### Hook Scripts (in `~/.claude/hooks/`)

| File | Purpose |
|------|---------|
| `waiting-notify-stop.sh` | Notify script for Stop hook (5min grace) |
| `waiting-notify-permission.sh` | Notify script for PermissionRequest (10s grace) |
| `waiting-notify-idle.sh` | Notify script for idle_prompt (0s grace) |
| `waiting-stop.sh` | Stop script (records activity, kills nag) |

### Temporary Files (in `/tmp/`)

| Pattern | Purpose |
|---------|---------|
| `waiting-nag-<session_id>.pid` | PID of nag loop for each session |
| `waiting-activity-<session_id>` | Last activity timestamp per session |

### Claude Settings
Location: `~/.claude/settings.json`

The hooks are registered in Claude Code's settings file and are loaded when Claude Code starts. **You must restart Claude Code after running `waiting` for changes to take effect.**

---

## Grace Period Behavior

The grace period determines how long after your last activity before a hook will trigger a notification:

- **`grace_period_stop: 300`** (5 minutes)
  - After Claude finishes responding, only alert if you haven't interacted in 5+ minutes
  - Prevents annoying bells when you're actively working with Claude

- **`grace_period_permission: 10`** (10 seconds)
  - Permission dialogs need your attention, so short grace period
  - Still gives a brief buffer to prevent double-alerts

- **`grace_period_idle: 0`** (no grace)
  - The `idle_prompt` notification already has a built-in 60-second delay
  - No additional grace period needed

### How Grace is Checked

```bash
if [ -f "$ACTIVITY_FILE" ]; then
    last_activity=$(cat "$ACTIVITY_FILE")
    now=$(date +%s)
    elapsed=$((now - last_activity))
    if [ "$elapsed" -lt "$GRACE_PERIOD" ]; then
        # User was active recently, skip notification
        exit 0
    fi
fi
```

If the user was active within the grace period, the script exits immediately without playing any sound or starting a nag loop.

---

## Kill Behavior

The `waiting kill` command (and `waiting disable`) will:

1. Find all session-specific PID files (`/tmp/waiting-nag-*.pid`)
2. Kill each process and its children
3. Also kill any orphaned processes via `pkill -f waiting-notify`
4. Update all activity files to current time (prevents immediate re-triggering)
5. Clean up legacy single-PID files for backwards compatibility

---

## Troubleshooting

### Bell not triggering at all
1. Check hooks are registered: `cat ~/.claude/settings.json`
2. Restart Claude Code (hooks are cached at startup)
3. Check grace periods aren't too long: `waiting configure --show`

### Bell triggering too often
1. Increase grace periods: `waiting configure --grace-stop 600`
2. Check you're on the latest version with session isolation

### Multiple terminals interfering
1. Ensure you're using the latest version with session-specific PID files
2. Run `waiting` again to regenerate scripts
3. Restart all Claude Code sessions

### Bell won't stop
1. Run `waiting kill` to stop all nag loops
2. Check for orphaned processes: `ps aux | grep waiting`
3. Manually kill if needed: `pkill -f waiting-notify`
