# Waiting - User Guide

**Version:** 2.0.0
**Last Updated:** January 5, 2026

---

## Overview

`waiting` notifies you with a bell sound when Claude Code needs your input. It includes safeguards to ensure sounds stop immediately when you respond.

---

## Quick Start

```bash
# Enable notifications
waiting

# Check health
waiting status

# Diagnose issues
waiting doctor

# Stop sounds immediately
waiting kill

# Disable notifications
waiting disable
```

---

## Commands

### `waiting`
Enables notifications. Run after installing or to update hooks.

### `waiting status`
Shows current configuration and health:
```
Status: enabled
Hook version: 2.0.0 (current)
Latest version: 2.0.0

Running nags: 0

Configuration:
  Audio: default
  Interval: 30s
  Grace periods:
    permission: 10s
```

### `waiting doctor`
Diagnoses common issues:
```
[OK] Hook version: 2.0.0
[OK] No stray nag processes
[OK] Claude settings configured
[OK] All required hook scripts present

All checks passed!
```

Auto-fix with: `waiting doctor --fix`

### `waiting kill`
Immediately stops all notification sounds without disabling the system.

### `waiting disable`
Removes all hooks and stops notifications.

### `waiting configure`
Customize settings:
```bash
waiting configure --interval 60      # Seconds between bells
waiting configure --grace-permission 15  # Seconds before first bell
waiting configure --volume 75        # Volume percentage
waiting configure --show             # View current config
```

---

## Troubleshooting

### "I hear stray bells that won't stop"
```bash
waiting kill
waiting doctor --fix
```
Then restart Claude Code.

### "I don't hear any notification"
1. Check if enabled: `waiting status`
2. Check debug log: `tail -20 /tmp/waiting-activity-debug.log`
3. Verify audio works: `aplay ~/.claude/hooks/../waiting/Cool_bell_final.wav`

### "Hooks are outdated"
```bash
waiting doctor --fix
# or simply
waiting
```
Then restart Claude Code.

---

## How It Works

1. **Permission dialog appears** - Claude needs your approval
2. **Grace period** - Waits 10 seconds (configurable)
3. **Bell plays** - If you haven't responded
4. **You respond** - Bell stops immediately
5. **Repeat** - For next permission dialog

---

## Safeguards

- **Stop-signal mechanism** - Sounds stop within 200ms of your response
- **Version tracking** - Warns when hooks are outdated
- **Doctor command** - Auto-diagnoses and fixes issues
- **Orphan cleanup** - Removes stale processes automatically
