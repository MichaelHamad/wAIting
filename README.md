# waiting

Plays a sound when Claude Code needs your attention and you haven't responded.

## Install

```bash
pip install -e .
```

## Usage

```bash
waiting          # Enable notifications
waiting disable  # Disable notifications
waiting status   # Check status and current config
waiting kill     # Stop current nag sound without disabling
```

Restart Claude Code after enabling for hooks to take effect.

## Configuration

Config is stored in `~/.waiting.json`. Edit directly or use the CLI:

```bash
waiting configure --show      # View current config as JSON
waiting configure --reset     # Reset to defaults
```

### All Options

| Option | Default | Description |
|--------|---------|-------------|
| `audio` | `"default"` | Sound file path, or `"default"` for bundled bell.wav |
| `interval` | `30` | Seconds between repeated bell sounds |
| `max_nags` | `0` | Max times to play bell (0 = unlimited) |
| `volume` | `100` | Volume percentage (1-100) |
| `enabled_hooks` | `["stop", "permission", "idle"]` | Which hooks are active |
| `grace_period_stop` | `300` | Seconds to wait after Claude stops before bell |
| `grace_period_permission` | `10` | Seconds to wait after permission dialog before bell |
| `grace_period_idle` | `0` | Extra seconds after Claude's 60s idle detection |

### Example ~/.waiting.json

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

### CLI Examples

```bash
# Change nag interval
waiting configure --interval 60

# Change grace periods
waiting configure --grace-permission 5
waiting configure --grace-stop 120

# Volume and audio
waiting configure --volume 50
waiting configure --audio /path/to/sound.wav

# Enable/disable specific hooks
waiting configure --disable-hook stop
waiting configure --enable-hook idle
waiting configure --hooks permission,idle   # Set exactly which hooks are active
```

## Hooks Explained

Three types of Claude Code events can trigger notifications:

### Permission Hook (`permission`)
**Triggers when:** Claude shows a permission dialog (e.g., "Allow tool X?")

**Grace period:** 10 seconds (default)

**Use case:** You stepped away and Claude is waiting for approval. After 10 seconds of no response, bell plays.

### Stop Hook (`stop`)
**Triggers when:** Claude finishes responding

**Grace period:** 300 seconds / 5 minutes (default)

**Use case:** Claude finished a long task while you were AFK. If you don't interact within 5 minutes, bell plays to let you know it's done.

### Idle Hook (`idle`)
**Triggers when:** Claude's built-in `idle_prompt` fires (after 60s of inactivity)

**Grace period:** 0 seconds (default)

**Use case:** Claude has been waiting at a prompt for 60+ seconds. Bell plays immediately since the 60s wait is already built into Claude.

## How Grace Periods Work

Grace periods implement "wait and see" logic:

1. Hook fires (e.g., permission dialog appears)
2. Background process starts and waits for grace period
3. During wait, checks if you responded (sent message or approved tool)
4. If you responded → no bell, process exits silently
5. If no response after grace period → bell plays
6. Bell repeats every `interval` seconds until you respond (or `max_nags` reached)

This prevents annoying you when you're actively working - the bell only plays if you're actually AFK.

## Activity Tracking

Two events are tracked as "user activity":
- **UserPromptSubmit** - You sent a message to Claude
- **PreToolUse** - You approved a tool

When either occurs, any running nag process is killed immediately.

## Requirements

- Python 3.9+
- Audio player (auto-detected in order):
  - `paplay` (PulseAudio) - supports volume
  - `pw-play` (PipeWire) - supports volume
  - `aplay` (ALSA) - no volume control
  - `afplay` (macOS) - supports volume
  - `powershell.exe` (WSL) - Windows audio via PowerShell
