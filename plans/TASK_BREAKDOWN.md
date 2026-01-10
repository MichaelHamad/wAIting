# Task Breakdown - Waiting MVP Implementation

**Status:** Ready for Implementation
**Difficulty:** Intermediate
**Estimated Duration:** 5 weeks

---

## Quick Reference: All Implementation Tasks

This document provides a flat, searchable list of all implementation tasks organized by phase. Use this alongside IMPLEMENTATION_PLAN.md for detailed context.

---

## Phase 1: Foundation (Week 1-2) - 10 Tasks

### 1.1 Project Configuration (1-2 tasks)

**Task 1.1.1: Update pyproject.toml**
- **File:** `/home/michael/projects/waiting_new/pyproject.toml`
- **Current State:** Minimal package metadata
- **Changes:**
  ```toml
  [project.scripts]
  waiting = "waiting.__main__:main"

  [tool.pytest.ini_options]
  testpaths = ["tests"]
  python_files = "test_*.py"
  addopts = "-v --tb=short"
  ```
- **Why:** Declares CLI entry point and pytest configuration
- **Test:** `pytest --version` works

**Task 1.1.2: Create pytest.ini**
- **File:** `/home/michael/projects/waiting_new/pytest.ini`
- **Content:**
  ```ini
  [pytest]
  testpaths = tests
  python_files = test_*.py
  addopts = -v --tb=short
  ```
- **Why:** Centralized pytest configuration
- **Test:** `pytest tests/` discovers and runs tests

---

### 1.2 Core Modules (6 tasks)

**Task 1.2.1: Create errors.py**
- **File:** `/home/michael/projects/waiting_new/src/waiting/errors.py`
- **Classes:**
  - `WaitingError(Exception)` - base exception
  - `ConfigError(WaitingError)` - config validation failures
  - `HookError(WaitingError)` - hook installation failures
  - `AudioError(WaitingError)` - audio playback failures
  - `StateError(WaitingError)` - state file management failures
- **Why:** Structured exception handling throughout codebase
- **Test:** `from waiting.errors import ConfigError` succeeds

**Task 1.2.2: Create logging.py**
- **File:** `/home/michael/projects/waiting_new/src/waiting/logging.py`
- **Functions:**
  - `setup_logging() -> logging.Logger` - configure file logging to ~/.waiting.log
  - Format: `[TIMESTAMP] LEVEL: MESSAGE`
- **Why:** Centralized logging for debugging hook execution
- **Test:**
  ```python
  logger = setup_logging()
  logger.info("test")
  assert Path.home() / ".waiting.log" has content
  ```

**Task 1.2.3: Create Config dataclass (config.py - Part 1)**
- **File:** `/home/michael/projects/waiting_new/src/waiting/config.py`
- **Class:**
  ```python
  @dataclass(frozen=True)
  class Config:
      grace_period: int  # seconds, >= 1
      volume: int        # 1-100
      audio: str         # "default" or file path

      def validate(self) -> tuple[bool, str | None]:
          """Return (is_valid, error_message)"""
  ```
- **Why:** Type-safe configuration container with validation
- **Test:**
  ```python
  config = Config(30, 100, "default")
  assert config.grace_period == 30
  valid, err = config.validate()
  assert valid is True
  ```

**Task 1.2.4: Add config loading (config.py - Part 2)**
- **File:** `/home/michael/projects/waiting_new/src/waiting/config.py`
- **Functions:**
  - `load_config(path: Path | None = None) -> Config` - load from ~/.waiting.json or create defaults
  - `save_config(config: Config, path: Path | None = None) -> None` - write to ~/.waiting.json
- **Default values:**
  ```python
  DEFAULT_CONFIG = {
      "grace_period": 30,
      "volume": 100,
      "audio": "default"
  }
  ```
- **Why:** Persist user configuration across sessions
- **Test:**
  ```python
  config = load_config()
  assert config.grace_period == 30
  save_config(Config(45, 80, "default"))
  loaded = load_config()
  assert loaded.grace_period == 45
  ```

**Task 1.2.5: Create state.py**
- **File:** `/home/michael/projects/waiting_new/src/waiting/state.py`
- **Functions:**
  - `generate_session_id(hook_input: dict) -> str` - extract from JSON or MD5 fallback
  - `write_pid_file(session_id: str, pid: int) -> Path` - write to /tmp/waiting-audio-{session}.pid
  - `read_pid_file(session_id: str) -> int | None` - read PID from file
  - `create_stop_signal(session_id: str) -> Path` - create /tmp/waiting-stop-{session}
  - `has_stop_signal(session_id: str) -> bool` - check if signal file exists
  - `cleanup(session_id: str) -> None` - remove PID and stop signal files
  - `cleanup_old_files(age_hours: int = 1) -> None` - prune files older than N hours
