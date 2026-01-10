# Quick Start Guide - Waiting MVP Implementation

**For:** Senior Engineer implementing Waiting system
**Duration:** 5 weeks
**Difficulty:** Intermediate
**Key Skills:** Python, Bash, type hints, testing

---

## What You're Building

An audio notification system that plays a bell when Claude Code permission dialogs go unanswered.

```
Permission Dialog Appears
       ↓ (30 second wait)
Grace Period Expires
       ↓
Play Bell Sound
       ↓
User Responds = Stop Audio
```

---

## High-Level Architecture

```
Claude Code Hooks (JSON events)
         ↓
Bash Hook Scripts (/tmp state files)
         ↓
Python Core Modules (config, audio, state)
         ↓
Cross-Platform Audio Players
         ↓
Speaker/Headphones
```

---

## Phase-by-Phase Breakdown

### Phase 1: Foundation (Week 1) - Make config/state/logging work
**6 Python modules + 3 test files**

```python
# Core modules you'll create:
config.py      → Config dataclass, load/save
state.py       → Session ID, temp file helpers
logging.py     → Log setup to ~/.waiting.log
errors.py      → Custom exceptions
cli.py         → Command handlers (stub in Phase 1)
hooks/manager.py → Hook management (stub in Phase 1)
```

**Key takeaway:** Config loads from `~/.waiting.json`, state uses `/tmp/waiting-*` files

### Phase 2: Hooks (Week 2-3) - Make bash scripts work
**2 Bash scripts + hook manager**

```bash
waiting-notify-permission.sh  → On permission dialog:
                                 • Extract session_id from JSON
                                 • Wait grace_period seconds
                                 • Play audio if no stop signal

waiting-activity-tooluse.sh   → On user response:
                                 • Create stop signal /tmp/waiting-stop-{sid}
                                 • Kill audio process
```

**Key takeaway:** Hooks communicate via temp files, zero-dependency

### Phase 3: Audio (Week 3-4) - Make sound work across platforms
**Protocol + 3 Linux players + macOS + Windows**

```python
AudioPlayer protocol → Interface all players implement

Linux players:
  • PulseAudioPlayer (paplay) - try first
  • PipeWirePlayer (pw-play) - fallback
  • ALSAPlayer (aplay) - final fallback

macOS:
  • AFPlayPlayer (afplay)

Windows/WSL:
  • PowerShellPlayer (powershell.exe)
```

**Key takeaway:** Strategy pattern selects first available player

### Phase 4: CLI (Week 4) - Make `waiting` command work
**3 CLI commands + entry point**

```bash
waiting              # Enable notifications
waiting disable      # Disable notifications
waiting status       # Show current config
waiting --help       # Show help
```

**Key takeaway:** CLI installs/removes hooks and displays config

### Phase 5: QA (Week 5) - Test everything
**80% coverage + documentation**

```python
pytest --cov=src/waiting tests/
→ Unit tests (isolated modules)
→ Integration tests (component interactions)
→ Platform tests (Linux, macOS, WSL)
```

**Key takeaway:** Comprehensive test coverage before release

---

## Key Files You'll Create

### Configuration & State
```
src/waiting/config.py          Config loading/validation
src/waiting/state.py           Temp file state management
src/waiting/errors.py          Custom exceptions
src/waiting/logging.py         Log setup
```

### Audio Playback
```
src/waiting/audio.py                   Main audio interface
src/waiting/audio_players/base.py      Protocol definition
src/waiting/audio_players/linux.py     PulseAudio, PipeWire, ALSA
src/waiting/audio_players/macos.py     afplay
src/waiting/audio_players/windows.py   PowerShell
```

### Hook System
```
src/waiting/hooks/manager.py                  Hook install/remove
src/waiting/hooks/scripts/waiting-notify-permission.sh  Bash script
src/waiting/hooks/scripts/waiting-activity-tooluse.sh   Bash script
```

### CLI & Entry Point
```
src/waiting/cli.py             Command handlers
src/waiting/__main__.py         Entry point
```

### Tests
```
tests/conftest.py              Shared fixtures
tests/unit/test_config.py      Config tests
tests/unit/test_state.py       State tests
tests/unit/test_audio.py       Audio tests
tests/unit/test_audio_players.py  Player tests
tests/unit/test_hooks.py       Hook tests
tests/unit/test_cli.py         CLI tests
tests/integration/test_*.py    Integration tests
```

---

## Development Workflow

### Each Feature Implementation

1. **Write tests first** (TDD approach)
   ```bash
   # tests/unit/test_config.py
   def test_load_default_config():
       config = load_config()
       assert config.grace_period == 30
   ```

2. **Implement module** (make tests pass)
   ```python
   # src/waiting/config.py
   def load_config(path: Path | None = None) -> Config:
       # Implementation
   ```

3. **Run and verify**
   ```bash
   pytest tests/unit/test_config.py -v
   ```

4. **Commit with descriptive message**
   ```bash
   git add tests/ src/
   git commit -m "feat: add Config class with load/save functions"
   ```

### Type Hints (Strict)

