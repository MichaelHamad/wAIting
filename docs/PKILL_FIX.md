# Why pkill -f Wasn't Working (And How We Fixed It)

## The Problem

When a user approves a permission dialog, PreToolUse fires and tries to kill the nag process:

```bash
pkill -f "waiting-nag-$SESSION_ID"
```

But the debug log showed:
```
No nag processes found for: waiting-nag-60ff026a-f034-4d24-94d1-cf2993f6062e
```

Yet `ps aux` showed processes were clearly running:
```
/bin/bash /home/michael/.claude/hooks/waiting-notify-permission.sh
```

## Root Cause

`pkill -f` matches against `/proc/<pid>/cmdline` - the **command line** used to start the process.

Our original approach tried to set a marker variable inside the subshell:

```bash
(
    _MARKER_FOR_PKILL="$NAG_MARKER"  # This does NOT appear in cmdline!
    sleep 10
    play_sound
    ...
) &
```

**This doesn't work because:**
- Shell variables exist only in memory
- They don't appear in `/proc/cmdline`
- `pkill -f` has nothing to match against

The command line for a subshell is just the parent script path:
```
/bin/bash /home/michael/.claude/hooks/waiting-notify-permission.sh
```

There's no session ID anywhere in that string.

## The Solution: Wrapper Script with Marker in Filename

Instead of a subshell, we create a **separate script file** with the session marker in its **filename**:

```bash
NAG_MARKER="waiting-nag-$SESSION_ID"
NAG_SCRIPT="/tmp/$NAG_MARKER.sh"

# Write the nag loop to a file
cat > "$NAG_SCRIPT" << 'EOF'
#!/bin/bash
sleep 10
play_sound
...
EOF

chmod +x "$NAG_SCRIPT"

# Run it in background
"$NAG_SCRIPT" &
```

Now `ps aux` shows:
```
/bin/bash /tmp/waiting-nag-60ff026a-f034-4d24-94d1-cf2993f6062e.sh
```

And `pkill -f "waiting-nag-60ff026a"` **matches** because the marker is in the path!

## Why This Works

| Approach | cmdline | pkill -f matches? |
|----------|---------|-------------------|
| Subshell with variable | `/bin/bash script.sh` | No |
| `bash -c "marker; code"` | `bash -c marker; code...` | Yes (but escaping is complex) |
| Wrapper script file | `/bin/bash /tmp/waiting-nag-SESSION.sh` | Yes |

The wrapper script approach is:
1. **Reliable** - The path is always in cmdline
2. **Simple** - No complex escaping needed
3. **Clean** - Script file is deleted after use

## Implementation Details

### PermissionRequest Hook

```bash
# Create wrapper script with session marker in filename
NAG_SCRIPT="/tmp/$NAG_MARKER.sh"

cat > "$NAG_SCRIPT" << NAGEOF
#!/bin/bash
# Nag loop code here...
NAGEOF

chmod +x "$NAG_SCRIPT"
"$NAG_SCRIPT" &
echo $! > "$PID_FILE"
```

### PreToolUse Hook

```bash
NAG_MARKER="waiting-nag-$SESSION_ID"

# Kill by pattern - matches the script path
pkill -f "$NAG_MARKER"

# Clean up files
rm -f "/tmp/$NAG_MARKER.pid" "/tmp/$NAG_MARKER.sh"
```

## Alternative Approaches Considered

### 1. `exec -a` to rename process
```bash
exec -a "waiting-nag-$SESSION_ID" bash -c '...'
```
- Sets a custom process name
- Complex when passing code to bash -c
- Not all systems support it

### 2. `bash -c` with marker in string
```bash
bash -c ": $NAG_MARKER; actual_code_here" &
```
- The `:` is a no-op but appears in cmdline
- Requires complex escaping in Python f-strings
- Error-prone with nested quotes

### 3. Environment variable
```bash
NAG_MARKER="$NAG_MARKER" bash -c '...' &
```
- Environment variables don't appear in cmdline
- Would need to grep /proc/*/environ instead
- More complex and less portable

## Lessons Learned

1. **Shell variables are invisible to pkill -f** - They exist in memory, not in the command line
2. **Subshell command lines are just the parent script** - No way to inject markers
3. **File paths are reliable markers** - They always appear in cmdline
4. **Test with `ps aux | grep`** - See exactly what pkill -f will match against
