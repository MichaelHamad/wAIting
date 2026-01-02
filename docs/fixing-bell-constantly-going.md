# Fixing Bell Constantly Going Off

## Fundamental Concern

`waiting` runs *inside* a terminal process. It has no way to know if that terminal window is:
- The active/focused window (user is looking at it)
- A background window (user is in another app)

The bell should only ring when the user is **not paying attention** to the terminal. But from inside a PTY wrapper, we cannot detect window focus state.

## What We Currently Detect

- Output stalled ✓
- User hasn't typed recently ✓
- Raw mode / prompt pattern ✓

## What We CAN'T Detect From Inside a Terminal

- Is the terminal window focused?
- Is the user looking at the screen?
- Is the terminal app (Terminal/Cursor/iTerm/VS Code) the frontmost application?

## Why "User Idle" Isn't Enough

If the user stops typing for 2 seconds while reading output, the bell rings - even though they're actively watching the terminal. The current implementation conflates "not typing" with "not paying attention."

## Possible Solutions

### 1. OS-Level Focus Detection (macOS specific)
- Use `osascript` or `NSWorkspace` to check if Terminal/Cursor/iTerm is the frontmost app
- Adds complexity and OS dependency
- Would need to handle multiple terminal apps

### 2. Increase Idle Threshold Significantly
- e.g., 30+ seconds of no typing
- Assumes if you haven't typed in 30s, you've walked away
- Simple but imprecise - false negatives for quick breaks

### 3. Only Alert on Window Blur Event
- Requires terminal integration
- Not possible from within a PTY
- Would need terminal-specific plugins/extensions

### 4. Manual Toggle (Simplest)
- Add a `--background` flag that user sets when they know they'll step away
- User explicitly opts into alerts
- No false positives, but requires user action

### 5. Hybrid Approach
- Combine OS focus detection with idle threshold
- Only alert if: terminal NOT focused AND user idle AND command waiting
- Best accuracy but most complex

## Current Status

Investigating solutions. Need to decide on approach before implementation.

---

## Investigation: Why Bell Still Rings After Recent Fix

### The Problem
After implementing user idle tracking and requiring output stall, the bell STILL rings:
- While Claude is generating output (during "thinking" pauses)
- While user is typing

### Root Cause Analysis

Looking at `runner.py` I/O loop (lines 134-163):
1. Output read in chunks, `record_output()` called
2. Input read, `record_input()` called
3. Then `detector.check()` runs

**The issue:** Claude Code (and LLM CLIs) have natural pauses >2 seconds while "thinking":
1. `stall_duration` exceeds 2.0 seconds (STALL_THRESHOLD)
2. `is_raw_mode()` returns `True` (Claude Code uses raw mode constantly)
3. Detector thinks command is waiting for input
4. User hasn't typed in 2+ seconds (they're waiting for Claude)
5. Bell rings - FALSE POSITIVE

### Why Raw Mode Detection Fails for LLM CLIs

Raw mode detection was designed for simple prompts like `input("Name: ")`. But LLM CLIs:
- Are ALWAYS in raw mode (for reading keystrokes)
- Have long pauses between output chunks (thinking time)
- The pause + raw mode = false "waiting for input" detection

### Proposed Fix

**Option A: Remove raw mode detection entirely**
- Only use stall + prompt pattern matching
- More conservative, fewer false positives
- May miss some edge cases

**Option B: Increase stall threshold significantly**
- e.g., 10-30 seconds
- Assumes LLM thinking time is <10 seconds
- May still have false positives with slow models

**Option C: Track output streaming state**
- If output was received recently (within last N seconds), don't alert
- Distinguishes "paused while outputting" from "truly waiting for input"

---

## Key Insight: Primary Use Case is LLM CLIs

The primary purpose of `waiting` is to support **vibe coding** - working with LLM CLIs like Claude Code, Cursor, etc.

### What "Waiting for Input" Means for LLM CLIs

**IS waiting for input:**
- LLM finished responding, showing prompt like `>`
- LLM asking a clarifying question
- LLM waiting for user approval/confirmation

**NOT waiting for input:**
- LLM is "thinking" (pausing between output chunks)
- LLM is streaming output slowly
- LLM is processing/running tools

### Revised Detection Strategy

1. **Remove raw mode detection entirely** - useless for LLM CLIs
2. **Increase stall threshold significantly** - LLMs can think for 30-60+ seconds
3. **Prompt pattern is the KEY signal** - detect actual prompts like `>`, `?`
4. **Only alert when:** stall (30+ seconds) AND prompt pattern detected AND user idle

### Recommended Implementation

```python
# New thresholds for LLM CLI use case
STALL_THRESHOLD = 30.0  # LLMs can think for a long time
USER_IDLE_THRESHOLD = 5.0  # User might pause while reading

def _check_waiting(self, pty_fd: int, now: float) -> bool:
    stall_duration = now - self.last_output_time

    # Must have long stall before considering waiting
    if stall_duration < STALL_THRESHOLD:
        return False

    # Only trigger on prompt pattern - no raw mode check
    if matches_prompt_pattern(self.last_line):
        return True

    return False
```
