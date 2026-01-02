# Plan: Replace Terminal Bell with Custom WAV Sound

## Goal
Play `bell.wav` instead of the terminal bell character (`\a`) when waiting is detected, without changing any other functionality.

## Approach
Modify `BellNotifier` to play the wav file using macOS `afplay` command. No CLI changes, no new flags - just swap the notification mechanism.

## Changes Required

### File: `waiting/notifiers.py`

**Current:**
```python
class BellNotifier:
    def notify(self) -> None:
        sys.stdout.write('\a')
        sys.stdout.flush()
```

**New:**
```python
import subprocess
from pathlib import Path

class BellNotifier:
    def __init__(self):
        # bell.wav is in the package directory
        self.sound_file = Path(__file__).parent.parent / "bell.wav"

    def notify(self) -> None:
        if self.sound_file.exists():
            # Run afplay in background, suppress output
            subprocess.Popen(
                ["afplay", str(self.sound_file)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            # Fallback to terminal bell if wav missing
            sys.stdout.write('\a')
            sys.stdout.flush()
```

## Key Details

- Uses `subprocess.Popen` (non-blocking) so it doesn't pause the I/O loop
- Falls back to terminal bell if `bell.wav` is missing
- `afplay` is built into macOS (no dependencies)
- No changes to `cli.py`, `runner.py`, or detection logic

## Files Modified
- `waiting/notifiers.py` - only file changed

## Testing
```bash
waiting python -c "input('test: ')"
# Should hear bell.wav sound instead of terminal ding
```