Every function must have types:
```python
# GOOD
def play_audio(file_path: str, volume: int, logger: logging.Logger) -> int:
    """Play audio file and return process ID."""
    pass

# BAD - missing return type
def play_audio(file_path: str, volume: int, logger):
    pass

# BAD - missing parameter types
def play_audio(file_path, volume, logger: logging.Logger) -> int:
    pass
```

### Functional Style

- **Pure functions** - same input always produces same output
- **No mutable globals** - pass dependencies as arguments
- **Return tuples for results** - (value, error) or (success, message)
- **Exceptions for exceptional errors** - invalid config, file not found

```python
# GOOD - pure function
def validate_grace_period(value: int) -> tuple[bool, str | None]:
    if value <= 0:
        return False, "grace_period must be positive"
    return True, None

# GOOD - dependency injection
def play_audio(player: AudioPlayer, file: str, volume: int) -> int:
    return player.play(file, volume)

# AVOID - mutable global state
config = load_config()  # Global!
def play_audio(file: str, volume: int) -> int:
    return player.play(file, volume)  # Uses global config
```

---

## Testing Approach

### Unit Tests (Isolated)
Test individual functions with mocks:
```python
def test_config_validation():
    # Arrange
    config = Config(grace_period=-1, volume=100, audio="default")

    # Act
    is_valid, error = config.validate()

    # Assert
    assert is_valid is False
    assert "positive" in error.lower()
```

### Integration Tests (Components)
Test multiple components working together:
```python
def test_permission_hook_lifecycle(tmp_home):
    # Arrange: create config and hooks
    config = Config(30, 100, "default")
    HookManager().install(config)

    # Act: simulate permission dialog
    permission_output = run_hook("waiting-notify-permission.sh", hook_json)

    # Assert: verify grace period started
    assert Path("/tmp/waiting-*").exists()
```

### Test Fixtures
```python
@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    """Mock home directory for testing"""
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path

@pytest.fixture
def sample_config():
    """Standard test config"""
    return Config(grace_period=30, volume=100, audio="default")
```

---

## Common Patterns You'll Use

### 1. Type-Safe Config
```python
@dataclass(frozen=True)  # Immutable
class Config:
    grace_period: int
    volume: int
    audio: str

    def validate(self) -> tuple[bool, str | None]:
        """Return (is_valid, error_message)"""
        if self.grace_period <= 0:
            return False, "grace_period must be positive"
        return True, None
```

### 2. Strategy Pattern (Audio Players)
```python
class AudioPlayer(Protocol):
    def play(self, file: str, volume: int) -> int: ...
    def available(self) -> bool: ...

def get_audio_player() -> AudioPlayer:
    for Player in [PulseAudioPlayer, PipeWirePlayer, ALSAPlayer]:
        if Player().available():
            return Player()
    raise AudioError("No player available")
```

### 3. Dependency Injection
```python
def play_audio(
    file_path: str,
    volume: int,
    logger: logging.Logger,
    player: AudioPlayer | None = None  # Optional inject
) -> int:
    player = player or get_audio_player()
    return player.play(file_path, volume)

# Testing: easy to mock
mock_player = MockAudioPlayer()
play_audio("test.wav", 100, logger, player=mock_player)
```

### 4. Result Tuples
```python
# Instead of exceptions for validation
def validate_config(config: Config) -> tuple[bool, str | None]:
    is_valid, error = config.validate()
    if not is_valid:
        return False, error
    return True, None

# Usage
is_valid, error = validate_config(config)
if not is_valid:
    raise ConfigError(error)  # Only raise on unexpected errors
```

---

## Common Mistakes to Avoid

### ❌ Global State
```python
# DON'T
config = load_config()

def play_audio():
    # Uses global config
    return player.play(config.audio)

# DO
def play_audio(config: Config):
    return player.play(config.audio)
```

### ❌ Missing Type Hints
```python
# DON'T
def load_config(path):
    return Config(...)

# DO
def load_config(path: Path | None = None) -> Config:
    return Config(...)
```

### ❌ Bare Except
```python
# DON'T
try:
    player.play(file)
except:  # Catches everything, including KeyboardInterrupt!
    pass

# DO
try:
    player.play(file)
except AudioError as e:
    logger.error(f"Audio failed: {e}")
except Exception as e:  # Catch unexpected errors
    logger.error(f"Unexpected error: {e}")
```

### ❌ No Validation
```python
# DON'T
config = Config(grace_period=-1, volume=150, audio="")

# DO
config = Config(grace_period=30, volume=100, audio="default")
is_valid, error = config.validate()
if not is_valid:
    raise ConfigError(error)
```

### ❌ Unclear Return Types
```python
# DON'T
def get_session_id(hook_input):
    # Could return string or None, unclear
    if "session_id" in hook_input:
        return hook_input["session_id"]

# DO
def generate_session_id(hook_input: dict) -> str:
    """Generate or extract session ID, never returns None"""
    session_id = hook_input.get("session_id", "")
    if session_id:
        return session_id
    return generate_fallback_session_id()
```

---

