"""Performance benchmarks for Waiting system components."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from waiting.audio import get_audio_player, play_audio, resolve_audio_file
from waiting.cli import CLI
from waiting.config import Config, load_config, save_config
from waiting.logging import setup_logging
from waiting.settings import load_settings, save_settings


class TestAudioPlayerPerformance:
    """Profile audio player initialization and operation."""

    @patch("waiting.audio.platform.system")
    def test_get_audio_player_initialization_time(self, mock_system):
        """Measure time to initialize audio player."""
        mock_system.return_value = "Darwin"
        with patch("waiting.audio_players.macos.AFPlayPlayer") as mock_player_class:
            mock_player = MagicMock()
            mock_player.available.return_value = True
            mock_player_class.return_value = mock_player

            start = time.perf_counter()
            player = get_audio_player()
            elapsed = time.perf_counter() - start

            assert player is not None
            # Audio player initialization should be sub-millisecond
            assert elapsed < 0.01, f"Audio player init took {elapsed:.4f}s, expected <0.01s"

    @patch("waiting.audio.platform.system")
    def test_get_audio_player_availability_check_time(self, mock_system):
        """Measure time to check audio player availability."""
        mock_system.return_value = "Darwin"
        with patch("waiting.audio_players.macos.AFPlayPlayer") as mock_player_class:
            mock_player = MagicMock()
            mock_player.available.return_value = True
            mock_player_class.return_value = mock_player

            player = get_audio_player()

            start = time.perf_counter()
            available = player.available()
            elapsed = time.perf_counter() - start

            assert isinstance(available, bool)
            # Availability check should be sub-millisecond
            assert elapsed < 0.005, f"Availability check took {elapsed:.4f}s, expected <0.005s"

    @patch("waiting.audio.get_audio_player")
    def test_play_audio_startup_latency(self, mock_get_player):
        """Measure audio playback startup latency."""
        mock_player = MagicMock()
        mock_player.play.return_value = 12345
        mock_player.name.return_value = "TestPlayer"
        mock_get_player.return_value = mock_player

        with patch("waiting.audio.resolve_audio_file") as mock_resolve:
            mock_resolve.return_value = "/tmp/test.wav"

            start = time.perf_counter()
            pid = play_audio("/tmp/test.wav", 100, setup_logging())
            elapsed = time.perf_counter() - start

            assert pid == 12345
            # Play startup (excluding subprocess) should be sub-millisecond
            assert elapsed < 0.01, f"Play audio startup took {elapsed:.4f}s, expected <0.01s"

    @patch("waiting.audio.get_audio_player")
    def test_resolve_audio_file_performance(self, mock_get_player):
        """Measure audio file resolution performance."""
        with patch("pathlib.Path.exists", return_value=True):
            start = time.perf_counter()
            result = resolve_audio_file("/tmp/test.wav")
            elapsed = time.perf_counter() - start

            assert result is not None
            # File resolution should be very fast
            assert elapsed < 0.005, f"File resolution took {elapsed:.4f}s, expected <0.005s"

    @patch("waiting.audio.platform.system")
    def test_audio_player_name_performance(self, mock_system):
        """Measure audio player name() method performance."""
        mock_system.return_value = "Darwin"
        with patch("waiting.audio_players.macos.AFPlayPlayer") as mock_player_class:
            mock_player = MagicMock()
            mock_player.available.return_value = True
            mock_player.name.return_value = "TestPlayer"
            mock_player_class.return_value = mock_player

            player = get_audio_player()

            start = time.perf_counter()
            name = player.name()
            elapsed = time.perf_counter() - start

            assert isinstance(name, str)
            assert len(name) > 0
            # Name retrieval should be sub-microsecond
            assert elapsed < 0.001, f"Name retrieval took {elapsed:.4f}s, expected <0.001s"


class TestConfigLoadingPerformance:
    """Profile configuration loading performance."""

    def test_config_load_time(self, tmp_config_dir):
        """Measure time to load configuration from disk."""
        config_path = tmp_config_dir / ".waiting.json"
        config = Config(grace_period=30, volume=100, audio="default")
        save_config(config, config_path)

        start = time.perf_counter()
        loaded = load_config(config_path)
        elapsed = time.perf_counter() - start

        assert loaded.grace_period == 30
        assert loaded.volume == 100
        # Config load should be sub-millisecond
        assert elapsed < 0.01, f"Config load took {elapsed:.4f}s, expected <0.01s"

    def test_config_save_time(self, tmp_config_dir):
        """Measure time to save configuration to disk."""
        config = Config(grace_period=30, volume=100, audio="default")
        config_path = tmp_config_dir / ".waiting.json"

        start = time.perf_counter()
        save_config(config, config_path)
        elapsed = time.perf_counter() - start

        assert config_path.exists()
        # Config save should be sub-millisecond
        assert elapsed < 0.01, f"Config save took {elapsed:.4f}s, expected <0.01s"

    def test_config_validation_time(self):
        """Measure configuration validation performance."""
        config = Config(grace_period=30, volume=100, audio="default")

        start = time.perf_counter()
        is_valid, error = config.validate()
        elapsed = time.perf_counter() - start

        assert is_valid
        assert error is None
        # Validation should be sub-microsecond
        assert elapsed < 0.001, f"Validation took {elapsed:.4f}s, expected <0.001s"

    def test_settings_load_time(self, tmp_home):
        """Measure time to load Claude settings from disk."""
        settings_path = tmp_home / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps({"key": "value"}))

        start = time.perf_counter()
        settings = load_settings(settings_path)
        elapsed = time.perf_counter() - start

        assert settings["key"] == "value"
        # Settings load should be sub-millisecond
        assert elapsed < 0.01, f"Settings load took {elapsed:.4f}s, expected <0.01s"

    def test_settings_save_time(self, tmp_home):
        """Measure time to save Claude settings to disk."""
        settings_path = tmp_home / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings = {"key": "value"}

        start = time.perf_counter()
        save_settings(settings, settings_path)
        elapsed = time.perf_counter() - start

        assert settings_path.exists()
        # Settings save should be sub-millisecond
        assert elapsed < 0.01, f"Settings save took {elapsed:.4f}s, expected <0.01s"


class TestCLIPerformance:
    """Profile CLI command execution time."""

    def test_cli_initialization_time(self):
        """Measure time to initialize CLI."""
        start = time.perf_counter()
        cli = CLI()
        elapsed = time.perf_counter() - start

        assert cli is not None
        # CLI init should include logging setup and be sub-millisecond
        assert elapsed < 0.05, f"CLI init took {elapsed:.4f}s, expected <0.05s"

    def test_help_command_time(self, capsys):
        """Measure time to display help message."""
        cli = CLI()

        start = time.perf_counter()
        result = cli.show_help()
        elapsed = time.perf_counter() - start

        assert result == 0
        # Help command should be very fast
        assert elapsed < 0.01, f"Help command took {elapsed:.4f}s, expected <0.01s"

    @patch("waiting.cli.HookManager")
    @patch("waiting.cli.load_config")
    def test_status_command_time(self, mock_load_config, mock_hook_manager, capsys):
        """Measure time to show status."""
        mock_load_config.return_value = Config(grace_period=30, volume=100, audio="default")
        mock_manager = MagicMock()
        mock_manager.is_installed.return_value = True
        mock_manager.get_hook_paths.return_value = {}
        mock_hook_manager.return_value = mock_manager

        cli = CLI()

        start = time.perf_counter()
        result = cli.status()
        elapsed = time.perf_counter() - start

        assert result == 0
        # Status command should be sub-10ms
        assert elapsed < 0.01, f"Status command took {elapsed:.4f}s, expected <0.01s"


class TestLoggingPerformance:
    """Profile logging system performance."""

    def test_logging_setup_time(self, tmp_home):
        """Measure time to set up logging system."""
        start = time.perf_counter()
        logger = setup_logging()
        elapsed = time.perf_counter() - start

        assert logger is not None
        # Logging setup should be fast (includes file I/O)
        assert elapsed < 0.05, f"Logging setup took {elapsed:.4f}s, expected <0.05s"

    def test_log_message_write_time(self, tmp_home):
        """Measure time to write a log message."""
        logger = setup_logging()

        start = time.perf_counter()
        logger.info("Test message")
        elapsed = time.perf_counter() - start

        # Logging a message should be sub-millisecond
        assert elapsed < 0.01, f"Log message write took {elapsed:.4f}s, expected <0.01s"


class TestMemoryUsage:
    """Monitor memory usage patterns during operations."""

    @patch("waiting.audio.platform.system")
    def test_audio_player_memory_footprint(self, mock_system):
        """Verify audio player doesn't have excessive memory overhead."""
        import sys

        mock_system.return_value = "Darwin"
        with patch("waiting.audio_players.macos.AFPlayPlayer") as mock_player_class:
            mock_player = MagicMock()
            mock_player.available.return_value = True
            mock_player_class.return_value = mock_player

            player = get_audio_player()
            # Check that player object is not excessively large
            player_size = sys.getsizeof(player)

            # Player should be lightweight (typically < 500 bytes for object overhead)
            assert player_size < 5000, f"Player object size {player_size} bytes seems excessive"

    def test_config_memory_footprint(self):
        """Verify config object has minimal memory overhead."""
        import sys

        config = Config(grace_period=30, volume=100, audio="default")
        config_size = sys.getsizeof(config)

        # Config should be very small (typically < 200 bytes)
        assert config_size < 1000, f"Config object size {config_size} bytes seems excessive"


