# Waiting - Audio Notification System for Claude Code

An audio notification system that plays a bell sound when Claude Code permission dialogs appear and the user doesn't respond within a grace period.

## Overview

**Waiting** solves the problem of missed permission dialogs in Claude Code. When you step away from your desk and Claude needs permission to execute an action (run a command, read a file, etc.), a dialog appears but you may not notice it. With Waiting enabled, if you don't respond within the grace period (default 30 seconds), an audible bell notification plays to alert you.

## Quick Start

### Installation

```bash
pip install -e .
waiting enable
```

Then restart Claude Code for the hooks to take effect.

### First Use

1. Run a command in Claude Code that requires permission
2. Don't respond to the permission dialog
3. After 30 seconds, you'll hear a bell notification
4. Respond to the permission dialog and the bell will stop immediately

### Configuration

Edit `~/.waiting.json` to customize the behavior:

```json
{
  "grace_period": 30,
  "volume": 100,
  "audio": "default"
}
```

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| `grace_period` | 30 | 1-3600 | Seconds to wait before playing bell |
| `volume` | 100 | 1-100 | Bell volume percentage |
| `audio` | "default" | path or "default" | Audio file to play or system default |

## Features

- **Cross-platform**: Works on Linux, macOS, and WSL
- **Zero dependencies**: Uses only Python 3.9+ standard library
- **Hook-driven**: Integrates with Claude Code's permission system
- **Configurable**: Customize grace period, volume, and audio file
- **Graceful**: Continues working even if audio unavailable
- **Instant response**: Bell stops immediately when you respond to dialog

## Architecture Overview

```
Claude Code Permission System
         ↓
    Hook Event Triggered
         ↓
    ┌────────────────────────────┐
    │  Waiting Hook Script        │
    │  (waiting-notify-*.sh)      │
    └────────────────────────────┘
         ↓
    ┌────────────────────────────┐
    │  Waiting Python Module      │
    │  - Config loader            │
    │  - Audio player             │
    │  - State management         │
    └────────────────────────────┘
         ↓
    ┌────────────────────────────┐
    │  Platform Audio System      │
    │  - Linux: paplay/pw-play    │
    │  - macOS: afplay            │
    │  - Windows: PowerShell      │
    └────────────────────────────┘
```

### Key Components

#### Configuration Management (`config.py`)
- Loads and validates configuration from `~/.waiting.json`
- Provides sensible defaults
- Strict type validation (grace_period > 0, volume 1-100)

#### Hook Management (`hooks/manager.py`)
- Installs/removes hook scripts to `~/.claude/hooks/`
- Registers hooks in `~/.claude/settings.json`
- Two hooks: PermissionRequest (notify) and PreToolUse (cancel)

#### Audio System (`audio.py`, `audio_players/`)
- Platform detection and player selection
- Supports: PulseAudio, PipeWire, ALSA, AFPlay, PowerShell
- Audio file resolution (system sounds or custom)
- Process management (play/kill)

#### State Management (`state.py`)
- Temporary files for inter-process communication
- Session-based isolation
- PID tracking for audio processes

#### CLI Interface (`cli.py`)
- User-friendly command-line interface
- Commands: `waiting`, `waiting enable`, `waiting disable`, `waiting status`
- Clear feedback and error messages

## How It Works

### Flow Diagram

```
1. User triggers permission dialog in Claude Code
   └─→ PermissionRequest hook event fires
       └─→ waiting-notify-permission.sh executes

2. Hook script:
   ├─→ Loads configuration (grace_period, volume, audio)
   ├─→ Waits for grace period (e.g., 30 seconds)
   ├─→ Checks if user responded (via activity hook)
   └─→ If no response → play audio via Python module

3. User responds to dialog
   └─→ PreToolUse hook event fires
       └─→ waiting-activity-tooluse.sh executes
           └─→ Signals running audio to stop immediately

4. Audio stops and system returns to idle
```

### Session Isolation

Each Claude Code session has a unique ID that Waiting uses to isolate state. This allows multiple concurrent sessions without interference.

- Stop signal file: `/tmp/waiting-stop-{session_id}`
- Audio PID file: `/tmp/waiting-audio-{session_id}.pid`

## Platform Support

| Platform | Status | Audio Backend |
|----------|--------|---------------|
| Linux (PulseAudio) | Tested | paplay |
| Linux (PipeWire) | Tested | pw-play |
| Linux (ALSA) | Tested | aplay |
| macOS | Tested | afplay |
| WSL (Windows) | Tested | PowerShell |

## Documentation

- **[INSTALLATION.md](./INSTALLATION.md)** - Detailed setup and configuration
- **[USAGE.md](./USAGE.md)** - CLI commands, configuration options, and troubleshooting
- **[DEVELOPMENT.md](./DEVELOPMENT.md)** - For contributors and developers

## Commands

```bash
waiting                  # Enable notifications (install hooks)
waiting enable          # Same as 'waiting'
waiting disable         # Disable notifications (remove hooks)
waiting status          # Show configuration and hook status
waiting --help          # Show help message
```

## Project Status

- **Version**: 0.1.0 (MVP)
- **Tests**: 238+ passing tests across all components
- **Implementation**: Complete with all core features
- **Stability**: Production-ready for MVP phase

## Design Philosophy

Waiting follows these principles:

1. **No external dependencies** - Uses only Python 3.9+ standard library
2. **Stateless design** - No background daemon or persistent process
3. **Hook-driven** - Integrates with Claude Code's native event system
4. **Graceful degradation** - Continues working even if audio unavailable
5. **Functional style** - Strict type hints, immutable data structures
6. **User-focused** - Clear feedback, sensible defaults, easy configuration

## License

See repository for license information.

## Contributing

See [DEVELOPMENT.md](./DEVELOPMENT.md) for contribution guidelines.

## Support

For issues, questions, or feature requests, refer to the repository's issue tracker or documentation.
