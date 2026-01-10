"""Audio playback interface with platform detection."""

import logging
import platform
import sys
from importlib.resources import files
from pathlib import Path

from .errors import AudioError
from .audio_players.base import AudioPlayer


# Cache for audio player instance (for testing purposes)
_audio_player_cache = None


def _clear_audio_player_cache() -> None:
    """Clear the audio player cache. Used for testing purposes."""
    global _audio_player_cache
    _audio_player_cache = None


def get_audio_player() -> AudioPlayer:
    """
    Auto-detect and return appropriate audio player for platform.

    Caches player instance to avoid repeated initialization overhead.

    Returns:
        AudioPlayer: Platform-specific audio player

    Raises:
        AudioError: If no suitable player found
    """
    global _audio_player_cache

    # Return cached player if available
    if _audio_player_cache is not None:
        return _audio_player_cache

    system = platform.system()

    if system == "Linux":
        from .audio_players.linux import get_linux_player

        try:
            player = get_linux_player()
            _audio_player_cache = player
            return player
        except Exception as e:
            raise AudioError(f"No Linux audio player available: {e}")

    elif system == "Darwin":  # macOS
        from .audio_players.macos import AFPlayPlayer

        player = AFPlayPlayer()
        if not player.available():
            raise AudioError("AFPlay not available on macOS")
        _audio_player_cache = player
        return player

    elif system == "Windows":
        from .audio_players.windows import PowerShellPlayer

        player = PowerShellPlayer()
        if not player.available():
            raise AudioError("PowerShell not available on Windows")
        _audio_player_cache = player
        return player

    else:
        raise AudioError(f"Unsupported platform: {system}")


def resolve_audio_file(audio_config: str) -> Path | str:
    """
    Resolve audio file path from configuration.

    Prioritizes bundled sound file for "default" audio config.

    Args:
        audio_config: Audio path or "default"

    Returns:
        Path | str: Resolved audio file path or "default"

    Raises:
        AudioError: If custom file not found
    """
    if audio_config == "default":
        # FIRST PRIORITY: Try bundled sound file
        try:
            resource_path = files("waiting.assets").joinpath("Cool_bell_final.wav")
            if resource_path.is_file():
                return Path(str(resource_path))
        except Exception:
            pass  # Continue to fallback

        # FALLBACK: If bundled sound fails, return "default" string
        # Platform players will handle with system beep/bell
        return "default"

    # Custom audio file path
    audio_path = Path(audio_config).expanduser()

    if not audio_path.exists():
        raise AudioError(f"Audio file not found: {audio_config}")

    return audio_path


def play_audio(file_path: str, volume: int, logger: logging.Logger | None = None) -> int:
    """
    Play audio file and return process ID.

    Args:
        file_path: Path to audio file or "default"
        volume: Volume 1-100
        logger: Optional logger instance

    Returns:
        int: Process ID of audio player

    Raises:
        AudioError: If playback fails
    """
    if logger is None:
        from .logging import setup_logging

        logger = setup_logging()

    try:
        player = get_audio_player()
        resolved_path = resolve_audio_file(file_path)
        pid = player.play(str(resolved_path), volume)

        logger.info(
            f"Audio playing with PID {pid} using {player.name()} "
            f"(file: {file_path}, volume: {volume}%)"
        )
        return pid

    except Exception as e:
        logger.error(f"Audio playback failed: {e}")
        raise AudioError(str(e)) from e


def kill_audio(pid: int, logger: logging.Logger | None = None) -> bool:
    """
    Kill audio process by PID.

    Args:
        pid: Process ID to kill
        logger: Optional logger instance

    Returns:
        bool: True if killed, False if already gone

    Raises:
        AudioError: If kill fails
    """
    if logger is None:
        from .logging import setup_logging

        logger = setup_logging()

    try:
        player = get_audio_player()
        result = player.kill(pid)

        if result:
            logger.info(f"Killed audio process PID {pid}")
        else:
            logger.warning(f"Audio process PID {pid} already gone")

        return result

    except Exception as e:
        logger.warning(f"Failed to kill audio process: {e}")
        # Try OS-level kill as fallback
        import subprocess

        try:
            subprocess.run(["kill", str(pid)], check=False)
            logger.info(f"Force killed audio process PID {pid}")
            return True
        except Exception:
            return False


# CLI entry point for hook scripts
if __name__ == "__main__":
    """
    Command-line interface for audio playback.
    Used by hook scripts to play audio.

    Usage: python -m waiting.audio <file_path> <volume>
    """
    if len(sys.argv) < 3:
        print("Usage: python -m waiting.audio <file_path> <volume>", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    volume = int(sys.argv[2])

    from .logging import setup_logging

    logger = setup_logging()

    try:
        pid = play_audio(file_path, volume, logger)
        print(pid)
        sys.exit(0)
    except AudioError as e:
        logger.error(f"Audio playback failed: {e}")
        sys.exit(1)
