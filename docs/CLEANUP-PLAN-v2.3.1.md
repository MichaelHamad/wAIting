# Cleanup Plan: v2.3.1 Improvements

**Date:** January 5, 2026
**Current Version:** 2.3.0
**Target Version:** 2.3.1
**Status:** Planning

---

## Overview

Code review of v2.3.0 PreToolUse hook identified several issues that should be addressed before MVP launch. This document outlines the problems and proposed fixes.

---

## Issues Identified

### Issue 1: Duplicate Audio Kill Loop (Priority: Low)

**Location:** `src/waiting/cli.py` lines 855-871

**Problem:**
```bash
# Kill audio by tracked PID
for audiopid in /tmp/waiting-audio-*.pid; do
    if [ -f "$audiopid" ]; then
        kill "$(cat "$audiopid")" 2>/dev/null
        kill -9 "$(cat "$audiopid")" 2>/dev/null
        rm -f "$audiopid"
    fi
done

# Kill ALL audio processes (handles orphans from other sessions)
for audiopid in /tmp/waiting-audio-*.pid; do
    if [ -f "$audiopid" ]; then
        kill "$(cat "$audiopid")" 2>/dev/null
        kill -9 "$(cat "$audiopid")" 2>/dev/null
        rm -f "$audiopid"
    fi
done
```

These two loops are **identical**. The comment says the second handles "orphans from other sessions" but both iterate over the same glob pattern `*.pid`. The second loop is redundant.

**Impact:** None functionally - just code bloat and confusion.

**Fix:** Remove the duplicate loop.

---

### Issue 2: pgrep Pattern Brittleness (Priority: Medium)

**Location:** `src/waiting/cli.py` lines 873-877

**Problem:**
```bash
pgrep -f "paplay.*(waiting-bell|Cool_bell)"
```

This pattern:
- Matches `Cool_bell` which works for `Cool_bell_final.wav`
- But is hardcoded to specific filename patterns
- If user changes audio file, pgrep won't catch it

**Impact:** If audio filename changes, aggressive kill won't work.

**Fix Options:**
1. **Option A:** Use a more generic pattern like `paplay.*/waiting/` (matches any file in waiting directory)
2. **Option B:** Kill ALL paplay processes owned by current user (aggressive but simple)
3. **Option C:** Store audio command pattern in config and use it in pgrep

**Recommendation:** Option A - pattern based on directory path is more stable than filename.

---

### Issue 3: Stop Signal Removal May Affect Other Sessions (Priority: Low)

**Location:** `src/waiting/cli.py` line 916

**Problem:**
```bash
rm -f /tmp/waiting-stop-*
```

This removes ALL stop signals, not just the current session's. If multiple Claude sessions are running:
1. Session A creates stop signal for its nag
2. Session B runs PreToolUse cleanup
3. Session B removes Session A's stop signal
4. Session A's nag doesn't see the signal and keeps running

**Impact:** Rare edge case - only affects multi-session scenarios.

**Fix:** Only remove current session's stop signal:
```bash
rm -f "/tmp/waiting-stop-$SESSION_ID"
```

Or remove only after confirming nag is dead.

---

### Issue 4: Race Condition in Fast Permission Sequences (Priority: Medium)

**Location:** Conceptual issue with 0.3s sleep

**Problem:**
Timeline:
1. T=0.0s: User approves Permission A
2. T=0.0s: PreToolUse creates stop signal for session
3. T=0.1s: Permission B appears (new PermissionRequest fires)
4. T=0.1s: PermissionRequest starts new nag for Permission B
5. T=0.1s: New nag sees stop signal from step 2 and exits immediately
6. T=0.3s: PreToolUse finishes, removes stop signal
7. Result: Permission B never gets a nag!

**Impact:** In rapid permission sequences, some permissions may not trigger notifications.

**Fix Options:**
1. **Option A:** PermissionRequest hook should remove stop signal BEFORE starting new nag
2. **Option B:** Use session-specific stop signals more carefully
3. **Option C:** Add a "nag ID" to differentiate which nag should respond to which signal

**Recommendation:** Option A - PermissionRequest already does this at line 101:
```bash
rm -f "$STOP_SIGNAL"
```

Need to verify this runs BEFORE nag starts. If it does, this is already handled.

---

### Issue 5: Activity Timestamp Set After Delay (Priority: Low)

**Location:** `src/waiting/cli.py` lines 841-844

