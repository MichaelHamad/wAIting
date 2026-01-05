# SESSION_ID Parameter Fix - January 4, 2026 (22:20)

## Problem

Audio PID files were being written to `/tmp/waiting-audio-.pid` (empty SESSION_ID), causing audio kill commands to fail. Bells continued playing after user responded.

## Root Cause

The nag script heredoc used a **quoted delimiter** which prevents variable expansion:

```bash
cat << 'NAGEOF' > "$NAG_SCRIPT"
# Inside here, $SESSION_ID is NOT expanded - it's literal text
AUDIO_PID_FILE="/tmp/waiting-audio-$SESSION_ID.pid"
NAGEOF
```

With `<< 'NAGEOF'` (quoted), bash does NOT expand variables inside the heredoc. The nag script received the literal string `$SESSION_ID` which evaluated to empty at runtime.

## Evidence

Debug logs showed:
- Audio PID file created as `/tmp/waiting-audio-.pid` (empty session ID)
- Kill commands targeting `/tmp/waiting-audio-$SESSION_ID.pid` couldn't find the file

## Fix

Pass SESSION_ID as a parameter to the nag script instead of relying on heredoc expansion:

**Before (broken):**
```bash
cat << 'NAGEOF' > "$NAG_SCRIPT"
# $SESSION_ID not expanded - empty at runtime
NAGEOF
"$NAG_SCRIPT" "$INTERVAL" "$MAX_NAGS" ...
```

**After (fixed):**
```bash
cat << 'NAGEOF' > "$NAG_SCRIPT"
SESSION_ID="$7"  # or $8 depending on script
NAGEOF
"$NAG_SCRIPT" "$INTERVAL" "$MAX_NAGS" ... "$SESSION_ID"
```

## Files Changed

| File | Functions Modified |
|------|-------------------|
| `src/waiting/cli.py` | `create_stop_script()` - SESSION_ID as $8 |
| `src/waiting/cli.py` | `create_permission_script()` - SESSION_ID as $7 |
| `src/waiting/cli.py` | `create_idle_script()` - SESSION_ID as $6 |

## Why Quoted Heredoc?

The quoted delimiter `<< 'NAGEOF'` was intentional - it prevents the outer shell from expanding variables like `$INTERVAL`, `$!`, `$$` that need to be evaluated at nag script runtime, not at hook generation time.

The fix correctly passes SESSION_ID as a positional parameter while keeping the heredoc quoted.

## Requires

**Restart Claude Code** for the updated hooks to take effect.
