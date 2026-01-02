# Developer Testing Guide

How to test the `waiting` wrapper while developing.

## Setup

```bash
cd /path/to/waiting
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

## Quick Test Cycle

After making changes, test immediately:

```bash
# Reload your changes (editable install auto-reloads)
waiting echo "test"
```

## Test Commands

### 1. Basic Smoke Tests

```bash
# Should exit immediately, no bell
waiting echo "hello"

# Should exit with code 1
waiting false
echo $?  # Prints: 1

# Should exit with code 0
waiting true
echo $?  # Prints: 0
```

### 2. Bell Detection Tests

```bash
# SHOULD trigger bell (prompt with colon)
waiting python -c "input('Enter name: ')"

# SHOULD trigger bell (prompt with question mark)
waiting python -c "input('Continue? ')"

# SHOULD trigger bell (Y/n prompt)
waiting python -c "input('[Y/n] ')"

# Should NOT trigger bell (no prompt pattern)
waiting sleep 2

# Should NOT trigger bell (exits too fast)
waiting echo "fast exit"
```

### 3. Interactive Tests

```bash
# Test Python REPL - bell at each >>> prompt
waiting python3
# Type some commands, verify bell rings at each prompt
# Exit with: exit()

# Test with a real interactive program
waiting less README.md
# Verify: bell rings, arrow keys work, 'q' exits
```

### 4. Signal Tests

```bash
# Ctrl+C should kill the wrapped command
waiting sleep 100
# Press Ctrl+C - should exit immediately

# Exit code for killed process
waiting sleep 100
# Press Ctrl+C
echo $?  # Should print 130 (128 + SIGINT)
```

### 5. PTY Transparency Tests

```bash
# Colors should work
waiting ls --color=auto

# Arrow keys should work in interactive programs
waiting python3
# Press up arrow - should show command history

# Window resize should work
waiting vim test.txt
# Resize terminal window - vim should adapt
```

## Automated Tests

```bash
# Run all tests
make test

# Run with verbose output
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_detector.py -v

# Run specific test
python -m pytest tests/test_utils.py::TestStripAnsi::test_color_codes -v

# Run with print output visible
python -m pytest tests/ -v -s
```

## Debugging

### Add Debug Output

Temporarily add prints to see what's happening:

```python
# In detector.py
def check(self, pty_fd: int) -> bool:
    print(f"DEBUG: state={self.state}, last_line={self.last_line!r}")
    # ...
```

### Test Detection Logic Directly

```python
# Quick REPL test
source venv/bin/activate
python3

>>> from waiting.utils import matches_prompt_pattern
>>> matches_prompt_pattern("Enter password:")
True
>>> matches_prompt_pattern("Processing...")
False

>>> from waiting.utils import strip_ansi
>>> strip_ansi("\x1b[32mgreen\x1b[0m")
'green'
```

### Test Detector State Machine

```python
python3

>>> from waiting.detector import WaitDetector, State
>>> d = WaitDetector()
>>> d.state
<State.RUNNING: 1>

>>> d.record_output(b"Enter name: ")
>>> d.last_line
'Enter name: '

>>> # Simulate stall
>>> import time
>>> d.last_output_time = time.monotonic() - 3  # 3 seconds ago
>>> from unittest.mock import patch
>>> with patch('waiting.detector.is_raw_mode', return_value=False):
...     result = d.check(0)
>>> d.state
<State.WAITING: 2>
>>> result
True
```

## Common Issues

### Bell Not Sounding

1. Test bell directly: `printf '\a'`
2. Check terminal settings (audible bell enabled)
3. Check system volume

### Changes Not Taking Effect

1. Make sure you used `pip install -e .` (editable install)
2. For `__init__.py` version changes, reinstall: `pip install -e .`

### Tests Failing

```bash
# See full error output
python -m pytest tests/ -v --tb=long

# Run just the failing test
python -m pytest tests/test_detector.py::TestIsRawMode -v
```

## Test Matrix

Run through this checklist before committing:

| Test | Command | Expected |
|------|---------|----------|
| Fast exit | `waiting echo hi` | No bell, exits 0 |
| Exit code | `waiting false` | No bell, exits 1 |
| Prompt colon | `waiting python -c "input('x: ')"` | Bell rings |
| Prompt question | `waiting python -c "input('x? ')"` | Bell rings |
| No prompt | `waiting sleep 2` | No bell |
| Ctrl+C | `waiting sleep 100` + Ctrl+C | Exits immediately |
| Colors | `waiting ls --color` | Colors visible |
| REPL | `waiting python3` | Bell at >>> |
| All tests | `make test` | 41 passed |

## File Watching (Optional)

Auto-run tests on file changes:

```bash
pip install pytest-watch
ptw tests/
```
