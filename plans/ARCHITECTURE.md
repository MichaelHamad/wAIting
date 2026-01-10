# Technical Architecture - Waiting Audio Notification System

**Document Type:** System Design & Architecture Overview
**Audience:** Engineers implementing the system
**Last Updated:** 2026-01-10

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Component Architecture](#component-architecture)
3. [Event Flow](#event-flow)
4. [State Management](#state-management)
5. [Hook System Integration](#hook-system-integration)
6. [Audio Playback Strategy](#audio-playback-strategy)
7. [Design Patterns](#design-patterns)
8. [Error Handling](#error-handling)
9. [Security Considerations](#security-considerations)
10. [Performance Characteristics](#performance-characteristics)

---

## System Overview

### Purpose
Waiting detects when Claude Code displays a permission dialog and plays an audible bell notification if the user doesn't respond within a configurable grace period.

### Key Characteristics
- **Zero external dependencies** - no third-party packages required
- **Hook-driven** - uses Claude Code's PermissionRequest and PreToolUse hooks
- **Cross-platform** - Linux (PulseAudio, PipeWire, ALSA), macOS (afplay), Windows/WSL (PowerShell)
- **Stateless design** - no persistent background process, communicates via temp files
- **Graceful degradation** - system continues functioning even if audio unavailable

### System Boundaries
```
Claude Code Hook Events (JSON)
            ↓
Bash Hook Scripts (lightweight)
            ↓
Python Core (config, state, audio)
            ↓
OS Audio Systems (paplay, afplay, etc.)
            ↓
User's Speaker/Headphones
```

---

## Component Architecture

### Component Dependency Map

```
┌─────────────────────────────────────────────────────────────┐
│                    Claude Code                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  PermissionRequest Hook    PreToolUse Hook             │ │
│  └────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┬─
                                                              │
                        ┌───────────────────────────────────┘
                        │
                        ↓
        ┌───────────────────────────────┐
        │  Hook Scripts (Bash)          │
        ├───────────────────────────────┤
        │ • waiting-notify-permission   │ ← Triggered by PermissionRequest
        │ • waiting-activity-tooluse    │ ← Triggered by PreToolUse
        └──────┬────────────────────────┘
               │
        ┌──────┴────────────────────────┐
        │  Temporary State Files (/tmp) │
        ├─────────────────────────────┐─┤
        │ /tmp/waiting-stop-{sid}      │ │ Stop signal
        │ /tmp/waiting-audio-{sid}.pid │ │ Audio process ID
        └──────┬────────────────────────┘
               │
        ┌──────┴──────────────────────────────────┐
        │  Python Waiting Package                 │
        ├──────────────────────────────────────────┤
        │                                           │
        │  ┌─────────────────────────────────────┐ │
        │  │ Configuration                       │ │
        │  │ • config.py (load/validate)         │ │
        │  │ • ~/.waiting.json (user config)     │ │
        │  └─────────────────────────────────────┘ │
        │                                           │
        │  ┌─────────────────────────────────────┐ │
        │  │ State Management                    │ │
        │  │ • state.py (session tracking)       │ │
        │  │ • Temp file operations              │ │
        │  └─────────────────────────────────────┘ │
        │                                           │
        │  ┌─────────────────────────────────────┐ │
        │  │ Audio Playback                      │ │
        │  │ • audio.py (main interface)         │ │
        │  │ • audio_players/ (platform impl)    │ │
        │  │   - linux.py (paplay, pw-play, aplay)
        │  │   - macos.py (afplay)               │ │
        │  │   - windows.py (powershell)         │ │
        │  └─────────────────────────────────────┘ │
        │                                           │
        │  ┌─────────────────────────────────────┐ │
        │  │ Hook Management                     │ │
        │  │ • hooks/manager.py (install/remove) │ │
        │  │ • hooks/scripts/ (templates)        │ │
        │  └─────────────────────────────────────┘ │
        │                                           │
        │  ┌─────────────────────────────────────┐ │
        │  │ CLI Interface                       │ │
        │  │ • cli.py (commands)                 │ │
        │  │ • __main__.py (entry point)         │ │
        │  └─────────────────────────────────────┘ │
        │                                           │
        │  ┌─────────────────────────────────────┐ │
        │  │ Support Modules                     │ │
        │  │ • logging.py (log setup)            │ │
        │  │ • errors.py (exceptions)            │ │
        │  └─────────────────────────────────────┘ │
        │                                           │
        └──────────────────────────────────────────┘
               │
        ┌──────┴──────────────────────────┐
        │  OS Audio Systems               │
        ├─────────────────────────────────┤
        │ Linux: paplay, pw-play, aplay   │
        │ macOS: afplay                   │
        │ Windows/WSL: powershell         │
        └──────┬───────────────────────────┘
               │
               ↓
        ┌──────────────────┐
        │  Audio Output    │
        │  (Speaker/Headphones)
        └──────────────────┘
```

### Module Responsibilities

#### Configuration Module (`config.py`)
- **Responsibility:** Load, validate, and persist user configuration
- **Exports:**
  - `Config` dataclass (frozen, immutable)
  - `load_config()` function
  - `save_config()` function
- **Interaction:**
  - Reads from `~/.waiting.json`
  - Provides defaults if file missing
  - Validates all values (grace_period > 0, volume 1-100, audio file exists)
- **Error Handling:** Raises `ConfigError` on validation failure
- **Usage:** All modules that need settings load config via this module

#### State Management Module (`state.py`)
- **Responsibility:** Manage cross-process session state via temp files
- **Exports:**
  - Session ID generation (from JSON or MD5 fallback)
  - Temp file helpers (write/read/delete)
  - Cleanup functions
- **Interaction:**
  - Writes to `/tmp/waiting-*.pid` and `/tmp/waiting-stop-*`
  - Called by hook scripts and Python code
  - Supports cleanup of old files
- **Error Handling:** Logs warnings, continues gracefully if files unavailable
- **Usage:** Hook scripts and audio module use this for state coordination

#### Audio Module (`audio.py`)
- **Responsibility:** Main interface for audio playback
- **Exports:**
  - `play_audio()` - play file and return PID
  - `kill_audio()` - terminate audio process
  - `get_audio_player()` - platform detection
  - `resolve_audio_file()` - file validation
- **Interaction:**
  - Selects platform-specific player implementation
  - Logs all operations
  - Can be invoked as CLI module by hook scripts
- **Error Handling:** Raises `AudioError`, logs failures, continues gracefully
- **Usage:** Hook scripts invoke via `python3 -m waiting.audio`, Python code calls functions directly

#### Audio Players Module (`audio_players/`)
- **Responsibility:** Platform-specific audio playback
- **Structure:**
  - `base.py` - `AudioPlayer` protocol definition
  - `linux.py` - PulseAudio, PipeWire, ALSA implementations
  - `macos.py` - afplay implementation
  - `windows.py` - PowerShell implementation
- **Pattern:** Strategy pattern (pluggable players)
- **Usage:** `audio.py` selects and uses appropriate player

#### Hook Manager Module (`hooks/manager.py`)
- **Responsibility:** Install and remove hook scripts
- **Exports:**
  - `HookManager` class with methods:
    - `install(config)` - write hook scripts to ~/.claude/hooks/
    - `remove()` - delete hook scripts
    - `is_installed()` - check if hooks present
    - `get_hook_paths()` - return installed hook paths
- **Interaction:**
  - Creates ~/.claude/hooks/ if needed
  - Generates scripts from templates
  - Sets file permissions (0o755)
- **Error Handling:** Raises `HookError` on permission/file errors
- **Usage:** CLI `enable`/`disable` commands use this

#### CLI Module (`cli.py`)
- **Responsibility:** User-facing command interface
- **Exports:**
  - `CLI` class with methods:
    - `enable()` - install hooks, create config
    - `disable()` - remove hooks
    - `status()` - display current state
    - `show_help()` - display usage
- **Output:** Formatted text with status symbols (✓, ✗)
- **Error Handling:** Catches exceptions, returns appropriate exit codes
- **Usage:** Main entry point for `waiting` command

#### Logging Module (`logging.py`)
- **Responsibility:** Configure logging to `~/.waiting.log`
- **Exports:**
  - `setup_logging()` - return configured logger
- **Format:** `[TIMESTAMP] LEVEL: MESSAGE`
- **Location:** `~/.waiting.log` (append mode)
- **Usage:** All modules call `setup_logging()` to get logger

#### Error Module (`errors.py`)
- **Responsibility:** Define custom exceptions
- **Hierarchy:**
  ```
  WaitingError (base)
  ├── ConfigError (validation failures)
  ├── HookError (hook installation/execution)
  ├── AudioError (audio playback failures)
  └── StateError (state file management)
  ```
- **Usage:** Modules raise specific exceptions for different failures

---

## Event Flow

### Permission Dialog Notification Flow

```
Timeline (Seconds):
  0s  [Permission dialog appears in Claude Code]
      ↓
      Claude Code triggers PermissionRequest hook
      ↓
      Hook JSON includes session_id, permission details, etc.
      ↓
      ~/.claude/hooks/waiting-notify-permission.sh executes
      ↓
      Script extracts session_id from JSON
      ↓
      Script creates /tmp/waiting-stop-{sid} (empty file, marker)
      ↓
      Script creates background sleep loop (grace period)
      ↓
      Background loop monitors /tmp/waiting-stop-{sid}

  0-30s [User may respond to dialog]
      ↓
      If user approves/denies permission dialog
      ↓
      Claude Code triggers PreToolUse hook
      ↓
      ~/.claude/hooks/waiting-activity-tooluse.sh executes
      ↓
      Script extracts same session_id
      ↓
      Script creates /tmp/waiting-stop-{sid} (marker file)
      ↓
      Script reads /tmp/waiting-audio-{sid}.pid if exists
      ↓
      Script kills audio process if running
      ↓
      Script removes temp files
      ↓
      DONE - no audio played, user responded in time

  30s [No response, grace period expires]
      ↓
      Background sleep loop exits normally
      ↓
      Script checks if /tmp/waiting-stop-{sid} exists
      ↓
      If NOT present, grace period expired normally
      ↓
      Script invokes: python3 -m waiting.audio "default" 100
      ↓
      Python audio module:
        1. Detects platform (Linux, macOS, Windows)
        2. Selects audio player (paplay, afplay, powershell, etc.)
        3. Resolves audio file ("default" → system bell path)
        4. Executes player process
        5. Returns PID to stdout
      ↓
      Script captures PID, writes to /tmp/waiting-audio-{sid}.pid
      ↓
      Script waits for audio process to complete
      ↓
      Cleanup: removes /tmp/waiting-stop-{sid}, /tmp/waiting-audio-{sid}.pid
      ↓
      DONE - audio played
```

### State Transitions Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                   WAITING SYSTEM STATE MACHINE              │
└─────────────────────────────────────────────────────────────┘

    [IDLE]
      │
      │ PermissionRequest hook fires
      ↓
    [PERMISSION_DETECTED]
      │
      ├─→ Grace period timer starts
      │
      │ (30 second countdown)
      │
      ├─→ (0-30s) PreToolUse hook fires (user responds)
      │   │
      │   ↓ Stop signal created
      │   [STOPPED]
      │   │
      │   ↓ Cleanup temp files
      │   [IDLE]
      │
      └─→ (30s) Grace period expires without interruption
          │
          ↓ No stop signal present
          [PLAYING_AUDIO]
          │
          ├─→ Audio process runs (1-2 seconds typically)
          │
          ↓
          [AUDIO_COMPLETE]
          │
          ↓ Cleanup temp files
          [IDLE]
```

---

## State Management

### Temp File Strategy

**Why temp files instead of persistent daemon/database?**
- MVP requirement: zero external dependencies
- Hooks are independent processes (can't maintain in-memory state)
- Simple to debug (human-readable files)
- Cross-platform (all systems have /tmp)
- Self-cleaning (old files auto-pruned)
- Atomic operations (file existence is atomic)

### State Files

#### Stop Signal File
- **Path:** `/tmp/waiting-stop-{session_id}`
- **Content:** Empty (file existence is the signal)
- **Lifetime:** Created by `waiting-activity-tooluse.sh`, deleted after permission hook checks it
- **Purpose:** Signal permission hook that user responded
- **Synchronization:** Non-blocking check (loop in permission hook)

**Session ID Examples:**
```
From Claude hook JSON:  "abc-123-def-456-ghi"
MD5 fallback:           "3d2f8e4c6b1a9f7e2d5c"  (MD5 of hostname+timestamp)
```

#### Audio PID File
- **Path:** `/tmp/waiting-audio-{session_id}.pid`
- **Content:** Process ID of audio player (e.g., "12345")
- **Lifetime:** Created by permission hook before starting audio, read by activity hook to kill process
- **Purpose:** Allow activity hook to terminate audio if user responds during audio playback
- **Cleanup:** Deleted after audio completes or is killed

### Session ID Generation

```python
# Priority order:
1. Extract from Claude's hook JSON: hook_input.get("session_id")
2. If not present, generate fallback:
   MD5(hostname + current_timestamp_nanoseconds)

# Example:
{
  "event": "PermissionRequest",
  "session_id": "sess-20260110-141530-abc123def",  # Preferred
  "permission": {...}
}

# Fallback if JSON missing session_id:
hostname="michael-laptop"
timestamp_ns="1736342130123456789"
combined="michael-laptop1736342130123456789"
session_id=MD5(combined)="a7f3c2e8b1d6f4a9"
```

### Cleanup Strategy

**Automatic Cleanup (after each notification cycle):**
1. Permission hook completes or timer expires
2. Activity hook runs or grace period elapses
3. Both delete their temp files: `/tmp/waiting-stop-*`, `/tmp/waiting-audio-*.pid`

**Cleanup of Old Files:**
```python
# Run periodically (or at startup)
def cleanup_old_files(age_hours: int = 1):
    """Remove /tmp/waiting-* files older than age_hours"""
    cutoff_time = time.time() - (age_hours * 3600)
    for file in Path("/tmp").glob("waiting-*"):
        if file.stat().st_mtime < cutoff_time:
            file.unlink()
```

**Orphaned File Prevention:**
- Old files (> 1 hour) are auto-pruned
- Each notification cycle cleans its files
- Activity hook kills audio process immediately
- Graceful handling if files already deleted

---

## Hook System Integration

### Claude Code Hook System

**Two Hooks Used:**

1. **PermissionRequest Hook**
   - **Trigger:** User sees permission dialog (e.g., "Allow bash command?")
   - **Input:** JSON stdin with session_id, permission details
   - **Location:** `~/.claude/hooks/` directory
   - **Script Name:** `waiting-notify-permission.sh`
   - **Timing:** Synchronous (hook output can be captured)
   - **Purpose:** Start grace period timer

2. **PreToolUse Hook**
   - **Trigger:** Before executing tool (user approved/denied permission)
   - **Input:** JSON stdin with session_id, tool details
   - **Location:** `~/.claude/hooks/` directory
   - **Script Name:** `waiting-activity-tooluse.sh`
   - **Timing:** Synchronous
   - **Purpose:** Signal that user responded, stop audio

### Hook Script Requirements

**Bash Script Constraints:**
- Lightweight and fast (hook execution shouldn't slow Claude Code)
- Must handle missing dependencies gracefully (jq might not be installed)
- Output minimal (hooks shouldn't pollute stdout)
- Exit cleanly (exit code 0 always)

**Template Architecture:**
```bash
#!/bin/bash
set -e

# 1. Parse input (stdin from Claude)
HOOK_JSON=$(cat)
SESSION_ID=$(parse_session_id "$HOOK_JSON")

# 2. Load configuration (Python module or JSON parsing)
CONFIG=$(load_config)

# 3. Manage state (create/check/delete temp files)
create_state_files "$SESSION_ID"

# 4. Core logic (timer loop, signal check, or cleanup)
main_logic

# 5. Cleanup (remove state files)
cleanup_state_files

# 6. Exit cleanly
exit 0
```

### Hook Installation Process

```python
class HookManager:
    def install(config: Config) -> None:
        # 1. Create ~/.claude/hooks/ if needed
        hook_dir = Path.home() / ".claude" / "hooks"
        hook_dir.mkdir(parents=True, exist_ok=True)

        # 2. Read hook script templates from package
        permission_template = load_script_template("waiting-notify-permission.sh")
        activity_template = load_script_template("waiting-activity-tooluse.sh")

        # 3. Write scripts to hook directory
        permission_path = hook_dir / "waiting-notify-permission.sh"
        activity_path = hook_dir / "waiting-activity-tooluse.sh"

        permission_path.write_text(permission_template)
        activity_path.write_text(activity_template)

        # 4. Make executable
        permission_path.chmod(0o755)
        activity_path.chmod(0o755)
```

---

## Audio Playback Strategy

### Platform Detection

```python
def get_audio_player() -> AudioPlayer:
    system = platform.system()

    if system == "Linux":
        # Fallback chain: paplay → pw-play → aplay
        return get_linux_player()
    elif system == "Darwin":  # macOS
        return AFPlayPlayer()
    elif system == "Windows":
        return PowerShellPlayer()
    else:
        raise AudioError(f"Unsupported platform: {system}")
```

### Linux Fallback Chain

**Why multiple players?**
- **paplay** - PulseAudio (most common on desktop Linux)
- **pw-play** - PipeWire (newer, becoming standard)
- **aplay** - ALSA (fallback, sometimes only option)

**Selection Logic:**
```python
def get_linux_player() -> AudioPlayer:
    players = [
        PulseAudioPlayer(),    # Try paplay first
        PipeWirePlayer(),      # Then pw-play
        ALSAPlayer(),          # Finally aplay
    ]

    for player in players:
        if player.available():
            logger.info(f"Using audio player: {player.name()}")
            return player

    raise AudioError("No audio player available on Linux")
```

**Player Availability Check:**
```python
class PulseAudioPlayer:
    def available(self) -> bool:
        """Check if paplay command exists"""
        try:
            subprocess.run(
                ["which", "paplay"],
                capture_output=True,
                check=True,
                timeout=1
            )
            return True
        except:
            return False
```

### Volume Control

**Volume Range:** 1-100 (percentage)

**Per-Player Conversion:**
```
paplay:
  1-100 → 0-65536 (hardware range)
  Conversion: int((volume / 100.0) * 65536)

pw-play:
  1-100 → 0.0-1.0
  Conversion: volume / 100.0

aplay:
  1-100 → 1-100% (direct percentage)
  Conversion: str(volume) + "%"

afplay (macOS):
  1-100 → 0.0-1.0
  Conversion: volume / 100.0

powershell (Windows):
  No native volume control in SoundPlayer
  Volume handled by OS system settings
```

### Audio File Resolution

```python
def resolve_audio_file(audio_config: str) -> Path | str:
    if audio_config == "default":
        # Try to find system bell sounds
        candidates = [
            Path("/usr/share/sounds/freedesktop/stereo/complete.oga"),
            Path("/usr/share/sounds/freedesktop/stereo/bell.oga"),
            Path("/System/Library/Sounds/Glass.aiff"),  # macOS
            Path("/System/Library/Sounds/Ping.aiff"),   # macOS
        ]

        for path in candidates:
            if path.exists():
                return path

        # Fallback to system bell (platform-dependent)
        return "default"

    # Custom audio file
    audio_path = Path(audio_config).expanduser().resolve()
    if not audio_path.exists():
        raise AudioError(f"Audio file not found: {audio_config}")
    return audio_path
```

### Graceful Degradation

**If audio player unavailable:**
1. Log warning to `~/.waiting.log`
2. Continue without playing audio
3. Permission dialog still functions normally
4. `waiting status` indicates audio unavailable

**If audio file invalid:**
1. Log error
2. Fall back to system bell
3. If system bell also fails, skip audio but continue

---

## Design Patterns

### 1. Strategy Pattern (Audio Players)

```python
# Protocol defines strategy interface
class AudioPlayer(Protocol):
    def play(file_path: str, volume: int) -> int: ...
    def available(self) -> bool: ...

# Multiple implementations
class PulseAudioPlayer: ...
class PipeWirePlayer: ...
class ALSAPlayer: ...

# Context selects strategy
def get_audio_player() -> AudioPlayer:
    # Select first available
    for player_class in players:
        if player_class().available():
            return player_class()
```

### 2. Immutable Data Pattern (Configuration)

```python
@dataclass(frozen=True)  # Immutable after creation
class Config:
    grace_period: int
    volume: int
    audio: str

    def validate(self) -> tuple[bool, str | None]:
        # Validation logic returns result tuple
        pass

# Usage: Create new Config instead of mutating
original = Config(30, 100, "default")
updated = Config(45, 80, original.audio)  # New instance
```

### 3. Dependency Injection

```python
# Instead of global state
def play_audio(
    file_path: str,
    volume: int,
    logger: logging.Logger,  # Injected
    audio_player: AudioPlayer | None = None  # Injected optional
) -> int:
    player = audio_player or get_audio_player()
    # Use injected dependencies
    logger.info(...)
    return player.play(file_path, volume)

# Testing: Easy to mock
mock_player = MockAudioPlayer()
pid = play_audio("test.wav", 100, test_logger, audio_player=mock_player)
```

### 4. Functional Error Handling

```python
# Return tuple (is_valid, error_message) instead of raising
def validate_config(config: Config) -> tuple[bool, str | None]:
    if config.grace_period <= 0:
        return False, "grace_period must be positive"
    if not (1 <= config.volume <= 100):
        return False, "volume must be 1-100"
    return True, None

# Usage: Caller decides how to handle
is_valid, error = validate_config(config)
if not is_valid:
    raise ConfigError(error)
    # or: logger.warn(error); use_defaults()
```

### 5. Protocol-Based Polymorphism

```python
from typing import Protocol

class AudioPlayer(Protocol):
    """Any class implementing this is an AudioPlayer"""
    def play(self, file_path: str, volume: int) -> int: ...
    def available(self) -> bool: ...

# No explicit inheritance needed
class PulseAudioPlayer:
    def play(self, file_path: str, volume: int) -> int:
        # Implementation
    def available(self) -> bool:
        # Implementation

# Type checkers recognize it implements protocol
player: AudioPlayer = PulseAudioPlayer()  # Valid
```

---

## Error Handling

### Exception Hierarchy

```python
WaitingError (base class)
├── ConfigError
│   └── Raised: Invalid config file, validation failure
│   └── Caught by: CLI, hook manager
│   └── User message: "Invalid configuration: ..."
│
├── HookError
│   └── Raised: Hook installation/removal failure
│   └── Caught by: CLI enable/disable commands
│   └── User message: "Failed to install hooks: ..."
│
├── AudioError
│   └── Raised: Audio playback failure, player unavailable
│   └── Caught by: audio module
│   └── User message: Logged, silent degradation
│
└── StateError
    └── Raised: Temp file operation failures
    └── Caught by: state module
    └── User message: Logged, continues with fallback
```

### Error Recovery Strategies

**Configuration Error:**
```python
try:
    config = load_config()
except ConfigError as e:
    logger.error(f"Config error: {e}")
    # Use defaults and continue
    config = Config(30, 100, "default")
```

**Hook Installation Error:**
```python
try:
    HookManager().install(config)
except HookError as e:
    print(f"✗ Error: {e}")
    return 1  # Exit with error code
```

**Audio Playback Error:**
```python
try:
    pid = play_audio(file_path, volume)
except AudioError as e:
    logger.warn(f"Audio unavailable: {e}")
    # Continue without playing - don't break permission dialog
    return None
```

**State File Error:**
```python
try:
    write_pid_file(session_id, pid)
except StateError as e:
    logger.warn(f"State file error: {e}")
    # Continue - worst case: can't kill audio later
    # But audio will eventually complete
```

---

## Security Considerations

### Threat Model

1. **Malicious hook JSON input**
   - Mitigation: Parse with validation, extract only session_id
   - No code execution via JSON content

2. **Temp file tampering**
   - Mitigation: Paths include random session_id
   - Files created in user's /tmp (user can modify if needed)
   - Auto-cleanup of old files prevents attacks

3. **Configuration file tampering**
   - Mitigation: User owns ~/.waiting.json
   - Invalid configs caught during validation
   - Worst case: wrong volume or audio file

4. **Audio player execution**
   - Mitigation: Audio path validated before execution
   - Only shell-safe characters in file paths
   - No shell interpolation (subprocess.run with list args)

### Input Validation

```python
# Session ID: alphanumeric, hyphens, underscores only
VALID_SESSION_ID = re.compile(r"^[a-zA-Z0-9_\-]{8,50}$")

# Audio file path: prevent directory traversal
def safe_audio_path(audio_config: str) -> Path:
    path = Path(audio_config).expanduser().resolve()
    # Ensure path is within home directory or /usr/share/sounds
    if not (path.is_relative_to(Path.home()) or
            path.is_relative_to(Path("/usr/share/sounds"))):
        raise AudioError(f"Audio path outside allowed directories: {audio_config}")
    return path

# Volume: 1-100 only
if not (1 <= volume <= 100):
    raise ConfigError(f"Volume must be 1-100, got {volume}")

# Grace period: positive integer
if not isinstance(grace_period, int) or grace_period <= 0:
    raise ConfigError(f"Grace period must be positive integer")
```

### File Permissions

```python
# Hook scripts: world-readable, owner-executable only
HOOK_PERMS = 0o755  # rwxr-xr-x
# (standard for executable scripts)

# Config file: user-readable/writable only (if desired)
CONFIG_PERMS = 0o644  # rw-r--r--
# (JSON is human-readable config)

# Log file: user-readable/writable only
LOG_PERMS = 0o644  # rw-r--r--
# (logs may contain debug info)
```

---

## Performance Characteristics

### Latency Requirements

| Operation | Target | Justification |
|-----------|--------|---------------|
| Grace period timer | ±1 second | Human acceptable, not perceptible |
| Audio startup | < 500ms | User expects quick response |
| Stop signal detection | < 100ms | Immediate feel when user responds |
| Hook script execution | < 100ms | Shouldn't slow Claude Code |

### Resource Usage

**Memory:**
- Waiting Python modules: ~5-10 MB (importing only)
- No background process (zero idle memory)
- Minimal temp files (< 1KB per session)

**CPU:**
- Grace period timer: Negligible (background sleep loop)
- Audio playback: Depends on player (usually < 5% CPU)
- Hook script execution: Milliseconds

**Disk:**
- Package size: ~50KB (source code only)
- Config file: ~200 bytes
- Log file: ~1KB per notification
- Temp files: < 1KB per session, auto-cleaned

### Concurrency

**Current Design:**
- One permission dialog at a time (Claude Code limitation)
- No parallel notifications
- Sequential hook execution

**If Future Extension Needed:**
- Session ID ensures isolation per permission dialog
- Temp files are session-specific (/tmp/waiting-{sid})
- No shared state between sessions
- Can handle multiple concurrent sessions safely

---

## Testing Strategy

### Unit Test Levels

```
Level 1: Module Functions
├── config.py: load, save, validate
├── state.py: session ID, temp files, cleanup
├── audio.py: platform detection, file resolution
├── audio_players/*: player interface, availability
└── logging.py: setup, output format

Level 2: Class/Component Behavior
├── HookManager: install, remove, detect
├── CLI: enable, disable, status
└── Config: dataclass validation

Level 3: Error Handling
├── ConfigError cases
├── AudioError cases
├── HookError cases
└── StateError cases
```

### Integration Test Levels

```
Level 1: Module Integration
├── Config + State: config affects state behavior
├── Audio + AudioPlayers: player selection works
└── HookManager + Scripts: templates generate correctly

Level 2: Component Workflows
├── CLI enable → hooks installed → status shows enabled
├── Permission hook → grace period → audio plays
└── Activity hook → stop signal → audio killed

Level 3: End-to-End System
├── Install → enable → trigger permission → audio plays → disable
└── Configuration persistence across enable/disable/status
```

### Mock Strategy

```python
# Mock filesystem
@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path

# Mock audio player
class MockAudioPlayer:
    def play(self, file, volume):
        return 12345  # Fake PID
    def available(self):
        return True

# Mock subprocess (for hook execution)
@patch("subprocess.run")
def test_hook_script(mock_run):
    mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
    # Test logic
```

---

## Future Extensibility

### Potential Future Features (Not in MVP)

1. **Multiple Notification Triggers**
   - Additional hooks: `stop` event, `idle` event
   - Each trigger maintains separate timer/state
   - Session ID expansion to include trigger type

2. **Repeating/Nag Alerts**
   - Play bell multiple times (e.g., every 10s)
   - Configurable repeat interval
   - Stop on user response (same mechanism)

3. **Scheduling/Quiet Hours**
   - Configuration: time ranges to suppress alerts
   - Keep same hook/state mechanism, add time check

4. **Sound Selection UI**
   - Web interface to browse/test sounds
   - Keep CLI as alternative
   - Same config file format

5. **Desktop Notifications**
   - Combine audio with visual alerts
   - `notify-send` on Linux, NSUserNotification on macOS
   - Keep modular (separate module)

### Design for Extensibility

**Current Architecture Supports:**
- Protocol-based audio players (easy to add new platforms)
- Modular config validation (easy to add new settings)
- Hook script templates (easy to add new hooks)
- Functional error handling (easy to extend error types)

**Would Need for Future:**
- Trigger abstraction (generic notification scheduling)
- UI framework (separate from CLI)
- Async event handling (if scaling to many concurrent notifications)

---

## Deployment & Release Strategy

### Installation Flow

```
User runs: pip install -e .
  ↓
Package installed with entry point "waiting"
  ↓
User runs: waiting
  ↓
CLI.enable() called
  ↓
Config created at ~/.waiting.json with defaults
Hooks installed at ~/.claude/hooks/waiting-*.sh
  ↓
User restarts Claude Code
  ↓
Claude Code discovers and loads hooks
  ↓
Next permission dialog triggers notification system
```

### Upgrade Considerations

**From v0.1.0 to v0.2.0 (hypothetical):**
- Config format compatible (JSON, extensible)
- Hook scripts regenerated on upgrade
- Old temp files auto-cleaned
- Logs remain (user can review history)

---

## Summary

**Waiting** is a lightweight, hook-driven audio notification system with:
- **Zero external dependencies** for runtime
- **Cross-platform support** via strategy pattern
- **Simple state management** via temp files
- **Graceful degradation** on missing audio
- **Functional programming style** with strict typing
- **Modular architecture** supporting future extensions

The system is designed for **reliability** (multiple fallbacks), **simplicity** (no daemon, no database), and **user control** (configurable, easy to disable).

