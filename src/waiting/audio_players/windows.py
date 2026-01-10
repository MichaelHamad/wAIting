"""Windows and WSL audio player implementation."""

import subprocess
from shutil import which


class PowerShellPlayer:
    """PowerShell audio player for Windows/WSL."""

    def play(self, file_path: str, volume: int) -> int:
        """
        Play audio using PowerShell (Windows/WSL).

        Args:
            file_path: Path to audio file or "default"
            volume: Volume 1-100

        Returns:
            int: Process ID

        Raises:
            Exception: If playback fails
        """
        # Convert volume 1-100 to 0.0-1.0 scale
        ps_volume = volume / 100.0

        if file_path == "default":
            # Play system beep using PowerShell
            ps_script = f"[System.Media.SystemSounds]::Beep.Play()"
        else:
            # Play file with volume control
            ps_script = f"""
$player = New-Object System.Media.SoundPlayer
$player.SoundLocation = '{file_path}'
$volume = {ps_volume}
$player.Volume = [math]::Min(1.0, [math]::Max(0.0, $volume))
$player.PlaySync()
"""

        cmd = ["powershell.exe", "-Command", ps_script]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc.pid

    def kill(self, pid: int) -> bool:
        """Kill audio process by PID."""
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False)
            return True
        except Exception:
            return False

    def available(self) -> bool:
        """Check if PowerShell is available."""
        return which("powershell.exe") is not None

    def name(self) -> str:
        """Return player name."""
        return "PowerShell"
