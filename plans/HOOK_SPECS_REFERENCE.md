# Hook Specs Reference for Waiting Implementation

**Quick Reference for Developers**
**Based on:** Official Claude Code Hooks Reference (`info.md`)

---

## Hook Registration (CRITICAL)

### Where Hooks Live
- **Script Location:** `~/.claude/hooks/waiting-*.sh`
- **Registration:** `~/.claude/settings.json` (MUST be registered here!)
- **Settings Structure:**
  ```json
  {
    "hooks": {
      "PermissionRequest": [
        {
          "matcher": ".*",
          "hooks": [{
            "type": "command",
            "command": "~/.claude/hooks/waiting-notify-permission.sh"
          }]
        }
      ],
      "PreToolUse": [
        {
          "matcher": ".*",
          "hooks": [{
            "type": "command",
            "command": "~/.claude/hooks/waiting-activity-tooluse.sh"
          }]
        }
      ]
    }
  }
  ```

### How to Register Hooks (HookManager Job)
1. Load `~/.claude/settings.json` (or create empty)
2. Merge in waiting hooks under `hooks.PermissionRequest` and `hooks.PreToolUse`
3. **IMPORTANT:** Preserve any existing hooks from other tools
4. Save back to `~/.claude/settings.json`

### How to Unregister Hooks
1. Load `~/.claude/settings.json`
2. Remove waiting hooks from `hooks.PermissionRequest` and `hooks.PreToolUse`
3. **IMPORTANT:** Don't delete entire event keys if other hooks exist
4. Save back (or delete file if no hooks remain)

---

## Hook Input Format

### Standard Fields (All Hooks)
```json
{
  "session_id": "abc123",                    // Unique session identifier
  "transcript_path": "/path/to/transcript",  // Conversation history file
  "cwd": "/current/working/directory",       // Where Claude Code is running
  "permission_mode": "default",              // Current permission mode
  "hook_event_name": "PermissionRequest"     // Name of this event
}
```

### PermissionRequest Specific Input (Line 335-338)
- Includes all standard fields
- May include tool-specific fields (tool name, permission type, etc.)

### PreToolUse Specific Input (Line 503-521)
```json
{
  "tool_name": "Write",                // Which tool is being called
  "tool_input": { /* ... */ },         // Parameters for the tool
  "tool_use_id": "toolu_01ABC123..."   // Unique identifier for this tool call
}
```

---

## Hook Output Format

### Exit Codes (Line 631-670)
```
Exit 0:   Success - stdout processed for JSON, may contain context
Exit 2:   Blocking error - stderr shown to Claude (JSON ignored)
Other:    Non-blocking error - stderr shown in verbose mode
```

### JSON Response for PermissionRequest (Line 748-767)
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow" | "deny" | "ask",
      "updatedInput": { /* optional: modify tool params */ },
      "message": "string (for deny only)"
    }
  }
}
```

### JSON Response for PreToolUse (Line 711-739)
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow" | "deny" | "ask",
    "permissionDecisionReason": "string",
    "updatedInput": { /* optional: modify tool params */ }
  }
}
```

---

## Hook Events: PermissionRequest vs PreToolUse

### PermissionRequest (Line 335-338)
- **When:** User sees a permission dialog
- **Purpose:** Auto-allow/deny permissions on behalf of user
- **Usage in Waiting:** Start grace period timer, play audio if dialog unanswered
- **Output:** Can auto-allow/deny with `decision.behavior`

### PreToolUse (Line 318-333)
- **When:** Before ANY tool is executed (Read, Write, Edit, Bash, etc.)
- **Purpose:** Block tool calls, ask for confirmation, or log activity
- **Matcher:** Can target specific tools by name
- **Usage in Waiting:** Detect user activity (any tool = user responded)
- **Output:** Can allow/deny/ask with `permissionDecision`

### In Waiting Context
- **PermissionRequest Hook:** Monitors grace period, plays audio if user doesn't respond
- **PreToolUse Hook:** Detects ANY tool use as "user activity" = user responded
- **Coordination:** PreToolUse creates stop signal, PermissionRequest monitors it

---

## Session ID (Critical for State Coordination)

### From Hook Specs (Line 492, 509, 529)
- `session_id` provided in hook input JSON
- Unique per permission dialog
- Same `session_id` passed to both PermissionRequest and PreToolUse hooks

### Fallback Implementation
```bash
SESSION_ID=$(echo "$HOOK_JSON" | jq -r '.session_id // empty' 2>/dev/null)
if [ -z "$SESSION_ID" ]; then
  SESSION_ID=$(echo "$(hostname)-$(date +%s%N)" | md5sum | cut -d' ' -f1)
fi
```

### Why Session ID Matters
- PermissionRequest hook creates `/tmp/waiting-audio-{SESSION_ID}.pid`
- PreToolUse hook reads same PID file to kill audio
- Both hooks use session ID to coordinate without process-to-process communication

---

## Error Handling

### Exit Code 2: Blocking Error (Line 657)
```bash
# Example: Config file corrupt
echo "Error: ~/.waiting.json is invalid JSON" >&2
exit 2  # Shows error to Claude, blocks action
```

