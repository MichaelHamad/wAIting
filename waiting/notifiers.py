"""Notification handlers for wait alerts."""

import subprocess
import sys
from pathlib import Path


class BellNotifier:
    """Notifier that plays a custom sound or falls back to terminal bell."""

    def __init__(self):
        # bell.wav is in the package root directory
        self.sound_file = Path(__file__).parent.parent / "bell.wav"

    def notify(self) -> None:
        """Play custom sound or fall back to terminal bell."""
        if self.sound_file.exists():
            # Run afplay in background, suppress output
            subprocess.Popen(
                ["afplay", str(self.sound_file)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            # Fallback to terminal bell if wav missing
            sys.stdout.write('\a')
            sys.stdout.flush()
