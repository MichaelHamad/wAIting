# Plan: True Input-Blocked Detection via Process Introspection

## Goal

Replace heuristic detection (stall + pattern match) with **true detection** of whether the child process is blocked waiting for user input on stdin.

## Current Approach (Heuristic)

```
Alert if: (no output for 30s) AND (last line matches prompt pattern)
```

**Problem:** False positives/negatives when patterns don't match reality.

## Proposed Approach (True Detection)

```
Alert if: (child process is blocked in read() syscall on PTY) AND (user idle)
```

---

## Technical Implementation

### Linux: `/proc/<pid>/stat` and `/proc/<pid>/wchan`

#### Signal 1: Process State

```bash
cat /proc/<pid>/stat | awk '{print $3}'
```

Returns single character:
- `S` = Sleeping (interruptible) — **likely blocked on I/O**
- `R` = Running
- `D` = Disk sleep (uninterruptible)
- `Z` = Zombie
- `T` = Stopped

**Blocked on read = state `S`**

#### Signal 2: Wait Channel (wchan)

```bash
cat /proc/<pid>/wchan
```

Returns kernel function where process is sleeping:
- `do_select` — blocked in select()
- `n_tty_read` — **blocked reading from TTY**
- `wait_woken` — waiting for I/O
- `pipe_read` — blocked on pipe
- `unix_stream_read_generic` — blocked on socket

**Key signal:** `n_tty_read` or `tty_read` = blocked reading from terminal.

#### Signal 3: File Descriptor State

```bash
ls -la /proc/<pid>/fd/0
```

Check if fd 0 (stdin) points to the PTY we control.

### macOS: `ps` and `dtrace`

#### Signal 1: Process State via `ps`

```bash
ps -o state= -p <pid>
```

Returns:
- `S` = Sleeping
- `R` = Running
- `U` = Uninterruptible wait

Less granular than Linux — can't distinguish *why* it's sleeping.

#### Signal 2: `dtrace` (requires SIP disabled or entitlements)

```bash
sudo dtrace -n 'syscall::read:entry /pid == $target/ { printf("read on fd %d", arg0); }' -p <pid>
```

**Problem:** Requires root or special entitlements. Not practical for general use.

#### Signal 3: `lsof` for fd inspection

```bash
lsof -p <pid> | grep -E "^.*\s+0[rwu]"
```

Shows what fd 0 is connected to.

---

## Implementation Plan

### Phase 1: Linux Implementation (P0)

**File:** `waiting/detector.py`

#### 1.1 Add process introspection module

Create `waiting/process_state.py`:

```python
import os
from enum import Enum
from typing import Optional

class BlockedState(Enum):
    UNKNOWN = "unknown"
    NOT_BLOCKED = "not_blocked"
    BLOCKED_TTY_READ = "blocked_tty_read"
    BLOCKED_OTHER = "blocked_other"

def get_blocked_state_linux(pid: int) -> BlockedState:
    """Check if process is blocked reading from TTY on Linux."""
    try:
        # Check process state
        with open(f"/proc/{pid}/stat") as f:
            stat = f.read().split()
            state = stat[2]  # Third field is state
            if state != 'S':
                return BlockedState.NOT_BLOCKED

        # Check wait channel
        wchan_path = f"/proc/{pid}/wchan"
        if os.path.exists(wchan_path):
            with open(wchan_path) as f:
                wchan = f.read().strip()
                if wchan in ('n_tty_read', 'tty_read', 'wait_woken'):
                    return BlockedState.BLOCKED_TTY_READ
                elif wchan in ('do_select', 'poll_schedule_timeout'):
                    # Might be blocked on TTY via select
                    return BlockedState.BLOCKED_OTHER

        return BlockedState.BLOCKED_OTHER
    except (FileNotFoundError, PermissionError, IndexError):
        return BlockedState.UNKNOWN
```

#### 1.2 Modify detector to use true detection on Linux

```python
import platform

def _check_waiting(self, pty_fd: int, now: float) -> bool:
    # Startup grace period
    if now - self.startup_time < STARTUP_GRACE:
        return False

    # TRUE DETECTION: Check if child is blocked on TTY read
    if platform.system() == 'Linux' and self.child_pid:
        from .process_state import get_blocked_state_linux, BlockedState
        state = get_blocked_state_linux(self.child_pid)
        if state == BlockedState.BLOCKED_TTY_READ:
            return True
        elif state == BlockedState.NOT_BLOCKED:
            return False
        # If UNKNOWN, fall through to heuristic

    # FALLBACK: Heuristic detection (macOS, or Linux edge cases)
    stall_duration = now - self.last_output_time
    if stall_duration < STALL_THRESHOLD:
        return False
    return matches_prompt_pattern(self.last_visible_line)
```

#### 1.3 Pass child_pid to detector

Modify `runner.py` to pass `child_pid` to detector:

```python
self.detector = WaitDetector(child_pid=self.child_pid)
```

