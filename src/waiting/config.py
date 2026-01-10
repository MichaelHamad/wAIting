"""Configuration management for the Waiting system."""

import json
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigError


@dataclass(frozen=True)
class Config:
    """Immutable configuration for the Waiting system."""

    grace_period: int
    volume: int
    audio: str

    def validate(self) -> tuple[bool, str | None]:
        """
        Validate configuration values.

        Returns:
            tuple[bool, str | None]: (is_valid, error_message)
        """
        if not isinstance(self.grace_period, int) or self.grace_period <= 0:
            return False, "grace_period must be a positive integer"

        if not isinstance(self.volume, int) or not (1 <= self.volume <= 100):
            return False, "volume must be an integer between 1 and 100"

        if not isinstance(self.audio, str):
            return False, "audio must be a string (path or 'default')"

        return True, None


DEFAULT_CONFIG = Config(grace_period=30, volume=100, audio="default")


def load_config(config_path: Path | None = None) -> Config:
    """
    Load configuration from file or create defaults.

    Args:
        config_path: Path to config file. Defaults to ~/.waiting.json

    Returns:
        Config: Loaded or default configuration

    Raises:
        ConfigError: If config file exists but is invalid
    """
    if config_path is None:
        config_path = Path.home() / ".waiting.json"

    # If config doesn't exist, create it with defaults
    if not config_path.exists():
        save_config(DEFAULT_CONFIG, config_path)
        return DEFAULT_CONFIG

    # Load existing config
    try:
        with open(config_path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ConfigError(f"Failed to load config from {config_path}: {e}")

    # Extract fields with defaults
    grace_period = data.get("grace_period", DEFAULT_CONFIG.grace_period)
    volume = data.get("volume", DEFAULT_CONFIG.volume)
    audio = data.get("audio", DEFAULT_CONFIG.audio)

    config = Config(
        grace_period=grace_period,
        volume=volume,
        audio=audio,
    )

    # Validate
    is_valid, error = config.validate()
    if not is_valid:
        raise ConfigError(f"Invalid configuration in {config_path}: {error}")

    return config


def save_config(config: Config, config_path: Path | None = None) -> None:
    """
    Save configuration to file.

    Args:
        config: Config object to save
        config_path: Path to config file. Defaults to ~/.waiting.json

    Raises:
        ConfigError: If save fails
    """
    if config_path is None:
        config_path = Path.home() / ".waiting.json"

    # Validate before saving
    is_valid, error = config.validate()
    if not is_valid:
        raise ConfigError(f"Cannot save invalid configuration: {error}")

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(
                {
                    "grace_period": config.grace_period,
                    "volume": config.volume,
                    "audio": config.audio,
                },
                f,
                indent=2,
            )
    except OSError as e:
        raise ConfigError(f"Failed to save config to {config_path}: {e}")
