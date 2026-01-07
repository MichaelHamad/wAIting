# Waiting - User Experience Guide

This document explains what users experience when using the Waiting notification tool.

---

## Overview

Waiting plays a bell sound when Claude Code needs your attention and you're not responding. It's designed to let you step away from your desk without missing important moments.

---

## Default Behavior (Out of the Box)

After running `waiting` and restarting Claude Code:

| Event | Bell Plays? | Repeats? |
|-------|-------------|----------|
| Claude finishes a response | Yes (after grace period) | Yes, every 30s |
| Claude idle at prompt for 60s | Yes (after grace period) | Yes, every 30s |
| Permission dialog appears | No (not enabled) | N/A |

**Default settings:**
- Grace period: 30 seconds
- Interval: 30 seconds between repeats
- Enabled hooks: stop, idle

### Why These Defaults?

- **Stop + Idle hooks are reliable** - They fire consistently for all users
- **Permission hook is situational** - Only fires for non-auto-approved tools, which is rare for most users

---

## What Each Hook Does

### Stop Hook (enabled by default)

**What it detects:** Claude finished generating a response

**User scenario:**
```
You: "Refactor this codebase"
Claude: [works for 10 minutes, finishes]
You: [AFK getting coffee]
...grace period passes...
🔔 Bell plays - "Claude is done!"
```

Bell only plays if you're AFK. Repeats every `interval` seconds until you respond.

---

### Idle Hook (enabled by default)

**What it detects:** You haven't typed anything for 60+ seconds while Claude waits at the prompt

**User scenario:**
```
Claude: "Should I proceed with option A or B?"
You: [reading, then get distracted]
...60 seconds pass (built into Claude) + grace period...
🔔 Bell plays - "Claude is waiting for you!"
```

Note: Claude's idle detection has a built-in 60-second delay before firing.

---

### Permission Hook (NOT enabled by default)

**What it detects:** Claude shows a permission dialog (e.g., "Allow Bash command?")

**User scenario:**
```
Claude: [wants to run a command]
Dialog: "Allow Bash: rm -rf node_modules?"
You: [AFK]
...grace period passes...
🔔 Bell plays once - "Claude needs permission!"
(no repeat - single alert only)
```

**Repeats:** No - plays once and exits

**Why single bell?** Permission dialogs are time-sensitive. A single alert is sufficient.

**Why not default?** Most users have auto-approve rules. When tools are auto-approved, this hook never fires.

**Enable with:**

```bash
waiting configure --enable-hook permission
```

---

## Bell Behavior

### Repeat Pattern

When a bell triggers:

1. Grace period elapses (varies by hook)
2. **Bell plays**
3. Waits `interval` seconds (default: 30)
4. **Bell plays again**
5. Repeats until you respond (or `max_nags` reached)

### What Stops the Bell

Any of these actions kill the bell immediately:

- You send a message to Claude
- You approve/deny a permission dialog
- You run `waiting kill`

Response time: < 1 second (hooks check every second)

---

## Configuration UX

### Quick Commands

```bash
waiting                  # Enable with defaults
waiting disable          # Turn off completely
waiting kill             # Stop current bell (stay enabled)
waiting status           # See what's active
```

### Adjusting Behavior

```bash
# Less aggressive (longer waits, quieter)
waiting configure --grace-period 120 --interval 60 --volume 50

# More aggressive (shorter waits, frequent bells)
waiting configure --grace-period 10 --interval 15

# Limit bell repeats
waiting configure --max-nags 3   # Stop after 3 bells
```

### Managing Hooks

```bash
# See what's enabled
waiting status
# Output: Enabled hooks: stop, idle

# Add permission alerts
waiting configure --enable-hook permission

# Remove stop alerts
waiting configure --disable-hook stop

# Set exactly which hooks are active
waiting configure --hooks idle,permission
```

---

## Typical User Journeys

### Journey 1: New User (Default Experience)

```bash
$ pip install -e .
$ waiting
Hooks installed. Restart Claude Code to activate.

$ # User restarts Claude Code

# Later...
$ # User asks Claude to do a long task
$ # User walks away
$ # 5 minutes after Claude finishes...
🔔 Bell plays
$ # User returns, sees Claude is done
```

### Journey 2: User Wants Permission Alerts

```bash
$ waiting configure --enable-hook permission
Configuration updated.
Hooks regenerated with new configuration.

$ # User restarts Claude Code

# Later...
$ # Permission dialog appears
$ # User is AFK
$ # 10 seconds later...
🔔 Bell plays
```

### Journey 3: User Finds Bells Too Frequent

```bash
$ waiting status
Enabled hooks: stop, idle
Interval: 30s
Grace periods: stop=300s, idle=0s

$ waiting configure --interval 90 --grace-stop 600
Configuration updated.

$ # Now: 10 min wait before first bell, 90s between repeats
```

### Journey 4: User Wants Silence Temporarily

```bash
$ waiting kill          # Stops current bell
$ # Bell stops, but hooks remain active

# Or to fully disable:
$ waiting disable       # Removes all hooks
```

---

## Status Output Explained

```bash
$ waiting status

Status: enabled                           # Hooks are installed
Hook version: 2.3.0                       # Version of installed hooks
Latest version: 2.3.0                     # Version in code (should match)

Running nags: 0                           # Active bell processes

Configuration:
  Audio: default                          # Using bundled bell.wav
  Grace period: 30s                       # Wait before first bell
  Interval: 30s                           # Bell repeats every 30s
  Max nags: 0 (0=unlimited)               # No limit on repeats
  Volume: 100%                            # Full volume
  Enabled hooks: stop, idle               # Active hook types
```

---

## Edge Cases

### Multiple Claude Sessions

Each Claude Code session has its own state. Bells from one session don't affect another.

### Claude Crashes

Orphan protection kicks in:
- Bell processes have a 10-minute max lifetime
- Stop hook checks Claude's heartbeat (2-min timeout)
- Run `waiting doctor` to clean up stale files

### No Sound?

1. Check volume: `waiting configure --volume 100`
2. Check audio player: `which paplay || which aplay || which afplay`
3. Check system audio isn't muted
4. Try: `waiting configure --audio /path/to/custom.wav`

---

## Summary: When Will I Hear a Bell?

| Situation | Default Config | Repeats? |
|-----------|---------------|----------|
| Claude finished, I'm AFK for 30+ sec | 🔔 Yes | Every 30s |
| Claude waiting at prompt for 60+ sec | 🔔 Yes | Every 30s |
| Permission dialog appears | ❌ No (opt-in) | Once only |
| I'm actively chatting with Claude | ❌ No | N/A |
| I responded before grace period ended | ❌ No | N/A |
