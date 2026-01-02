# Progress Check - January 2, 2026

## Session Goal
Get `waiting` to correctly detect when Claude CLI is waiting for user input and ring the bell.

---

## Challenges Faced

### Challenge 1: Bell Ringing Constantly
**Problem:** Bell was ringing while Claude was outputting and while user was typing.

**Root Cause:**
- Raw mode detection was too aggressive - Claude CLI is ALWAYS in raw mode
- STALL_THRESHOLD was only 2 seconds - LLMs pause longer while "thinking"

**Fix Applied:**
- Removed raw mode as sole trigger
- Increased STALL_THRESHOLD to 30 seconds
- Added USER_IDLE_THRESHOLD (5 seconds of no typing before alerting)

---

### Challenge 2: Primary Use Case Misunderstanding
**Problem:** Detection logic was built for simple CLI prompts like `input("Name:")`, not LLM CLIs.

**Root Cause:** The primary use case (vibe coding with LLM CLIs) wasn't clarified upfront.

**Impact:**
- Raw mode detection is useless for LLM CLIs (always true)
- Short stall thresholds cause false positives during LLM "thinking"

**Fix Applied:**
- STALL_THRESHOLD increased to 30s (later 5s for testing)
- Removed raw mode from detection logic
- Added prompt pattern matching for Claude CLI patterns

---

### Challenge 3: Text Pattern Matching Not Working
**Problem:** Added patterns for Claude CLI prompts (`❯`, `Do you want to`, etc.) but bell still didn't ring.

**Root Cause:** Discovered via debug output that `last_line` was capturing `'[?2026l'` (a terminal control sequence), not the visible menu text.

**Discovery:**
```
[DEBUG] stall=2.1s, pattern=False, line='[?2026l'
```

The visible menu text was being overwritten by subsequent terminal control sequences.

---

### Challenge 4: Fundamental Approach Question
**Problem:** Are we even detecting the right thing?

**Current Approach:** Pattern matching on visible text output
- Fragile - depends on exact text patterns
- Gets overwritten by terminal control sequences
- Doesn't detect the actual "waiting for input" state

**Better Approach Identified:** Detect terminal control sequences that indicate interactive mode
- `\x1b[?2026l` = end synchronized update (menu finished drawing)
- `\x1b[?25l` = cursor hidden (interactive input mode)
- These sequences ARE the signal that interactive mode started

---

## Current State

### What's Working
- Basic PTY wrapper functionality
- Custom bell.wav sound playback
- User idle detection
- Stall detection

### What's Not Working
- Reliable detection of Claude CLI's interactive prompts
- Bell not ringing when choice menus are displayed

### Files Modified This Session
- `waiting/detector.py` - thresholds, detection logic, debug output
- `waiting/utils.py` - added Claude CLI patterns
- Various docs created

---

## Next Steps

**Proposed new approach:** Instead of pattern matching visible text, detect terminal control sequences that indicate interactive selection mode:

1. Detect `\x1b[?2026l` (synchronized update end)
2. Detect `\x1b[?25l` (cursor hidden)
3. Combined with output stall = interactive mode waiting for input

This is more reliable because it detects the *mechanism* terminals use for interactive menus, not the *text* displayed.

---

## Lessons Learned

1. **Clarify use case upfront** - "LLM CLI" vs "general CLI" requires different detection strategies
2. **Debug output is essential** - We only found the `[?2026l` issue by adding debug logging
3. **Terminal control sequences matter** - They contain signals about terminal state that text patterns miss
4. **Don't patch around issues** - Address fundamental problems instead of adding workarounds
