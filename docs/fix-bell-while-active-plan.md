# Plan: Fix Bell Ringing While User is Active

## Problem
The bell rings constantly because:
1. Raw mode detection alone triggers WAITING state (line 102-103)
2. Many CLIs (like Claude Code) keep terminal in raw mode constantly
3. No tracking of user activity - bell rings even while typing

## Root Cause (detector.py lines 99-103)
```python
def _check_waiting(self, pty_fd: int, now: float) -> bool:
    if is_raw_mode(pty_fd):
        return True  # TOO AGGRESSIVE - raw mode alone shouldn't trigger
```

## Solution: Two Changes

### Change 1: Require Output Stall for ALL Detection
Raw mode alone is not enough. Require output stall + (raw mode OR prompt pattern).

```python
def _check_waiting(self, pty_fd: int, now: float) -> bool:
    """Determine if the command is currently waiting for input."""
    stall_duration = now - self.last_output_time

    # Must have output stall before considering waiting
    if stall_duration < STALL_THRESHOLD:
        return False

    # After stall: check raw mode OR prompt pattern
    if is_raw_mode(pty_fd):
        return True
    if matches_prompt_pattern(self.last_line):
        return True

    return False
```

### Change 2: Track User Input Recency
Don't alert if user recently typed.

Add constant:
```python
USER_IDLE_THRESHOLD = 2.0  # seconds of no typing before alerting
```

Add instance variable in `__init__`:
```python
self.last_input_time = time.monotonic()
```

Update `record_input()`:
```python
def record_input(self) -> None:
    self.last_input_time = time.monotonic()
    if self.state == State.WAITING:
        self._transition_to_running("input")
```

Update `_should_alert()` (add at top):
```python
def _should_alert(self, now: float) -> bool:
    # Don't alert if user recently typed
    if now - self.last_input_time < USER_IDLE_THRESHOLD:
        return False
    # ... rest of existing logic
```

## Files Modified
- `waiting/detector.py` only

## Testing
```bash
waiting python -c "input('test: ')"
# 1. Wait without typing - bell after ~2 seconds
# 2. Type something, then stop - bell after ~2 seconds of idle
# 3. Keep typing - NO bell while typing
```
