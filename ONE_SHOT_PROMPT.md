# One-Shot Prompt: Create "waiting" CLI Tool

Create a Python CLI tool called "waiting" that provides audio notifications when Claude Code (Anthropic's CLI coding assistant) needs user input. The tool hooks into Claude Code's hook system to detect waiting states and plays a sound to alert the user.

## Project Structure

```
waiting/
├── pyproject.toml
├── src/
│   └── waiting/
│       ├── __init__.py
│       ├── cli.py
│       └── bell.wav  (bundled notification sound)
```

## Requirements

- Python 3.9+
- Single dependency: `click>=8.0.0`
- Build system: hatchling
- Entry point: `waiting` command

## Core Concept

Claude Code has a hook system that fires shell commands on events like:
- `Stop` - When Claude finishes responding
- `PermissionRequest` - When Claude shows a permission dialog
- `Notification` with matcher `idle_prompt` - After 60s of inactivity
- `UserPromptSubmit` - When user sends a message
- `PreToolUse` - When a tool is about to execute

This tool:
1. Generates shell scripts that play audio notifications
2. Installs those scripts as hooks in `~/.claude/settings.json`
3. Tracks user activity to avoid spamming notifications
4. Supports configurable grace periods, nag intervals, and repeat counts

## Configuration

Store in `~/.waiting.json` (overridable via `WAITING_CONFIG` env var):

```json
{
  "audio": "default",
  "interval": 30,
  "max_nags": 0,
  "volume": 100,
  "enabled_hooks": ["stop", "permission", "idle"],
  "grace_period_stop": 300,
  "grace_period_permission": 10,
  "grace_period_idle": 0
}
```

- `audio`: "default" uses bundled bell.wav, or path to custom .wav
- `interval`: Seconds between repeated notifications (0 = no repeat)
- `max_nags`: Maximum repeats (0 = unlimited)
- `enabled_hooks`: Which hook types to enable
- Grace periods: Seconds of inactivity required before bell plays

## Hook Behavior Details

### Stop Hook (grace_period_stop: 300s default)
"Wait and see" logic:
1. Record timestamp when Claude finishes responding
2. Wait for grace_period in background
3. Check if user was active since Stop fired
4. If no activity → play bell (user is AFK)

### Permission Hook (grace_period_permission: 10s default)
"Wait and see" with pending marker:
1. Create pending marker file
2. Wait grace_period in background
3. Check if user was active since dialog opened
4. If no activity → play bell

### Idle Hook (grace_period_idle: 0s default)
- Claude's `idle_prompt` already has 60s built-in delay
- Optional additional grace period checking
- Plays immediately when triggered (after 60s idle)

### Activity Tracking

Session-specific files in `/tmp/`:
- `waiting-activity-stop-{session_id}` - Stop hook activity
- `waiting-activity-permission-{session_id}` - Permission hook activity
- `waiting-nag-{session_id}.pid` - Running nag process PID
- `waiting-stop-time-{session_id}` - When Stop hook fired
- `waiting-pending-{session_id}` - Permission dialog pending marker
- `waiting-heartbeat-{session_id}` - Proves Claude is alive

Session ID extraction from hook stdin:
```bash
SESSION_ID=$(echo "$HOOK_INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)
if [ -z "$SESSION_ID" ]; then
    SESSION_ID=$(echo "$HOOK_INPUT" | md5sum | cut -c1-8)
fi
```

### Nag Loop
- Background process that repeats sound at interval
- Checks for user activity and stops when detected
- Max lifetime of 10 minutes (orphan protection)
- Heartbeat mechanism (2 min timeout) to detect dead Claude sessions
- Killed via `pkill -f "waiting-nag-{session_id}"`

## Cross-Platform Audio Detection

Scripts auto-detect available audio players in order:
1. `paplay` (PulseAudio) - with volume control
2. `pw-play` (PipeWire) - with volume control
3. `aplay` (ALSA) - no volume control
4. `afplay` (macOS) - with volume control
5. `powershell.exe` (WSL) - Windows path conversion via wslpath

## CLI Commands

### `waiting` (main command)
Enable notifications with current config. Options:
- `--audio PATH` - Custom audio file
- `--interval INT` - Nag interval seconds
- `--max-nags INT` - Max repeats

### `waiting disable`
Remove all hooks and scripts, kill nag processes.

### `waiting kill`
Stop current nag loop without disabling hooks.

### `waiting status`
Show current configuration and active hooks.

### `waiting configure`
Modify settings. Options:
- `--audio PATH` - Set audio file ("default" for bundled)
- `--interval INT` - Set nag interval
- `--max-nags INT` - Set max repeats
- `--grace-stop INT` - Stop hook grace period
- `--grace-permission INT` - Permission hook grace period
- `--grace-idle INT` - Idle hook grace period
- `--enable-hook {stop,permission,idle}` - Enable a hook
- `--disable-hook {stop,permission,idle}` - Disable a hook
- `--hooks LIST` - Set all enabled hooks (comma-separated)
- `--show` - Show config without modifying
- `--reset` - Reset to defaults

## Generated Scripts

Place in `~/.claude/hooks/`:

1. **waiting-notify-stop.sh** - Stop hook with wait-and-see
2. **waiting-notify-permission.sh** - Permission hook with pending marker
3. **waiting-notify-idle.sh** - Idle hook
4. **waiting-activity-submit.sh** - UserPromptSubmit activity tracking
5. **waiting-activity-tooluse.sh** - PreToolUse activity tracking

Scripts must:
- Be executable (chmod +x)
- Read JSON from stdin to get session_id
- Handle background nag loops properly
- Clean up PID files on exit
- Use SIGTERM trap for clean termination

## Claude Settings Integration

Add hooks to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "/path/to/script.sh", "timeout": 10}]}],
    "PermissionRequest": [...],
    "Notification": [{"matcher": "idle_prompt", "hooks": [...]}],
    "UserPromptSubmit": [...],
    "PreToolUse": [...]
  }
}
```

## Key Implementation Details

1. **Script generation uses f-strings** - Python generates bash scripts with embedded config values

2. **Activity scripts update both stop and permission files** - UserPromptSubmit updates both, PreToolUse updates permission only (but always updates activity now to prevent false AFK detection)

3. **Pending marker distinguishes user approvals** - PermissionRequest creates marker, PreToolUse checks for it

4. **Hook identification** - `_is_waiting_hook()` checks if command contains "waiting-notify", "waiting-stop", or "waiting-activity"

5. **Background process management** - Uses `pkill -f "waiting-nag-{session}"` pattern matching for reliable process termination

6. **Wrapper script for detachment** - Permission hook uses wrapper to properly detach nag process from parent

7. **1-second buffer on activity timestamps** - Handles same-second cascading dialogs

## pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "waiting"
version = "0.1.0"
description = "Notify when your AI coding assistant is waiting for input"
requires-python = ">=3.9"
dependencies = ["click>=8.0.0"]

[project.scripts]
waiting = "waiting.cli:cli"

[tool.hatch.build.targets.wheel]
packages = ["src/waiting"]
artifacts = ["src/waiting/*.wav"]

[tool.hatch.build.targets.sdist]
include = ["src/waiting/*.wav"]
```

