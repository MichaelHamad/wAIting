# Development Guide

Guide for contributors and developers working on the Waiting audio notification system.

## Quick Start for Developers

### 1. Set Up Development Environment

```bash
# Clone repository
git clone <repository-url>
cd waiting_new

# Create Python virtual environment (optional but recommended)
python3.9 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with test dependencies
pip install -e ".[dev]"
pip install pytest pytest-cov
```

### 2. Verify Installation

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src/waiting --cov-report=html

# Check code
python -m waiting --help
```

### 3. Run Tests During Development

```bash
# Watch mode (requires pytest-watch)
ptw tests/

# Run specific test file
pytest tests/unit/test_config.py -v

# Run specific test
pytest tests/unit/test_config.py::test_load_default_config -v

# Run with detailed output
pytest tests/ -vv -s
```

## Project Structure

```
waiting_new/
├── src/waiting/                  # Main source code
│   ├── __init__.py              # Package initialization
│   ├── __main__.py              # CLI entry point (waiting command)
│   ├── cli.py                   # Command-line interface
│   ├── config.py                # Configuration management
│   ├── audio.py                 # Audio playback interface
│   ├── errors.py                # Custom exceptions
│   ├── logging.py               # Logging setup
│   ├── state.py                 # State management (temp files)
│   ├── settings.py              # Claude settings integration
│   ├── hooks/                   # Hook system
│   │   ├── __init__.py
│   │   ├── manager.py           # Hook installation/removal
│   │   └── scripts/             # Hook bash scripts
│   │       ├── waiting-notify-permission.sh
│   │       └── waiting-activity-tooluse.sh
│   └── audio_players/           # Platform-specific audio
│       ├── __init__.py
│       ├── base.py              # AudioPlayer base class
│       ├── linux.py             # Linux implementation
│       ├── macos.py             # macOS implementation
│       └── windows.py           # Windows/WSL implementation
│
├── tests/                        # Test suite
│   ├── __init__.py
│   └── unit/
│       ├── test_*.py            # Unit tests for each module
│       └── conftest.py          # Pytest fixtures and config
│
├── docs/                         # Documentation
│   ├── README.md                # Project overview
│   ├── INSTALLATION.md          # Setup guide
│   ├── USAGE.md                 # User guide
│   └── DEVELOPMENT.md           # This file
│
├── pyproject.toml               # Project metadata and dependencies
├── pytest.ini                   # Pytest configuration
├── CLAUDE.md                    # Project guidance for Claude
├── PRD.md                       # Product requirements document
└── ENGINEERING_GUIDE.md         # Engineering documentation

