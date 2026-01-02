# macOS Detection Accuracy Improvements

## Current State

On macOS, `waiting` uses **heuristic detection** because `/proc` doesn't exist:

```
Alert if: (no output for 30s) AND (last line matches prompt pattern)
```

This works but has limitations:
- 30s delay before detection
- Relies on pattern matching (can miss unusual prompts)
- Can false-positive on LLM-generated text containing prompt-like patterns

## Why macOS Lacks True Detection

Linux provides `/proc/<pid>/wchan` which tells us exactly what kernel function a process is sleeping in. If it's `n_tty_read`, we know definitively the process is blocked waiting for terminal input.

macOS has no equivalent:
- No `/proc` filesystem
- `ps` only shows coarse state (`S` = sleeping, no detail on *why*)
- `dtrace` requires root or SIP disabled
- Activity Monitor doesn't expose syscall-level state

## Improvement Options (Ranked by Feasibility)

### Option A: PTY Write-Readiness Check (Recommended)

**Concept:** If the child process is blocked reading from the PTY slave, the PTY master should be write-ready (kernel is waiting to deliver data).

```python
import select

def is_child_likely_waiting(master_fd: int) -> bool:
    _, writable, _ = select.select([], [master_fd], [], 0)
    return len(writable) > 0
```

**Pros:**
- Pure stdlib, no dependencies
- Works on macOS and Linux
- Can reduce stall threshold to 2-5s

**Cons:**
- Not 100% reliable (fd can be write-ready for other reasons)
- Best combined with short stall check

**Implementation:**
```python
# In _check_waiting():
if stall_duration >= 2.0:  # Short stall
    _, writable, _ = select.select([], [pty_fd], [], 0)
    if writable and matches_prompt_pattern(self.last_visible_line):
        return True
```

### Option B: termios Raw Mode Detection

**Concept:** Interactive prompts often switch the terminal to raw mode for character-by-character input.

```python
import termios

def is_raw_mode(fd: int) -> bool:
    attrs = termios.tcgetattr(fd)
    lflag = attrs[3]
    return not (lflag & termios.ICANON)
```

**Pros:**
- Works on macOS
- Good signal for interactive prompts

**Cons:**
- LLM CLIs (Claude Code, etc.) are always in raw mode
- Can't distinguish "prompt raw mode" from "always raw mode"
- Only useful for traditional CLI tools

### Option C: Process Group / Session Monitoring

**Concept:** Check if the foreground process group is waiting for input.

```python
import os

def get_foreground_pgrp(fd: int) -> int:
    return os.tcgetpgrp(fd)
```

**Pros:**
- Can identify which process is in foreground
- stdlib only

**Cons:**
- Doesn't tell us if that process is blocked on read
- Limited additional signal

### Option D: libproc via ctypes (Advanced)

**Concept:** macOS has `libproc` which can get process info.

```python
import ctypes

libproc = ctypes.CDLL('/usr/lib/libproc.dylib')
# Use proc_pidinfo to get process state
```

**Pros:**
- More detailed than `ps`
- Might expose wait channel info

**Cons:**
- Complex, fragile
- Undocumented APIs may change
- Still won't give syscall-level detail like Linux

### Option E: Reduce Reliance on Detection

**Concept:** Instead of detecting, use UI hints.

- Add a keyboard shortcut (e.g., Ctrl+B) to manually trigger bell
- Show a status indicator in a tmux/screen status line
- Integrate with iTerm2's notification API

**Pros:**
- 100% reliable (user-triggered)
- No false positives

**Cons:**
- Requires user action
- Defeats purpose of automatic detection

---

## Recommended macOS Strategy

Combine **Option A + current heuristic** for best results:

```python
def _check_waiting_macos(self, pty_fd: int, now: float) -> bool:
    stall_duration = now - self.last_output_time

    # Quick check: if output is fresh, not waiting
    if stall_duration < 2.0:
        return False

    # Check PTY write-readiness
    _, writable, _ = select.select([], [pty_fd], [], 0)
    if not writable:
        return False  # Child not blocked on read

    # PTY is write-ready + stalled = likely waiting
    # Use pattern matching as confirmation
    if matches_prompt_pattern(self.last_visible_line):
        return True

    # Long stall with write-ready = probably waiting even without pattern
    if stall_duration >= 10.0:
        return True

    return False
```

**Benefits:**
- Reduces detection time from 30s to 2-10s
- PTY write-readiness adds confidence
- Pattern matching reduces false positives
- Falls back to time-based detection for unusual prompts

---

## Implementation Priority

| Priority | Option | Effort | Improvement |
|----------|--------|--------|-------------|
| P0 | A (PTY write-ready) | Low | 2-5s detection |
| P1 | Tune patterns for Claude/Cursor | Low | Fewer misses |
| P2 | D (libproc) | High | Marginal |
| Skip | B (raw mode) | Low | Not useful for LLM CLIs |

---

## Testing on macOS

After implementing Option A:

```bash
# Should alert within 5s
waiting cat

# Should alert within 5s
waiting bash -c 'read -p "Name: " x'

# Should NOT alert (no prompt)
waiting sleep 60
```

---

## Environment Variables

For tuning without code changes:

```bash
# Reduce stall threshold for faster detection
export WAITING_STALL=10

# Reduce nag interval
export WAITING_NAG=30

# Enable debug logging (if implemented)
export WAITING_DEBUG=1
```
