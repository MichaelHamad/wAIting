# Approaches for Killing Nag Processes

## Problem Statement

When a user interacts with Claude Code (approves permission or sends a message), any running nag process should immediately stop. Currently, nags sometimes continue playing even after user interaction.

## Current Issues

1. **Pending file mechanism is unreliable** - PreToolUse sometimes doesn't find the pending file
2. **pkill not always killing processes** - Nag continues even after kill signal sent
3. **Activity tracking complexity** - Distinguishing user-approved vs auto-approved tools adds complexity

## Approach 1: Simplified Hook-Based (Recommended for Now)

### Overview
Simplify the current implementation by removing the pending file mechanism and having both user interaction hooks always kill nags.

### Design

```
UserPromptSubmit (user presses Enter)
    ↓
1. Update activity timestamp
2. Kill ALL nag processes (pkill -f "waiting-nag-SESSION")
3. Clean up PID files

PreToolUse (user approves permission OR auto-approved tool)
    ↓
1. Update activity timestamp (always, not just for user approvals)
2. Kill ALL nag processes (pkill -f "waiting-nag-SESSION")
3. Clean up PID files
```

### Key Insight

When a permission dialog is showing, Claude is **blocked** - it cannot execute any other tools. Therefore:
- The FIRST PreToolUse after PermissionRequest is ALWAYS the user-approved permission
- We don't need a pending file to detect this
- We can safely kill the nag on ANY PreToolUse

### Rationale for "Always Kill"

**Q: Won't auto-approved tools kill nags prematurely?**

A: No, because:
1. If permission dialog is showing, Claude can't run auto-approved tools (blocked waiting for user)
2. If auto-approved tools are running, there's no permission dialog (Claude is working)
3. These states are mutually exclusive

**Q: Won't auto-approved tools update activity and make grace period always pass?**

A: Yes, but this is acceptable:
- If user just sent a message and Claude is running tools, user is active
- If user goes AFK, no new messages → no UserPromptSubmit → activity becomes stale
- Grace period still detects true AFK states

### Implementation Changes

**Remove:**
- Pending file creation in PermissionRequest
- Pending file check in PreToolUse
- All `/tmp/waiting-pending-*` file operations

**Simplify PreToolUse:**
```bash
#!/bin/bash
DEBUG_LOG="/tmp/waiting-debug.log"
HOOK_INPUT=$(cat)
SESSION_ID=$(echo "$HOOK_INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)

echo "$(date): PreToolUse fired" >> "$DEBUG_LOG"
echo "  Session: $SESSION_ID" >> "$DEBUG_LOG"

# Update activity
NOW=$(date +%s)
echo "$NOW" > "/tmp/waiting-activity-permission-$SESSION_ID"
echo "  Updated activity: $NOW" >> "$DEBUG_LOG"

# Kill nag
NAG_MARKER="waiting-nag-$SESSION_ID"
if pkill -f "$NAG_MARKER" 2>/dev/null; then
    echo "  Killed nag: $NAG_MARKER" >> "$DEBUG_LOG"
fi
rm -f "/tmp/$NAG_MARKER.pid" "/tmp/$NAG_MARKER.sh"
```

### Pros
- Much simpler code
- Fewer temp files
- Easier to reason about
- Works with current Claude Code hook system

### Cons
- Auto-approved tools update activity (but this is acceptable)
- Still relies on pkill working correctly
- Can't distinguish "user actively approved" vs "tool auto-ran"

### Testing Strategy

1. **Test 1: Single permission approval**
   - Trigger permission dialog
   - Approve within 10s
   - Verify: No bell plays
   - Check debug log: PreToolUse should kill nag

2. **Test 2: Multiple rapid permissions**
   - Trigger multiple permission dialogs in quick succession
   - Approve each one
   - Verify: Each spawns and kills its own nag independently

3. **Test 3: User sends message**
   - Start permission dialog (nag starts)
   - Send a message before 10s expires
   - Verify: UserPromptSubmit kills nag, no bell

4. **Test 4: True AFK**
   - Trigger permission dialog
   - Don't interact for >10s
   - Verify: Bell plays (correct behavior)

---

