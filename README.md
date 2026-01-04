# waiting

Plays a sound when Claude Code needs permission and you haven't responded.

## Install

```bash
pip install -e .
```

## Usage

```bash
waiting          # Enable notifications
waiting disable  # Disable notifications
waiting status   # Check if enabled
```

Restart Claude Code after enabling for hooks to take effect.

## Configuration

```bash
waiting configure --show              # View current config
waiting configure --interval 60       # Nag every 60 seconds
waiting configure --grace-period 15   # Wait 15 seconds before first nag
waiting configure --max-nags 5        # Stop after 5 nags (0 = unlimited)
waiting configure --audio /path/to.wav  # Custom sound
```

Config stored in `~/.waiting.json`.

## How It Works

Claude Code hooks trigger shell scripts when:
- Permission dialog appears → starts a background nag process
- User approves tool or sends message → kills the nag process

The nag process waits for the grace period, then plays a bell sound repeatedly until you respond.

## Requirements

- Python 3.9+
- Audio player: `aplay`, `paplay`, `afplay`, or PowerShell (WSL)
