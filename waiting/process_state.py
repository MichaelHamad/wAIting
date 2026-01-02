"""Process state introspection for true input-blocked detection.

On Linux, we can read /proc/<pid>/wchan to determine if a process is
blocked waiting for terminal input. This provides definitive detection
rather than heuristics.

On macOS, /proc doesn't exist, so we fall back to heuristic detection.
"""

import os
import platform
from enum import Enum
from typing import List, Optional


class BlockedState(Enum):
    """State of a process with respect to input blocking."""
    UNKNOWN = "unknown"           # Could not determine (permissions, not Linux, etc.)
    NOT_BLOCKED = "not_blocked"   # Process is running or blocked on something else
    BLOCKED_TTY_READ = "blocked_tty_read"  # Definitively blocked reading from TTY
    BLOCKED_SELECT = "blocked_select"      # Blocked in select/poll (might be TTY)


# Kernel wait channel names that indicate TTY read blocking
_TTY_READ_WCHANS = frozenset({
    'n_tty_read',           # Standard TTY read
    'tty_read',             # Generic TTY read
    'pty_read',             # PTY-specific read
    'wait_woken',           # Waiting for I/O wakeup
})

# Wait channels that indicate select/poll (might be waiting on TTY)
_SELECT_WCHANS = frozenset({
    'do_select',
    'do_poll',
    'poll_schedule_timeout',
    'do_sys_poll',
    'core_sys_select',
})


def get_process_state_linux(pid: int) -> str:
    """Get single-character process state from /proc/<pid>/stat.

    Returns:
        'R' = Running
        'S' = Sleeping (interruptible) - likely blocked on I/O
        'D' = Disk sleep (uninterruptible)
        'Z' = Zombie
        'T' = Stopped
        '?' = Unknown/error
    """
    try:
        with open(f"/proc/{pid}/stat", 'r') as f:
            # Format: pid (comm) state ...
            # comm can contain spaces/parens, so find last ')' first
            content = f.read()
            last_paren = content.rfind(')')
            if last_paren == -1:
                return '?'
            # State is first field after the closing paren
            fields_after_comm = content[last_paren + 2:].split()
            if fields_after_comm:
                return fields_after_comm[0]
    except (FileNotFoundError, PermissionError, IndexError, OSError):
        pass
    return '?'


def get_wchan_linux(pid: int) -> Optional[str]:
    """Get the kernel wait channel for a process.

    Returns the name of the kernel function where the process is sleeping,
    or None if unavailable.
    """
    try:
        wchan_path = f"/proc/{pid}/wchan"
        if os.path.exists(wchan_path):
            with open(wchan_path, 'r') as f:
                wchan = f.read().strip()
                # '0' means not sleeping
                if wchan and wchan != '0':
                    return wchan
    except (FileNotFoundError, PermissionError, OSError):
        pass
    return None


def get_blocked_state_linux(pid: int) -> BlockedState:
    """Determine if a process is blocked waiting for TTY input on Linux.

    Uses /proc/<pid>/stat for process state and /proc/<pid>/wchan for
    the kernel wait channel.

    Returns:
        BlockedState indicating whether process is blocked on TTY read.
    """
    # First check if process is sleeping
    state = get_process_state_linux(pid)
    if state == '?':
        return BlockedState.UNKNOWN
    if state != 'S':
        # Not sleeping = not blocked on read
        return BlockedState.NOT_BLOCKED

    # Process is sleeping - check what it's waiting on
    wchan = get_wchan_linux(pid)
    if wchan is None:
        return BlockedState.UNKNOWN

    if wchan in _TTY_READ_WCHANS:
        return BlockedState.BLOCKED_TTY_READ

    if wchan in _SELECT_WCHANS:
        return BlockedState.BLOCKED_SELECT

    return BlockedState.NOT_BLOCKED


def get_descendant_pids_linux(pid: int) -> List[int]:
    """Get all descendant PIDs of a process on Linux.

    Recursively finds all children, grandchildren, etc.
    """
    descendants = []
    try:
        # Try /proc/<pid>/task/<pid>/children first (Linux 3.5+)
        children_path = f"/proc/{pid}/task/{pid}/children"
        if os.path.exists(children_path):
            with open(children_path, 'r') as f:
                child_pids = [int(p) for p in f.read().split() if p.strip()]
                for child_pid in child_pids:
                    descendants.append(child_pid)
                    descendants.extend(get_descendant_pids_linux(child_pid))
    except (FileNotFoundError, PermissionError, ValueError, OSError):
        pass
    return descendants


def is_any_process_blocked_on_tty(pid: int) -> BlockedState:
    """Check if the process or any of its descendants are blocked on TTY read.

    This is important because the direct child might spawn subprocesses
    (e.g., claude spawns node) and we need to detect when ANY of them
    are waiting for input.

    Returns:
        BlockedState.BLOCKED_TTY_READ if any process is definitively blocked
        BlockedState.BLOCKED_SELECT if any process might be blocked (via select)
        BlockedState.NOT_BLOCKED if no process is blocked
        BlockedState.UNKNOWN if we couldn't determine
    """
    if platform.system() != 'Linux':
        return BlockedState.UNKNOWN

    # Check main process and all descendants
    all_pids = [pid] + get_descendant_pids_linux(pid)

    found_select = False
    found_unknown = False

    for check_pid in all_pids:
        state = get_blocked_state_linux(check_pid)
        if state == BlockedState.BLOCKED_TTY_READ:
            # Definitive - return immediately
            return BlockedState.BLOCKED_TTY_READ
        elif state == BlockedState.BLOCKED_SELECT:
            found_select = True
        elif state == BlockedState.UNKNOWN:
            found_unknown = True

    if found_select:
        return BlockedState.BLOCKED_SELECT
    if found_unknown:
        return BlockedState.UNKNOWN
    return BlockedState.NOT_BLOCKED


def is_linux() -> bool:
    """Check if we're running on Linux."""
    return platform.system() == 'Linux'