## Approach 2: OS-Level Activity Detection (Future Enhancement)

### Overview
Monitor user activity at the OS level (keypresses, mouse movement, window focus) rather than relying solely on Claude Code hooks.

### Design

```
Background daemon monitors:
    - Keyboard events (any keypress)
    - Mouse events (movement, clicks)
    - Window focus (Claude terminal is active)
        ↓
Updates: /tmp/waiting-last-os-activity-TIMESTAMP
        ↓
Nag script checks this file (in addition to hook-based activity)
```

### Implementation Requirements

#### Linux (X11)
```bash
# Monitor X11 input events
xinput test-xi2 --root | while read line; do
    echo $(date +%s) > /tmp/waiting-last-os-activity
done
```

**Issues:**
- Requires X11 (doesn't work on Wayland)
- Needs `xinput` installed
- Must run as background daemon

#### Linux (Wayland)
- No standard API for global input monitoring
- Would need compositor-specific solutions (very fragile)

#### macOS
```bash
# Use Quartz Event Services via Python
python3 <<EOF
from Quartz import CGEventSourceSecondsSinceLastEventType, kCGEventSourceStateHIDSystemState
import time

while True:
    idle = CGEventSourceSecondsSinceLastEventType(kCGEventSourceStateHIDSystemState, -1)
    active_time = int(time.time() - idle)
    with open('/tmp/waiting-last-os-activity', 'w') as f:
        f.write(str(active_time))
    time.sleep(1)
EOF
```

**Issues:**
- Requires Python with PyObjC
- Needs accessibility permissions
- Battery drain (constant polling)

#### Windows/WSL
- WSL can't access Windows input events directly
- Would need Windows-side helper service
- Extreme complexity

### Pros
- Detects ALL user activity, not just Claude interactions
- More accurate "user is present" detection
- Better UX (won't nag if user is actively typing in terminal)

### Cons
- **Much more complex** - requires platform-specific native code
- **Security/privacy concerns** - keylogging-like behavior
- **Requires additional dependencies** - X11 tools, Python libraries, etc.
- **Platform-specific** - different implementation for each OS
- **Maintenance burden** - breaks with OS updates (especially Wayland transition)
- **Installation friction** - users need to grant permissions, install deps
- **Battery impact** - constant monitoring drains power on laptops

### Why Not Recommended (Yet)

1. **Scope creep** - Turns a simple bash script tool into a complex daemon
2. **Platform fragmentation** - Would need 4+ different implementations
3. **Privacy** - Monitoring all input feels invasive
4. **Diminishing returns** - Current hook-based approach covers 90% of cases
5. **Better solved elsewhere** - This is really a window manager / desktop environment feature

### Alternative: Window Focus Detection

A middle ground: only check if Claude's terminal window is focused.

```bash
# Linux X11
ACTIVE_WINDOW=$(xdotool getactivewindow getwindowname)
if [[ "$ACTIVE_WINDOW" == *"claude"* ]]; then
    # User is looking at Claude, don't nag
fi
```

**Pros:**
- Less invasive than full input monitoring
- Simpler than full OS-level detection
- Good proxy for "user is paying attention"

**Cons:**
- Still platform-specific
- Doesn't work in all terminal emulators
- User might be reading docs in another window while waiting for Claude

---

## Recommendation

**Implement Approach 1 (Simplified Hook-Based) immediately:**
- Fixes current bugs
- Simpler, more maintainable
- Works cross-platform with no additional deps
- Covers the vast majority of use cases

**Consider Approach 2 (OS-Level Detection) only if:**
- Users consistently report false positives ("I was right there!")
- Simplified approach proves insufficient
- Someone willing to maintain platform-specific code

**Most likely path forward:**
1. Ship simplified hook-based version
2. Gather real-world usage data
3. If false positives are rare (as expected), declare victory
4. If false positives are common, revisit OS-level detection

---

## Decision Log

**Date:** Jan 3, 2026
**Decision:** Proceed with Approach 1 (Simplified Hook-Based)
**Rationale:** Solves immediate bug, minimal complexity, covers 90%+ of cases
**Next Review:** After 2 weeks of real-world usage