class TestEndToEndLatency:
    """Measure end-to-end latency for critical paths."""

    @patch("waiting.audio.get_audio_player")
    def test_audio_playback_pipeline_latency(self, mock_get_player, tmp_config_dir):
        """Measure total latency for audio playback pipeline."""
        mock_player = MagicMock()
        mock_player.play.return_value = 12345
        mock_player.name.return_value = "TestPlayer"
        mock_get_player.return_value = mock_player

        with patch("waiting.audio.resolve_audio_file") as mock_resolve:
            mock_resolve.return_value = "/tmp/test.wav"

            start = time.perf_counter()
            # Load config
            config = Config(grace_period=30, volume=100, audio="default")
            # Play audio
            pid = play_audio("default", config.volume, setup_logging())
            elapsed = time.perf_counter() - start

            assert pid == 12345
            # Total latency should be sub-10ms
            assert elapsed < 0.01, f"Audio pipeline took {elapsed:.4f}s, expected <0.01s"

    @patch("waiting.cli.HookManager")
    @patch("waiting.cli.load_config")
    def test_cli_status_pipeline_latency(self, mock_load_config, mock_hook_manager):
        """Measure end-to-end latency for status command."""
        mock_load_config.return_value = Config(grace_period=30, volume=100, audio="default")
        mock_manager = MagicMock()
        mock_manager.is_installed.return_value = True
        mock_manager.get_hook_paths.return_value = {}
        mock_hook_manager.return_value = mock_manager

        start = time.perf_counter()
        cli = CLI()
        result = cli.status()
        elapsed = time.perf_counter() - start

        assert result == 0
        # Full pipeline should be sub-10ms
        assert elapsed < 0.01, f"CLI pipeline took {elapsed:.4f}s, expected <0.01s"