**Problem:**
```bash
sleep 0.3  # Line 839
# ... then ...
ACTIVITY_TIME=$(($(date +%s) + 1))  # Line 842
```

The activity timestamp is set 0.3 seconds after the user actually responded.

**Impact:** Minimal - the +1 buffer accounts for this. But technically imprecise.

**Fix:** Move activity timestamp update BEFORE the sleep:
```bash
ACTIVITY_TIME=$(($(date +%s) + 1))
echo "$ACTIVITY_TIME" > "/tmp/waiting-activity-stop-$SESSION_ID"
echo "$ACTIVITY_TIME" > "/tmp/waiting-activity-permission-$SESSION_ID"
sleep 0.3
```

---

## Proposed Changes for v2.3.1

### Change 1: Remove Duplicate Loop

**File:** `src/waiting/cli.py`

**Action:** Delete lines 864-871 (the duplicate loop)

**Before:**
```bash
# Kill audio by tracked PID
for audiopid in /tmp/waiting-audio-*.pid; do
    ...
done

# Kill ALL audio processes (handles orphans from other sessions)
for audiopid in /tmp/waiting-audio-*.pid; do
    ...
done
```

**After:**
```bash
# Kill audio by tracked PID (handles all sessions via *.pid glob)
for audiopid in /tmp/waiting-audio-*.pid; do
    ...
done
```

---

### Change 2: Improve pgrep Pattern

**File:** `src/waiting/cli.py`

**Action:** Update pgrep patterns to match directory path instead of filename

**Before:**
```bash
pgrep -f "paplay.*(waiting-bell|Cool_bell)" | xargs -r kill -9 2>/dev/null
```

**After:**
```bash
pgrep -f "paplay.*/waiting/" | xargs -r kill -9 2>/dev/null
```

This matches any audio file in the `/waiting/` directory, regardless of filename.

---

### Change 3: Session-Specific Stop Signal Cleanup

**File:** `src/waiting/cli.py`

**Action:** Only remove current session's stop signal, leave others intact

**Before:**
```bash
rm -f /tmp/waiting-stop-*
```

**After:**
```bash
rm -f "/tmp/waiting-stop-$SESSION_ID"
```

---

### Change 4: Move Activity Timestamp Before Sleep

**File:** `src/waiting/cli.py`

**Action:** Reorder to set timestamp immediately when user responds

**Before:**
```bash
sleep 0.3

ACTIVITY_TIME=$(($(date +%s) + 1))
echo "$ACTIVITY_TIME" > "/tmp/waiting-activity-stop-$SESSION_ID"
```

**After:**
```bash
ACTIVITY_TIME=$(($(date +%s) + 1))
echo "$ACTIVITY_TIME" > "/tmp/waiting-activity-stop-$SESSION_ID"
echo "$ACTIVITY_TIME" > "/tmp/waiting-activity-permission-$SESSION_ID"

sleep 0.3
```

---

## Implementation Order

1. **Change 1** - Remove duplicate loop (trivial, no risk)
2. **Change 4** - Move activity timestamp (low risk, improves accuracy)
3. **Change 3** - Session-specific cleanup (low risk, prevents edge case)
4. **Change 2** - Improve pgrep pattern (medium risk, needs testing)

---

## Testing Plan

After implementing changes:

1. **Basic flow test:**
   - Trigger permission dialog
   - Wait for bell
   - Approve
   - Verify bell stops immediately

2. **Rapid permission test:**
   - Trigger permission A
   - Approve immediately (before bell)
   - Trigger permission B
   - Verify B's bell still works

3. **Multi-session test (if possible):**
   - Run two Claude instances
   - Trigger permissions in both
   - Verify they don't interfere

4. **Audio file rename test:**
   - Rename Cool_bell_final.wav temporarily
   - Verify pgrep still catches audio processes

---

## Decision Required

**Question for stakeholder:** Should we implement these v2.3.1 fixes before MVP launch, or ship v2.3.0 and address these in a follow-up release?

**Recommendation:** The duplicate loop and timestamp ordering are safe to fix now. The pgrep pattern change should be tested more thoroughly and could wait for v2.4.0.

---

## Version History

| Version | Status | Changes |
|---------|--------|---------|
| 2.0.0 | Shipped | Stop-signal mechanism |
| 2.1.0 | Shipped | Fixed permission hook blocking |
| 2.2.0 | Shipped | Audio kill before nag kill |
| 2.3.0 | Current | Aggressive audio killing in PreToolUse |
| 2.3.1 | Planned | Cleanup duplicate code, improve patterns |
