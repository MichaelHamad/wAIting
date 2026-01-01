# Implementation Plan: waiting

A CLI utility that detects when interactive commands are waiting for user input and alerts the developer.

---

## Overview

Build a transparent PTY wrapper that:
1. Spawns commands in a pseudo-terminal
2. Detects waiting states via terminal mode + output stall heuristics
3. Alerts via terminal bell (and optionally desktop notifications)
4. Passes through all I/O transparently (zero visual change)

---

## File Structure

```
waiting/
├── __init__.py          # Package init, version
├── __main__.py          # Entry: python -m waiting
├── cli.py               # Argument parsing (argparse)
├── runner.py            # PTY spawn + bidirectional I/O passthrough
├── detector.py          # Wait detection state machine
├── events.py            # Event types (dataclasses)
├── notifiers.py         # Bell + desktop notification handlers
└── utils.py             # ANSI stripping, helpers

tests/
├── __init__.py
├── test_detector.py     # Unit tests for wait detection logic
├── test_utils.py        # Unit tests for utilities
└── test_integration.py  # End-to-end tests

pyproject.toml           # Package config + entry point
```

---

## Implementation Steps

### Step 1: Project Scaffolding
Create `pyproject.toml` with:
- Package metadata (name, version, description)
- Python 3.10+ requirement
- Console script entry point: `waiting = "waiting.cli:main"`
- No external dependencies

Create `waiting/__init__.py` with version string.

### Step 2: Events Module (`events.py`)
Define event types as dataclasses:
```python
@dataclass
class WaitingEntered:
    timestamp: float

@dataclass
class WaitingExited:
    timestamp: float
    reason: str  # "input", "output", "exit"

@dataclass
class ProcessExited:
    exit_code: int
```

### Step 3: Utilities Module (`utils.py`)
- `strip_ansi(text: str) -> str` - Remove ANSI escape codes
- `matches_prompt_pattern(line: str) -> bool` - Check against prompt patterns
- Prompt patterns from spec: `?`, `:`, `>`, `[Y/n]`, `[yes/no]`, `(y/n)`

### Step 4: Wait Detector (`detector.py`)
State machine with states: `RUNNING`, `WAITING`

Detection logic:
```python
def check_waiting(pty_fd, last_output_time, last_line) -> bool:
    # Primary: raw mode detection
    if is_raw_mode(pty_fd):
        return True

    # Secondary: output stall + prompt pattern
    stalled = (time.monotonic() - last_output_time) >= STALL_THRESHOLD
    if stalled and matches_prompt_pattern(last_line):
        return True

    return False
```

Configuration:
- `STALL_THRESHOLD = 2.0` seconds
- `NAG_INTERVAL = 25` seconds (repeat alert while waiting)

Emit events on state transitions.

### Step 5: Notifiers (`notifiers.py`)
```python
class BellNotifier:
    def notify(self):
        sys.stdout.write('\a')
        sys.stdout.flush()

class DesktopNotifier:
    def notify(self):
        if sys.platform == 'darwin':
            subprocess.run(['osascript', '-e',
                'display notification "Command needs input" with title "waiting"'])
        else:  # Linux
            subprocess.run(['notify-send', 'waiting', 'Command needs input'])
```

### Step 6: PTY Runner (`runner.py`)
Core I/O loop:
1. Fork PTY with `pty.fork()`
2. Set up signal handlers (SIGINT, SIGTERM, SIGWINCH)
3. Use `select.select()` to multiplex:
   - stdin → pty (user input)
   - pty → stdout (command output)
4. Track `last_output_time` and `last_line` for detector
5. On stdin activity: signal detector (input detected)
6. Poll detector periodically (~100ms)
7. Handle window resize (SIGWINCH → `ioctl` TIOCSWINSZ)

Key considerations:
- Set stdin to raw mode for transparent passthrough
- Restore terminal settings on exit (cleanup handler)
- Pass through SIGINT to child process

### Step 7: CLI Interface (`cli.py`)
```python
def main():
    parser = argparse.ArgumentParser(
        prog='waiting',
        description='Run a command and alert when it waits for input'
    )
    parser.add_argument('command', nargs=argparse.REMAINDER)
    parser.add_argument('--notify', action='store_true',
                        help='Enable desktop notifications')
    parser.add_argument('--no-bell', action='store_true',
                        help='Disable terminal bell')

    args = parser.parse_args()
    # ... run command with runner
    sys.exit(exit_code)  # passthrough exit code
```

### Step 8: Entry Point (`__main__.py`)
```python
from waiting.cli import main
if __name__ == '__main__':
    main()
```

### Step 9: Unit Tests
Using `unittest`:

**test_detector.py:**
- Test `is_raw_mode()` with mocked termios
- Test state transitions (RUNNING → WAITING → RUNNING)
- Test debounce/nag interval logic

**test_utils.py:**
- Test `strip_ansi()` with various escape codes
- Test `matches_prompt_pattern()` with examples from spec

**test_integration.py:**
- Test with `python -c "input('test: ')"`
- Test with `sleep 1` (no alert)
- Test with `echo hello` (immediate exit)
- Test Ctrl+C passthrough

---

## Key Design Decisions

### Debounce Strategy
- Alert immediately on entering WAITING state
- Repeat ("nag") every 25 seconds while still waiting
- Stop immediately when:
  - Stdin activity detected (user typing)
  - Output resumes from command
  - Process exits
- Global minimum 1 second between any alerts (safety net)

### Transparency
- No output from `waiting` itself (unless `--debug` in future)
- Only side-channel: `\a` bell character, OS notifications
- Exit code passthrough

### Terminal Handling
- Save/restore terminal settings with `termios.tcgetattr/tcsetattr`
- Use `atexit` + signal handlers for cleanup
- Handle SIGWINCH for window resize propagation

---

## Success Criteria Verification

| Test | Expected |
|------|----------|
| `waiting python -c "input('test: ')"` | Bell after prompt appears |
| `waiting sleep 5` | No bell (no prompt) |
| `waiting echo hello` | No bell (exits immediately) |
| Colors/arrow keys in wrapped command | Work normally |
| Ctrl+C | Kills wrapped command |
| Exit code | Passed through |

---

## Implementation Order

1. `pyproject.toml` + `waiting/__init__.py` (scaffolding)
2. `events.py` (simple dataclasses)
3. `utils.py` (ANSI strip, prompt matching)
4. `detector.py` (state machine, detection logic)
5. `notifiers.py` (bell, desktop)
6. `runner.py` (PTY + I/O loop - most complex)
7. `cli.py` + `__main__.py` (wire it together)
8. Tests
9. Manual verification of success criteria
