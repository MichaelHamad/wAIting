# Nag Terminal Death Fix - January 4, 2026 (22:45)

## Problem

When Claude Code terminal is closed, nag processes continue running in the background because they were launched with `nohup` and `disown`.

## Root Cause

The nag scripts were launched with:
```bash
nohup "$NAG_SCRIPT" ... > /dev/null 2>&1 &
echo $! > "$PID_FILE"
disown
```

- `nohup` makes the process immune to SIGHUP (signal sent when terminal closes)
- `disown` removes the process from the shell's job table

This was originally done to keep nags running independently, but it causes orphaned processes when the terminal closes unexpectedly.

## Fix

Removed `nohup` and `disown` from all nag script launches:

```bash
"$NAG_SCRIPT" ... > /dev/null 2>&1 &
echo $! > "$PID_FILE"
```

Now when the terminal (Claude Code) closes:
1. Shell sends SIGHUP to all child processes
2. Nag process receives SIGHUP and terminates
3. No orphaned nags remain

## Files Changed

| File | Lines Modified |
|------|----------------|
| `src/waiting/cli.py` | Stop script (~223), Permission script (~349), Idle script (~464) |

## Behavior Change

| Scenario | Before | After |
|----------|--------|-------|
| Terminal closes normally | Nag continues running | Nag dies |
| Terminal killed (SIGKILL) | Nag continues running | Nag dies (SIGHUP) |
| Claude Code restart | Nags orphaned, bells continue | Nags killed with terminal |

## Combined with Activity Hook Cleanup

This fix works together with the activity hook cleanup that kills ALL nags:
- Activity hooks: Kill all nags when user responds (handles cross-session orphans)
- Terminal death: Nags automatically die when terminal closes (handles normal exits)

## Requires

**Restart Claude Code** for the new hooks to take effect.
