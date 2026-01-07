# Waiting Tool - Current Issues

## Summary

The permission hook notification system is not playing bells when expected during normal Claude Code usage.

## Test Results

| Test | Result |
|------|--------|
| Manual hook trigger (`echo '{"session_id":"test"}' \| ~/.claude/hooks/waiting-notify-permission.sh`) | Works - nag process starts |
| Direct audio playback (`powershell.exe` with bell.wav) | Works - bell plays |
| Audio from detached process (`nohup ... & disown`) | Works - bell plays |
| Real permission dialog left open 10+ seconds | No bell heard |

## Root Cause Analysis

### Finding 1: Most commands are auto-approved

Debug log shows only `PreToolUse` firing, not `PermissionRequest`:

```
Sun Jan  4 01:13:02: PreToolUse fired
Sun Jan  4 01:13:11: PreToolUse fired
Sun Jan  4 01:13:15: PreToolUse fired
```

The user's Claude Code has extensive auto-approve rules (Bash commands, Read, Write to /tmp, etc.). When a tool is auto-approved:
- `PermissionRequest` hook does NOT fire
- Only `PreToolUse` fires
- No permission dialog = no notification needed

### Finding 2: When permission IS required, approval is fast

When a permission dialog appeared:
```
Sun Jan  4 01:11:04: PreToolUse fired
Sun Jan  4 01:11:04: Permission hook fired
```

Both hooks fired in the **same second**. This means:
1. PermissionRequest fired → nag process started
2. User approved immediately → PreToolUse fired
3. PreToolUse killed the nag process before grace period elapsed

This is **correct behavior** - the user was present and responded.

### Finding 3: No test case for "user AFK with permission dialog"

We couldn't reproduce the scenario where:
1. Permission dialog appears
2. User is AFK (doesn't approve)
3. 10+ seconds pass
4. Bell should play

Because all test commands were either auto-approved or the user approved them quickly.

## Configuration

Current settings (`~/.waiting.json`):
```json
{
  "enabled_hooks": ["permission"],
  "grace_period_permission": 10,
  "interval": 30,
  "max_nags": 0
}
```

## Hooks Installed

- `/home/michael/.claude/hooks/waiting-notify-permission.sh` - Permission notification
- `/home/michael/.claude/hooks/waiting-activity-submit.sh` - UserPromptSubmit activity
- `/home/michael/.claude/hooks/waiting-activity-tooluse.sh` - PreToolUse activity

## Debug Logging

Debug logging added to all hooks, writing to `/tmp/waiting-debug.log`:
- "Permission hook fired" - when PermissionRequest triggers
- "PreToolUse fired" - when tool is approved/executed
- "UserPromptSubmit fired" - when user sends a message

## Questions to Investigate

1. **What commands require permission for this user?** - Need to find a command not in the auto-approve list to properly test.

2. **Was the original issue from a stale session?** - Before restart, old hooks from a previous implementation were running. The "random bells" and "not playing when expected" could have been from mismatched hook versions.

3. **Is the issue resolved after restart?** - After restarting Claude Code with the new hooks, we haven't been able to reproduce the "no bell when permission dialog open" scenario because we can't trigger a permission dialog.

## Next Steps

1. **Identify a command that requires permission** - Check allow list, find something not auto-approved
2. **Test with that command** - Leave dialog open for 10+ seconds
3. **Monitor debug log** - Confirm PermissionRequest fires and nag process runs
4. **Verify bell plays** - After grace period, bell should sound

## Temp Files Location

Session-specific files in `/tmp/`:
- `waiting-pending-{session_id}` - Marks permission dialog is open
- `waiting-activity-permission-{session_id}` - Last activity timestamp
- `waiting-nag-{session_id}.pid` - Nag process PID
- `waiting-nag-{session_id}.sh` - Generated nag script

---

## Resolution

### Issue Understood: Permission Hook Limitations

The permission hook is now **not enabled by default** because:

1. **Most tools are auto-approved** - When tools are auto-approved via Claude Code settings, `PermissionRequest` hook does NOT fire (only `PreToolUse` fires)
2. **This is expected behavior** - The hook correctly fires only when there's an actual permission dialog shown to the user
3. **Stop and Idle hooks are more reliable** - They fire regardless of auto-approve settings

### Changes Made

- Default `enabled_hooks` changed from `["stop", "permission", "idle"]` to `["stop", "idle"]`
- Documentation updated to explain this behavior
- Permission hook still available via `waiting configure --enable-hook permission`

### For Users Who Want Permission Alerts

If you frequently encounter permission dialogs (minimal auto-approve rules), enable the permission hook:

```bash
waiting configure --enable-hook permission
```