## Running Tests During Development

### First time setup
```bash
cd /home/michael/projects/waiting_new
python -m venv venv
source venv/bin/activate
pip install pytest pytest-cov
```

### Run tests frequently
```bash
# All tests
pytest tests/

# Specific file
pytest tests/unit/test_config.py

# Specific test
pytest tests/unit/test_config.py::test_load_default_config

# With coverage
pytest --cov=src/waiting tests/

# Verbose output
pytest tests/ -v

# Stop on first failure
pytest tests/ -x
```

---

## Git Workflow

### Before you start
```bash
git status  # Check you're on mvp-fresh-start branch
git pull    # Get latest
```

### As you implement
```bash
# Phase 1: Foundation
git add src/waiting/config.py tests/unit/test_config.py
git commit -m "feat: add Config class with load/save functions"

git add src/waiting/state.py tests/unit/test_state.py
git commit -m "feat: add state management with temp file helpers"

# Each commit should be focused on one feature
```

### Before pushing
```bash
pytest tests/ --cov=src/waiting
# Ensure 80%+ coverage
```

---

## Key Dates & Milestones

| Week | Phase | Deliverable | Tests |
|------|-------|-------------|-------|
| 1 | Foundation | Config, state, logging | 100% unit coverage |
| 2-3 | Hooks | Hook scripts, manager | 100% hook tests |
| 3-4 | Audio | Audio players, playback | 100% audio tests |
| 4 | CLI | enable/disable/status | 100% CLI tests |
| 5 | QA | 80% overall coverage | All tests passing |

---

## Questions to Ask When Stuck

1. **"How should this handle an error?"**
   - Check error.py for exception types
   - Use specific exceptions (ConfigError, AudioError, etc.)

2. **"Should this take a parameter?"**
   - Yes, use dependency injection
   - Avoid global state

3. **"What should the return type be?"**
   - Single value: return type directly (→ int)
   - Optional: use | None (→ int | None)
   - Success/failure: use tuple (→ tuple[bool, str | None])
   - Multiple values: use dataclass or dict

4. **"How do I test this?"**
   - Unit test: mock all dependencies
   - Integration test: combine multiple components
   - Use tmp_home fixture for filesystem operations

5. **"Is this change too big?"**
   - Commit when: one feature complete, tests green
   - Don't commit when: multiple unrelated changes, tests failing

---

## Resources Within This Repo

**Read in order:**
1. **IMPLEMENTATION_PLAN.md** - Detailed plan (you are here)
2. **TASK_BREAKDOWN.md** - Flat list of all tasks
3. **ARCHITECTURE.md** - System design decisions
4. **PRD.md** - User requirements
5. **pm-user-stories.md** - User stories from PM

**Reference often:**
- AGENTS.md - Engineering rules you're following
- CLAUDE.md - Project guidelines

---

## Example: Implementing First Feature

### Feature: Load configuration from JSON

**1. Write test first** (tests/unit/test_config.py)
```python
def test_load_default_config(tmp_home):
    """Config should have defaults if file missing"""
    config = load_config()
    assert config.grace_period == 30
    assert config.volume == 100
    assert config.audio == "default"
```

**2. Implement** (src/waiting/config.py)
```python
from dataclasses import dataclass
from pathlib import Path
import json

DEFAULT_CONFIG = {
    "grace_period": 30,
    "volume": 100,
    "audio": "default"
}

@dataclass(frozen=True)
class Config:
    grace_period: int
    volume: int
    audio: str

def load_config(path: Path | None = None) -> Config:
    path = path or (Path.home() / ".waiting.json")
    if path.exists():
        data = json.loads(path.read_text())
    else:
        data = DEFAULT_CONFIG
    return Config(**data)
```

**3. Run test**
```bash
pytest tests/unit/test_config.py::test_load_default_config -v
# PASSED
```

**4. Commit**
```bash
git add src/waiting/config.py tests/unit/test_config.py
git commit -m "feat: add Config dataclass and load_config function"
```

**5. Continue with next feature**
- Add save_config() test
- Implement save_config()
- Commit

---

## You're Ready When...

- [ ] You understand the overall architecture (system overview section)
- [ ] You know what each phase delivers (5 phases, 5 weeks)
- [ ] You can explain the hook system (permission + activity hooks, temp files)
- [ ] You know the test-first workflow (test, implement, commit)
- [ ] You're comfortable with Python type hints (every function)
- [ ] You understand dependency injection (no global state)

---

## Final Checklist Before Starting Week 1

- [ ] Clone/navigate to `/home/michael/projects/waiting_new`
- [ ] Create virtual environment: `python -m venv venv`
- [ ] Activate: `source venv/bin/activate`
- [ ] Install pytest: `pip install pytest pytest-cov`
- [ ] Confirm test runner works: `pytest --version`
- [ ] Read ARCHITECTURE.md to understand system design
- [ ] Review Phase 1 tasks in TASK_BREAKDOWN.md
- [ ] Create first test file and run it
- [ ] Make first commit
- [ ] Begin Phase 1 implementation

**Good luck! Build something great!**

