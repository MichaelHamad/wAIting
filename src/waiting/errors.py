"""Custom exception types for the Waiting notification system."""


class WaitingError(Exception):
    """Base exception for all Waiting system errors."""

    pass


class ConfigError(WaitingError):
    """Raised when configuration loading, validation, or saving fails."""

    pass


class HookError(WaitingError):
    """Raised when hook installation, removal, or execution fails."""

    pass


class AudioError(WaitingError):
    """Raised when audio playback or player selection fails."""

    pass


class SettingsError(WaitingError):
    """Raised when settings.json loading, merging, or saving fails."""

    pass
