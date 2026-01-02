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

```
Claude needs permission (tool use, question, etc.)
        ↓
PermissionRequest hook fires
        ↓
Grace period check: responded recently?
        ↓
YES → Skip immediate sound, start nag loop
NO  → Play sound immediately, start nag loop
        ↓
Nag every 15s until you respond
        ↓
You respond → PreToolUse fires → nag stops
```

## Configuration

Settings are stored in `~/.waiting.json`:

```json
{
  "audio": "default",
  "grace_period": 60,
  "interval": 15,
  "max_nags": 0
}
```

| Setting | Default | Description |
|---------|---------|-------------|
| `audio` | `"default"` | Sound file path, or `"default"` for bundled bell |
| `grace_period` | `60` | Seconds after responding to suppress immediate alert |
| `interval` | `15` | Seconds between repeated nags (0 = no repeat) |
| `max_nags` | `0` | Max repeat alerts (0 = unlimited) |

### Configure via CLI

```bash
waiting configure                     # View current settings
waiting configure --interval 30       # Change nag interval
waiting configure --grace-period 30   # Change grace period
waiting configure --audio /path/to/sound.wav  # Custom sound
waiting configure --reset             # Reset to defaults
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

### One-off Overrides

```bash
waiting --interval 10              # Override interval for this run
waiting --grace-period 0           # Disable grace period for this run
waiting --audio /path/to/bell.wav  # Use different sound for this run
```

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
- Increase grace period: `waiting configure --grace-period 120`
- Increase interval: `waiting configure --interval 60`

**Not getting notifications?**
- Check status: `waiting status`
- Re-enable: `waiting`
- Check hooks: `cat ~/.claude/settings.json | grep -A 20 hooks`
