# Orphan Nag Cleanup Fix - January 4, 2026 (22:30)

## Problem

When Claude Code restarts with a new session_id, old nag processes from the previous session become orphaned and continue playing bells.

## Root Cause

Activity hooks were only killing session-specific nags:

```bash
# Old code - only kills current session's nags
pkill -f "waiting-nag-$SESSION_ID" 2>/dev/null
```

When Claude Code restarts:
1. New SESSION_ID is generated (e.g., `abc123`)
2. Old nags have different SESSION_ID (e.g., `xyz789`)
3. `pkill -f "waiting-nag-abc123"` doesn't match `waiting-nag-xyz789`
4. Old nags continue running and playing bells

## Fix

Updated activity hooks to kill ALL nag processes, not just session-specific ones:

```bash
# Kill nag process for this session
pkill -f "waiting-nag-$SESSION_ID" 2>/dev/null

# Kill ALL orphaned nags from any session (cleanup on restart)
pkill -f "waiting-nag-" 2>/dev/null

# Kill all audio
pkill -f "waiting-bell.wav" 2>/dev/null

# Cleanup all temp files
rm -f /tmp/waiting-nag-*.pid
rm -f /tmp/waiting-pending-*
rm -f /tmp/waiting-audio-*.pid
```

## Files Changed

| File | Functions Modified |
|------|-------------------|
| `src/waiting/cli.py` | `create_activity_submit_script()` |
| `src/waiting/cli.py` | `create_activity_tooluse_script()` |

## Why This Works

- First `pkill` targets the current session's nags (fast, specific)
- Second `pkill` catches any orphaned nags from old sessions
- File cleanup removes all temp files regardless of session ID
- Any user activity now cleans up the entire system

## Requires

**Restart Claude Code** for the updated activity hooks to take effect.
