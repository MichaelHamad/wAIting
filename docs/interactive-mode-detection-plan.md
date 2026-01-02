# Plan: Interactive Mode Detection for Vibe Coding

## The Goal

**Problem:** Vibe coders using LLM CLIs (Claude Code, Cursor, etc.) are often required to make choices via interactive prompts. If the user is tabbed out or not paying attention, they miss these prompts and the LLM can't continue.

**Solution:** `waiting` detects when an interactive prompt appears and rings the bell to alert the user.

---

## What We Need to Detect

When LLM CLIs show choice dialogs like:

```
Do you want to make this edit?
❯ 1. Yes
  2. Yes, allow all edits
  3. Type here to tell Claude what to do differently
```

The terminal:
1. Draws the menu
2. Sends control sequences (like `\x1b[?2026l` - end synchronized update)
3. Enters interactive mode waiting for arrow keys / enter
4. Stops outputting until user responds

**The control sequences ARE the signal that interactive mode started.**

---

## Discovery from Debugging

Debug output showed:
```
[DEBUG] stall=2.1s, pattern=False, line='[?2026l'
```

The `\x1b[?2026l` sequence is sent AFTER the menu is drawn. This sequence indicates:
- Synchronized update ended (menu finished rendering)
- Terminal is now waiting for user input

---

## Implementation Plan

### Step 1: Define Interactive Mode Sequences

Add to `detector.py`:

```python
# Terminal sequences that indicate interactive mode
INTERACTIVE_SEQUENCES = [
    b'\x1b[?2026l',   # synchronized update end (menu drawn)
    b'\x1b[?25l',     # cursor hidden (input mode)
    b'\x1b[?1049h',   # alternate screen buffer
]
```

### Step 2: Track Interactive Mode in Detector

Add to `WaitDetector.__init__`:

```python
self.interactive_mode = False
self.interactive_mode_time: Optional[float] = None
```

### Step 3: Detect Sequences in record_output

Update `record_output()` to detect sequences on raw bytes:

```python
def record_output(self, data: bytes) -> None:
    self.last_output_time = time.monotonic()

    # Detect interactive mode sequences
    for seq in INTERACTIVE_SEQUENCES:
        if seq in data:
            self.interactive_mode = True
            self.interactive_mode_time = time.monotonic()
            break

    # ... existing line extraction code ...
```

### Step 4: Update Detection Logic

Update `_check_waiting()`:

```python
def _check_waiting(self, pty_fd: int, now: float) -> bool:
    stall_duration = now - self.last_output_time

    # Must have output stall
    if stall_duration < STALL_THRESHOLD:
        return False

    # Interactive mode detected = waiting for user choice
    if self.interactive_mode:
        return True

    # Fallback: prompt pattern matching
    if matches_prompt_pattern(self.last_line):
        return True

    return False
```

### Step 5: Reset Interactive Mode on User Input

Update `record_input()`:

```python
def record_input(self) -> None:
    self.last_input_time = time.monotonic()
    self.interactive_mode = False  # User responded, exit interactive mode
    if self.state == State.WAITING:
        self._transition_to_running("input")
```

---

## Detection Logic Summary

**Bell rings when ALL of these are true:**
1. Output has stalled (5+ seconds for testing, 30s for production)
2. Interactive mode sequence was detected (`\x1b[?2026l`, etc.)
3. User hasn't typed recently (5+ seconds)

---

## Files to Modify

1. **`waiting/detector.py`**
   - Add `INTERACTIVE_SEQUENCES` constant
   - Add `interactive_mode` and `interactive_mode_time` attributes
   - Update `record_output()` to detect sequences
   - Update `_check_waiting()` to use interactive mode
   - Update `record_input()` to reset interactive mode

2. **`waiting/utils.py`** (optional)
   - Keep prompt patterns as fallback

3. **`tests/test_detector.py`**
   - Add tests for interactive mode detection

---

## Test Cases

1. **Interactive sequence triggers detection**
   - Send data containing `\x1b[?2026l`
   - Verify `interactive_mode = True`

2. **Bell rings after stall + interactive mode**
   - Simulate interactive sequence
   - Wait for stall threshold
   - Verify alert is triggered

3. **User input resets interactive mode**
   - Enter interactive mode
   - Call `record_input()`
   - Verify `interactive_mode = False`

4. **Normal output doesn't trigger interactive mode**
   - Send regular text output
   - Verify `interactive_mode = False`

---

## Thresholds

For testing:
```python
STALL_THRESHOLD = 5.0
USER_IDLE_THRESHOLD = 5.0
```

For production:
```python
STALL_THRESHOLD = 10.0  # LLMs can pause, but 10s+ with interactive mode = waiting
USER_IDLE_THRESHOLD = 5.0
```

---

## Why This Approach Works

1. **Detects the mechanism, not the text** - Terminal sequences are reliable indicators
2. **Works for all LLM CLIs** - They all use similar terminal sequences for menus
3. **Low false positive rate** - These sequences only appear for interactive prompts
4. **Fast** - Simple byte sequence search, runs in O(n) where n = output size
