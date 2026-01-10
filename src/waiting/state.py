"""State management using temporary files for session tracking."""

import hashlib
import re
from pathlib import Path


# Valid session ID pattern: alphanumeric, hyphens, underscores only
VALID_SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def _is_valid_session_id(session_id: str) -> bool:
    """
    Validate session ID for safe file path usage.

    Args:
        session_id: Session ID to validate

    Returns:
        bool: True if session ID is safe, False otherwise
    """
    if not session_id:
        return False
    # Max length to prevent filesystem issues
    if len(session_id) > 128:
        return False
    return bool(VALID_SESSION_ID_PATTERN.match(session_id))


def generate_session_id(hook_input: dict | None = None) -> str:
    """
    Generate a unique session ID.

    If hook_input contains a valid session_id field, use it.
    Otherwise, generate one from hostname + timestamp.

    Args:
        hook_input: Hook input JSON (optional)

    Returns:
        str: Unique session ID (guaranteed safe for file paths)
    """
    if hook_input and isinstance(hook_input, dict):
        session_id = hook_input.get("session_id")
        if session_id and isinstance(session_id, str) and _is_valid_session_id(session_id):
            return session_id

    # Fallback: MD5 hash of hostname + timestamp
    import socket
    import time

    timestamp = time.time_ns()
    hostname = socket.gethostname()
    source = f"{hostname}-{timestamp}"
    return hashlib.md5(source.encode()).hexdigest()


def write_pid_file(session_id: str, pid: int) -> Path:
    """
    Write audio process PID to temp file.

    Args:
        session_id: Session identifier
        pid: Process ID to store

    Returns:
        Path: Path to PID file
    """
    pid_file = Path(f"/tmp/waiting-audio-{session_id}.pid")
    try:
        pid_file.write_text(str(pid))
    except OSError as e:
        raise IOError(f"Failed to write PID file: {e}")
    return pid_file


def read_pid_file(session_id: str) -> int | None:
    """
    Read audio process PID from temp file.

    Args:
        session_id: Session identifier

    Returns:
        int | None: Process ID if file exists and is valid, None otherwise
    """
    pid_file = Path(f"/tmp/waiting-audio-{session_id}.pid")
    if not pid_file.exists():
        return None

    try:
        pid_str = pid_file.read_text().strip()
        return int(pid_str)
    except (ValueError, OSError):
        return None


def create_stop_signal(session_id: str) -> Path:
    """
    Create stop signal file.

    This signals the permission hook to cancel audio playback.

    Args:
        session_id: Session identifier

    Returns:
        Path: Path to stop signal file
    """
    stop_signal = Path(f"/tmp/waiting-stop-{session_id}")
    try:
        stop_signal.touch()
    except OSError as e:
        raise IOError(f"Failed to create stop signal: {e}")
    return stop_signal


def has_stop_signal(session_id: str) -> bool:
    """
    Check if stop signal file exists (user responded).

    Args:
        session_id: Session identifier

    Returns:
        bool: True if stop signal exists, False otherwise
    """
    stop_signal = Path(f"/tmp/waiting-stop-{session_id}")
    return stop_signal.exists()


def cleanup(session_id: str) -> None:
    """
    Remove all temporary files for a session.

    Args:
        session_id: Session identifier
    """
    files_to_remove = [
        Path(f"/tmp/waiting-stop-{session_id}"),
        Path(f"/tmp/waiting-audio-{session_id}.pid"),
    ]

    for file_path in files_to_remove:
        try:
            if file_path.exists():
                file_path.unlink()
        except OSError:
            # Silently ignore cleanup failures
            pass


def cleanup_old_files(age_hours: int = 1) -> None:
    """
    Remove temporary files older than specified age.

    Args:
        age_hours: Remove files older than this many hours
    """
    import time

    now = time.time()
    age_seconds = age_hours * 3600

    for pattern in ["waiting-stop-*", "waiting-audio-*.pid"]:
        for file_path in Path("/tmp").glob(pattern):
            try:
                file_stat = file_path.stat()
                if now - file_stat.st_mtime > age_seconds:
                    file_path.unlink()
            except OSError:
                # Silently ignore files that can't be deleted
                pass
