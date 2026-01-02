# Project Status - January 1-2, 2026

## Project Overview

**waiting** - CLI utility that detects when LLM CLIs (Claude Code, Cursor, etc.) are waiting for user input via interactive choice dialogs and alerts the user with a bell sound.

**Core Problem Solved:** Vibe coders often miss interactive prompts while tabbed out or not paying attention, blocking the LLM from continuing.

---

## Current Status: IMPLEMENTATION IN PROGRESS

**Phase:** Detection logic refinement (moved past MVP into real-world testing)

**Health:** 43 tests passing, basic functionality working, detection strategy refined

---

## What We Built

### Core Architecture (Working ✅)
- **runner.py** (213 lines) - PTY wrapper with I/O multiplexing
  - `pty.fork()` spawns commands in pseudo-terminal
  - `select.select()` with 100ms polling
  - Signal handling (SIGINT, SIGTERM, SIGWINCH)
  - Transparent I/O passthrough

- **detector.py** (159 lines) - State machine for wait detection
  - `State.RUNNING` / `State.WAITING` states
  - Output stall detection
  - Interactive mode sequence detection
  - User idle tracking

- **notifiers.py** (27 lines) - Custom sound notifications
  - Plays `bell.wav` using `afplay`
  - Falls back to terminal bell if missing

- **utils.py** (55 lines) - Prompt pattern matching
  - ANSI stripping
  - Comprehensive prompt pattern detection

- **cli.py** (49 lines) - Argument parsing
- **events.py** (22 lines) - Event dataclasses

### Test Suite (Working ✅)
- 43 tests passing (16 detector, 11 utils, 16 integration)
- Interactive mode detection tests
- State transition tests
- Pattern matching tests

---

## Recent Changes (This Session)

### Problem Discovered
Bell was ringing constantly because:
1. Raw mode detection too aggressive (LLM CLIs always in raw mode)
2. Stall threshold too short (2s - LLMs pause longer)
3. Text pattern matching fragile (sequences overwrote visible text)

### Solution Implemented
**Detection Strategy Shift: Terminal Sequence Detection**

Moved from text pattern matching to detecting terminal control sequences that indicate interactive mode:

**INTERACTIVE_SEQUENCES:**
- `\x1b[?2026l` - synchronized update end (menu finished drawing)
- `\x1b[?25l` - cursor hidden (interactive input mode)
- `\x1b[?1049h` - alternate screen buffer (full-screen UI)

**New Detection Logic:**
```
Bell rings when ALL true:
1. Output stalled (5+ seconds for testing)
2. Interactive sequence detected OR prompt pattern matched
3. User hasn't typed in 5+ seconds
4. State is WAITING
```

**Key Fix:** Reset `interactive_mode` if output continues without the sequence (means CLI is still outputting, not waiting for input)

---

## Current Issue Being Tested

**Issue:** Bell keeps ringing at startup because `\x1b[?2026l` is sent during normal output initialization.

**Solution Applied:** Only keep `interactive_mode = True` if output stops after the sequence. If more output comes without the sequence, reset to False.

**Status:** Awaiting functional test in Claude Code window. User restarted with latest fix.

---

## Thresholds (Current Testing Values)

```python
STALL_THRESHOLD = 5.0         # seconds before checking for waiting
NAG_INTERVAL = 5.0            # repeat alert interval
USER_IDLE_THRESHOLD = 5.0     # seconds of no typing
MIN_ALERT_GAP = 1.0           # minimum between any alerts
```

*Note: Set to 5s for quick testing. Production should be 30s for STALL_THRESHOLD*

---

## What's Working

✅ PTY wrapper and I/O passthrough
✅ Custom bell.wav notifications
✅ Terminal sequence detection for interactive mode
✅ User idle tracking
✅ Nag interval (repeat alerts)
✅ State machine transitions
✅ Test suite (43 tests)

---

## What Needs Work

⚠️ Fine-tune interactive sequence detection (false positives at startup)
⚠️ Increase STALL_THRESHOLD to 30s for production
⚠️ Test against real Claude Code/Cursor workflows
⚠️ Handle edge cases (rapid mode switching, etc.)

---

## Files Modified This Session

- `waiting/detector.py` - Complete rewrite of detection logic
- `waiting/utils.py` - Added Claude CLI prompt patterns
- `tests/test_detector.py` - Rewrote tests for interactive mode
- Various docs created/updated

---

## Documentation Created

- `docs/progress-check-jan-2026.md` - Challenge summary
- `docs/interactive-mode-detection-plan.md` - Detection strategy
- `docs/fixing-bell-constantly-going.md` - Problem analysis
- `docs/functional-test-plan.md` - Test procedures
- `docs/QUICKSTART.md` - User guide
- `docs/implement-custom-bell-plan.md` - Bell implementation
- `docs/fix-bell-while-active-plan.md` - Earlier iteration

---

## Next Steps

1. **Test current fix** - Verify bell behavior in Claude Code window
2. **Validate detection** - Ensure bell only rings for choice dialogs
3. **Production thresholds** - Increase STALL_THRESHOLD to 30s
4. **Edge case testing** - Rapid output changes, nested prompts
5. **Phase 2 features** - Desktop notifications, CLI flags

---

## Key Learnings

1. **Clarify use case upfront** - Initial approach was generic CLI detection, needed LLM CLI specifics
2. **Terminal sequences matter** - They contain more reliable signals than visible text
3. **Text patterns are fragile** - Control sequences overwrite last_line, breaking matching
4. **Thresholds matter for LLMs** - 2s stall too short, need 30s+ for LLM thinking
5. **Debug output essential** - Only found `\x1b[?2026l` issue through stderr logging

---

## Architecture Strengths

- Clean separation: runner → detector → notifier
- Extensible detection (easy to add new signals)
- State machine prevents false positives
- No external dependencies (stdlib only)
- Comprehensive test coverage

---

## Known Limitations

- No OS-level window focus detection (can't tell if user tabbed out)
- Terminal sequence detection may vary across terminals
- Thresholds tuned for Claude CLI, may need adjustment for other LLMs
- Only works with systems supporting `afplay` (macOS)

---

## Recommended Testing Plan

1. **Interactive mode tests:**
   - Ask Claude Code to show a choice dialog
   - Wait without typing - verify bell rings ~10s
   - Type quickly - verify bell doesn't ring
   - Let Claude finish outputting - verify bell turns off

2. **Edge cases:**
   - Rapid output switches
   - Slow LLM responses (>30s thinking)
   - Nested menus

3. **Production settings:**
   - Increase STALL_THRESHOLD to 30s
   - Re-test all scenarios

---

## Session Summary

Shifted detection strategy from text pattern matching to terminal sequence detection. This is more reliable for LLM CLIs because terminal sequences are the actual mechanism used for interactive prompts. Currently testing the fix for false positives at startup.
