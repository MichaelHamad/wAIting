"""Event types for wait detection."""

from dataclasses import dataclass


@dataclass
class WaitingEntered:
    """Emitted when the command enters a waiting state."""
    timestamp: float


@dataclass
class WaitingExited:
    """Emitted when the command exits a waiting state."""
    timestamp: float
    reason: str  # "input", "output", "exit"


@dataclass
class ProcessExited:
    """Emitted when the wrapped process terminates."""
    exit_code: int
