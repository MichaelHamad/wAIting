# Monitoring Mode Delay Analysis

**Date:** January 3, 2026
**Context:** Session 4 - Addressing premature bells in monitoring mode

## Problem Statement

When user approves Dialog A and Dialog B appears immediately (cascading dialogs), the monitoring mode nag skips the first bell but enters the nag loop, which plays a bell after 15 seconds. This is too aggressive - the user may still be at their computer reading Dialog B.

## Current Behavior

```
T=0:  User approves Dialog A
T=0:  Dialog B appears → nag enters monitoring mode (skips first bell)
T=15: Nag loop plays bell ❌ (user likely still present, reading dialog)
T=30: Another bell
T=45: Another bell
```

**User feedback:** "why would the monitoring start playing bells at 15 seconds? thats way too soon"

## Proposed Fix

Add longer initial delay in monitoring mode before first nag loop bell:

```bash
# In monitoring mode, wait longer before assuming user is AFK
if [ "$SKIP_FIRST_BELL" = true ]; then
    echo "  Monitoring mode: waiting ${LOOKBACK_WINDOW}s before first nag" >> "$DEBUG_LOG"
    # Sleep the lookback window duration before starting nag loop
    for i in $(seq 1 "$LOOKBACK_WINDOW"); do
        sleep 1
        if [ ! -f "$PID_FILE" ]; then
            exit 0
        fi
    done
fi
```

**New behavior:**
```
T=0:  User approves Dialog A
T=0:  Dialog B appears → monitoring mode (skips first bell)
T=30: First nag loop bell ✓ (reasonable delay)
T=45: Second bell
T=60: Third bell
```

## Pros

### 1. Better User Experience
- Reduces false alarms when user is actively working
- Gives user time to read and understand new dialogs (20-30s is reasonable)
- Feels less aggressive and annoying
- Aligns with user expectations ("I just approved something, I'm clearly here")

### 2. Handles Rapid Workflow
- User approving 3-4 dialogs in quick succession won't get nagged
- As long as they keep approving within 30s, no bells
- Once they stop (go AFK), bells start after 30s

### 3. Clear Intent Signaling
- 30s delay = "I see you were active recently, I'll give you benefit of doubt"
- 15s interval = "You've been idle a while, I'll keep reminding you"

### 4. Leverages Existing Config
- Uses the lookback_window config (already 30s)
- No new configuration needed
- Consistent with the "recent activity" concept

## Cons

### 1. Longer AFK Detection
- If user walks away immediately after approving Dialog A, they wait 30s for first bell (was 15s)
- **Impact:** 15 second delay in notification
- **Severity:** Low - they're already away, 15s difference is minor

### 2. Inconsistent Timing
- Normal dialog: 10s grace → bell
- Monitoring mode: 30s delay → bell
- **Impact:** User might be confused why timing varies
- **Mitigation:** This is actually intentional and logical - different scenarios have different delays

### 3. Complexity
- Adds another code path with different timing logic
- More to test and maintain
- **Impact:** Moderate - but isolated to monitoring mode logic

### 4. Might Still Be Too Short/Long
- 30s might not be enough for some users (reading complex dialog)
- 30s might be too long for others (want faster notifications)
- **Mitigation:** Make it configurable separately from lookback_window?

### 5. Edge Case: User Approves at T=29
- User sits idle for 29s
- Just as bell is about to play (T=30), user approves
- Activity updated, but nag might play bell anyway (race condition)
- **Impact:** Low - sound might play once, then nag exits
- **Severity:** Minor annoyance, rare occurrence

## Alternatives Considered

### Alternative 1: Increase INTERVAL Globally
**Change:** Set INTERVAL to 30s instead of 15s everywhere

**Pros:**
- Simpler (one value to change)
- Consistent timing across all scenarios
- Less aggressive overall

**Cons:**
- Normal AFK detection also becomes slower (10s grace + 30s = 40s)
- Less frequent reminders (every 30s instead of 15s)
- Doesn't solve the fundamental issue (monitoring mode needs different timing)

**Verdict:** ❌ Doesn't address the core problem

