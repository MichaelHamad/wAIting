"""Tests for the config module."""

import json
from pathlib import Path

import pytest

from waiting.config import Config, DEFAULT_CONFIG, load_config, save_config
from waiting.errors import ConfigError


class TestConfig:
    """Tests for Config dataclass."""

    def test_default_config_values(self):
        """Config should have sensible defaults."""
        config = Config(grace_period=30, volume=100, audio="default")
        assert config.grace_period == 30
        assert config.volume == 100
        assert config.audio == "default"

    def test_config_is_frozen(self):
        """Config should be immutable."""
        config = Config(grace_period=30, volume=100, audio="default")
        with pytest.raises(AttributeError):
            config.grace_period = 60

    def test_validate_grace_period_positive(self):
        """Grace period must be positive."""
        config = Config(grace_period=-1, volume=100, audio="default")
        is_valid, error = config.validate()
        assert not is_valid
        assert "positive" in error.lower()

    def test_validate_grace_period_zero(self):
        """Grace period cannot be zero."""
        config = Config(grace_period=0, volume=100, audio="default")
        is_valid, error = config.validate()
        assert not is_valid

    def test_validate_volume_too_low(self):
        """Volume must be at least 1."""
        config = Config(grace_period=30, volume=0, audio="default")
        is_valid, error = config.validate()
        assert not is_valid
        assert "1 and 100" in error

    def test_validate_volume_too_high(self):
        """Volume must not exceed 100."""
        config = Config(grace_period=30, volume=101, audio="default")
        is_valid, error = config.validate()
        assert not is_valid
        assert "1 and 100" in error

    def test_validate_volume_valid_range(self):
        """Volume between 1-100 should pass."""
        for vol in [1, 50, 100]:
            config = Config(grace_period=30, volume=vol, audio="default")
            is_valid, error = config.validate()
            assert is_valid
            assert error is None

    def test_validate_grace_period_valid(self):
        """Grace period should validate for positive integers."""
        config = Config(grace_period=45, volume=100, audio="default")
        is_valid, error = config.validate()
        assert is_valid
        assert error is None

    def test_validate_audio_custom_path(self):
        """Audio can be a custom file path."""
        config = Config(grace_period=30, volume=100, audio="/path/to/sound.wav")
        is_valid, error = config.validate()
        assert is_valid
        assert error is None


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_missing_config_creates_defaults(self, tmp_home):
        """Missing config should create defaults."""
        config_path = tmp_home / ".waiting.json"
        assert not config_path.exists()

        config = load_config(config_path)

        assert config.grace_period == DEFAULT_CONFIG.grace_period
        assert config.volume == DEFAULT_CONFIG.volume
        assert config.audio == DEFAULT_CONFIG.audio
        assert config_path.exists()

    def test_load_existing_config(self, tmp_config_file):
        """Should load existing config correctly."""
        config = load_config(tmp_config_file)

        assert config.grace_period == 30
        assert config.volume == 100
        assert config.audio == "default"

    def test_load_custom_config_values(self, tmp_home):
        """Should load custom config values."""
        config_path = tmp_home / ".waiting.json"
        config_path.write_text(
            json.dumps(
                {"grace_period": 45, "volume": 75, "audio": "/custom/sound.wav"}
            )
        )

        config = load_config(config_path)

        assert config.grace_period == 45
        assert config.volume == 75
        assert config.audio == "/custom/sound.wav"

    def test_load_invalid_json_raises_error(self, tmp_home):
        """Invalid JSON should raise ConfigError."""
        config_path = tmp_home / ".waiting.json"
        config_path.write_text("{ invalid json }")

        with pytest.raises(ConfigError):
            load_config(config_path)

    def test_load_invalid_config_values_raise_error(self, tmp_home):
        """Invalid config values should raise ConfigError."""
        config_path = tmp_home / ".waiting.json"
        config_path.write_text(json.dumps({"grace_period": -5}))

        with pytest.raises(ConfigError):
            load_config(config_path)

    def test_load_config_with_defaults_path(self, tmp_home):
        """Should use ~/.waiting.json as default path."""
        config_path = tmp_home / ".waiting.json"
        config_path.write_text(json.dumps({"grace_period": 60}))

        config = load_config()

        # Note: This uses the mocked home from tmp_home fixture
        # In actual test, HOME env var is mocked by tmp_home fixture
        assert config.grace_period == 60

    def test_load_config_partial_data(self, tmp_home):
        """Should use defaults for missing fields."""
        config_path = tmp_home / ".waiting.json"
        config_path.write_text(json.dumps({"grace_period": 45}))

        config = load_config(config_path)

        assert config.grace_period == 45
        assert config.volume == 100  # default
        assert config.audio == "default"  # default


class TestSaveConfig:
    """Tests for save_config function."""

    def test_save_config_creates_file(self, tmp_home):
        """Should create config file."""
        config_path = tmp_home / ".waiting.json"
        config = Config(grace_period=30, volume=80, audio="default")

        save_config(config, config_path)

        assert config_path.exists()
        data = json.loads(config_path.read_text())
        assert data["grace_period"] == 30
        assert data["volume"] == 80
        assert data["audio"] == "default"

    def test_save_config_overwrites_existing(self, tmp_config_file):
        """Should overwrite existing config."""
        config = Config(grace_period=45, volume=75, audio="/new/sound.wav")

        save_config(config, tmp_config_file)

        data = json.loads(tmp_config_file.read_text())
        assert data["grace_period"] == 45
        assert data["volume"] == 75
        assert data["audio"] == "/new/sound.wav"

    def test_save_invalid_config_raises_error(self, tmp_home):
        """Should not save invalid config."""
        config_path = tmp_home / ".waiting.json"
        config = Config(grace_period=-1, volume=100, audio="default")

        with pytest.raises(ConfigError):
            save_config(config, config_path)

    def test_save_config_creates_parent_dirs(self, tmp_path):
        """Should create parent directories if needed."""
        config_path = tmp_path / "nested" / "dir" / ".waiting.json"
        config = Config(grace_period=30, volume=100, audio="default")

        save_config(config, config_path)

        assert config_path.exists()
        assert config_path.parent.exists()

    def test_save_and_load_roundtrip(self, tmp_home):
        """Saved config should match loaded config."""
        config_path = tmp_home / ".waiting.json"
        original = Config(grace_period=45, volume=80, audio="/test/sound.wav")

        save_config(original, config_path)
        loaded = load_config(config_path)

        assert loaded.grace_period == original.grace_period
        assert loaded.volume == original.volume
        assert loaded.audio == original.audio

    def test_save_config_json_formatting(self, tmp_home):
        """Saved config should be valid, readable JSON."""
        config_path = tmp_home / ".waiting.json"
        config = Config(grace_period=30, volume=100, audio="default")

        save_config(config, config_path)

        content = config_path.read_text()
        # Should be parseable
        data = json.loads(content)
        # Should have proper formatting (indentation)
        assert "\n" in content
