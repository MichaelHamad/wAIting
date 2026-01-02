# Project Overview: waiting

## The Problem

When using Claude Code, you often tab away to do other things - check documentation, watch YouTube, browse the web. Meanwhile, Claude finishes its work and asks you a question or needs permission to proceed.

**The result:** You come back 10, 20, even 30 minutes later to find Claude has been sitting there waiting for you the whole time. Productivity lost.

Claude Code has a built-in `idle_prompt` notification, but it only triggers after **60 seconds of inactivity**. That's too slow - by the time it fires, you've already context-switched and forgotten about Claude.

## Our Solution

**waiting** is a simple CLI tool that plays a sound immediately when Claude Code needs your input.

```
pip install waiting
waiting
```

That's it. Now you'll hear a bell the moment Claude needs you.

### Key Features

1. **Immediate notification** - Sound plays right when Claude asks, not after 60 seconds
2. **Persistent nagging** - If you don't respond, it keeps reminding you every 15 seconds
3. **Grace period** - Won't spam you if you just responded (configurable)
4. **Simple config** - One JSON file at `~/.waiting.json`
5. **Cross-platform** - Works on Linux, macOS, and WSL

## Why We Built It This Way

### Why hooks instead of polling?

Claude Code provides a hook system that fires events when things happen. We use:

- `PermissionRequest` - fires when Claude needs user approval
- `PreToolUse` - fires when user approves (before tool runs)
- `PostToolUse` - fires when tool completes

This is **event-driven**, not polling. Zero CPU usage when idle, instant response when needed.

### Why a nag loop?

A single notification isn't enough. If you're deep in another task, you might miss one bell. The nag loop ensures you eventually hear it:

```
PermissionRequest → bell → wait 15s → bell → wait 15s → bell → ...
                                                            ↓
                                              User responds → stop
```

### Why a grace period?

Without it, rapid-fire tool approvals would be annoying:

```
Claude: "Can I read file A?" → bell
You: "Yes"
Claude: "Can I read file B?" → bell (annoying!)
You: "Yes"
Claude: "Can I edit file C?" → bell (very annoying!)
```

With a 60-second grace period, if you just responded, we assume you're still watching and skip the immediate bell. But the nag loop still starts - so if you *do* tab away, you'll still get reminded after 15 seconds.

### Why PreToolUse for stopping?

Initially we used `PostToolUse` to stop the nag loop. Problem: tools can take time to execute. If you approve a 30-second build command, the nag loop keeps running during execution.

`PreToolUse` fires immediately when you approve, *before* the tool runs. The nag stops instantly.

### Why `~/.waiting.json`?

Config location options we considered:

| Location | Pros | Cons |
|----------|------|------|
| `~/.config/waiting/config.json` | XDG standard | Nested, hard to find |
| `~/.claude/waiting.json` | Near Claude config | Hidden directory |
| `./waiting.json` | Project-local | Scattered configs, confusing |
| **`~/.waiting.json`** | **Easy to find, global** | Dot file (but common) |

We chose `~/.waiting.json` because:
- It's in the home directory (easy: `cat ~/.waiting.json`)
- It's global (one config works everywhere)
- Users can override with `WAITING_CONFIG` env var if needed

### Why shell scripts for hooks?

Claude Code hooks execute commands. We generate shell scripts that:

1. Check grace period (should we alert?)
2. Play sound (cross-platform audio detection)
3. Start background nag loop
4. Write PID file (so we can stop it later)

Shell scripts are simple, portable, and have no runtime dependencies.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Claude Code                              │
│                                                                 │
│  Hooks System                                                   │
│  ├── PermissionRequest → waiting-notify.sh                      │
│  ├── PreToolUse        → waiting-stop.sh                        │
│  └── PostToolUse       → waiting-stop.sh                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ~/.claude/hooks/                             │
│                                                                 │
│  waiting-notify.sh                                              │
│  ├── Check grace period (/tmp/waiting-last-activity)           │
│  ├── Kill existing nag loop                                     │
│  ├── Play sound (aplay/paplay/afplay/powershell)               │
│  └── Start background nag loop → PID to /tmp/waiting-nag.pid   │
│                                                                 │
│  waiting-stop.sh                                                │
│  ├── Record activity timestamp                                  │
│  └── Kill nag loop (read PID, kill process)                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     ~/.waiting.json                             │
│                                                                 │
│  {                                                              │
│    "audio": "default",                                          │
│    "grace_period": 60,                                          │
│    "interval": 15,                                              │
│    "max_nags": 0                                                │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
```

## Trade-offs

| Decision | Trade-off |
|----------|-----------|
| Grace period | Might miss prompt if you tab away within 60s of responding |
| Nag loop | Could be annoying if interval too short |
| Global config | Can't have per-project settings (but can override with env var) |
| Shell scripts | Less portable than pure Python, but simpler hook integration |

## Future Considerations

- **Different sounds for different events** - permission vs question vs error
- **Desktop notifications** - in addition to sound
- **Per-project config** - detect `.waiting.json` in project root
- **Quiet hours** - don't nag during certain times
