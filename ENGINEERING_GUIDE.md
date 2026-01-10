# Engineering Guide - Waiting Audio Notification System MVP

**Status:** Ready for Implementation
**Branch:** mvp-fresh-start
**Prepared for:** Senior Engineer implementing features
**Date:** 2026-01-10

---

## Welcome to Waiting

You have been tasked with implementing the **Waiting** audio notification system for Claude Code. This document is your roadmap to understanding what needs to be built and how to build it.

---

## 📋 Document Index & Reading Guide

Read these in order based on your needs:

### For First-Time Understanding
1. **README** (first 5 minutes)
   - What is Waiting?
   - Why does it exist?
   - How do users use it?

2. **QUICK_START.md** (10 minutes)
   - High-level architecture diagram
   - Phase-by-phase breakdown
   - Common patterns you'll use
   - Tips and mistakes to avoid

3. **ARCHITECTURE.md** (20 minutes)
   - System design decisions
   - Component responsibilities
   - Event flow diagrams
   - Error handling strategy

### For Detailed Implementation
4. **IMPLEMENTATION_PLAN.md** (30 minutes)
   - Full phased approach (5 weeks)
   - Technical decisions and trade-offs
   - File structure and dependencies
   - Risk mitigation strategies

5. **TASK_BREAKDOWN.md** (reference)
   - Flat list of all 38 implementation tasks
   - Grouped by phase
   - Detailed acceptance criteria
   - Use as a checklist during implementation

### For Requirements
6. **plans/pm-user-stories.md**
   - 22 user stories from Product Manager
   - Acceptance criteria for each story
   - Business value and success metrics
   - Roadmap for future phases

---

## 🎯 Project at a Glance

### What You're Building
An audio notification system that plays a bell when Claude Code permission dialogs go unanswered.

```
User working in Claude Code
         ↓
Permission dialog appears (e.g., "Allow bash command?")
         ↓ (30 second default wait)
Grace period elapses, user hasn't responded
         ↓
Play audible bell notification
         ↓
User responds to permission → bell stops immediately
```

