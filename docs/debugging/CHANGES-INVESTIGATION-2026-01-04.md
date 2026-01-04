# Changes Investigation - January 4, 2026

## What Changed Between Commits

### Commit History (most recent first)
```
aa67e59 Add debugging session documentation for Jan 4, 2026
c3e6c1b feels close to working
c86651e Rewrite cli.py with full ONE_SHOT_PROMPT.md spec
a90f936 Rewrite as minimal MVP
e572470 Add one-shot prompts for recreating waiting MVP
```

### Diff: aa67e59 (HEAD) vs c3e6c1b (previous)

**Files Changed:** Only documentation files added
- `DEBUGGING-SESSION-2026-01-04.md` (new)
- `PROGRESS-2026-01-04.md` (new)

**No changes to `src/waiting/cli.py`**

### Diff: c3e6c1b vs c86651e

**No changes to any files** - commit c3e6c1b appears to be documentation-only or identical to c86651e.

---

## Changes Made During This Session (Then Reverted)

### Change Applied to `src/waiting/cli.py`

**Location:** Line 259 in `create_permission_script()` function, inside the NAGEOF heredoc

**Original code:**
```bash
start_time=$(date +%s)
```

**Changed to:**
```bash
start_time=$(($(date +%s) + 2))
```

**Reason for change:** Based on DEBUGGING-SESSION-2026-01-04.md which documented a race condition fix where `PreToolUse` fires in the same second as `PermissionRequest`, setting activity to `now+1`, causing the nag script to exit immediately.

**Why reverted:** User reported this change broke the bell functionality. The original code was working before the restart.

---

## Current State

- `src/waiting/cli.py` is unchanged from commit c86651e
- Working tree is clean
- The `+2` buffer fix mentioned in DEBUGGING-SESSION-2026-01-04.md is **NOT** in the code
- The fix was only applied directly to the generated hook script (`~/.claude/hooks/waiting-notify-permission.sh`) during the previous debugging session, not to `cli.py`

---

## Configuration State

### ~/.waiting.json
```json
{
  "audio": "default",
  "interval": 30,
  "max_nags": 0,
  "volume": 100,
  "enabled_hooks": ["permission"],
  "grace_period_stop": 300,
  "grace_period_permission": 10,
  "grace_period_idle": 0
}
```

Only the `permission` hook is enabled. Stop and idle hooks are disabled.

### ~/.claude/settings.json hooks
```json
{
  "PermissionRequest": [...],
  "UserPromptSubmit": [...],
  "PreToolUse": [...]
}
```

Stop and Notification (idle) hooks are NOT registered because they're disabled in config.

---

## Key Finding

The DEBUGGING-SESSION-2026-01-04.md file documents a `+2` buffer fix that was applied **directly to the hook script** during debugging, but this fix was **never committed to `cli.py`**.

When `waiting` command is run, it regenerates the hook scripts from `cli.py`, overwriting any manual fixes applied to the hook scripts.

This means:
1. The "working" version had the fix manually applied to `~/.claude/hooks/waiting-notify-permission.sh`
2. After restart and running `waiting` again, the hooks were regenerated WITHOUT the fix
3. This could explain why the bell stopped working after restart

---

## Potential Fix Options

1. **Apply the +2 buffer fix to cli.py** - Makes the fix permanent
2. **Don't run `waiting` command** - Preserves manually fixed hook scripts
3. **Investigate if +2 buffer is actually needed** - The user says original code was working
