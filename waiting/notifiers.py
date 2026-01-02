"""Notification handlers for wait alerts."""

import sys


class BellNotifier:
    """Notifier that emits a terminal bell character."""

    def notify(self) -> None:
        """Send a terminal bell."""
        sys.stdout.write('\a')
        sys.stdout.flush()
