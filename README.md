# waiting

Plays a sound notification when Claude Code needs your attention and you're not responding.

Perfect for when you step away from your desk while Claude is working on a long task.

## Quick Start

```bash
# Install
pip install -e .

# Enable notifications
waiting

# Restart Claude Code for hooks to take effect
```

That's it! You'll now get audio alerts when Claude needs you.

## Usage

```bash
waiting                  # Enable notifications
waiting disable          # Disable all notifications
waiting status           # View current config
waiting kill             # Stop current alert
waiting configure --show # View full config as JSON
```

**Important:** Restart Claude Code after enabling/disabling.

## Configuration

All settings in `~/.waiting.json`:

```json
{
  "audio": "default",
  "volume": 100,
  "enabled_hooks": ["stop", "idle"],
  "grace_period": 30,
  "interval": 30,
  "max_nags": 0
}
```

### Options

| Option | Default | CLI Flag | Description |
|--------|---------|----------|-------------|
| `audio` | `"default"` | `--audio` | Sound file or `"default"` |
| `volume` | `100` | `--volume` | Volume 1-100 |
| `grace_period` | `30` | `--grace-period` | Seconds before first bell |
| `interval` | `30` | `--interval` | Seconds between bell repeats |
| `max_nags` | `0` | `--max-nags` | Max repeats (0=unlimited) |
| `enabled_hooks` | `["stop", "idle"]` | `--enable-hook`, `--disable-hook` | Which hooks are active |

### Examples

```bash
# Less aggressive (longer waits)
waiting configure --grace-period 120 --interval 60

# More aggressive (shorter waits)
waiting configure --grace-period 10 --interval 15

# Limit repeats
waiting configure --max-nags 3

# Enable permission hook
waiting configure --enable-hook permission

# Disable stop hook
waiting configure --disable-hook stop

# Set specific hooks
waiting configure --hooks stop,idle

# Quiet mode
waiting configure --volume 30

# Reset to defaults
waiting configure --reset
```

## Hooks

Three types of events can trigger notifications:

### Stop Hook (enabled by default)

**Triggers:** Claude finishes responding

After grace period, bell plays. Repeats until you respond.

### Idle Hook (enabled by default)

**Triggers:** Claude idle for 60+ seconds

Note: Claude has a built-in 60-second delay before firing idle.

### Permission Hook (NOT enabled by default)

**Triggers:** Claude shows a permission dialog

Plays once (no repeat). Not enabled by default because most tools are auto-approved.

Enable with:
```bash
waiting configure --enable-hook permission
```

## How It Works

1. Grace period passes after event
2. Bell plays
3. Bell repeats every `interval` seconds
4. When you respond, bell stops immediately

Activity is detected via:
- Sending a message to Claude
- Approving/denying a permission

## Troubleshooting

```bash
# Check status
waiting status

# Check audio player
which paplay || which aplay || which afplay

# Reset and try again
waiting disable
waiting
# Restart Claude Code
```

## Requirements

- Python 3.9+
- Audio player (auto-detected):
  - `paplay` (PulseAudio)
  - `pw-play` (PipeWire)
  - `aplay` (ALSA)
  - `afplay` (macOS)
  - `powershell.exe` (WSL)
