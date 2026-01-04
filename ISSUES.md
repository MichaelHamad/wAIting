# Issues and Troubleshooting Log

## Issue: Stop Hook Running Unexpectedly

**Symptom**: Bell notifications kept playing during code editing session, even though we hadn't run `waiting` command.

**Root Cause**: Hooks persist in `~/.claude/settings.json` from previous sessions. The hook scripts in `~/.claude/hooks/` are self-contained bash scripts that don't require the venv or `waiting` command to run.

**Discovery**: Checked `~/.claude/settings.json` and found all four hooks still registered:
- `UserPromptSubmit` → `waiting-activity-submit.sh`
- `Stop` → `waiting-notify-stop.sh`
- `PermissionRequest` → `waiting-notify-permission.sh`
- `PreToolUse` → `waiting-activity-permission.sh`

## What We Tried

### 1. Disabled Stop Hook Selectively
```bash
waiting configure --disable-hook stop
waiting
```
This removed just the Stop hook while keeping Permission and Idle hooks active.

### 2. Full Disable
```bash
waiting disable
```
This cleared all hooks from `~/.claude/settings.json` (file became `{}`).

## Key Learnings

1. **Hooks are global, not project-specific**
   - Registered in `~/.claude/settings.json`
   - Scripts live in `~/.claude/hooks/`
   - Shared across all Claude Code sessions

2. **Hooks are cached at startup**
   - Changes to settings.json don't take effect immediately
   - Must restart Claude Code session to pick up new hook configuration

3. **Scripts are self-contained bash**
   - Use system audio players (aplay, afplay, powershell.exe)
   - No Python/venv required to execute
   - Run via Claude Code's hook system, not the `waiting` CLI

4. **Stop hook fires on every Claude response**
   - This is by design (alerts when Claude finishes)
   - Can be noisy during active development
   - Use `--disable-hook stop` to disable selectively

## Recommendations for Development

- Run `waiting disable` before starting a code editing session
- Or selectively disable stop hook: `waiting configure --disable-hook stop && waiting`
- Remember to restart Claude Code after changing hook configuration