```

## Module Descriptions

### Core Modules

#### `config.py` - Configuration Management
Handles loading, validating, and saving configuration.

**Key Classes:**
- `Config` - Immutable configuration dataclass
- Functions: `load_config()`, `save_config()`

**Responsibility:**
- Load config from `~/.waiting.json`
- Validate configuration values
- Provide sensible defaults
- Create config on first run

**Testing:**
```bash
pytest tests/unit/test_config.py -v
```

#### `cli.py` - Command-Line Interface
User-facing command-line interface for Waiting.

**Key Classes:**
- `CLI` - Main CLI handler

**Commands:**
- `enable` - Install hooks
- `disable` - Remove hooks
- `status` - Show configuration
- `show_help` - Display help

**Testing:**
```bash
pytest tests/unit/test_cli.py -v
```

#### `audio.py` - Audio Playback Interface
Cross-platform audio playback with automatic platform detection.

**Key Functions:**
- `get_audio_player()` - Get platform-specific player
- `play_audio()` - Play audio file
- `kill_audio()` - Stop audio playback
- `resolve_audio_file()` - Resolve audio path

**Supports:**
- Linux (PulseAudio, PipeWire, ALSA)
- macOS (AFPlay)
- Windows/WSL (PowerShell)

**Testing:**
```bash
pytest tests/unit/test_audio.py -v
pytest tests/unit/test_audio_players.py -v
```

#### `state.py` - State Management
Inter-process communication via temporary files.

**Key Functions:**
- Session ID management
- Stop signal files
- Audio process PID tracking

**Testing:**
```bash
pytest tests/unit/test_state.py -v
```

#### `settings.py` - Claude Settings Integration
Integration with Claude Code's settings system.

**Key Functions:**
- `load_settings()` - Load Claude's settings.json
- `save_settings()` - Save updated settings
- `merge_hooks_into_settings()` - Register hooks
- `remove_hooks_from_settings()` - Unregister hooks

**Testing:**
```bash
pytest tests/unit/test_settings.py -v
```

#### `hooks/manager.py` - Hook Management
Installation and removal of hook scripts.

**Key Classes:**
- `HookManager` - Manages hook lifecycle

**Responsibilities:**
- Copy hook scripts to `~/.claude/hooks/`
- Register hooks in Claude settings
- Remove hooks and settings on disable
- Check hook installation status

**Testing:**
```bash
pytest tests/unit/test_hooks.py -v
```

#### `audio_players/` - Platform Audio
Platform-specific audio player implementations.

**Base Class:**
- `AudioPlayer` - Abstract base with interface

**Implementations:**
- `LinuxPlayer` - Selects paplay/pw-play/aplay
- `AFPlayPlayer` - macOS audio player
- `PowerShellPlayer` - Windows/WSL audio player

**Testing:**
```bash
pytest tests/unit/test_audio_players.py -v
```

### Utility Modules

#### `errors.py` - Custom Exceptions
Domain-specific exceptions.

**Exceptions:**
- `WaitingError` - Base exception
- `ConfigError` - Configuration issues
- `HookError` - Hook installation issues
- `AudioError` - Audio playback issues

#### `logging.py` - Logging Configuration
Centralized logging setup.

**Key Functions:**
- `setup_logging()` - Initialize logger

**Logs to:** `~/.waiting.log`

### Hook Scripts

#### `waiting-notify-permission.sh`
Bash script triggered on `PermissionRequest` hook event.

**Responsibilities:**
- Load configuration
- Wait for grace period
- Check if user responded
- Play audio if timeout

#### `waiting-activity-tooluse.sh`
Bash script triggered on `PreToolUse` hook event.

**Responsibilities:**
- Detect user activity
- Signal audio to stop
- Clean up state files

## Code Style and Guidelines

### Style Requirements

Follow these principles from AGENTS.md:

1. **Functional Style**
   - Prefer pure functions over methods
   - Minimize side effects
   - Use immutable data structures when possible
   - Use dataclasses for configuration

2. **Type Hints**
   - All functions must have type hints
   - Use strict typing (no `Any` unless necessary)
   - Include return type annotations

3. **Documentation**
   - Docstrings for all public functions and classes
   - Include args, returns, and raises sections
   - Add examples for complex functions

4. **Error Handling**
   - Use custom exceptions (not generic ones)
   - Provide clear error messages
   - Log errors with context

### Code Examples

**Good function:**
```python
def load_config(config_path: Path | None = None) -> Config:
    """
    Load configuration from file or create defaults.

    Args:
        config_path: Path to config file. Defaults to ~/.waiting.json

    Returns:
        Config: Loaded or default configuration

    Raises:
        ConfigError: If config file exists but is invalid
    """
    if config_path is None:
        config_path = Path.home() / ".waiting.json"

    if not config_path.exists():
        save_config(DEFAULT_CONFIG, config_path)
        return DEFAULT_CONFIG

    try:
        with open(config_path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ConfigError(f"Failed to load config: {e}")

    return Config(...)
```

**Good dataclass:**
```python
@dataclass(frozen=True)
class Config:
    """Immutable configuration for the Waiting system."""
    grace_period: int
    volume: int
    audio: str

    def validate(self) -> tuple[bool, str | None]:
        """Validate configuration values."""
        # validation logic
        return True, None
```

## Testing Strategy

### Test Organization

Tests are organized by module in `tests/unit/`:

```
tests/unit/
├── test_audio.py           # Audio playback tests
├── test_audio_players.py   # Platform player tests
├── test_cli.py             # CLI command tests
├── test_config.py          # Configuration tests
├── test_hooks.py           # Hook management tests
├── test_main.py            # Main entry point tests
├── test_settings.py        # Settings integration tests
├── test_state.py           # State management tests
└── conftest.py             # Shared fixtures
```

### Testing Principles

1. **Test-First Development**
   - Write tests before implementing features
   - Use tests to clarify requirements

2. **Unit Tests**
   - Test individual functions/classes in isolation
   - Mock external dependencies (file system, subprocess)
   - Aim for high coverage (>90%)

3. **Test Fixtures**
   - Use `conftest.py` for shared fixtures
   - Create temporary directories for file operations
   - Clean up after each test

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/unit/test_config.py -v

# Specific test function
pytest tests/unit/test_config.py::test_load_default_config -v

# With coverage
pytest tests/ --cov=src/waiting --cov-report=html

# Verbose output
pytest tests/ -vv -s

# Stop on first failure
pytest tests/ -x

# Run only recently failed tests
pytest tests/ --lf
```

### Coverage Requirements

- Target: >90% code coverage
- Required: >85% code coverage
- Generate report: `pytest tests/ --cov=src/waiting --cov-report=html`
- View report: `open htmlcov/index.html`

## Development Workflow

### Making Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature
   ```

2. **Write tests first**
   - Add test cases in appropriate `test_*.py` file
   - Tests should fail initially (red)

3. **Implement feature**
   - Make tests pass (green)
   - Follow code style guidelines
   - Add documentation

4. **Run full test suite**
   ```bash
   pytest tests/ -v --cov=src/waiting
   ```

5. **Commit changes**
   ```bash
   git add .
   git commit -m "feat: Add feature description"
   ```

### Commit Message Format

Use conventional commits:

- `feat: Add new feature`
- `fix: Fix bug in module`
- `test: Add tests for feature`
- `docs: Update documentation`
- `refactor: Refactor code without behavior change`
- `chore: Update dependencies, configs, etc`

### Pull Request Process

1. Push branch to repository
2. Open pull request with clear description
3. Ensure all tests pass
4. Maintain >90% coverage
5. Address review feedback
6. Merge once approved

## Debugging Tips

### Enable Debug Logging

Modify logging level temporarily:

```python
from .logging import setup_logging
logger = setup_logging()
logger.setLevel(logging.DEBUG)
```

### Check Logs

```bash
tail -f ~/.waiting.log
```

### Interactive Testing

```bash
python -c "from waiting.config import load_config; print(load_config())"
```

### Mock Testing

Use pytest fixtures and mocks:

```python
from unittest.mock import patch, MagicMock

def test_with_mock(tmp_path):
    config_path = tmp_path / "config.json"
    with patch('pathlib.Path.home', return_value=tmp_path):
        from waiting.config import load_config
        config = load_config(config_path)
        assert config.grace_period == 30
```

## Common Development Tasks

### Adding a New Configuration Option

1. Add field to `Config` dataclass in `config.py`
2. Update `DEFAULT_CONFIG`
3. Add validation in `Config.validate()`
4. Add to help text in `cli.py`
5. Write tests in `test_config.py`
6. Update documentation in `docs/USAGE.md`

### Adding Support for New Audio Player

1. Create new player class in `audio_players/` extending `AudioPlayer`
2. Implement `available()`, `play()`, `kill()` methods
3. Add to platform detection in `audio.py`
4. Write tests in `test_audio_players.py`
5. Update documentation

### Fixing a Bug

1. Write a test that reproduces the bug
2. Verify test fails
3. Fix the bug
4. Verify test passes
5. Check no other tests broke
6. Commit with message: `fix: Description of bug fix`

## Continuous Integration

The repository likely has CI configured to run:
- Linting (code style)
- Tests (pytest)
- Coverage (pytest-cov)
- Type checking (mypy/pyright)

Run locally before pushing:
```bash
pytest tests/ -v --cov=src/waiting
```

## Performance Considerations

1. **Hook Execution**
   - Hooks run synchronously during permission dialogs
   - Keep hook scripts fast (minimal computation)
   - Lazy-import heavy modules when needed

2. **Audio Playback**
   - Audio plays asynchronously (non-blocking)
   - Uses subprocess for platform separation
   - PID tracking for cleanup

3. **Configuration**
   - Loaded once per hook execution
   - Immutable dataclass prevents accidental changes

## Troubleshooting Development

### Import Errors

Ensure package is installed in editable mode:
```bash
pip install -e .
```

### Tests Fail After Changes

Clear pytest cache:
```bash
pytest --cache-clear tests/
```

### Type Checking Fails

Ensure type hints are correct:
```bash
# Check with mypy (if configured)
mypy src/waiting/
```

### Virtual Environment Issues

Recreate virtual environment:
```bash
rm -rf venv
python3.9 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

## Contributing

1. Follow code style guidelines
2. Write tests for new features
3. Maintain >90% code coverage
4. Update documentation
5. Use conventional commit messages
6. Provide clear PR descriptions

## Additional Resources

- **Project Overview**: See [README.md](./README.md)
- **User Guide**: See [USAGE.md](./USAGE.md)
- **Installation**: See [INSTALLATION.md](./INSTALLATION.md)
- **Product Requirements**: See `../PRD.md`
- **Engineering Guide**: See `../ENGINEERING_GUIDE.md`

## Support

For questions about development:
1. Check existing code and tests for examples
2. Review documentation files
3. Check git history for similar changes
4. Ask in project discussions or issues
