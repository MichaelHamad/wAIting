"""Pytest configuration and fixtures for Waiting tests."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

# Clear audio player cache before each test to avoid cache pollution
@pytest.fixture(autouse=True)
def _clear_audio_cache():
    """Clear audio player cache before each test."""
    from waiting.audio import _clear_audio_player_cache
    _clear_audio_player_cache()
    yield
    _clear_audio_player_cache()


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    """
    Mock home directory for isolated tests.

    Args:
        tmp_path: Pytest temporary directory
        monkeypatch: Pytest monkeypatch fixture

    Yields:
        Path: Temporary home directory
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    yield tmp_path


@pytest.fixture
def tmp_config_dir(tmp_path):
    """
    Temporary directory for config files.

    Args:
        tmp_path: Pytest temporary directory

    Yields:
        Path: Temporary config directory
    """
    yield tmp_path


@pytest.fixture
def tmp_claude_dir(tmp_home):
    """
    Temporary ~/.claude directory.

    Args:
        tmp_home: Mocked home directory

    Yields:
        Path: Temporary .claude directory
    """
    claude_dir = tmp_home / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    yield claude_dir


@pytest.fixture
def tmp_settings(tmp_home):
    """
    Temporary settings.json file in mocked home.

    Args:
        tmp_home: Mocked home directory

    Yields:
        Path: Path to temporary settings.json
    """
    claude_dir = tmp_home / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    settings_path = claude_dir / "settings.json"
    settings_path.write_text(json.dumps({}))
    yield settings_path


@pytest.fixture
def tmp_config_file(tmp_home):
    """
    Temporary waiting.json config file.

    Args:
        tmp_home: Mocked home directory

    Yields:
        Path: Path to temporary waiting.json
    """
    config_path = tmp_home / ".waiting.json"
    config_path.write_text(
        json.dumps(
            {"grace_period": 30, "volume": 100, "audio": "default"}
        )
    )
    yield config_path


@pytest.fixture
def tmp_hooks_dir(tmp_home):
    """
    Temporary ~/.claude/hooks directory.

    Args:
        tmp_home: Mocked home directory

    Yields:
        Path: Path to temporary hooks directory
    """
    hooks_dir = tmp_home / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    yield hooks_dir
