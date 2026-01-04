# Installing Waiting on macOS

This guide walks you through installing and configuring `waiting` on macOS.

## Prerequisites

- macOS 10.15 (Catalina) or later
- Python 3.9 or later
- Claude Code CLI installed

### Check Python Version

```bash
python3 --version
```

If Python is not installed, install it via Homebrew:

```bash
brew install python@3.11
```

### Check Claude Code

```bash
claude --version
```

If not installed, see [Claude Code installation docs](https://claude.ai/code).

## Installation

### Option 1: Install from PyPI (Recommended)

```bash
pip3 install waiting-notify
```

### Option 2: Install from GitHub

```bash
pip3 install git+https://github.com/USERNAME/waiting.git
```

### Option 3: Install from Source

```bash
git clone https://github.com/USERNAME/waiting.git
cd waiting
pip3 install .
```

## Setup

### 1. Enable Notifications

```bash
waiting
```

You should see:

```
Setting up waiting notification...
  Audio: /path/to/bell.wav
  Interval: 15s
  Max nags: unlimited
  Enabled hooks: permission
  Grace periods:
    Permission hook: 10s
  Scripts: ~/.claude/hooks
  Hooks: ~/.claude/settings.json

Done! Claude Code will nag you when waiting for input.
```

### 2. Restart Claude Code

**Important:** Claude Code caches hooks at startup. You must restart Claude Code for the hooks to take effect.

```bash
# If running in terminal, close and reopen
# Or use Cmd+Q to quit Claude Code completely, then reopen
```

### 3. Verify Setup

```bash
waiting status
```

Should show:

```
Status: ENABLED
  Active hooks: permission
  Scripts: ~/.claude/hooks
```

## Audio on macOS

Waiting uses `afplay` (built into macOS) to play sounds. Test that audio works:

```bash
# Test with the bundled bell
afplay ~/.local/lib/python3.11/site-packages/waiting/bell.wav

# Or test with a system sound
afplay /System/Library/Sounds/Glass.aiff
```

### Custom Sound

To use a different sound:

```bash
# Use a system sound
waiting configure --audio /System/Library/Sounds/Ping.aiff

# Use your own sound (WAV or AIFF)
waiting configure --audio ~/Downloads/my-alert.wav

# Apply changes
waiting
```

### Available System Sounds

macOS includes sounds in `/System/Library/Sounds/`:

```bash
ls /System/Library/Sounds/
```

Common options:
- `Glass.aiff` - Subtle glass tap
- `Ping.aiff` - Classic ping
- `Pop.aiff` - Soft pop
- `Purr.aiff` - Gentle purr
- `Submarine.aiff` - Sonar ping
- `Tink.aiff` - Light tink

## Configuration

### View Current Settings

```bash
waiting configure --show
```

### Adjust Timing

```bash
# Delay before bell plays (default: 10s)
waiting configure --grace-permission 15

# Time between repeat alerts (default: 15s)
waiting configure --interval 30

# Maximum alerts (0 = unlimited)
waiting configure --max-nags 5

# Apply changes
waiting
```

### Reset to Defaults

```bash
waiting configure --reset
waiting
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `waiting` | Enable notifications |
| `waiting status` | Show current status |
| `waiting disable` | Disable notifications |
| `waiting kill` | Stop current alert without disabling |
| `waiting configure` | View/modify settings |
| `waiting --help` | Show all options |

## Troubleshooting

### No Sound Playing

1. **Check volume**: Make sure your Mac's volume is not muted

2. **Test audio manually**:
   ```bash
   afplay /System/Library/Sounds/Glass.aiff
   ```

3. **Check audio file exists**:
   ```bash
   waiting status
   # Look for the Audio: line and verify the path exists
   ls -la /path/to/audio/file
   ```

### Bell Plays But Won't Stop

```bash
# Stop all alert loops
waiting kill

# If that doesn't work, manually kill processes
pkill -f waiting-notify
```

### Hooks Not Working After Install

Claude Code caches hooks at startup. You must:

1. Quit Claude Code completely (Cmd+Q)
2. Reopen Claude Code
3. Verify: `waiting status`

### Permission Denied Errors

If you see permission errors:

```bash
# Make hook scripts executable
chmod +x ~/.claude/hooks/waiting-*.sh
```

### Multiple Terminals

Each Claude Code session is tracked independently. If you have multiple terminals:

- Each terminal has its own alert loop
- `waiting kill` stops alerts in ALL terminals
- Activity in one terminal doesn't affect others

## Uninstall

```bash
# Disable hooks first
waiting disable

# Remove package
pip3 uninstall waiting-notify

# Optional: Remove config file
rm ~/.waiting.json
```

## Getting Help

- Check status: `waiting status`
- View logs: `cat /tmp/waiting-debug.log`
- Report issues: https://github.com/USERNAME/waiting/issues