### Alternative 2: Remove Monitoring Mode Entirely
**Change:** If user was recently active → exit nag entirely (don't monitor)

**Pros:**
- Much simpler code
- No premature bells ever
- Original approach from before Session 4

**Cons:**
- Loses the benefit of monitoring (bells won't play if user goes AFK later)
- User sits at dialog for 20 minutes with no bell (original bug returns)

**Verdict:** ❌ Regresses to the 20-minute silent dialog bug

### Alternative 3: Different Monitoring Delay (20s)
**Change:** Use a middle ground (20s) instead of 30s

**Pros:**
- Faster than 30s
- Still better than 15s
- Balances responsiveness and patience

**Cons:**
- Adds new config value (monitoring_delay)
- 20s might still feel too short
- Arbitrary choice

**Verdict:** 🤔 Possible, but 30s (lookback_window) is more logical

### Alternative 4: Make It Configurable
**Change:** Add `monitoring_delay` config separate from lookback_window

**Pros:**
- Users can tune to their preference
- Maximum flexibility
- Advanced users can optimize

**Cons:**
- More configuration to understand
- More testing needed
- Complexity for minimal gain
- Most users won't change defaults

**Verdict:** 🤔 Could add later if needed, but start with 30s default

### Alternative 5: Progressive Delay
**Change:** First bell at 30s, second at 45s, third at 60s (increasing intervals)

**Pros:**
- Gentle escalation
- Gives user increasing benefit of doubt
- Feels more intelligent

**Cons:**
- Complex to implement
- Harder to understand behavior
- Might delay notifications too much

**Verdict:** ❌ Over-engineered for this problem

## Recommendation

**✅ Implement the proposed fix: 30s initial delay in monitoring mode**

**Rationale:**
1. Directly addresses user complaint ("15s is too soon")
2. Simple implementation (reuse lookback_window value)
3. Logical and consistent (recent activity = longer patience)
4. Minimal downside (15s slower AFK detection in edge case)
5. Preserves monitoring benefit (bells eventually play if user stays AFK)

**Implementation:**
- Add 30s sleep before entering nag loop when in monitoring mode
- Keep all other behavior the same
- Log the monitoring delay for debugging

**Success Criteria:**
- User approves Dialog A, Dialog B appears immediately
- User takes 20s to read Dialog B
- No bell plays while reading
- User approves Dialog B → no bells ever play
- If user walks away at Dialog B → bells start at T=30

## Configuration Impact

Current config:
```json
{
  "grace_period_permission": 10,
  "lookback_window": 30,
  "interval": 15,
  "max_nags": 0
}
```

**Values used:**
- **Normal dialog (user not recently active):**
  - Grace period: 10s
  - First bell: 10s
  - Subsequent bells: every 15s

- **Monitoring mode (user recently active):**
  - Monitoring delay: 30s (lookback_window)
  - First bell: 30s
  - Subsequent bells: every 15s

This reuses existing config values and requires no new configuration.

## Testing Plan

1. **Rapid successive dialogs:**
   - Trigger Dialog A → wait 5s → approve
   - Dialog B appears immediately
   - Verify: No bell for 30 seconds
   - Approve Dialog B at T=20
   - Verify: No bells ever play

2. **User goes AFK in monitoring mode:**
   - Trigger Dialog A → wait 5s → approve
   - Dialog B appears immediately
   - Walk away (don't approve)
   - Verify: Bell plays at T=30
   - Verify: Bells continue every 15s

3. **Normal AFK (not recently active):**
   - Trigger Dialog A
   - Walk away immediately
   - Verify: Bell plays at T=10 (grace period)
   - Verify: Bells continue every 15s

4. **Edge case - approve during monitoring delay:**
   - Trigger Dialog A → approve
   - Dialog B appears → monitoring mode
   - Wait 25s
   - Approve Dialog B
   - Verify: No bells play (approved before T=30)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Too slow for power users | Low | Low | Future: make configurable |
| Race condition at T=30 | Medium | Low | Acceptable - bell plays once max |
| Confusion about timing | Low | Low | Clear logging explains behavior |
| Regression (monitoring breaks) | Low | High | Thorough testing before deploy |

## Conclusion

The 30-second initial delay for monitoring mode is the right solution:
- ✅ Solves user's complaint
- ✅ Simple to implement
- ✅ Logical and consistent
- ✅ Low risk
- ✅ No new configuration needed

**Proceed with implementation.**
