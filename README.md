# Waiting - Audio Notification System for Claude Code

[![Tests Passing](https://img.shields.io/badge/tests-238%2B%20passing-brightgreen)]()
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)]()

An audio notification system that plays a bell sound when Claude Code permission dialogs appear and the user doesn't respond within a grace period.

## The Problem

You're focused on your work in Claude Code when suddenly you need to step away. You return to find a permission dialog waiting for your approval, and Claude has been blocked for the past 10 minutes. With Waiting, you'll get an audible notification after a configurable grace period (default 30 seconds) so you never miss a permission request again.

## The Solution

Waiting integrates with Claude Code's hook system to monitor permission requests. When a dialog appears and you don't respond within the grace period, an audible bell notification plays. When you respond, the notification stops immediately.

## Features

- **Cross-platform**: Works on Linux, macOS, and Windows (WSL)
- **Zero dependencies**: Uses only Python 3.9+ standard library
- **Easy to install**: Single command installation
- **Configurable**: Customize grace period, volume, and audio file
- **Hook-driven**: Integrates with Claude Code's native event system
- **Graceful**: Continues working even if audio unavailable

## Quick Start

### 1. Install

```bash
pip install -e .
```

### 2. Enable

```bash
waiting enable
```

Then restart Claude Code for hooks to take effect.

### 3. Test

Trigger a permission dialog in Claude Code and don't respond. After 30 seconds, you'll hear a bell.

## Documentation

- **[Project Overview](./docs/README.md)** - What is Waiting and how it works
- **[Installation Guide](./docs/INSTALLATION.md)** - Step-by-step setup with system requirements
- **[Usage Guide](./docs/USAGE.md)** - CLI commands, configuration, and troubleshooting
- **[Development Guide](./docs/DEVELOPMENT.md)** - For contributors and developers

## Commands

```bash
waiting              # Enable notifications (install hooks)
waiting disable      # Disable notifications (remove hooks)
waiting status       # Show configuration and hook status
waiting --help       # Show help message
```

## Configuration

Edit `~/.waiting.json` to customize:

```json
{
  "grace_period": 30,  # Wait this many seconds before bell
  "volume": 100,       # Bell volume (1-100%)
  "audio": "default"   # "default" or path to audio file
}
```

See [USAGE Guide](./docs/USAGE.md) for detailed configuration options and examples.

## Architecture

```
Claude Code Permission System
         ↓
    Hook Event Triggered
         ↓
    Waiting Hook Script
         ↓
    Waiting Python Module
         ↓
    Platform Audio System
```

Waiting uses Claude Code's hook system (PermissionRequest and PreToolUse events) to monitor permission dialogs and user responses. When a dialog appears, a hook script starts a timer. If the user doesn't respond within the grace period, the script plays an audio notification. When the user responds, another hook signals the audio to stop immediately.

## System Requirements

- **Python**: 3.9 or higher
- **OS**: Linux, macOS, or Windows (WSL)
- **Audio**: Platform audio system (included on all platforms)
  - Linux: PulseAudio, PipeWire, or ALSA
  - macOS: Built-in (AFPlay)
  - Windows: Built-in (PowerShell)

## Project Status

- **Version**: 0.1.0 (MVP)
- **Tests**: 238+ passing tests
- **Implementation**: Complete with all core features
- **Stability**: Production-ready

## Installation & Setup

For detailed installation instructions including system requirements and troubleshooting, see [INSTALLATION Guide](./docs/INSTALLATION.md).

Quick start:
1. `pip install -e .` - Install package
2. `waiting enable` - Install hooks
3. Restart Claude Code
4. Test with a permission dialog

## Usage Examples

### Default Configuration
```bash
waiting status
# Grace period: 30s, Volume: 100%
```

### Quiet Notifications
```json
{
  "grace_period": 45,
  "volume": 30,
  "audio": "default"
}
```

### Custom Audio File
```json
{
  "grace_period": 30,
  "volume": 80,
  "audio": "~/Sounds/notification.wav"
}
```

For more examples, see [USAGE Guide](./docs/USAGE.md).

## How It Works

### Event Flow

1. **Permission Dialog Appears**
   - Claude Code triggers PermissionRequest hook event
   - Waiting hook script starts grace period timer

2. **Grace Period Elapses**
   - If user hasn't responded, bell notification plays
   - Audio continues playing in background

3. **User Responds**
   - Claude Code triggers PreToolUse hook event (user activity)
   - Waiting hook script signals audio to stop immediately
   - System returns to idle state

### Session Isolation

Each Claude Code session has a unique ID. Waiting uses this for isolated state management:

- Stop signal: `/tmp/waiting-stop-{session_id}`
- Audio PID: `/tmp/waiting-audio-{session_id}.pid`

This prevents interference between concurrent sessions.

## Troubleshooting

### Bell Not Playing
- Verify system audio works: `paplay --help` (Linux) or `afplay -h` (macOS)
- Check system volume isn't muted
- Verify Waiting is enabled: `waiting status`
- See [USAGE Guide - Troubleshooting](./docs/USAGE.md#troubleshooting)

### Hooks Not Triggering
- Restart Claude Code after enabling
- Verify hooks are installed: `ls ~/.claude/hooks/waiting-*.sh`
- Trigger a new permission dialog
- See [INSTALLATION Guide](./docs/INSTALLATION.md#troubleshooting-installation)

For more troubleshooting, see [USAGE Guide](./docs/USAGE.md#troubleshooting).

## Development

For developers interested in contributing or understanding the codebase:

See [DEVELOPMENT Guide](./docs/DEVELOPMENT.md) which includes:
- Development setup
- Running tests
- Code structure
- Contributing guidelines

Quick start for development:

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Check code quality
pytest tests/ --cov=src/waiting --cov-report=html
```

## Architecture & Design

For architectural details, design decisions, and component descriptions, see [Project Overview](./docs/README.md#architecture-overview).

## License

[See LICENSE file for details]

## Contributing

Contributions are welcome! See [DEVELOPMENT Guide](./docs/DEVELOPMENT.md#contributing) for guidelines.

## Support & Issues

- **Documentation**: See `docs/` directory
- **Logs**: Check `~/.waiting.log`
- **Configuration**: See `~/.waiting.json`
- **Status**: Run `waiting status`

---

**Ready to get started?** See [INSTALLATION Guide](./docs/INSTALLATION.md).

**Already installed?** See [USAGE Guide](./docs/USAGE.md).

**Want to contribute?** See [DEVELOPMENT Guide](./docs/DEVELOPMENT.md).