### Exit Code 0: Success with Optional Output
```bash
# Example: Just continue (for PermissionRequest/PreToolUse)
exit 0

# Example: With JSON response
echo '{"hookSpecificOutput": {"hookEventName": "PermissionRequest", ...}}'
exit 0
```

### Exit Code 1+: Non-Blocking Error
```bash
# Example: Warning but doesn't block
echo "Warning: jq not found, using defaults" >&2
exit 1
```

---

## jq Dependency Notes

### Why jq Needed
- Parse hook input JSON
- Parse config file JSON
- Extract session_id, grace_period, volume, audio path

### How to Handle If jq Missing
```bash
SESSION_ID=$(echo "$HOOK_JSON" | jq -r '.session_id // empty' 2>/dev/null || echo "")
if [ -z "$SESSION_ID" ]; then
  # Use fallback generation
  SESSION_ID=$(echo "$(hostname)-$(date +%s%N)" | md5sum | cut -d' ' -f1)
fi
```

### jq Availability
- Ubuntu/Debian: `apt install jq`
- macOS: `brew install jq`
- Alpine: `apk add jq`
- Usually pre-installed on modern systems

---

## Matcher Pattern (Line 44-49)

### For PermissionRequest and PreToolUse
- Simple string: Matches exactly (case-sensitive)
- Regex: `Edit|Write`, `Notebook.*`
- Wildcard: `*` matches all tools
- Empty string: Also matches all tools

### Waiting Implementation
- Using `.*` to match all tools/permissions
- This ensures both hooks fire for any activity

---

## Timeout Behavior (Line 54, 1104-1106)

### Default Timeout: 60 seconds
- Configurable in settings.json via `timeout` field
- Not typically needed for Waiting (scripts exit immediately)
- Mostly relevant for long-running scripts

### For Waiting Scripts
- Permission hook: Exits immediately (timeout not reached)
- Activity hook: Exits immediately (timeout not reached)
- Grace period runs in background (not subject to hook timeout)

---

## Environment Variables Available

### Standard in Hook Scripts
- `HOME` - User's home directory
- `CLAUDE_PROJECT_DIR` - Project root (where Claude Code started)
- `CLAUDE_CODE_REMOTE` - "true" if remote environment, empty if local

### Used in Waiting
- `HOME` → for config paths, temp files, log file
- Not using `CLAUDE_PROJECT_DIR` (hooks in user home, not project)

---

## Logging and Debugging

### Hook Execution in verbose mode (ctrl+o)
- Shows which hook is running
- Shows exit code and output
- Shows any errors

### For Waiting
- Log to `~/.waiting.log` for persistent debugging
- Include session ID in all log messages
- Include timestamps
- Include event name (PermissionRequest vs PreToolUse)

### Example Log Format
```
[2026-01-10 14:23:45] PermissionRequest detected. Session: abc123, Grace: 30s
[2026-01-10 14:24:15] User activity detected. Tool: Write. Session: abc123
```

---

## Security Considerations (Line 1063-1101)

### Risks with Hooks
- Execute arbitrary shell commands automatically
- Run with user's credentials
- Can access any file user can access
- Can modify/delete files

### Waiting-Specific Security
- Hooks only: read config, parse JSON, play audio, manage temp files
- No privileged operations
- No file modifications (except temp files and logs)
- Config validation before use
- Graceful errors (no crashes)

### Best Practices Applied in Waiting
- Always quote shell variables: `"$SESSION_ID"` not `$SESSION_ID`
- No eval or command injection risks
- Config loaded from user's home (trusted location)
- Temp files in `/tmp` (expected location)
- Logs in `~/.waiting.log` (user's home)

---

## Testing Hook Scripts

### Manual Testing
```bash
# Simulate PermissionRequest input
echo '{"session_id": "test123", "hook_event_name": "PermissionRequest"}' | \
  ~/.claude/hooks/waiting-notify-permission.sh

# Simulate PreToolUse input
echo '{"session_id": "test123", "tool_name": "Write", "hook_event_name": "PreToolUse"}' | \
  ~/.claude/hooks/waiting-activity-tooluse.sh
```

### Expected Behavior
- Exit immediately (exit 0)
- Create temp files
- Log to `~/.waiting.log`
- Play audio (if grace period expires)

---

## Integration Checklist

### For HookManager (settings.py integration)
- [ ] Load `~/.claude/settings.json` (or create empty dict)
- [ ] Merge waiting hooks into `hooks.PermissionRequest` and `hooks.PreToolUse`
- [ ] Preserve existing hooks from other tools
- [ ] Save back to `~/.claude/settings.json`
- [ ] Handle missing settings file gracefully
- [ ] Make directories if needed: `mkdir -p ~/.claude`

### For Hook Scripts
- [ ] Parse JSON from stdin
- [ ] Extract session_id with fallback
- [ ] Load config from `~/.waiting.json`
- [ ] Exit immediately (grace period in background)
- [ ] Create/monitor temp files
- [ ] Log all activity
- [ ] Handle missing jq gracefully
- [ ] Handle missing config gracefully

---

## Reference Links in Specs

- Hook Events Overview: Line 316-427
- Hook Input: Line 484-629
- Hook Output: Line 631-856
- Debugging: Line 1119-1170
- Security: Line 1063-1101

---

**Last Updated:** 2026-01-10
**Based on:** Claude Code Hooks Reference (info.md)
