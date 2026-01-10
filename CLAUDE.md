# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**waiting** is a notification system for Claude Code that plays audio alerts when Claude needs user attention (finished responding, waiting for permission, or idle). It works by installing bash hook scripts that Claude Code triggers on various events.

## Build & Development Commands

```bash
# Install in development mode
pip install -e .

# Run the CLI
waiting                  # Enable notifications
waiting disable          # Disable all notifications
waiting status           # View current config and hook health
waiting configure --show # View full config as JSON
waiting doctor --fix     # Diagnose and fix common issues
waiting kill             # Stop current alert without disabling
```

## Architecture

### Core Components

The entire application lives in a single file: `src/waiting/cli.py`

**Key concepts:**

1. **Hook Scripts** - Bash scripts installed to `~/.claude/hooks/` that Claude Code executes on events:
   - `waiting-notify-stop.sh` - Triggered when Claude finishes responding
   - `waiting-notify-permission.sh` - Triggered on permission dialogs
   - `waiting-notify-idle.sh` - Triggered when Claude is idle for 60s+
   - `waiting-activity-submit.sh` - Triggered when user submits a message (kills active nags)
   - `waiting-activity-tooluse.sh` - Triggered on PreToolUse (kills active nags)

2. **Nag Process** - Background bash process that plays audio after grace period, repeating at intervals until user responds. Each hook spawns an inline nag script to `/tmp/waiting-nag-{session_id}.sh`.

3. **Stop Signal Pattern** - Nags poll for `/tmp/waiting-stop-{session_id}` file. Activity hooks create this file to signal nags to exit cleanly. This is more reliable than SIGTERM because SIGKILL doesn't run cleanup traps.

4. **Session Tracking** - Uses session_id from Claude's hook JSON input to track multiple concurrent sessions. Falls back to MD5 hash if session_id missing.

### Temp File Conventions

All state is managed via `/tmp/` files:
- `/tmp/waiting-nag-{session}.pid` - PID of running nag process
- `/tmp/waiting-stop-{session}` - Stop signal file (presence = stop)
- `/tmp/waiting-audio-{session}.pid` - PID of audio player process
- `/tmp/waiting-pending-{session}` - Marks permission dialog open
- `/tmp/waiting-activity-*-{session}` - Timestamp of last user activity

### Configuration

User config stored in `~/.waiting.json`. Settings registered in `~/.claude/settings.json` under the `hooks` key.

Hook version tracking (`HOOK_VERSION` constant) allows detecting outdated hooks when CLI version updates.

### Audio Playback

Cross-platform audio via cascading command detection: `paplay` → `pw-play` → `aplay` → `afplay` → `powershell.exe` (WSL). Audio PID tracked for explicit termination since SIGKILL won't run cleanup traps.

## Hook Event Flow

```
Claude finishes → Stop hook fires → Creates nag process → Grace period
                                                        → Plays audio
User responds → UserPromptSubmit/PreToolUse → Creates stop signal → Nag exits
```

Critical timing: Activity hooks add +1 or +2 second buffer to timestamps to avoid race conditions with hook execution order.