class TestCachingOpportunities:
    """Identify and verify caching opportunities."""

    @patch("waiting.audio.platform.system")
    def test_repeated_audio_player_calls(self, mock_system):
        """Verify repeated player retrieval is efficient."""
        mock_system.return_value = "Darwin"
        with patch("waiting.audio_players.macos.AFPlayPlayer") as mock_player_class:
            mock_player = MagicMock()
            mock_player.available.return_value = True
            mock_player_class.return_value = mock_player

            # Get player multiple times - should be fast due to minimal init
            times = []
            for _ in range(5):
                start = time.perf_counter()
                player = get_audio_player()
                elapsed = time.perf_counter() - start
                times.append(elapsed)

            # Each call should be consistently fast
            avg_time = sum(times) / len(times)
            assert avg_time < 0.005, f"Average player init took {avg_time:.4f}s, expected <0.005s"

    def test_repeated_config_loads(self, tmp_config_dir):
        """Verify repeated config loads are efficient."""
        config_path = tmp_config_dir / ".waiting.json"
        config = Config(grace_period=30, volume=100, audio="default")
        save_config(config, config_path)

        times = []
        for _ in range(5):
            start = time.perf_counter()
            loaded = load_config(config_path)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        assert avg_time < 0.005, f"Average config load took {avg_time:.4f}s, expected <0.005s"

    def test_repeated_settings_loads(self, tmp_home):
        """Verify repeated settings loads are efficient."""
        settings_path = tmp_home / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps({"key": "value"}))

        times = []
        for _ in range(5):
            start = time.perf_counter()
            settings = load_settings(settings_path)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        assert avg_time < 0.005, f"Average settings load took {avg_time:.4f}s, expected <0.005s"
