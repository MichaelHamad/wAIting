# Race Condition Fix Options

## The Problem

When multiple `PermissionRequest` hooks fire simultaneously (which happens when Claude uses multiple tools in quick succession), each spawns a background nag process. This causes:

1. Multiple bells ringing simultaneously
2. Orphaned processes that don't get killed when user approves
3. Bells continuing after user has responded

## Current Approach (Fragile)

Each process stores its PID and checks if it matches the PID file before playing sound:

```bash
MY_PID=$BASHPID
sleep 0.1  # Wait for parent to write file
CURRENT_PID=$(cat "$PID_FILE")
if [ "$CURRENT_PID" != "$MY_PID" ]; then
    exit 0  # We've been superseded
fi
```

**Problems:**
- Still has race windows
- Relies on timing (0.1s delay)
- Complex to reason about
- Doesn't always catch all cases

---

## Option 1: File Locking with flock

Use the kernel's file locking mechanism to ensure only one nag process runs at a time.

```bash
#!/bin/bash
LOCK_FILE="/tmp/waiting-lock-$SESSION_ID.lock"

# Try to acquire exclusive lock (non-blocking)
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    # Another nag is running, kill it and try again
    OLD_PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$OLD_PID" ]; then
        kill "$OLD_PID" 2>/dev/null
    fi
    sleep 0.1
    flock -n 200 || exit 0  # Still can't get lock, exit
fi

# We have the lock, proceed with nag
echo $$ > "$PID_FILE"
# ... rest of nag logic ...
```

**Pros:**
- Kernel-level guarantee of mutual exclusion
- No race conditions possible
- Clean and well-understood mechanism

**Cons:**
- Slightly more complex setup
- Lock file cleanup needed
- flock behavior varies slightly across systems

---

## Option 2: Kill All Before Start (Recommended)

Simply kill ALL existing permission nag processes before starting a new one. Brute force but effective.

```bash
#!/bin/bash
# Kill any existing nag processes for this session
pkill -f "waiting-nag-$SESSION_ID" 2>/dev/null

# Small delay to let processes die
sleep 0.2

# Remove stale PID file
rm -f "$PID_FILE"

# Start fresh nag process
(
    # ... nag logic ...
) &
echo $! > "$PID_FILE"
```

**To make processes identifiable, rename the background script or add a marker:**
```bash
# In the subshell, set a process title or use exec with a named script
exec -a "waiting-nag-$SESSION_ID" bash -c '
    # ... nag logic ...
'
```

**Pros:**
- Simple to understand
- Guarantees only one nag runs
- No race conditions - kill everything, start fresh
- Works reliably across all systems

**Cons:**
- Slightly aggressive (kills even if process was about to exit anyway)
- Small delay (0.2s) needed to ensure processes are dead
- Need to make processes identifiable by session

---

## Option 3: Single Nag Manager

Instead of spawning background processes for each PermissionRequest, have a persistent "nag manager" that receives commands.

```bash
# Nag manager (runs once, stays alive)
FIFO="/tmp/waiting-fifo-$SESSION_ID"
mkfifo "$FIFO" 2>/dev/null

while true; do
    cmd=$(cat "$FIFO")
    case "$cmd" in
        start)
            # Cancel any pending nag, start new timer
            ;;
        stop)
            # Cancel pending nag
            ;;
        quit)
            break
            ;;
    esac
done
```

```bash
# PermissionRequest hook (just sends command)
echo "start" > "/tmp/waiting-fifo-$SESSION_ID"
```

```bash
# PreToolUse hook (just sends command)
echo "stop" > "/tmp/waiting-fifo-$SESSION_ID"
```

**Pros:**
- Clean separation of concerns
- No race conditions (single process handles all commands)
- Easy to extend with new commands
- More efficient (no constant process spawning)

**Cons:**
- More complex architecture
- Need to manage the manager's lifecycle (start on first use, cleanup on exit)
- FIFO handling can be tricky
- Need to handle manager crashes

---

## Recommendation

**Option 2 (Kill All Before Start)** is the best balance of simplicity and reliability:

1. Easy to implement and understand
2. Guarantees correct behavior
3. No complex coordination needed
4. Works on all systems

The small delay (0.2s) is negligible in practice since the user won't notice it.

## Implementation Plan for Option 2

1. Modify `create_permission_notify_script()` to:
   - Add session ID to the subprocess name/command
   - At start: `pkill` all processes matching that session
   - Wait 0.2s for cleanup
   - Then start the new nag

2. Modify `PreToolUse` hook to:
   - Also use `pkill` to kill by pattern (backup to PID file method)

3. Remove the complex PID ownership checking (no longer needed)
