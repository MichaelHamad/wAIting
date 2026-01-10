"""macOS audio player implementation."""

import subprocess
from shutil import which


class AFPlayPlayer:
    """AFPlay player for macOS."""

    def play(self, file_path: str, volume: int) -> int:
        """
        Play audio using afplay.

        Args:
            file_path: Path to audio file or "default"
            volume: Volume 1-100

        Returns:
            int: Process ID

        Raises:
            Exception: If playback fails
        """
        # Convert volume 1-100 to 0.0-1.0 scale for afplay -v
        afplay_volume = volume / 100.0

        cmd = ["afplay"]

        if file_path != "default":
            cmd.append(file_path)
        else:
            # Use system bell sound on macOS
            cmd.append("/System/Library/Sounds/Glass.aiff")

        # afplay volume control via -v flag (0.0-1.0)
        cmd.extend(["-v", str(afplay_volume)])

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc.pid

    def kill(self, pid: int) -> bool:
        """Kill audio process by PID."""
        try:
            subprocess.run(["kill", str(pid)], check=False)
            return True
        except Exception:
            return False

    def available(self) -> bool:
        """Check if afplay is available."""
        return which("afplay") is not None

    def name(self) -> str:
        """Return player name."""
        return "AFPlay"