### Key Design Principles
- **Zero external dependencies** (Python 3.9+ only)
- **Hook-driven** (uses Claude Code's permission/activity events)
- **Cross-platform** (Linux, macOS, WSL)
- **Stateless design** (no background process)
- **Graceful degradation** (continues if audio unavailable)
- **Functional programming style** (strict type hints, no global state)
- **Test-first development** (tests written before implementation)

### Technology Stack
| Layer | Technology |
|-------|-----------|
| Language | Python 3.9+ with strict type hints |
| CLI | Built-in argparse |
| Audio | Platform-specific (paplay, afplay, powershell) |
| State Management | Temp files (/tmp/waiting-*) |
| Configuration | JSON (~/.waiting.json) |
| Logging | File-based (~/.waiting.log) |
| Testing | pytest + pytest-cov |

### Success Criteria (MVP Complete)
- [ ] All 22 user stories implemented
- [ ] All hook events detected and processed correctly
- [ ] Audio plays on 3+ platforms
- [ ] Configuration persists and validates
- [ ] CLI commands (enable/disable/status) work
- [ ] 80%+ test coverage
- [ ] Zero external dependencies
- [ ] Code follows functional style + strict typing

---

## 📅 5-Week Implementation Plan

### Week 1: Foundation
**Goal:** Establish core infrastructure
- Configuration management (load/save/validate)
- State management (session IDs, temp files)
- Logging infrastructure
- Test framework and fixtures
- Expected deliverables: 6 Python modules, 3 test files

### Week 2-3: Hooks & Events
**Goal:** Integrate with Claude Code hook system
- Hook manager (install/remove/detect)
- Permission request hook script (grace period logic)
- Activity/tool-use hook script (stop signal)
- Hook lifecycle tests
- Expected deliverables: 2 Bash scripts, hook manager, integration tests

### Week 3-4: Audio Playback
**Goal:** Cross-platform audio output
- Audio player protocol (strategy pattern)
- Linux players (PulseAudio, PipeWire, ALSA with fallback)
- macOS player (afplay)
- Windows/WSL player (PowerShell)
- Platform detection and audio file resolution
- Expected deliverables: 5 audio player classes, main audio interface

### Week 4: CLI Commands
**Goal:** User-facing command interface
- Enable command (install hooks)
- Disable command (remove hooks)
- Status command (show configuration)
- Help/usage display
- Expected deliverables: CLI class, entry point, integration tests

### Week 5: Testing & QA
**Goal:** Quality assurance and documentation
- Achieve 80%+ code coverage
- Platform-specific testing (Linux CI, manual macOS/WSL)
- User documentation (README, troubleshooting)
- Developer documentation (contribution guide)
- Final verification and release readiness

---

## 🏗️ Architecture Overview

### System Components

```
Claude Code Hook Events (JSON)
         ↓
Bash Hook Scripts (lightweight, fast)
         ↓ (state: /tmp/waiting-{session_id})
Python Core Modules
├── config.py (load ~/.waiting.json)
├── state.py (manage /tmp files)
├── audio.py (play sounds)
├── hooks/manager.py (install/remove)
├── cli.py (user commands)
└── errors.py + logging.py (support)
         ↓
Cross-Platform Audio Players
├── Linux: paplay/pw-play/aplay (fallback chain)
├── macOS: afplay
└── Windows/WSL: PowerShell
         ↓
User's Speaker/Headphones
```

### Key Design Patterns

1. **Strategy Pattern** - Audio players (pluggable per platform)
2. **Immutable Data** - Config dataclass (frozen=True)
3. **Dependency Injection** - No global state (pass deps as params)
4. **Functional Error Handling** - Return tuples (success, message)
5. **Protocol-Based Polymorphism** - AudioPlayer protocol (not inheritance)

---

## 🔑 Core Concepts You Must Understand

### 1. Hook System
**What are hooks?**
- Event-driven integration points in Claude Code
- JSON input via stdin
- Bash script location: `~/.claude/hooks/`

**Two hooks you'll use:**
| Hook | Trigger | Purpose |
|------|---------|---------|
| `waiting-notify-permission.sh` | Permission dialog appears | Start grace period timer |
| `waiting-activity-tooluse.sh` | User responds to dialog | Stop audio immediately |

### 2. Session IDs
- Extracted from Claude's hook JSON: `hook_input["session_id"]`
- Fallback: MD5 hash of hostname + timestamp
- Used to track state across hook invocations
- Example: `"abc-123-def-456"` or `"a7f3c2e8b1d6f4a9"`

### 3. Temp Files for State
- **Stop signal:** `/tmp/waiting-stop-{session_id}` (existence = signal)
- **Audio PID:** `/tmp/waiting-audio-{session_id}.pid` (contains process ID)
- Why? Cross-process communication, simple, self-cleaning

### 4. Configuration
- File: `~/.waiting.json`
- Format:
  ```json
  {
    "grace_period": 30,  // seconds to wait
    "volume": 100,       // 1-100 percentage
    "audio": "default"   // "default" or file path
  }
- Validated on load (raises ConfigError if invalid)
- Used by both Python code and Bash scripts

### 5. Audio Playback
- Detect platform (Linux/macOS/Windows)
- Select available player (fallback chain on Linux)
- Resolve audio file (validate if custom)
- Execute player, return PID
- Can be killed via PID if user responds

---

## 💻 Development Workflow

### Test-First Development (TDD)

```
1. Write test (tests/unit/test_config.py)
   └─ def test_load_default_config()

2. Implement feature (src/waiting/config.py)
   └─ def load_config()

3. Run test
   └─ pytest tests/unit/test_config.py

4. Commit when tests pass
   └─ git commit -m "feat: add load_config function"

5. Repeat for next feature
```

### Type Hints (Mandatory)
Every function must have complete type hints:

```python
# GOOD
def load_config(path: Path | None = None) -> Config:
    """Load configuration from ~/.waiting.json"""
    pass

# BAD - missing types
def load_config(path):
    pass

# BAD - incomplete types
def load_config(path: Path | None) -> Config:
    pass  # Missing return type for other path
```

### Functional Style
- Pure functions (same input → same output)
- No mutable globals
- Dependency injection (pass params, don't use globals)
- Return tuples for validation: `(success: bool, message: str | None)`

```python
# GOOD - pure function
def validate_grace_period(value: int) -> tuple[bool, str | None]:
    if value <= 0:
        return False, "must be positive"
    return True, None

# GOOD - dependency injection
def play_audio(config: Config, player: AudioPlayer) -> int:
    return player.play(config.audio, config.volume)

# BAD - global state
config = load_config()
def play_audio(player: AudioPlayer) -> int:
    return player.play(config.audio, config.volume)
```

### Testing Strategy
- **Unit tests** - Isolated functions with mocks
- **Integration tests** - Components working together
- **Platform tests** - Verify on Linux/macOS/WSL
- **Coverage target** - 80%+ code coverage

```bash
# Run all tests
pytest tests/

# With coverage
pytest --cov=src/waiting tests/

# Specific test
pytest tests/unit/test_config.py::test_load_default_config -v
```

---

## 📦 File Structure

### Source Code
```
src/waiting/
├── __init__.py
├── __main__.py              ← Entry point (waiting command)
├── cli.py                   ← Commands (enable/disable/status)
├── config.py                ← Configuration loading
├── state.py                 ← Temp file state management
├── audio.py                 ← Main audio interface
├── errors.py                ← Custom exceptions
├── logging.py               ← Logging setup
├── audio_players/
│   ├── __init__.py
│   ├── base.py             ← AudioPlayer protocol
│   ├── linux.py            ← Linux players (paplay, pw-play, aplay)
│   ├── macos.py            ← macOS player (afplay)
│   └── windows.py          ← Windows player (powershell)
└── hooks/
    ├── __init__.py
    ├── manager.py          ← Hook install/remove
    └── scripts/
        ├── waiting-notify-permission.sh
        └── waiting-activity-tooluse.sh
```

### Tests
```
tests/
├── conftest.py             ← Shared fixtures
├── unit/
│   ├── test_config.py
│   ├── test_state.py
│   ├── test_audio.py
│   ├── test_audio_players.py
│   ├── test_hooks.py
│   └── test_cli.py
└── integration/
    ├── test_cli.py
    ├── test_hook_lifecycle.py
    └── test_audio_playback.py
```

### Configuration & Documentation
```
~/.waiting.json             ← User configuration (created on first run)
~/.waiting.log              ← Debug logs
~/.claude/hooks/            ← Generated hook scripts (installed by manager)
pyproject.toml              ← Package metadata + entry point
```

---

## 🚀 Getting Started

### Before You Code
1. **Read QUICK_START.md** (10 min) - Get oriented
2. **Read ARCHITECTURE.md** (20 min) - Understand design
3. **Skim IMPLEMENTATION_PLAN.md** - Know what's coming
4. **Keep TASK_BREAKDOWN.md open** - Reference during work

### Setup Your Environment
```bash
cd /home/michael/projects/waiting_new
python -m venv venv
source venv/bin/activate
pip install pytest pytest-cov
```

### Week 1 Quick Start
```bash
# Create test file
touch tests/unit/test_config.py

# Write first test
# (see example in QUICK_START.md)

# Run test (will fail)
pytest tests/unit/test_config.py

# Create implementation
touch src/waiting/config.py

# Implement to pass test
# (TDD: test first, implement second)

# Verify test passes
pytest tests/unit/test_config.py -v

# Commit
git add src/ tests/
git commit -m "feat: add Config class and load_config function"
```

---

## ⚠️ Common Pitfalls

### ❌ Global State
Never use module-level config loading:
```python
# BAD
config = load_config()  # Global!
def play_audio():
    return player.play(config.audio)

# GOOD
def play_audio(config: Config):
    return player.play(config.audio)
```

### ❌ Missing Type Hints
```python
# BAD
def load_config(path):  # No types!
    return Config(...)

# GOOD
def load_config(path: Path | None = None) -> Config:
    return Config(...)
```

### ❌ Bare Except
```python
# BAD
try:
    player.play(file)
except:  # Catches KeyboardInterrupt!
    pass

# GOOD
try:
    player.play(file)
except AudioError as e:
    logger.error(str(e))
```

### ❌ No Validation
```python
# BAD
config = Config(grace_period=-1, volume=150, audio="")

# GOOD
config = Config(grace_period=30, volume=100, audio="default")
is_valid, error = config.validate()
if not is_valid:
    raise ConfigError(error)
```

---

## 📊 Progress Tracking

Use this checklist to track your implementation:

### Phase 1: Foundation ✓ when complete
- [ ] pyproject.toml updated with entry point
- [ ] pytest.ini created
- [ ] errors.py with 5 exception types
- [ ] logging.py with setup_logging()
- [ ] config.py with Config class and load/save
- [ ] state.py with session/temp file helpers
- [ ] conftest.py with fixtures
- [ ] All unit tests passing
- [ ] 100% coverage on Phase 1 modules

### Phase 2: Hooks ✓ when complete
- [ ] HookManager class (install/remove/detect)
- [ ] waiting-notify-permission.sh script
- [ ] waiting-activity-tooluse.sh script
- [ ] Hook installation tests
- [ ] Hook lifecycle integration tests
- [ ] All tests passing

### Phase 3: Audio ✓ when complete
- [ ] AudioPlayer protocol
- [ ] Linux players (3: paplay, pw-play, aplay)
- [ ] macOS player (afplay)
- [ ] Windows player (PowerShell)
- [ ] Main audio.py module
- [ ] Platform detection
- [ ] All audio tests passing

### Phase 4: CLI ✓ when complete
- [ ] CLI class (enable/disable/status/help)
- [ ] __main__.py entry point
- [ ] `waiting` command works end-to-end
- [ ] All CLI tests passing

### Phase 5: QA ✓ when complete
- [ ] 80%+ overall code coverage
- [ ] All tests passing
- [ ] Manual testing on supported platforms
- [ ] Documentation complete (README, troubleshooting)

---

## 🔗 Cross-References

### If You're Implementing...

**Configuration:**
→ See: ARCHITECTURE.md (Configuration Management section)
→ See: TASK_BREAKDOWN.md (Task 1.2.3, 1.2.4)
→ See: IMPLEMENTATION_PLAN.md (Phase 1.3-1.4)

**Hooks:**
→ See: ARCHITECTURE.md (Hook System Integration section)
→ See: TASK_BREAKDOWN.md (Tasks 2.1-2.3)
→ See: IMPLEMENTATION_PLAN.md (Phase 2)
→ See: PRD.md (Technical Implementation section)

**Audio Playback:**
→ See: ARCHITECTURE.md (Audio Playback Strategy section)
→ See: TASK_BREAKDOWN.md (Tasks 3.1-3.5)
→ See: IMPLEMENTATION_PLAN.md (Phase 3)

**CLI:**
→ See: ARCHITECTURE.md (CLI Module section)
→ See: TASK_BREAKDOWN.md (Tasks 4.1-4.2)
→ See: IMPLEMENTATION_PLAN.md (Phase 4)

**Testing:**
→ See: IMPLEMENTATION_PLAN.md (Testing Strategy section)
→ See: TASK_BREAKDOWN.md (Phase 5 tasks)
→ See: ARCHITECTURE.md (Testing Strategy section)

---

## 🎓 Learning Resources Within This Repo

**For Understanding Requirements:**
- pm-user-stories.md - 22 user stories with acceptance criteria

**For Architecture:**
- ARCHITECTURE.md - System design, patterns, decisions

**For Implementation:**
- IMPLEMENTATION_PLAN.md - Detailed phased approach
- TASK_BREAKDOWN.md - Flat task list with acceptance criteria
- QUICK_START.md - Quick reference guide

**For Project Rules:**
- AGENTS.md - Engineering principles (TDD, small commits, etc.)
- CLAUDE.md - Project guidelines

---

## ❓ Questions?

### "What should I do first?"
→ Read QUICK_START.md, then start with Phase 1 tasks

### "How do I run tests?"
→ `pytest tests/` - see QUICK_START.md (Running Tests section)

### "What are the design patterns?"
→ ARCHITECTURE.md (Design Patterns section)

### "How do hooks work?"
→ ARCHITECTURE.md (Hook System Integration section)

### "What's the technical decision for [X]?"
→ IMPLEMENTATION_PLAN.md (Technical Decisions & Trade-offs section)

### "I'm stuck on a task"
→ Check TASK_BREAKDOWN.md for acceptance criteria
→ Check QUICK_START.md for common patterns
→ Check ARCHITECTURE.md for relevant design

---

## 📝 Summary

You're implementing a **hook-driven audio notification system** that:
- Detects permission dialogs via Claude Code hooks
- Waits a grace period (configurable, default 30s)
- Plays a bell sound if user doesn't respond
- Stops immediately when user responds
- Works across Linux, macOS, and Windows
- Has zero external dependencies
- Uses functional programming with strict type hints
- Is thoroughly tested (80%+ coverage)

The implementation is divided into **5 phases over 5 weeks**, starting with foundation (config/state/logging), progressing through hooks and audio, culminating in CLI and QA.

**You have everything you need to succeed. Build something great!**

---

**Last updated:** 2026-01-10
**Prepared by:** Senior Engineer Agent (Claude Code)
**Status:** Ready for Implementation
**Branch:** mvp-fresh-start

