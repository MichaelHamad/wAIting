"""Linux audio player implementations."""

import subprocess
from pathlib import Path
from shutil import which

from ..errors import AudioError


# Common Linux system sound locations
LINUX_SYSTEM_SOUNDS = [
    "/usr/share/sounds/freedesktop/stereo/bell.oga",
    "/usr/share/sounds/freedesktop/stereo/complete.oga",
    "/usr/share/sounds/sound-icons/prompt.wav",
    "/usr/share/sounds/sound-icons/bell.wav",
]


def _find_system_sound() -> str | None:
    """
    Find an available system sound file on Linux.

    Returns:
        str | None: Path to system sound file, or None if not found
    """
    for sound_path in LINUX_SYSTEM_SOUNDS:
        if Path(sound_path).exists():
            return sound_path
    return None


class PulseAudioPlayer:
    """PulseAudio (paplay) player for Linux."""

    def play(self, file_path: str, volume: int) -> int:
        """
        Play audio using paplay.

        Args:
            file_path: Path to audio file or "default"
            volume: Volume 1-100

        Returns:
            int: Process ID

        Raises:
            Exception: If playback fails
        """
        # Convert volume 1-100 to paplay volume 0.0-1.0
        pa_volume = volume / 100.0

        cmd = [
            "paplay",
            "--volume",
            str(int(pa_volume * 65536)),  # paplay uses 0-65536 scale
        ]

        if file_path != "default":
            cmd.append(file_path)
        else:
            # Play system bell with alert role
            cmd.extend(["--property", "media.role=alert"])

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
        """Check if paplay is available."""
        return which("paplay") is not None

    def name(self) -> str:
        """Return player name."""
        return "PulseAudio"


class PipeWirePlayer:
    """PipeWire (pw-play) player for Linux."""

    def play(self, file_path: str, volume: int) -> int:
        """
        Play audio using pw-play.

        Args:
            file_path: Path to audio file or "default"
            volume: Volume 1-100

        Returns:
            int: Process ID

        Raises:
            AudioError: If "default" requested but no system sound found
            Exception: If playback fails
        """
        # Convert volume 1-100 to percentage
        pw_volume = volume / 100.0

        cmd = ["pw-play"]

        if file_path == "default":
            system_sound = _find_system_sound()
            if system_sound is None:
                raise AudioError(
                    "PipeWire player: No system sound found. "
                    "Install freedesktop-sound-theme or specify a custom audio file."
                )
            cmd.append(system_sound)
        else:
            cmd.append(file_path)

        # pw-play volume control via --volume argument
        cmd.extend(["--volume", str(pw_volume)])

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
        """Check if pw-play is available."""
        return which("pw-play") is not None

    def name(self) -> str:
        """Return player name."""
        return "PipeWire"


class ALSAPlayer:
    """ALSA (aplay) player for Linux."""

    def play(self, file_path: str, volume: int) -> int:
        """
        Play audio using aplay.

        Args:
            file_path: Path to audio file or "default"
            volume: Volume 1-100

        Returns:
            int: Process ID

        Raises:
            Exception: If playback fails
        """
        cmd = ["aplay"]

        if file_path == "default":
            # ALSA requires a file path; this should not happen with bundled sound
            # but handle gracefully as defensive programming
            raise AudioError("ALSA player requires a file path, cannot use 'default' string")

        cmd.append(file_path)

        # aplay volume control via -v flag (0-100)
        cmd.extend(["-v", str(volume)])

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
        """Check if aplay is available."""
        return which("aplay") is not None

    def name(self) -> str:
        """Return player name."""
        return "ALSA"


def get_linux_player() -> "AudioPlayer":
    """
    Get the first available Linux audio player.

    Tries in order: PulseAudio, PipeWire, ALSA

    Returns:
        AudioPlayer: First available player

    Raises:
        Exception: If no audio player is available
    """
    players = [PulseAudioPlayer(), PipeWirePlayer(), ALSAPlayer()]

    for player in players:
        if player.available():
            return player

    available_names = ", ".join(p.name() for p in players)
    raise Exception(f"No audio player available. Tried: {available_names}")
