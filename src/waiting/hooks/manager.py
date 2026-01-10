"""Hook installation and management for Waiting system."""

import shutil
from pathlib import Path

from ..config import Config
from ..errors import HookError
from ..logging import setup_logging
from ..settings import (
    get_hook_paths,
    is_installed,
    load_settings,
    merge_hooks_into_settings,
    remove_hooks_from_settings,
    save_settings,
)


class HookManager:
    """Manages hook installation, removal, and lifecycle."""

    def __init__(self, logger=None):
        """Initialize HookManager."""
        self.logger = logger or setup_logging()
        self.hooks_source_dir = Path(__file__).parent / "scripts"
        self.hooks_install_dir = Path.home() / ".claude" / "hooks"
        self.settings_path = Path.home() / ".claude" / "settings.json"

    def install(self, config: Config | None = None) -> None:
        """
        Install hook scripts and register them in settings.json.

        Args:
            config: Config object (optional, for logging)

        Raises:
            HookError: If installation fails
        """
        try:
            self.logger.info("Installing Waiting hooks")

            # Create hooks directory if needed
            self.hooks_install_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Created hooks directory: {self.hooks_install_dir}")

            # Copy hook scripts from project to ~/.claude/hooks/
            self._copy_hook_scripts()

            # Load settings and merge hooks
            settings = load_settings(self.settings_path)
            settings = merge_hooks_into_settings(settings)

            # Save updated settings
            save_settings(settings, self.settings_path)
            self.logger.info("Hooks registered in settings.json")

            self.logger.info("Hook installation complete")

        except Exception as e:
            self.logger.error(f"Hook installation failed: {e}")
            raise HookError(f"Failed to install hooks: {e}") from e

    def remove(self) -> None:
        """
        Remove hook scripts and unregister from settings.json.

        Raises:
            HookError: If removal fails
        """
        try:
            self.logger.info("Removing Waiting hooks")

            # Remove hook scripts from ~/.claude/hooks/
            self._remove_hook_scripts()

            # Load settings and remove hooks
            settings = load_settings(self.settings_path)
            settings = remove_hooks_from_settings(settings)

            # Save updated settings
            save_settings(settings, self.settings_path)
            self.logger.info("Hooks unregistered from settings.json")

            self.logger.info("Hook removal complete")

        except Exception as e:
            self.logger.error(f"Hook removal failed: {e}")
            raise HookError(f"Failed to remove hooks: {e}") from e

    def is_installed(self) -> bool:
        """
        Check if hooks are currently installed and registered.

        Returns:
            bool: True if hooks are installed and registered, False otherwise
        """
        try:
            # Check settings registration
            return is_installed(self.settings_path)
        except Exception as e:
            self.logger.warning(f"Error checking hook installation: {e}")
            return False

    def get_hook_paths(self) -> dict[str, Path]:
        """
        Get paths to installed hook scripts.

        Returns:
            dict: Mapping of hook names to installed script paths
        """
        return get_hook_paths()

    def _copy_hook_scripts(self) -> None:
        """Copy hook scripts from project to ~/.claude/hooks/."""
        hook_files = [
            "waiting-notify-permission.sh",
            "waiting-activity-tooluse.sh",
        ]

        for hook_file in hook_files:
            source = self.hooks_source_dir / hook_file
            dest = self.hooks_install_dir / hook_file

            if not source.exists():
                raise HookError(f"Hook script not found: {source}")

            shutil.copy2(source, dest)
            self.logger.debug(f"Copied hook script: {hook_file}")

            # Make executable
            dest.chmod(0o755)
            self.logger.debug(f"Made executable: {hook_file}")

    def _remove_hook_scripts(self) -> None:
        """Remove hook scripts from ~/.claude/hooks/."""
        hook_files = [
            "waiting-notify-permission.sh",
            "waiting-activity-tooluse.sh",
        ]

        for hook_file in hook_files:
            hook_path = self.hooks_install_dir / hook_file

            if hook_path.exists():
                try:
                    hook_path.unlink()
                    self.logger.debug(f"Removed hook script: {hook_file}")
                except OSError as e:
                    self.logger.warning(f"Failed to remove {hook_file}: {e}")
