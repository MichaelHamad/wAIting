"""Base protocol for audio player implementations."""

from typing import Protocol


class AudioPlayer(Protocol):
    """Interface for cross-platform audio playback."""

    def play(self, file_path: str, volume: int) -> int:
        """
        Play an audio file.

        Args:
            file_path: Path to audio file (or "default" for system bell)
            volume: Volume level 1-100

        Returns:
            int: Process ID of audio player

        Raises:
            Exception: If playback fails
        """
        ...

    def kill(self, pid: int) -> bool:
        """
        Kill audio process by PID.

        Args:
            pid: Process ID to kill

        Returns:
            bool: True if process was killed, False if already gone
        """
        ...

    def available(self) -> bool:
        """
        Check if audio player command is available on system.

        Returns:
            bool: True if player is available
        """
        ...

    def name(self) -> str:
        """
        Get human-readable name of audio player.

        Returns:
            str: Player name (e.g., "PulseAudio", "AFPlay")
        """
        ...
