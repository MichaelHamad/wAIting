"""Command-line interface for the Waiting notification system."""

import sys
from logging import Logger
from pathlib import Path

from .config import load_config
from .hooks.manager import HookManager
from .logging import setup_logging


class CLI:
    """Command-line interface for installing, removing, and managing Waiting."""

    def __init__(self, config_path: Path | None = None) -> None:
        """
        Initialize CLI with optional custom config path.

        Args:
            config_path: Path to config file. Defaults to ~/.waiting.json
        """
        self.config_path = config_path or (Path.home() / ".waiting.json")
        self.logger: Logger = setup_logging()

    def enable(self) -> int:
        """
        Enable waiting notifications (install hooks).

        Loads configuration, installs hooks, and provides next steps.

        Returns:
            int: 0 on success, 1 on error
        """
        try:
            config = load_config(self.config_path)
            hook_manager = HookManager(self.logger)
            hook_manager.install(config)

            print("✓ Waiting hooks installed to ~/.claude/hooks/")
            print("✓ Configuration: ~/.waiting.json")
            print("")
            print("Next steps:")
            print("  1. Restart Claude Code for hooks to take effect")
            print("  2. Trigger a permission dialog to test")

            return 0

        except Exception as e:
            print(f"✗ Error: {e}", file=sys.stderr)
            self.logger.error(f"Enable failed: {e}", exc_info=True)
            return 1

    def disable(self) -> int:
        """
        Disable waiting notifications (remove hooks).

        Removes hooks but preserves configuration file.

        Returns:
            int: 0 on success, 1 on error
        """
        try:
            hook_manager = HookManager(self.logger)
            hook_manager.remove()

            print("✓ Waiting hooks removed")
            print("✓ Configuration file preserved at ~/.waiting.json")

            return 0

        except Exception as e:
            print(f"✗ Error: {e}", file=sys.stderr)
            self.logger.error(f"Disable failed: {e}", exc_info=True)
            return 1

    def status(self) -> int:
        """
        Show current configuration and hook installation status.

        Displays grace period, volume, audio settings and hook status.

        Returns:
            int: 0 on success, 1 on error
        """
        try:
            config = load_config(self.config_path)
            hook_manager = HookManager(self.logger)
            is_installed = hook_manager.is_installed()

            print("Waiting - Audio Notification System")
            print("=" * 40)
            print(f"Status:         {'ENABLED' if is_installed else 'DISABLED'}")
            print(f"Grace Period:   {config.grace_period}s")
            print(f"Volume:         {config.volume}%")
            print(f"Audio:          {config.audio}")
            print(f"Config File:    {self.config_path}")
            print("")

            if is_installed:
                print("Hooks installed:")
                hook_paths = hook_manager.get_hook_paths()
                for hook_name, hook_path in hook_paths.items():
                    exists = "✓" if hook_path.exists() else "✗"
                    print(f"  {exists} {hook_name}")
            else:
                print("No hooks installed. Run 'waiting' to enable.")

            return 0

        except Exception as e:
            print(f"✗ Error: {e}", file=sys.stderr)
            self.logger.error(f"Status failed: {e}", exc_info=True)
            return 1

    def show_help(self) -> int:
        """
        Display help message with usage examples.

        Returns:
            int: 0 (always succeeds)
        """
        print(
            """
Waiting - Audio notification for Claude Code permission dialogs

Usage:
  waiting              Enable notifications (install hooks)
  waiting disable      Disable notifications (remove hooks)
  waiting status       Show current configuration
  waiting --help       Show this message

Configuration:
  Edit ~/.waiting.json to customize:
  - grace_period: seconds to wait before bell (default: 30)
  - volume: bell volume 1-100 (default: 100)
  - audio: path to audio file or "default" (default: "default")

More info: https://github.com/anthropics/waiting
        """
        )
        return 0
