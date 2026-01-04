# One-Shot Prompt: Create "waiting" CLI Tool (MVP)

Create a Python CLI tool called "waiting" that plays an audio notification when Claude Code shows a permission dialog and the user hasn't responded.

## Project Structure

```
waiting/
├── pyproject.toml
├── src/
│   └── waiting/
│       ├── __init__.py
│       ├── cli.py
│       └── bell.wav
```

## The Problem

Claude Code often needs permission to run commands. If you're AFK, you won't know it's waiting. This tool plays a sound to get your attention.

## How It Works

Claude Code has a hook system. We install shell scripts that fire on:
1. **PermissionRequest** - When permission dialog appears
2. **PreToolUse** - When user approves (tool about to run)
3. **UserPromptSubmit** - When user sends a message

The permission hook:
1. Creates a "pending" marker file
2. Waits 10 seconds (grace period)
3. Checks if user responded (activity file updated)
4. If no response → plays bell, starts nag loop
5. Nag loop repeats every 30s until user responds

## Configuration

`~/.waiting.json`:
```json
{
  "audio": "default",
  "interval": 30,
  "max_nags": 0,
  "grace_period": 10
}
```

## CLI Commands

- `waiting` - Enable notifications
- `waiting disable` - Remove hooks and scripts
- `waiting status` - Show if enabled
- `waiting configure --show` - Show config

## Key Files

Scripts go in `~/.claude/hooks/`:
- `waiting-notify-permission.sh` - Main notification script
- `waiting-activity-submit.sh` - Records activity on user message
- `waiting-activity-tooluse.sh` - Records activity on tool approval

Temp files in `/tmp/`:
- `waiting-pending-{session}` - Permission dialog is open
- `waiting-activity-{session}` - Last activity timestamp
- `waiting-nag-{session}.pid` - Running nag process

## The Permission Hook Script

This is the critical piece. Generate this bash script:

```bash
#!/bin/bash
# Waiting - Permission hook with wait-and-see logic

INTERVAL=30
MAX_NAGS=0
DELAY=10
AUDIO_PATH="/path/to/bell.wav"

# Get session ID from stdin JSON
HOOK_INPUT=$(cat)
SESSION_ID=$(echo "$HOOK_INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)
if [ -z "$SESSION_ID" ]; then
    SESSION_ID=$(echo "$HOOK_INPUT" | md5sum | cut -c1-8)
fi

# Session-specific files
NAG_MARKER="waiting-nag-$SESSION_ID"
PID_FILE="/tmp/$NAG_MARKER.pid"
PENDING_FILE="/tmp/waiting-pending-$SESSION_ID"
ACTIVITY_FILE="/tmp/waiting-activity-$SESSION_ID"

now=$(date +%s)

# Kill any existing nag for this session
pkill -f "$NAG_MARKER" 2>/dev/null
rm -f "$PID_FILE"
sleep 0.2

# Mark that permission dialog is open
echo "$now" > "$PENDING_FILE"

# Create nag script with session marker in filename (for pkill -f)
NAG_SCRIPT="/tmp/$NAG_MARKER.sh"

cat > "$NAG_SCRIPT" << 'NAGEOF'
#!/bin/bash
# ... nag loop implementation ...
# Key points:
# - trap SIGTERM for instant kill
# - play sound in background (&) so trap fires during playback
# - sleep in 1-second increments, check PID file each second
# - check activity file: if activity >= start_time, user responded, exit
# - max lifetime 10 minutes (orphan protection)
NAGEOF

chmod +x "$NAG_SCRIPT"

# Run detached (crucial for hook to return quickly)
nohup "$NAG_SCRIPT" > /dev/null 2>&1 &
echo $! > "$PID_FILE"
disown
```

## Activity Scripts

**UserPromptSubmit** (user sent message):
```bash
#!/bin/bash
HOOK_INPUT=$(cat)
SESSION_ID=$(echo "$HOOK_INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)
# ... fallback ...

# Update activity timestamp
echo "$(date +%s)" > "/tmp/waiting-activity-$SESSION_ID"

# Kill nag
pkill -f "waiting-nag-$SESSION_ID" 2>/dev/null
rm -f "/tmp/waiting-nag-$SESSION_ID.pid"
```

**PreToolUse** (tool approved/running):
```bash
#!/bin/bash
# Same pattern - update activity, kill nag, remove pending file
```

## Cross-Platform Audio

Detect available player:
```bash
play_sound() {
    if command -v aplay &> /dev/null; then
        aplay -q "$AUDIO_PATH" 2>/dev/null &
    elif command -v paplay &> /dev/null; then
        paplay "$AUDIO_PATH" 2>/dev/null &
    elif command -v afplay &> /dev/null; then
        afplay "$AUDIO_PATH" 2>/dev/null &
    elif command -v powershell.exe &> /dev/null; then
        win_path=$(wslpath -w "$AUDIO_PATH" 2>/dev/null)
        powershell.exe -c "(New-Object Media.SoundPlayer '$win_path').PlaySync()" &
    fi
}
```

## Claude Settings Integration

Add to `~/.claude/settings.json`:
```json
{
  "hooks": {
    "PermissionRequest": [{
      "matcher": "",
      "hooks": [{"type": "command", "command": "~/.claude/hooks/waiting-notify-permission.sh", "timeout": 10}]
    }],
    "PreToolUse": [{
      "matcher": "",
      "hooks": [{"type": "command", "command": "~/.claude/hooks/waiting-activity-tooluse.sh", "timeout": 5}]
    }],
    "UserPromptSubmit": [{
      "matcher": "",
      "hooks": [{"type": "command", "command": "~/.claude/hooks/waiting-activity-submit.sh", "timeout": 5}]
    }]
  }
}
```

## pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "waiting"
version = "0.1.0"
description = "Notify when Claude Code needs permission"
requires-python = ">=3.9"
dependencies = ["click>=8.0.0"]

[project.scripts]
waiting = "waiting.cli:cli"

[tool.hatch.build.targets.wheel]
packages = ["src/waiting"]
artifacts = ["src/waiting/*.wav"]
```

## Critical Implementation Details

1. **Nag script filename contains session ID** - Enables `pkill -f "waiting-nag-{session}"` to kill the right process

2. **Process must fully detach** - Use `nohup ... &` + `disown` so hook returns quickly (timeout is 10s)

3. **SIGTERM trap in nag script** - So approval kills sound immediately, not after interval

4. **Sound plays in background** - `aplay ... &` so SIGTERM trap can fire during playback

5. **1-second sleep increments** - Instead of `sleep 30`, loop `sleep 1` 30 times, checking PID file each second for responsive termination

6. **Activity timestamp with +1 buffer** - `$(($(date +%s) + 1))` handles same-second cascading dialogs

7. **Pending file** - Distinguishes user approval from auto-approved tools

## Implementation

Create `cli.py` with:
- `load_config()` / `save_config()` - JSON config management
- `create_permission_script()` - Generate the notification script
- `create_activity_scripts()` - Generate submit and tooluse scripts
- `setup_hooks()` - Add hooks to Claude settings
- `remove_hooks()` - Clean up hooks and scripts
- CLI commands using Click

The tool should work after:
```bash
pip install -e .
waiting
# (restart Claude Code to pick up hooks)
```
