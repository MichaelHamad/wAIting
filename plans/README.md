# Waiting - Implementation Plans and Specifications

This directory contains the complete implementation strategy for the **Waiting** audio notification system, refined based on the official Claude Code Hooks specification.

---

## Documents Overview

### 1. **IMPLEMENTATION_PLAN.md** (Main Document)
**Status:** Ready for Development
**Lines:** 1,711
**Purpose:** Complete phase-by-phase implementation strategy

Contains:
- Executive summary and 5-phase overview
- Project structure and file organization
- Detailed architecture and design patterns
- Complete Phase 1-5 task breakdowns
- Implementation checklist
- Technical decisions and trade-offs
- Risk mitigation strategies
- Success criteria

**Key Sections:**
- Phase 1: Foundation (Weeks 1-2)
- Phase 2: Hooks & Events (Weeks 2-3) - **UPDATED FOR HOOK REGISTRATION**
- Phase 3: Audio Playback (Weeks 3-4)
- Phase 4: CLI Commands (Week 4)
- Phase 5: Testing & QA (Week 5)

**Last Updated:** 2026-01-10 (Refined based on official hook specs)

---

### 2. **REFINEMENT_SUMMARY.md** (Executive Summary)
**Status:** Summary of Changes
**Lines:** 231
**Purpose:** Quick overview of what changed and why

Contains:
- Summary of refinements made
- Major changes from original plan
- Updated task descriptions
- Testing implications
- Compatibility with official specs

**Best for:** Quickly understanding what was added/changed

**Key Changes:**
- ✓ NEW: Phase 1 Task 1.6 - Settings Integration Module (CRITICAL)
- ✓ UPDATED: Phase 2 HookManager for settings.json registration
- ✓ CLARIFIED: Hook event flow and JSON response formats
- ✓ DISCOVERED: Notification hook event (future work)

---

### 3. **CRITICAL_FINDINGS.md** (Detailed Analysis)
**Status:** Issue Analysis
**Lines:** 415
**Purpose:** Detailed explanation of 10 critical findings and their impact

Contains:
- Problem statement for each finding
- Official spec evidence with line references
- Impact analysis (before/after)
- Implementation details
- Recommendations

**Best for:** Understanding WHY changes were needed

**Key Findings:**
1. Hook registration MUST go to ~/.claude/settings.json
2. session_id provided in hook input JSON
3. PreToolUse fires on EVERY tool call (any activity = response)
4. Hook scripts must exit immediately (background processes)
5. Official JSON response format documented
6. Settings merge must preserve existing hooks
7. Graceful degradation for jq
8. Exit code 2 for blocking errors
9. Notification hook event exists (future)
10. Settings file creation must be safe

---

### 4. **HOOK_SPECS_REFERENCE.md** (Developer Reference)
**Status:** Quick Reference
**Lines:** 354
**Purpose:** Quick lookup guide for hook implementation details

Contains:
- Hook registration (where and how)
- Hook input/output formats
- Event-specific details (PermissionRequest vs PreToolUse)
- Session ID handling
- Error handling patterns
- Security considerations
- Testing approaches
- Integration checklist

**Best for:** While writing hook scripts and settings integration code

**Key Sections:**
- Hook Registration (CRITICAL)
- Hook Input Format (Standard + Event-specific)
- Hook Output Format (Exit codes, JSON)
- Session ID handling
- Error codes and behaviors
- Testing procedures

---

## Quick Start for Developers

1. **Read First:** REFINEMENT_SUMMARY.md (5 min read)
2. **Understand Why:** CRITICAL_FINDINGS.md (15 min read)
3. **Implement:** Start with Phase 1 using IMPLEMENTATION_PLAN.md
4. **Reference:** Keep HOOK_SPECS_REFERENCE.md handy while coding

---

## Critical Changes Summary

### Priority 1: MUST IMPLEMENT
- **Phase 1 Task 1.6:** Settings module (handles ~/.claude/settings.json)
- **Phase 2 Task 2.1:** HookManager integration with settings
- **Tests:** Comprehensive coverage of settings merge/preserve

### Priority 2: CLARIFIED REQUIREMENTS
- **Task 2.2:** Hook script parses session_id from official hook JSON
- **Task 2.3:** PreToolUse detects any tool use (any activity = response)
- **All Scripts:** Exit immediately, grace period in background