- **Why:** Cross-process state management via temp files
- **Test:**
  ```python
  sid = generate_session_id({"session_id": "abc123"})
  assert sid == "abc123"
  write_pid_file(sid, 1234)
  assert read_pid_file(sid) == 1234
  create_stop_signal(sid)
  assert has_stop_signal(sid) is True
  cleanup(sid)
  assert Path(f"/tmp/waiting-audio-{sid}.pid").exists() is False
  ```

**Task 1.2.6: Create conftest.py**
- **File:** `/home/michael/projects/waiting_new/tests/conftest.py`
- **Fixtures:**
  - `tmp_home(tmp_path, monkeypatch)` - mock HOME directory
  - `tmp_config_dir(tmp_path)` - temporary config directory
  - `sample_config()` - Config object with default values
- **Why:** Shared test fixtures for isolation
- **Test:** Fixtures are available to all tests without import

---

### 1.3 Unit Tests (3 tasks)

**Task 1.3.1: Create test_config.py**
- **File:** `/home/michael/projects/waiting_new/tests/unit/test_config.py`
- **Test Classes:**
  - `TestConfigClass` - dataclass behavior, validation
  - `TestLoadConfig` - file loading, defaults, persistence
  - `TestSaveConfig` - write operations, file format
- **Tests:**
  - Default values
  - Valid configuration
  - Invalid grace_period (negative, zero, non-integer)
  - Invalid volume (< 1, > 100, non-integer)
  - Invalid audio file (doesn't exist)
  - Load missing config creates defaults
  - Save and reload roundtrip
  - File format is valid JSON
- **Why:** Ensure config system is robust
- **Pass Criteria:** All tests green, 100% coverage of config.py

**Task 1.3.2: Create test_state.py**
- **File:** `/home/michael/projects/waiting_new/tests/unit/test_state.py`
- **Test Classes:**
  - `TestSessionID` - ID generation and fallback
  - `TestPIDFile` - write/read/delete operations
  - `TestStopSignal` - signal creation and detection
  - `TestCleanup` - cleanup and pruning
- **Tests:**
  - Extract session ID from JSON
  - Generate fallback MD5 ID if missing
  - Write PID file and read back
  - Create stop signal file
  - Detect stop signal presence
  - Cleanup removes all files
  - Old files (> 1 hour) are pruned
  - Concurrent writes don't duplicate files
- **Why:** Validate state management is reliable
- **Pass Criteria:** All tests green, 100% coverage of state.py

**Task 1.3.3: Create test_logging.py**
- **File:** `/home/michael/projects/waiting_new/tests/unit/test_logging.py`
- **Tests:**
  - Logger is configured correctly
  - Logs written to ~/.waiting.log
  - Log format includes timestamp and level
  - Multiple log calls accumulate in file
- **Why:** Verify logging infrastructure works
- **Pass Criteria:** All tests green

---

## Phase 2: Hooks & Events (Weeks 2-3) - 8 Tasks

### 2.1 Hook Management (2 tasks)

**Task 2.1.1: Create hooks/manager.py**
- **File:** `/home/michael/projects/waiting_new/src/waiting/hooks/manager.py`
- **Class: HookManager**
  - `install(config: Config) -> None` - generate and write hook scripts
  - `remove() -> None` - delete hook scripts
  - `is_installed() -> bool` - check if hooks exist
  - `get_hook_paths() -> dict[str, Path]` - return {"permission": Path, "activity": Path}
- **Implementation Details:**
  - Create ~/.claude/hooks/ if doesn't exist
  - Generate hook scripts from bash templates (see tasks 2.2 and 2.3)
  - Set file mode to 0o755 (executable)
  - Handle FileNotFoundError, PermissionError gracefully
- **Why:** Manage hook lifecycle
- **Test:** All operations succeed, files created/deleted correctly

**Task 2.1.2: Create hooks/__init__.py**
- **File:** `/home/michael/projects/waiting_new/src/waiting/hooks/__init__.py`
- **Exports:** HookManager class
- **Why:** Package initialization
- **Test:** `from waiting.hooks import HookManager` succeeds

---

### 2.2 Hook Scripts (2 tasks)

**Task 2.2.1: Create waiting-notify-permission.sh script template**
- **File:** `/home/michael/projects/waiting_new/src/waiting/hooks/scripts/waiting-notify-permission.sh`
- **Template (bash):**
  ```bash
  #!/bin/bash
  set -e

  # Read hook JSON from stdin
  HOOK_JSON=$(cat)
  SESSION_ID=$(echo "$HOOK_JSON" | jq -r '.session_id // empty' 2>/dev/null || echo "")

  # Fallback: generate MD5 session ID
  if [ -z "$SESSION_ID" ]; then
    SESSION_ID=$(echo "$(hostname)-$(date +%s%N)" | md5sum | cut -d' ' -f1)
  fi

  CONFIG_FILE="$HOME/.waiting.json"
  GRACE_PERIOD=$(python3 -c "import json; c=json.load(open('$CONFIG_FILE')); print(c.get('grace_period', 30))" 2>/dev/null || echo 30)
  AUDIO=$(python3 -c "import json; c=json.load(open('$CONFIG_FILE')); print(c.get('audio', 'default'))" 2>/dev/null || echo "default")
  VOLUME=$(python3 -c "import json; c=json.load(open('$CONFIG_FILE')); print(c.get('volume', 100))" 2>/dev/null || echo 100)

  STOP_SIGNAL="/tmp/waiting-stop-$SESSION_ID"
  PID_FILE="/tmp/waiting-audio-$SESSION_ID.pid"

  # Log event
  echo "[$(date)] Permission request detected. Session: $SESSION_ID. Grace: ${GRACE_PERIOD}s" >> "$HOME/.waiting.log"

  # Run grace period in background
  (
    for ((i=0; i<$GRACE_PERIOD; i++)); do
      if [ -f "$STOP_SIGNAL" ]; then
        # User responded, exit
        rm -f "$STOP_SIGNAL" "$PID_FILE"
        echo "[$(date)] Stop signal detected. Session: $SESSION_ID. Audio canceled." >> "$HOME/.waiting.log"
        exit 0
      fi
      sleep 1
    done

    # Grace period expired, play audio
    if [ ! -f "$STOP_SIGNAL" ]; then
      echo "[$(date)] Grace period expired. Session: $SESSION_ID. Playing audio." >> "$HOME/.waiting.log"
      python3 -m waiting.audio play "$AUDIO" "$VOLUME" > "$PID_FILE" 2>> "$HOME/.waiting.log"
      AUDIO_PID=$(cat "$PID_FILE" 2>/dev/null || echo "")

      if [ -n "$AUDIO_PID" ]; then
        wait "$AUDIO_PID" 2>/dev/null || true
        echo "[$(date)] Audio completed. Session: $SESSION_ID. PID: $AUDIO_PID" >> "$HOME/.waiting.log"
      fi
    fi

    # Cleanup
    rm -f "$STOP_SIGNAL" "$PID_FILE"
  ) &

  exit 0
  ```
- **Why:** Trigger on PermissionRequest, manage grace period, play audio if no stop signal
- **Test:** Script executes without error, creates temp files, respects grace period

**Task 2.2.2: Create waiting-activity-tooluse.sh script template**
- **File:** `/home/michael/projects/waiting_new/src/waiting/hooks/scripts/waiting-activity-tooluse.sh`
- **Template (bash):**
  ```bash
  #!/bin/bash
  set -e

  HOOK_JSON=$(cat)
  SESSION_ID=$(echo "$HOOK_JSON" | jq -r '.session_id // empty' 2>/dev/null || echo "")

  if [ -z "$SESSION_ID" ]; then
    SESSION_ID=$(echo "$(hostname)-$(date +%s%N)" | md5sum | cut -d' ' -f1)
  fi

  STOP_SIGNAL="/tmp/waiting-stop-$SESSION_ID"
  PID_FILE="/tmp/waiting-audio-$SESSION_ID.pid"

  # User took action - signal permission hook to stop
  touch "$STOP_SIGNAL"

  # Kill audio process if running
  if [ -f "$PID_FILE" ]; then
    AUDIO_PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$AUDIO_PID" ]; then
      kill "$AUDIO_PID" 2>/dev/null || true
      rm -f "$PID_FILE"
      echo "[$(date)] Activity detected. Killed audio PID: $AUDIO_PID. Session: $SESSION_ID" >> "$HOME/.waiting.log"
    fi
  fi

  rm -f "$STOP_SIGNAL"

  exit 0
  ```
- **Why:** Trigger on PreToolUse (user response), stop audio immediately
- **Test:** Script executes, creates stop signal, kills audio process

---

### 2.3 Hook Tests (4 tasks)

**Task 2.3.1: Create test_hooks.py (Unit)**
- **File:** `/home/michael/projects/waiting_new/tests/unit/test_hooks.py`
- **Test Classes:**
  - `TestHookManager` - installation, removal, detection
- **Tests:**
  - Install creates hook files
  - Removed hooks deleted
  - Detect installed hooks
  - Hook files are executable
  - Permissions are correct
  - Create ~/.claude/hooks/ if missing
  - Handle permission errors gracefully
- **Why:** Verify hook manager logic
- **Pass Criteria:** All tests green

**Task 2.3.2: Create test_hook_lifecycle.py (Integration)**
- **File:** `/home/michael/projects/waiting_new/tests/integration/test_hook_lifecycle.py`
- **Test Classes:**
  - `TestPermissionHook` - end-to-end permission hook
  - `TestActivityHook` - end-to-end activity hook
  - `TestHookInteraction` - hooks working together
- **Tests:**
  - Permission hook receives JSON and creates temp files
  - Permission hook respects grace period timer
  - Activity hook creates stop signal
  - Permission hook detects stop signal and exits
  - Cleanup removes all temp files
  - Old temp files are pruned
- **Why:** Verify hook execution and interaction
- **Pass Criteria:** All tests green

**Task 2.3.3: Create test_state_integration.py**
- **File:** `/home/michael/projects/waiting_new/tests/integration/test_state_integration.py`
- **Tests:**
  - State operations work across hook processes
  - Temp files survive between hook invocations
  - Cleanup is atomic (no orphaned files)
- **Why:** Verify state management under realistic conditions
- **Pass Criteria:** All tests green

**Task 2.3.4: Integration test fixtures**
- **Update:** `/home/michael/projects/waiting_new/tests/conftest.py`
- **Fixtures:**
  - `mock_hook_input()` - return sample Claude hook JSON
  - `installed_hooks(tmp_home)` - fixture that installs hooks for testing
  - `cleanup_temp_files()` - cleanup /tmp files after tests
- **Why:** Support integration tests
- **Test:** Fixtures available to integration tests

---

## Phase 3: Audio Playback (Weeks 3-4) - 9 Tasks

### 3.1 Audio Player Protocol & Base (2 tasks)

**Task 3.1.1: Create audio_players/base.py**
- **File:** `/home/michael/projects/waiting_new/src/waiting/audio_players/base.py`
- **Protocol:**
  ```python
  from typing import Protocol

  class AudioPlayer(Protocol):
      def play(self, file_path: str, volume: int) -> int:
          """Play audio file. Returns process PID."""

      def kill(self, pid: int) -> bool:
          """Kill audio process. Returns True if killed."""

      def available(self) -> bool:
          """Check if player command is available."""

      def name(self) -> str:
          """Player name (e.g., 'paplay', 'afplay')."""
  ```
- **Why:** Define interface for all audio players
- **Test:** Protocol is importable and usable with type checkers

**Task 3.1.2: Create audio_players/__init__.py**
- **File:** `/home/michael/projects/waiting_new/src/waiting/audio_players/__init__.py`
- **Exports:** AudioPlayer protocol
- **Why:** Package initialization
- **Test:** `from waiting.audio_players import AudioPlayer` succeeds

---

### 3.2 Linux Audio Players (2 tasks)

**Task 3.2.1: Create audio_players/linux.py - PulseAudio**
- **File:** `/home/michael/projects/waiting_new/src/waiting/audio_players/linux.py`
- **Class: PulseAudioPlayer**
  ```python
  class PulseAudioPlayer:
      def play(self, file_path: str, volume: int) -> int:
          # volume 1-100 -> 0-65536 for paplay
          pa_volume = int((volume / 100.0) * 65536)
          cmd = ["paplay", "--volume", str(pa_volume)]
          if file_path != "default":
              cmd.append(file_path)
          # Execute subprocess, return PID

      def kill(self, pid: int) -> bool:
          # Kill process by PID

      def available(self) -> bool:
          # Check if paplay exists in PATH

      def name(self) -> str:
          return "paplay"
  ```
- **Why:** Support PulseAudio systems (most common)
- **Test:**
  - available() returns True/False based on system
  - play() returns valid PID
  - kill() terminates process

**Task 3.2.2: Create audio_players/linux.py - PipeWire and ALSA**
- **Add to:** `/home/michael/projects/waiting_new/src/waiting/audio_players/linux.py`
- **Classes:**
  - `PipeWirePlayer` - uses `pw-play` command
  - `ALSAPlayer` - uses `aplay` command
- **Fallback function:**
  ```python
  def get_linux_player() -> AudioPlayer:
      """Return first available player"""
      for Player in [PulseAudioPlayer, PipeWirePlayer, ALSAPlayer]:
          p = Player()
          if p.available():
              return p
      raise AudioError("No audio player available on Linux")
  ```
- **Why:** Support multiple Linux audio systems
- **Test:**
  - All three players implement AudioPlayer protocol
  - Fallback chain returns available player
  - Raises AudioError if none available

---

### 3.3 macOS & Windows Audio Players (2 tasks)

**Task 3.3.1: Create audio_players/macos.py**
- **File:** `/home/michael/projects/waiting_new/src/waiting/audio_players/macos.py`
- **Class: AFPlayPlayer**
  ```python
  class AFPlayPlayer:
      def play(self, file_path: str, volume: int) -> int:
          # afplay supports -v for volume (0.0-1.0)
          volume_float = volume / 100.0
          cmd = ["afplay", "-v", str(volume_float)]
          if file_path != "default":
              cmd.append(file_path)
          # Execute subprocess, return PID

      def available(self) -> bool:
          # Check if afplay exists (built-in on macOS)

      def name(self) -> str:
          return "afplay"
  ```
- **Why:** Support macOS native audio
- **Test:**
  - available() returns True on macOS
  - play() returns valid PID
  - Volume conversion is correct

**Task 3.3.2: Create audio_players/windows.py**
- **File:** `/home/michael/projects/waiting_new/src/waiting/audio_players/windows.py`
- **Class: PowerShellPlayer**
  ```python
  class PowerShellPlayer:
      def play(self, file_path: str, volume: int) -> int:
          # PowerShell audio in Windows/WSL
          ps_cmd = f"""
          $player = New-Object System.Media.SoundPlayer;
          $player.SoundLocation = '{file_path}';
          $player.Play();
          """
          cmd = ["powershell.exe", "-Command", ps_cmd]
          # Execute subprocess, return PID

      def available(self) -> bool:
          # Check if powershell.exe available (WSL fallback)

      def name(self) -> str:
          return "powershell"
  ```
- **Why:** Support Windows/WSL audio
- **Test:**
  - available() returns True on WSL
  - play() returns valid PID

---

### 3.4 Main Audio Module (3 tasks)

**Task 3.4.1: Create audio.py - Platform Detection**
- **File:** `/home/michael/projects/waiting_new/src/waiting/audio.py`
- **Function:**
  ```python
  import platform

  def get_audio_player() -> AudioPlayer:
      """Auto-detect and return platform-appropriate player"""
      system = platform.system()

      if system == "Linux":
          from .audio_players.linux import get_linux_player
          return get_linux_player()
      elif system == "Darwin":  # macOS
          from .audio_players.macos import AFPlayPlayer
          return AFPlayPlayer()
      elif system == "Windows":
          from .audio_players.windows import PowerShellPlayer
          return PowerShellPlayer()
      else:
          raise AudioError(f"Unsupported platform: {system}")
  ```
- **Why:** Select correct player per platform
- **Test:**
  - Returns correct player type per platform
  - Raises AudioError on unsupported platform

**Task 3.4.2: Create audio.py - Audio File Resolution**
- **Add to:** `/home/michael/projects/waiting_new/src/waiting/audio.py`
- **Function:**
  ```python
  def resolve_audio_file(audio_config: str) -> Path | str:
      """
      Resolve audio file path.
      If "default", return path to system bell.
      Otherwise validate file exists.
      """
      if audio_config == "default":
          candidates = [
              Path("/usr/share/sounds/freedesktop/stereo/complete.oga"),
              Path("/System/Library/Sounds/Glass.aiff"),  # macOS
          ]
          for path in candidates:
              if path.exists():
                  return path
          return "default"  # System bell fallback

      audio_path = Path(audio_config).expanduser().resolve()
      if not audio_path.exists():
          raise AudioError(f"Audio file not found: {audio_config}")
      return audio_path
  ```
- **Why:** Handle both default and custom audio files
- **Test:**
  - "default" resolves to valid system bell path
  - Custom paths are validated
  - Non-existent files raise AudioError

**Task 3.4.3: Create audio.py - Audio Playback Interface**
- **Add to:** `/home/michael/projects/waiting_new/src/waiting/audio.py`
- **Functions:**
  ```python
  def play_audio(
      file_path: str,
      volume: int,
      logger: logging.Logger | None = None
  ) -> int:
      """Play audio file and return PID"""
      logger = logger or setup_logging()
      try:
          player = get_audio_player()
          resolved_path = resolve_audio_file(file_path)
          pid = player.play(str(resolved_path), volume)
          logger.info(f"Audio playing: {file_path} (PID {pid}, Player: {player.name()})")
          return pid
      except Exception as e:
          logger.error(f"Audio playback failed: {e}")
          raise AudioError(str(e)) from e

  def kill_audio(pid: int, logger: logging.Logger | None = None) -> bool:
      """Kill audio process by PID"""
      logger = logger or setup_logging()
      try:
          import subprocess
          subprocess.run(["kill", str(pid)], check=False)
          logger.info(f"Killed audio process {pid}")
          return True
      except Exception as e:
          logger.error(f"Failed to kill audio {pid}: {e}")
          return False
  ```
- **CLI invocation (for hook scripts):**
  ```python
  if __name__ == "__main__":
      import sys
      if len(sys.argv) < 2:
          print("Usage: python -m waiting.audio <audio_file> [volume]", file=sys.stderr)
          sys.exit(1)
      file_path = sys.argv[1]
      volume = int(sys.argv[2]) if len(sys.argv) > 2 else 100
      logger = setup_logging()
      pid = play_audio(file_path, volume, logger)
      print(pid)
  ```
- **Why:** Main entry point for audio playback, callable from hooks
- **Test:**
  - play_audio() returns PID
  - kill_audio() terminates process
  - Module can be invoked as `python -m waiting.audio`

---

### 3.5 Audio Tests (2 tasks)

**Task 3.5.1: Create test_audio_players.py**
- **File:** `/home/michael/projects/waiting_new/tests/unit/test_audio_players.py`
- **Test Classes:**
  - `TestPulseAudioPlayer` - Linux
  - `TestPipeWirePlayer` - Linux
  - `TestALSAPlayer` - Linux
  - `TestAFPlayPlayer` - macOS
  - `TestPowerShellPlayer` - Windows
  - `TestLinuxFallback` - fallback chain
- **Tests:**
  - Each player available() check
  - Command construction (including volume)
  - Play returns valid PID
  - Kill terminates process
  - Fallback returns first available
- **Why:** Verify all audio player implementations
- **Pass Criteria:** All tests green, platform-specific tests conditional

**Task 3.5.2: Create test_audio.py**
- **File:** `/home/michael/projects/waiting_new/tests/unit/test_audio.py`
- **Test Classes:**
  - `TestPlatformDetection` - get_audio_player()
  - `TestAudioFileResolution` - resolve_audio_file()
  - `TestPlayAudio` - play_audio()
  - `TestKillAudio` - kill_audio()
- **Tests:**
  - Platform detection returns correct player type
  - "default" resolves to system bell
  - Custom paths validated
  - play_audio() returns PID and logs
  - kill_audio() terminates process
  - AudioError raised on invalid config
  - Module invocation as CLI works
- **Why:** Verify audio module interface
- **Pass Criteria:** All tests green

---

## Phase 4: CLI Commands (Week 4) - 5 Tasks

### 4.1 CLI Implementation (3 tasks)

**Task 4.1.1: Create cli.py**
- **File:** `/home/michael/projects/waiting_new/src/waiting/cli.py`
- **Class: CLI**
  ```python
  class CLI:
      def __init__(self, config_path: Path | None = None, logger: logging.Logger | None = None):
          self.config_path = config_path or (Path.home() / ".waiting.json")
          self.logger = logger or setup_logging()

      def enable(self) -> int:
          """Enable notifications by installing hooks"""
          # Load/create config
          # Install hooks
          # Print success message
          # Return 0 or 1

      def disable(self) -> int:
          """Disable notifications by removing hooks"""
          # Remove hooks
          # Print success message
          # Return 0 or 1

      def status(self) -> int:
          """Display current status and configuration"""
          # Load config
          # Check if hooks installed
          # Print formatted output
          # Return 0 or 1

      def show_help(self) -> int:
          """Display help message"""
          # Print usage info
          # Return 0
  ```
- **Output formatting:**
  - Use `✓` for success, `✗` for errors
  - Clear section headers
  - Actionable next steps
- **Why:** User-facing command interface
- **Test:**
  - enable() installs hooks, creates config, returns 0
  - disable() removes hooks, returns 0
  - status() displays config and hook status
  - Errors handled gracefully

**Task 4.1.2: Create __main__.py**
- **File:** `/home/michael/projects/waiting_new/src/waiting/__main__.py`
- **Function:**
  ```python
  def main(args: list[str] | None = None) -> int:
      """CLI entry point"""
      args = args or sys.argv[1:]
      cli = CLI()

      if not args or args[0] in ["--help", "-h", "help"]:
          return cli.show_help()

      command = args[0]

      if command == "enable":
          return cli.enable()
      elif command == "disable":
          return cli.disable()
      elif command == "status":
          return cli.status()
      else:
          print(f"Unknown command: {command}", file=sys.stderr)
          return 1

  if __name__ == "__main__":
      sys.exit(main())
  ```
- **Why:** Main entry point for `waiting` command
- **Test:**
  - `waiting` invokes enable
  - `waiting --help` shows help
  - `waiting status` displays status
  - Unknown commands show help and return 1

**Task 4.1.3: Update pyproject.toml for CLI**
- **File:** `/home/michael/projects/waiting_new/pyproject.toml`
- **Add:**
  ```toml
  [project.scripts]
  waiting = "waiting.__main__:main"
  ```
- **Why:** Makes `waiting` command available after install
- **Test:** `pip install -e .` makes `waiting` command available

---

### 4.2 CLI Tests (2 tasks)

**Task 4.2.1: Create test_cli.py (Unit)**
- **File:** `/home/michael/projects/waiting_new/tests/unit/test_cli.py`
- **Test Classes:**
  - `TestCLIEnable` - enable command
  - `TestCLIDisable` - disable command
  - `TestCLIStatus` - status command
  - `TestCLIHelp` - help display
  - `TestCLIErrors` - error handling
- **Tests:**
  - enable() creates config file
  - enable() installs hooks
  - enable() prints success message
  - disable() removes hooks
  - disable() preserves config
  - status() displays config
  - status() shows hook status
  - help() prints usage
  - Unknown commands return error
- **Why:** Verify CLI commands
- **Pass Criteria:** All tests green

**Task 4.2.2: Create test_cli.py (Integration)**
- **File:** `/home/michael/projects/waiting_new/tests/integration/test_cli.py`
- **Tests:**
  - Full workflow: enable → status → disable → status
  - Config persists across commands
  - Hooks verified by filesystem check
  - Error scenarios (invalid config, permission errors)
- **Why:** Verify end-to-end CLI workflow
- **Pass Criteria:** All tests green

---

## Phase 5: Testing & QA (Week 5) - 5 Tasks

### 5.1 Test Coverage (2 tasks)

**Task 5.1.1: Achieve 80%+ Code Coverage**
- **Run:** `pytest --cov=src/waiting --cov-report=html tests/`
- **Target:** 80%+ line coverage on all modules
- **Focus areas:**
  - Error handling paths (ConfigError, HookError, AudioError)
  - Fallback chains (audio player selection)
  - Edge cases (missing files, permission errors)
- **Why:** Ensure code quality and reliability
- **Pass Criteria:** Coverage >= 80%

**Task 5.1.2: Add Missing Test Cases**
- **Identify and add tests for:**
  - Logging edge cases
  - Concurrent access to temp files
  - Platform-specific paths
  - Error message formatting
- **Why:** Fill coverage gaps
- **Pass Criteria:** All identified gaps covered

---

### 5.2 Platform Testing (2 tasks)

**Task 5.2.1: Linux Testing (CI)**
- **Setup:**
  - GitHub Actions workflow (if using GitHub)
  - Install Python 3.9+
  - Install audio players (paplay, pw-play, aplay) or mock
- **Tests:**
  - Run full test suite
  - Test all Linux audio players
  - Verify hook script execution
- **Why:** Validate on primary platform
- **Pass Criteria:** All tests pass on Linux

**Task 5.2.2: Platform Documentation**
- **Create:** `/home/michael/projects/waiting_new/PLATFORM_NOTES.md`
- **Content:**
  - Linux: Confirmed working (distro, audio system)
  - macOS: Manual test (afplay availability)
  - Windows/WSL: Manual test (PowerShell availability)
  - Known issues and workarounds
- **Why:** Document platform-specific behavior
- **Pass Criteria:** All supported platforms documented

---

### 5.3 Documentation (1 task)

**Task 5.3.1: Create User Documentation**
- **Files to create:**

  **README.md**
  - Quick start (install, enable, test)
  - Configuration guide
  - Troubleshooting
  - Supported platforms

  **TROUBLESHOOTING.md**
  - "No audio plays" - check logs, test audio player
  - "Permission denied" - check ~/.claude/hooks/ permissions
  - "Config not applying" - restart Claude Code
  - "Too slow to react" - adjust grace_period
  - Platform-specific issues

  **CONTRIBUTING.md**
  - Development setup
  - Running tests
  - Commit message format
  - Pull request process

  **API.md** (optional)
  - Hook JSON schema
  - Audio player protocol
  - Config file format

- **Why:** Help users and contributors
- **Pass Criteria:** All files created and reviewed

---

## Task Dependency Graph

```
Phase 1 Foundation:
  1.1 pyproject.toml
  1.2 errors.py ──────────┐
  1.2 logging.py ─────────┤
  1.2 config.py ──────────┼──> 1.3 test_config.py
  1.2 state.py ───────────┤
  1.4 conftest.py────────┤
  1.2 pytest.ini ────────┘

Phase 2 Hooks:
  1.2 config.py ─────────┐
  2.1 manager.py ────────┼──> 2.2 hook scripts ──> 2.3 hook tests
  1.2 state.py ──────────┘

Phase 3 Audio:
  3.1 base.py
    ├─> 3.2 linux.py
    ├─> 3.3 macos.py
    ├─> 3.3 windows.py
    └─> 3.4 audio.py ──> 3.5 audio tests
  1.2 logging.py ────────┘

Phase 4 CLI:
  1.2 config.py ────────┐
  2.1 manager.py ───────┼──> 4.1 cli.py ──> 4.1 __main__.py ──> 4.2 cli tests
  3.4 audio.py ─────────┘

Phase 5 QA:
  All previous phases ──> 5.1 coverage ──> 5.2 platform tests ──> 5.3 docs
```

---

## Quick Start for Implementation

1. **Clone/navigate to project:**
   ```bash
   cd /home/michael/projects/waiting_new
   ```

2. **Week 1 workflow:**
   ```bash
   # Task 1.1.1 - Update pyproject.toml
   # Task 1.1.2 - Create pytest.ini
   # Task 1.2.1 - Create errors.py
   # Task 1.2.2 - Create logging.py
   # Task 1.2.3+4 - Create config.py
   # Task 1.2.5 - Create state.py
   # Task 1.2.6 - Create conftest.py
   # Task 1.3.1+2 - Create unit tests
   pytest tests/unit/
   ```

3. **Each task:**
   - Create file (follow type hints strictly)
   - Write/update tests first
   - Run `pytest` to verify
   - Commit with descriptive message

4. **Testing commands:**
   ```bash
   pytest tests/unit/              # Unit tests only
   pytest tests/integration/       # Integration tests only
   pytest tests/                   # All tests
   pytest --cov=src/waiting tests/ # With coverage
   ```

---

## Success Checklist

Use this as your go-live checklist:

**Phase 1 Complete:**
- [ ] All config, state, logging modules created
- [ ] All unit tests pass
- [ ] 100% coverage on Phase 1 modules

**Phase 2 Complete:**
- [ ] Hook manager functional
- [ ] Both hook scripts executable
- [ ] All hook tests pass

**Phase 3 Complete:**
- [ ] Audio players implemented for all platforms
- [ ] Audio module provides play_audio() and kill_audio()
- [ ] All audio tests pass

**Phase 4 Complete:**
- [ ] `waiting` command works
- [ ] `waiting enable` installs hooks
- [ ] `waiting disable` removes hooks
- [ ] `waiting status` shows config
- [ ] All CLI tests pass

**Phase 5 Complete:**
- [ ] 80%+ code coverage
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Manual testing on all supported platforms

**Go Live:**
- [ ] All acceptance criteria met
- [ ] Zero external dependencies
- [ ] Code follows functional style + strict typing
- [ ] Commits are small and focused

