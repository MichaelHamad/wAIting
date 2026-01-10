# Critical Findings: Hook Specs Review

**Date:** 2026-01-10
**Finding Type:** CRITICAL - Addresses Missing Requirements
**Status:** Incorporated into IMPLEMENTATION_PLAN.md

---

## Finding #1: Hook Registration REQUIRED in settings.json [CRITICAL]

### The Problem
The original implementation plan generated hook scripts but never registered them. Claude Code hook system requires hooks to be registered in `~/.claude/settings.json` to take effect.

### Official Spec Evidence
```
From info.md, lines 9-42:
"Hooks are organized by matchers, where each matcher can have multiple hooks"
Example shows hooks structure in ~/.claude/settings.json
```

### Impact
- **Before:** Hooks installed but wouldn't work (user would be confused)
- **After:** HookManager registers hooks in settings.json in two-step process

### Implementation
- **New Task 1.6:** `settings.py` module handles load/merge/save of settings.json
- **Updated Task 2.1:** HookManager uses settings.py to register hooks
- **Tests:** Comprehensive coverage of merge/preserve scenarios

---

## Finding #2: Hook Input Provides session_id [IMPORTANT]

### The Problem
Original plan had fallback MD5 hash for session_id but didn't emphasize that official hooks provide it.

### Official Spec Evidence
```
From info.md, line 492:
"session_id: string"

From info.md, line 509:
"session_id": "abc123"

Standard field in all hook input JSON
```

### Impact
- **Better:** Scripts should try to parse session_id from hook JSON first
- **Fallback:** Only use MD5 if session_id not in input (graceful degradation)

### Implementation
- Hook scripts now explicitly attempt to parse session_id from official hook input
- Clear documentation of JSON structure
- Fallback generation for edge cases

---

## Finding #3: PreToolUse Fires on EVERY Tool Call [IMPORTANT FOR ARCHITECTURE]

### The Problem
Original design wasn't clear about PreToolUse event frequency.

### Official Spec Evidence
```
From info.md, lines 318-333:
"PreToolUse: Runs after Claude creates tool parameters and before processing
the tool call."

"Common matchers: Task, Bash, Glob, Grep, Read, Edit, Write, WebFetch, WebSearch"

This means every tool call goes through PreToolUse
```

### Impact
- **Clarification:** PreToolUse firing = ANY user activity (any tool use)
- **Architecture:** This is the correct way to detect "user responded to permission"
- **Elegant:** No need for explicit "permission response" detection

### Implementation
- Documentation now clarifies this is intentional
- Task 2.3 updated with explicit note
- Tests verify behavior with various tool types

---

## Finding #4: Hook Scripts Must Exit Immediately [IMPORTANT FOR BEHAVIOR]

### The Problem
Original plan wasn't explicit about non-blocking behavior being critical.

### Official Spec Evidence
```
From info.md, lines 1104-1106:
"Timeout: 60-second execution limit by default"
"Parallelization: All matching hooks run in parallel"

This means hooks block the main loop if they don't exit quickly
```

### Impact
- **Critical:** Hook process itself must exit 0 quickly
- **Background Processes:** Grace period MUST run in background subshell (&)
- **Performance:** User shouldn't wait for grace period timer

### Implementation
- Hook scripts now explicitly show background execution (`&`)
- Comments explain why immediate exit is critical
- Pseudo-code shows subshell pattern

---

## Finding #5: Official Hook Response Format [IMPORTANT FOR FUTURE]

### The Problem
Original plan didn't explicitly reference JSON response formats.

### Official Spec Evidence
```
From info.md, lines 748-767 (PermissionRequest):
"hookSpecificOutput": {
  "hookEventName": "PermissionRequest",
  "decision": {
    "behavior": "allow" | "deny" | "ask"
  }
}

From info.md, lines 711-739 (PreToolUse):
"hookSpecificOutput": {
  "hookEventName": "PreToolUse",
  "permissionDecision": "allow" | "deny" | "ask"
}
```

### Impact
- **MVP:** Waiting doesn't need to return JSON responses (just exit 0)
- **Future:** If adding auto-allow/deny features, know exact JSON format
- **Consistency:** Documented for future feature development

### Implementation
- JSON response formats documented in Hook Specs Reference
- Currently scripts just exit 0 (let Claude handle permissions)
- Future phases can add JSON responses if needed

---

## Finding #6: Settings Merge Must Preserve Existing Hooks [CRITICAL FOR SAFETY]

### The Problem
If HookManager overwrites entire settings.json, it would delete user's other hooks.

### Official Spec Evidence
```
From info.md, line 102:
"When a plugin is enabled, its hooks are merged with user and project hooks"
"Multiple hooks from different sources can respond to the same event"

This implies hooks from multiple sources can coexist
```

### Impact
- **Safety Critical:** Merge, don't replace
- **User Experience:** User might have other hooks installed
- **Best Practice:** Only modify waiting hook entries, preserve others

### Implementation
- `settings.py` has explicit `merge_hooks_into_settings()` function
- Preserves existing hooks from other tools
- `remove_hooks_from_settings()` carefully removes only waiting hooks
- Tests verify existing hooks aren't affected

