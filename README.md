# waiting

Get notified when Claude Code needs your input.

Stop tabbing back to find Claude has been waiting for you for 10 minutes.

## Install

```bash
pip install waiting
```

## Quick Start

```bash
waiting          # Enable notifications
waiting status   # Check if enabled
waiting disable  # Turn off
```

That's it. You'll hear a sound when Claude Code needs your attention.

## How It Works

Waiting uses Claude Code hooks to detect when Claude needs your input:

| Hook | When it fires | Purpose |
|------|---------------|---------|
| `Stop` | Claude finishes responding | Alert if you've been away |
| `PermissionRequest` | Permission dialog shown | Alert for tool approvals |
| `idle_prompt` | 60s of idle (built-in) | Backup reminder |

Each hook has its own grace period - if you were recently active, the bell won't play.

```
Claude finishes responding
        ↓
Stop hook fires
        ↓
Grace period check: active in last 5 min?
        ↓
YES → No bell (you're actively working)
NO  → Play bell, start nag loop
        ↓
Nag every 15s until you respond
        ↓
You respond → activity recorded → nag stops
```

## Configuration

Settings are stored in `~/.waiting.json`:

```json
{
  "audio": "default",
  "interval": 15,
  "max_nags": 0,
  "enabled_hooks": ["stop", "permission", "idle"],
  "grace_period_stop": 300,
  "grace_period_permission": 10,
  "grace_period_idle": 0
}
```

| Setting | Default | Description |
|---------|---------|-------------|
| `audio` | `"default"` | Sound file path, or `"default"` for bundled bell |
| `interval` | `15` | Seconds between repeated nags (0 = no repeat) |
| `max_nags` | `0` | Max repeat alerts (0 = unlimited) |
| `enabled_hooks` | `["stop", "permission", "idle"]` | Which hooks are active |
| `grace_period_stop` | `300` | Grace period for Stop hook (5 min) |
| `grace_period_permission` | `10` | Grace period for Permission hook |
| `grace_period_idle` | `0` | Grace period for idle_prompt hook |

### Grace Periods

The grace period determines how long after your last activity before a hook will trigger:

- **`grace_period_stop: 300`** (5 min) - Only alert if you haven't interacted in 5+ minutes
- **`grace_period_permission: 10`** (10s) - Short delay for permission dialogs
- **`grace_period_idle: 0`** - No extra delay (idle_prompt has built-in 60s)

Activity is recorded when you:
- Submit a message to Claude
- Approve a permission dialog

### Configure via CLI

```bash
waiting configure                          # View current settings
waiting configure --interval 30            # Change nag interval
waiting configure --grace-stop 600         # 10 min grace for Stop hook
waiting configure --grace-permission 30    # 30s grace for permissions
waiting configure --disable-hook idle      # Disable idle hook
waiting configure --enable-hook idle       # Enable idle hook
waiting configure --hooks stop,permission  # Set exact hook list
waiting configure --audio /path/to/sound.wav  # Custom sound
waiting configure --reset                  # Reset to defaults
```

### Custom Config Location

Override with environment variable:

```bash
export WAITING_CONFIG=~/myconfig/waiting.json
```

## Commands

```bash
waiting                  # Enable with current config
waiting status           # Show status and settings
waiting kill             # Stop current nag loop (keeps hooks enabled)
waiting disable          # Disable notifications completely
waiting configure        # View/modify settings
waiting --help           # Show all options
```

## Multi-Terminal Support

Each Claude Code session is tracked independently. Nag loops in one terminal won't interfere with another.

## Requirements

- Python 3.9+
- Claude Code CLI
- Audio player (auto-detected):
  - Linux: `aplay`, `paplay`, or `pw-play`
  - macOS: `afplay`
  - WSL: `powershell.exe` (plays via Windows)

## Uninstall

```bash
waiting disable
pip uninstall waiting
rm ~/.waiting.json  # optional: remove config
```

## Troubleshooting

**No sound playing?**
- Check audio player: `aplay /path/to/sound.wav`
- WSL users: ensure PulseAudio or use PowerShell fallback

**Too many notifications?**
- Increase grace period: `waiting configure --grace-stop 600`
- Disable idle hook: `waiting configure --disable-hook idle`

**Not getting notifications?**
- Check status: `waiting status`
- Re-enable: `waiting`
- Restart Claude Code (hooks are cached at startup)

**Bell keeps playing after responding?**
- Run `waiting kill` to stop all nag loops
- Check for orphaned processes: `ps aux | grep waiting`