### Priority 3: FUTURE WORK
- **Task 2.5:** Notification hook for idle prompts (Phase 6+)
- **Feature:** Web UI for settings (future enhancement)

---

## Official Specs Reference

All refinements based on: `/home/michael/projects/waiting_new/info.md`

**Key Specification Areas:**
- Lines 9-42: Hook configuration structure
- Lines 318-338: PreToolUse and PermissionRequest events
- Lines 348-388: Notification event
- Lines 484-629: Hook input formats
- Lines 631-856: Hook output formats and responses
- Lines 1104-1106: Hook execution details (timeout, parallelization)

---

## Phase Overview

```
Week 1-2: Phase 1 Foundation
  ├── Project structure, config, logging
  └── Settings integration (NEW - CRITICAL)

Week 2-3: Phase 2 Hooks & Events
  ├── HookManager with settings integration
  ├── Permission hook script (PermissionRequest)
  └── Activity hook script (PreToolUse)

Week 3-4: Phase 3 Audio Playback
  ├── Cross-platform audio players
  ├── Platform detection
  └── Integration with hooks

Week 4: Phase 4 CLI Commands
  ├── enable/disable/status commands
  └── User-facing output

Week 5: Phase 5 Testing & QA
  ├── Coverage (80%+)
  ├── Platform validation
  └── Documentation
```

---

## Testing Strategy

### Unit Tests
- Config loading/validation
- State management (temp files)
- **Settings merge/preserve (NEW)**
- Audio player selection
- Hook script generation

### Integration Tests
- **Settings registration (NEW)**
- Hook lifecycle (install/remove)
- Audio playback with hooks
- CLI end-to-end

### Platform Tests
- Linux (paplay/pw-play/aplay fallback)
- macOS (afplay)
- WSL (PowerShell)

---

## Key Files Modified

- ✓ `/home/michael/projects/waiting_new/plans/IMPLEMENTATION_PLAN.md` - Comprehensive refinements

## Key Files Created

- ✓ `/home/michael/projects/waiting_new/plans/REFINEMENT_SUMMARY.md` - This document
- ✓ `/home/michael/projects/waiting_new/plans/CRITICAL_FINDINGS.md` - Detailed findings
- ✓ `/home/michael/projects/waiting_new/plans/HOOK_SPECS_REFERENCE.md` - Developer reference
- ✓ `/home/michael/projects/waiting_new/plans/README.md` - This index

---

## Next Steps

1. **Review** REFINEMENT_SUMMARY.md (5 min)
2. **Understand** CRITICAL_FINDINGS.md #1 - Hook Registration (10 min)
3. **Start Implementation** Phase 1 Task 1.1 (project setup)
4. **Priority:** Phase 1 Task 1.6 (settings.py) - this blocks Phase 2
5. **Reference:** Use HOOK_SPECS_REFERENCE.md while implementing hooks

---

## Questions?

**For Hook Specification Questions:**
- See HOOK_SPECS_REFERENCE.md
- Reference official docs: `/home/michael/projects/waiting_new/info.md`

**For Implementation Questions:**
- See IMPLEMENTATION_PLAN.md (Phase 1-5 breakdown)
- See CRITICAL_FINDINGS.md (why decisions were made)

**For Architecture Questions:**
- See IMPLEMENTATION_PLAN.md (Architecture & Design Patterns section)
- See REFINEMENT_SUMMARY.md (Updated design decisions)

---

## Document Statistics

| Document | Lines | Purpose | Best For |
|----------|-------|---------|----------|
| IMPLEMENTATION_PLAN.md | 1,711 | Complete strategy | Developers implementing |
| REFINEMENT_SUMMARY.md | 231 | Quick overview | Managers/reviewers |
| CRITICAL_FINDINGS.md | 415 | Detailed analysis | Understanding rationale |
| HOOK_SPECS_REFERENCE.md | 354 | Developer reference | Hands-on coding |
| README.md (this file) | ~200 | Index/navigation | Getting oriented |

**Total:** ~2,900 lines of documentation (single source of truth)

---

## Status

✓ **Review Complete**
✓ **Refinements Incorporated**
✓ **Ready for Development**

All refinements based on official Claude Code Hooks specification (info.md).

---

**Last Updated:** 2026-01-10
**Reviewed Against:** Official Claude Code Hooks Reference
**Status:** Ready for Implementation
