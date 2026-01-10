# Implementation Plan Refinement Summary

**Date:** 2026-01-10
**Reviewed Against:** Official Claude Code Hooks Reference (`info.md`)
**Status:** Ready for Development

---

## Executive Summary

The original IMPLEMENTATION_PLAN.md has been refined based on careful review of the official Claude Code hooks documentation. The refinements address critical gaps in hook registration, input/output handling, and settings file integration.

**Key Finding:** Hooks must be registered in `~/.claude/settings.json` to take effect. The original plan was missing this critical step.

---

## Major Changes

### 1. **NEW: Phase 1 Task 1.6 - Settings Integration Module** [CRITICAL]

**What was missing:**
- Original plan generated hook scripts but never registered them in settings
- No mechanism to preserve existing hooks when installing Waiting hooks

**What's new:**
- New `settings.py` module (Phase 1, Task 1.6)
- Handles loading/saving `~/.claude/settings.json`
- Merges Waiting hooks without overwriting other hooks
- Safe removal that cleans both scripts and settings registration
- Comprehensive test coverage in `test_settings.py`

**Impact on HookManager:**
- Phase 2 Task 2.1 updated to use settings.py
- HookManager now performs two-step installation:
  1. Write hook scripts to `~/.claude/hooks/`
  2. Register hooks in `~/.claude/settings.json`
- Removal also two-step process

---

### 2. **Clarified Hook Registration Format**

**Official spec requirement (line 9-42, 559-583 in info.md):**
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

**Added to Plan:**
- Explicit section "Critical Integration Point: Hook Registration" (line 222-262)
- Format examples in HookManager documentation
- Settings file path clarification

---

### 3. **Hook Script Improvements: Input/Output Handling**

#### PermissionRequest Hook (Task 2.2) - Enhanced
- Now explicitly parses `session_id` from official hook JSON input (official spec line 492)
- Fallback to MD5 hash if `session_id` not in input
- Updated pseudo-code shows error handling for jq unavailability
- Graceful degradation: exits successfully even if config missing

#### PreToolUse Hook (Task 2.3) - Clarified
- **IMPORTANT CLARIFICATION:** PreToolUse fires on EVERY tool call
- This is the correct way to detect "user responded to permission"
- Added documentation explaining: any tool use = activity
- Now logs tool name for debugging

#### Exit Code Behavior - Documented
- Exit 0: Success, optional JSON response
- Exit 2: Blocking error (stderr shown)
- Other: Non-blocking error
- Referenced official spec (line 631-651) for details

---

### 4. **Hook Input Structure - Explicit Documentation**

**Added to Plan (before hook script sections):**
- Standard hook input fields: `session_id`, `transcript_path`, `cwd`, `permission_mode`, `hook_event_name`
- JSON response format for PermissionRequest (lines 609-617)
- JSON response format for PreToolUse (not needed for MVP, but documented)
- Exit code meanings and behavior

---

### 5. **Future Enhancement: Notification Hook** [NEW TASK 2.5]

**Discovered in official specs (line 348+):**
- `Notification` hook event with matchers: `permission_prompt`, `idle_prompt`, `auth_success`
- Could support idle notifications (when Claude waiting for user input > 60s)

**Plan Impact:**
- New Task 2.5: "Future Hook: Notification Event (Out of Scope - Phase 6+)"
- Documented for future enhancement, not MVP
- Added to "Questions for Product Manager" section

---

### 6. **Updated Checklist**

**Phase 1 additions:**
- `test_settings.py` test file added
- `settings.py` module marked as CRITICAL FOR HOOKS

**Phase 2 updates:**
- All hook script tasks updated with [UPDATED WITH JSON RESPONSE] or [UPDATED WITH CLARIFICATION] tags
- Clearer acceptance criteria

---

## Testing Implications

### New Test Module: `tests/unit/test_settings.py`
- Load settings from file
- Save settings to file
- Merge hooks without destroying existing hooks
- Remove hooks cleanly
- Handle missing settings.json
- Preserve other user hooks during merge/remove

### Updated Hook Tests
- Settings integration tests (in Phase 2 integration tests)
- Verify hooks are registered in settings.json after install
- Verify hooks are removed from settings after uninstall

---

## Technical Decisions Refined

### Original Issue: Settings Registration
- **Before:** Plan assumed hooks would just run if script exists
- **After:** Clarified that Claude Code hook system requires registration in settings.json

### PreToolUse Event Interpretation
- **Confirmed:** PreToolUse fires on EVERY tool call
- **Correct approach:** This is the way to detect any user activity/response

### Session ID Handling
- **Confirmed:** `session_id` available in hook input per official spec
- **Fallback:** MD5 hash if not provided
- **Updated:** Scripts now attempt to parse from hook JSON first

---

## Compatibility with Official Specs

All changes align with official Claude Code hooks documentation:

| Feature | Spec Reference | Status |
|---------|-----------------|--------|
| Hook registration in settings.json | Line 9-42 | Implemented |
| Hook input format | Line 484-629 | Documented |
| Exit codes | Line 631-670 | Documented |
| JSON output format | Line 672-856 | Documented |
| PermissionRequest event | Line 335-338 | Implemented |
| PreToolUse event | Line 318-333 | Implemented |
| Notification event | Line 348-388 | Future (Phase 6+) |

---

## Files Modified

- `/home/michael/projects/waiting_new/plans/IMPLEMENTATION_PLAN.md` - Comprehensive refinements throughout

## Files Referenced

- `/home/michael/projects/waiting_new/info.md` - Official Claude Code hooks reference documentation

---

## Next Steps for Development

1. **Phase 1 Priority:** Implement `settings.py` module first (Task 1.6)
   - Test-driven development required
   - Comprehensive coverage of merge/remove scenarios

2. **Phase 2:** Hook scripts use session_id from official hook JSON input
   - Explicit error handling for JSON parsing
   - Graceful degradation if jq unavailable

3. **Phase 2:** HookManager integration with settings
   - Registration and removal both multi-step processes
   - Settings file preservation critical

4. **Testing:** Add settings integration to all hook tests
   - Verify registration in settings.json
   - Verify existing hooks preserved

---

## Questions Resolved

- ✓ Where do hooks get registered? → `~/.claude/settings.json`
- ✓ How to detect user response? → PreToolUse event (any tool use)
- ✓ What data available in hook input? → JSON with session_id, tool_name, etc.
- ✓ How to exit hook scripts? → Exit 0 immediately, background grace period
- ✓ What about future notifications? → Phase 6+, use Notification event

## Open Questions (for Product Manager)

1. Should the bell repeat if user still hasn't responded after first alert?
2. Interest in idle prompt notifications (Notification hook with idle_prompt matcher)?
3. Future support for stop/idle events beyond PermissionRequest?
4. CLI-only configuration or web UI in future?
5. Usage analytics desired (alert frequency, response latency)?

---

**Ready for implementation. All refinements based on official specifications.**