---

## Finding #7: graceful Degradation for jq [IMPORTANT FOR RELIABILITY]

### The Problem
Bash scripts depend on jq, but it might not be available everywhere.

### Official Spec Evidence
```
From info.md, line 1238 (context):
Scripts should handle their environment gracefully
Avoid external dependencies where possible
```

### Impact
- **Robustness:** Scripts should work even if jq is missing
- **Fallback:** Parse JSON manually or use defaults
- **User Experience:** Hooks fail gracefully with helpful logging

### Implementation
- Hook scripts test for jq: `command -v jq >/dev/null || ...`
- Use jq with error suppression: `jq ... 2>/dev/null || ...`
- Parse session_id from jq OR fallback to MD5 generation
- Load defaults if config parsing fails

---

## Finding #8: Exit Code 2 for Blocking Errors [IMPORTANT FOR ERROR HANDLING]

### The Problem
Bash scripts need to distinguish error severity.

### Official Spec Evidence
```
From info.md, lines 637-670:
"Exit code 0: Success"
"Exit code 2: Blocking error. Only stderr is used as error message"
"Other: Non-blocking error"

For PermissionRequest hook:
"Exit code 2 Behavior: Denies the permission, shows stderr to Claude"
```

### Impact
- **Error Handling:** Use exit 2 only for critical blocking errors
- **User Feedback:** Exit 2 shows stderr to Claude (proper error channel)
- **Graceful Degradation:** Use exit 0 for non-critical issues

### Implementation
- Documented exit code meanings in hook scripts
- Currently scripts use exit 0 (no blocking errors)
- Future: If validation needed, use exit 2 with clear stderr messages

---

## Finding #9: Notification Hook Event Exists (Future Work) [INFORMATIONAL]

### The Problem
Original plan didn't mention Notification event possibility.

### Official Spec Evidence
```
From info.md, lines 348-388:
"Notification: Runs when Claude Code sends notifications"

Matchers available:
- permission_prompt: Permission requests from Claude Code
- idle_prompt: When Claude waiting for user input (60+ seconds)
- auth_success: Authentication success notifications
- elicitation_dialog: When Claude needs input for MCP tool
```

### Impact
- **MVP Scope:** Doesn't need Notification hook (focused on PermissionRequest)
- **Future Enhancement:** Could add idle_prompt notifications
- **Design:** Separate feature from permission notifications

### Implementation
- Documented in Task 2.5 as "Future Hook: Notification Event"
- Not included in MVP scope
- Marked for Phase 6+ enhancement
- Added to Product Manager questions

---

## Finding #10: Settings File Creation Must Be Safe [IMPORTANT FOR INSTALLATION]

### The Problem
HookManager might run on systems with no existing settings.json.

### Official Spec Evidence
```
From info.md, line 13:
"~/.claude/settings.json - User settings"

Implies directory structure must exist:
~/.claude/ directory
```

### Impact
- **Safety:** Must create ~/.claude/ if missing
- **Robustness:** Handle JSON parse errors gracefully
- **Idempotency:** Safe to call HookManager.install() multiple times

### Implementation
- `settings.py` creates ~/.claude/ if needed
- Handles missing/empty settings.json
- Tests cover all creation scenarios
- Idempotent: calling install() multiple times is safe

---

## Summary: What Changed

| Area | Original | Refined | Impact |
|------|----------|---------|--------|
| Hook Registration | Scripts only | Scripts + settings.json | CRITICAL - hooks now work |
| Session ID | Fallback only | Parse from JSON + fallback | Better reliability |
| PreToolUse Purpose | Activity detection | Explicit: any tool = activity | Clearer architecture |
| Hook Exit Behavior | Mentioned | Explicit non-blocking requirement | Critical for UX |
| JSON Response Format | Not documented | Explicit with examples | Ready for future |
| Existing Hooks Safety | Not addressed | Explicit merge strategy | Critical for safety |
| jq Dependency | Assumed present | Graceful degradation documented | Better reliability |
| Error Codes | Not documented | Exit 0 vs 2 documented | Proper error handling |
| Future Notifications | Not mentioned | Documented in Phase 6+ | Product planning |
| File Creation | Not detailed | Explicit create ~/.claude/ | Robust installation |

---

## Recommendations

### For Development
1. Start with Phase 1 Task 1.6 (settings.py) - it's critical for hooks to work
2. Use info.md as reference while implementing hook scripts
3. Implement comprehensive tests for settings merge/preserve
4. Test jq unavailability scenarios
5. Verify session_id coordination between hooks

### For User Experience
1. `waiting` command should check for jq availability and warn if missing
2. Status command should verify hooks are registered in settings.json
3. Error messages should reference ~/.waiting.log for debugging
4. Documentation should explain restart requirement for hooks to take effect

### For Future
1. Consider adding validation hooks (exit 2 on invalid config)
2. Plan Phase 6+ for Notification hook with idle_prompt
3. Consider web UI for settings (instead of JSON editing)
4. Monitor usage metrics for user analytics

---

**All findings have been incorporated into the refined IMPLEMENTATION_PLAN.md**