## Implementation Notes

- Use `click.group(invoke_without_command=True)` for main command that enables when no subcommand
- Load config with defaults for missing values (merge user config over DEFAULT_CONFIG)
- Kill existing nag processes before setting up fresh hooks
- Clean up legacy hook types (PostToolUse) when removing hooks
- Handle both new session-specific and legacy single-file formats for backwards compatibility
- Scripts must work on Linux (aplay/paplay/pw-play), macOS (afplay), and WSL (powershell.exe)

Create the complete implementation in a single `cli.py` file with all the script generation functions, hook management, and CLI commands. The tool should work immediately after `pip install -e .` followed by running `waiting`.
--------------------------------
I copied and pasted below
------------------------------

 Good question. Looking at the prompt I created, it treats all three hooks (stop, permission, idle) somewhat equally. It doesn't reflect that the permission hook has been the most complex and actively debugged one.

  The prompt says briefly:

  ### Permission Hook (grace_period_permission: 10s default)
  "Wait and see" with pending marker:
  1. Create pending marker file
  2. Wait grace_period in background
  3. Check if user was active since dialog opened
  4. If no activity → play bell

  But the actual permission hook implementation has much more sophistication that isn't captured:

  - Wrapper script pattern for proper process detachment (disown, /dev/null redirection)
  - pkill -f marker pattern (waiting-nag-{session}) for reliable termination
  - SIGTERM trap that kills background sound processes for instant response
  - Sound plays in background (&) so trap can fire during playback
  - 1-second sleep increments in nag loop for responsive termination (vs full interval sleep)
  - Debug logging throughout (/tmp/waiting-debug.log)
  - Pending file cleanup in PreToolUse

  The recent commits also show this is where the active work is:
  - Fix permission hook not triggering bell - properly detach nag process
  - still not working, added kill all on launch, trying to fix stray bells

  Would you like me to update the prompt to:
  1. Emphasize permission hook as the primary/most sophisticated hook
  2. Include the actual bash script template for the permission hook (with all the nuances)
  3. Simplify to MVP scope - Maybe just the permission hook first, others later?