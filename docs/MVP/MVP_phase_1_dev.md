# MVP Phase 1 Development

## Overview

Phase 1 established the core functionality of the `waiting` CLI utility - a transparent PTY wrapper that detects when interactive commands are waiting for user input and alerts the developer via terminal bell.

## Completed: January 1, 2026

---

## What Was Built

### Core Package Structure

```
waiting/
├── __init__.py      # Package initialization, version "0.1.0"
├── __main__.py      # Entry point for `python -m waiting`
├── cli.py           # Command-line interface (argparse)
├── runner.py        # PTY spawn + bidirectional I/O passthrough
├── detector.py      # Wait detection state machine
├── events.py        # Event types (dataclasses)
├── notifiers.py     # Bell notification handler
└── utils.py         # ANSI stripping, prompt pattern matching
```

### Test Suite

```
tests/
├── __init__.py
├── test_utils.py        # 11 tests - ANSI stripping, prompt matching
├── test_detector.py     # 14 tests - state machine, raw mode detection
└── test_integration.py  # 16 tests - end-to-end CLI tests
```

**Total: 41 tests, all passing**

---

## Technical Implementation

### Wait Detection (detector.py)

Two-tier detection strategy:

1. **Primary: Raw Mode Detection**
   - Checks if the PTY is in raw mode via `termios.tcgetattr()`
   - Raw mode (ICANON flag off) indicates the command is waiting for single keypress input

2. **Secondary: Stall + Prompt Heuristics**
   - Triggers when output stalls for 2+ seconds (`STALL_THRESHOLD`)
   - AND the last output line matches prompt patterns (`:`, `?`, `>`, `[Y/n]`, etc.)

### State Machine

```
States: RUNNING <-> WAITING

Transitions:
- RUNNING -> WAITING: Raw mode detected OR (stall + prompt pattern)
- WAITING -> RUNNING: User input detected OR command output resumes
```

### Alert Behavior

- Bell (`\a`) emitted immediately on entering WAITING state
- Repeat alerts ("nag") every 5 seconds while still waiting (`NAG_INTERVAL`)
- Minimum 1 second gap between any alerts (`MIN_ALERT_GAP`)

### PTY Runner (runner.py)

- Uses `pty.fork()` to spawn commands in a pseudo-terminal
- `select.select()` for I/O multiplexing with 100ms poll interval
- Signal handling: SIGINT, SIGTERM forwarded to child; SIGWINCH propagates window size
- Terminal state saved/restored via `termios` for clean exit

---

## Verified Functionality

| Test Case | Result |
|-----------|--------|
| `waiting echo hello` | Exits immediately, no bell |
| `waiting sleep 2` | No bell (no prompt pattern) |
| `waiting true` | Exit code 0 passed through |
| `waiting false` | Exit code 1 passed through |
| `waiting sh -c "exit 42"` | Exit code 42 passed through |
| `waiting nonexistent_cmd` | Exit code 127 (command not found) |
| `waiting --help` | Shows usage information |

---

## Dependencies

**Runtime:** None (stdlib only - as per design requirement)

**Development:**
- pytest >= 7.0.0

---

## Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e .

# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/ -v
```

---

## Usage

```bash
# Basic usage
waiting <command> [args...]

# Examples
waiting python -c "input('Enter name: ')"
waiting npm install
waiting git commit

# With -- separator
waiting -- command --with-flags
```

---

## Deferred to Phase 2

The following features were intentionally excluded from MVP:

- Desktop notifications (`--notify` flag)
- Disable bell option (`--no-bell` flag)
- Debug mode (`--debug` flag)
- macOS notification center integration
- Linux notify-send integration

---

## Files Created

| File | Purpose |
|------|---------|
| `pyproject.toml` | Package configuration, entry point |
| `requirements.txt` | Runtime dependencies (empty) |
| `requirements-dev.txt` | Development dependencies (pytest) |
| `.gitignore` | Git ignore patterns |
| `waiting/__init__.py` | Package init, version string |
| `waiting/__main__.py` | `python -m waiting` support |
| `waiting/cli.py` | Argument parsing, main entry |
| `waiting/runner.py` | PTY wrapper, I/O loop |
| `waiting/detector.py` | Wait detection logic |
| `waiting/events.py` | Event dataclasses |
| `waiting/notifiers.py` | Bell notifier |
| `waiting/utils.py` | Utility functions |
| `tests/__init__.py` | Test package init |
| `tests/test_utils.py` | Utility function tests |
| `tests/test_detector.py` | Detector unit tests |
| `tests/test_integration.py` | End-to-end tests |

---

## Next Steps (Phase 2)

1. Add `DesktopNotifier` class with platform detection
2. Implement `--notify` flag for desktop notifications
3. Implement `--no-bell` flag to disable terminal bell
4. Add `--debug` flag for verbose output
5. Expand test coverage for notification scenarios