### Phase 2: macOS Fallback (P1)

macOS lacks `/proc`, so we use a hybrid approach:

#### 2.1 Use `select()` write-readiness as proxy

If the child is blocked reading from the PTY, the master fd should be write-ready (the kernel is waiting to deliver input to the child).

```python
def is_child_waiting_for_input_macos(master_fd: int) -> bool:
    """Check if child is likely blocked waiting for input."""
    import select
    _, writable, _ = select.select([], [master_fd], [], 0)
    return len(writable) > 0
```

**Caveat:** This isn't 100% reliable — fd might be write-ready for other reasons. Use in combination with output stall.

#### 2.2 Hybrid macOS detection

```python
if platform.system() == 'Darwin':
    stall_duration = now - self.last_output_time
    if stall_duration < STALL_THRESHOLD:
        return False

    # Check if master fd is write-ready (child waiting for input)
    if is_child_waiting_for_input_macos(pty_fd):
        return True

    # Fall back to pattern matching
    return matches_prompt_pattern(self.last_visible_line)
```

### Phase 3: Handle Subprocesses (P2)

Problem: The child might spawn subprocesses (e.g., `claude` spawns `node`). We need to check *all* descendants.

#### 3.1 Find all descendant PIDs

```python
def get_descendant_pids_linux(pid: int) -> list[int]:
    """Get all descendant PIDs of a process."""
    descendants = []
    try:
        children_path = f"/proc/{pid}/task/{pid}/children"
        if os.path.exists(children_path):
            with open(children_path) as f:
                child_pids = [int(p) for p in f.read().split()]
                for child_pid in child_pids:
                    descendants.append(child_pid)
                    descendants.extend(get_descendant_pids_linux(child_pid))
    except (FileNotFoundError, PermissionError, ValueError):
        pass
    return descendants
```

#### 3.2 Check if any descendant is blocked on TTY

```python
def any_descendant_blocked_on_tty(pid: int) -> bool:
    all_pids = [pid] + get_descendant_pids_linux(pid)
    return any(
        get_blocked_state_linux(p) == BlockedState.BLOCKED_TTY_READ
        for p in all_pids
    )
```

---

## Testing Plan

### Unit Tests

| Test | Description |
|------|-------------|
| `test_blocked_state_running_process` | Process actively running returns NOT_BLOCKED |
| `test_blocked_state_sleeping_on_tty` | Process in `cat` returns BLOCKED_TTY_READ |
| `test_blocked_state_sleeping_on_pipe` | Process in `read` on pipe returns BLOCKED_OTHER |
| `test_descendant_detection` | Finds grandchild blocked on TTY |
| `test_fallback_on_permission_error` | Returns UNKNOWN gracefully |

### Integration Tests

| Test | Scenario | Expected |
|------|----------|----------|
| `test_true_detect_cat` | Run `waiting cat`, wait 5s | Alert (cat blocked on stdin) |
| `test_true_detect_read_builtin` | Run `waiting bash -c 'read x'` | Alert |
| `test_no_alert_sleep` | Run `waiting sleep 60` | No alert (not blocked on TTY) |
| `test_no_alert_long_compile` | Run `waiting make bigproject` | No alert |
| `test_alert_sudo` | Run `waiting sudo ls` (password prompt) | Alert |

### Manual Validation

1. Run `waiting claude` in real workflow
2. Trigger choice dialog
3. Verify alert fires within 1-2s (not 30s)
4. Verify no false alerts during code generation

---

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `/proc` read fails (permissions) | Low | Fall back to heuristic |
| wchan names vary by kernel version | Medium | Match multiple variants |
| macOS `select()` false positives | Medium | Combine with stall check |
| Subprocess not detected | Low | Recursive descendant check |
| Performance overhead from /proc reads | Low | Read at most every 100ms |

---

## Success Criteria

1. **No false positives** during 60s LLM "thinking" pause
2. **Alert within 2s** when actual interactive prompt appears
3. **Works on Linux** with true detection
4. **Works on macOS** with improved heuristic
5. **All existing tests pass**
6. **New integration tests for true detection**

---

## File Changes Summary

| File | Change |
|------|--------|
| `waiting/process_state.py` | NEW - Process introspection functions |
| `waiting/detector.py` | Use true detection on Linux, pass child_pid |
| `waiting/runner.py` | Pass child_pid to detector |
| `tests/test_process_state.py` | NEW - Unit tests for introspection |
| `tests/test_true_detection.py` | NEW - Integration tests |

---

## Implementation Order

1. **P0:** Linux `/proc` introspection (`process_state.py`)
2. **P0:** Integrate into detector with fallback
3. **P1:** macOS `select()` write-readiness check
4. **P2:** Descendant process handling
5. **P2:** Reduce STALL_THRESHOLD on Linux (since we have true detection)

---

## Timeline Estimate

Not provided — focus on correctness over speed.
