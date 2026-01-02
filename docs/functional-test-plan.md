# Functional Test Plan for `waiting`

**Date:** January 2, 2026
**Version:** 2.0

---

## Overview

This document provides detailed test procedures for verifying the `waiting` tool correctly detects when LLM CLIs are waiting for user input and triggers bell alerts.

### Current Detection Settings

| Setting | Value | Description |
|---------|-------|-------------|
| `STALL_THRESHOLD` | 2.0s | Output stall time before checking for prompt |
| `NAG_INTERVAL` | 25.0s | Time between repeat alerts |
| `USER_IDLE_THRESHOLD` | 2.0s | User must be idle this long before alerting |
| `MIN_ALERT_GAP` | 1.0s | Minimum time between any alerts |

### Detected Prompt Patterns

The detector looks for these patterns in the last visible line:
- Endings: `?`, `:`, `>`
- Yes/No: `[Y/n]`, `[y/N]`, `[yes/no]`, `(y/n)`, `(yes/no)`
- Keywords: `password`, `enter`, `input`, `confirm`, `approve`
- Interactive: `❯`, `do you want to`, `would you like`, `select`, `choose`

---

## Test Environment Setup

```bash
# Terminal 1: Run waiting with Claude CLI
waiting claude

# Terminal 2 (optional): Monitor detector state
tail -f /tmp/waiting-debug.log
```

---

## Test Cases

### TEST 1: Question Mark Ending

**Objective:** Verify detection of prompts ending with `?`

**Prompt to paste:**
```
List exactly 3 ways to name a boolean variable, then on the FINAL line write only this text: "Which option do you prefer?"
```

**Expected behavior:**
1. Claude outputs 3 options
2. Final line is: `Which option do you prefer?`
3. After ~2 seconds of stall, bell rings
4. Bell repeats every 25 seconds if no response

**Pass criteria:** Bell rings within 5 seconds of Claude finishing output

---

### TEST 2: Colon Ending

**Objective:** Verify detection of prompts ending with `:`

**Prompt to paste:**
```
Explain what a variable is in one sentence. Then on a new line, write exactly: "Enter your answer:"
```

**Expected behavior:**
1. Claude outputs explanation
2. Final line is: `Enter your answer:`
3. Bell rings after ~2 second stall

**Pass criteria:** Bell rings within 5 seconds

---

### TEST 3: Yes/No Prompt

**Objective:** Verify detection of `[Y/n]` style prompts

**Prompt to paste:**
```
Propose renaming a variable from 'x' to 'count'. End your response with exactly: "Proceed with rename? [Y/n]"
```

**Expected behavior:**
1. Claude outputs proposal
2. Final line contains `[Y/n]`
3. Bell rings after stall

**Pass criteria:** Bell rings within 5 seconds

---

### TEST 4: Interactive Selection (❯)

**Objective:** Verify detection of arrow selector menus

**Prompt to paste:**
```
Show me a mock terminal menu that looks like this:
❯ Option 1
  Option 2
  Option 3
Then wait for my selection.
```

**Expected behavior:**
1. Claude outputs menu with `❯` character
2. Bell rings after stall (❯ pattern detected)

**Pass criteria:** Bell rings within 5 seconds

---

### TEST 5: Permission Prompt

**Objective:** Verify detection of "do you want to" prompts

**Prompt to paste:**
```
Tell me you found a bug. Then ask: "Do you want to fix it now?"
```

**Expected behavior:**
1. Claude outputs message
2. Final line contains "Do you want to"
3. Bell rings after stall

**Pass criteria:** Bell rings within 5 seconds

---

### TEST 6: Nag Interval

**Objective:** Verify bell repeats at 25-second intervals

**Prompt to paste:**
```
Ask me: "What is your name?"
```

**Procedure:**
1. Wait for first bell (~2s after output stops)
2. Do NOT type anything
3. Wait 25 more seconds
4. Second bell should ring
5. Wait 25 more seconds
6. Third bell should ring

**Pass criteria:** Bells ring at approximately 0s, 25s, 50s after detection

---

### TEST 7: User Activity Cancels Alert

**Objective:** Verify typing resets the idle timer

**Prompt to paste:**
```
Ask me: "Ready to continue?"
```

**Procedure:**
1. Wait for Claude to finish
2. Immediately start typing (anything)
3. Keep typing with gaps < 2 seconds
4. Bell should NOT ring while actively typing

**Pass criteria:** No bell while user is actively typing

---

## Negative Tests (Bell Should NOT Ring)

### NEGATIVE 1: No Prompt Pattern

**Prompt:**
```
Tell me a fun fact about penguins. Do not ask any questions.
```

**Expected:** No bell (output doesn't match prompt patterns)

---

### NEGATIVE 2: During Output

**Prompt:**
```
Write a 500-word essay about clouds.
```

**Expected:** No bell while Claude is actively outputting text

---

### NEGATIVE 3: Plain Statement

**Prompt:**
```
Say only: "The task is complete"
```

**Expected:** No bell (no prompt pattern in final line)

---

## Verification Checklist

| Test | Pattern | Bell Rang? | Time to Ring | Notes |
|------|---------|------------|--------------|-------|
| TEST 1 | `?` | ☐ | | |
| TEST 2 | `:` | ☐ | | |
| TEST 3 | `[Y/n]` | ☐ | | |
| TEST 4 | `❯` | ☐ | | |
| TEST 5 | `do you want to` | ☐ | | |
| TEST 6 | Nag interval | ☐ | | |
| TEST 7 | User activity | ☐ | | |
| NEG 1 | No pattern | ☐ | | |
| NEG 2 | During output | ☐ | | |
| NEG 3 | Statement | ☐ | | |

---

## Debugging

If tests fail, add debug output to `detector.py`:

```python
def _check_waiting(self, pty_fd: int, now: float) -> bool:
    stall_duration = now - self.last_output_time
    print(f"DEBUG: stall={stall_duration:.1f}s, line={self.last_visible_line!r}", flush=True)
    # ... rest of method
```

### Common Issues

1. **Bell never rings:** Check if `last_visible_line` contains expected pattern
2. **Bell rings during output:** `record_output()` not being called properly
3. **Wrong timing:** Verify `STALL_THRESHOLD` value in detector.py

---

## Test Results

**Tester:**
**Date:**
**Overall Result:** ☐ PASS / ☐ FAIL

**Notes:**
