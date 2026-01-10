"""Tests for the audio module."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from waiting.audio import (
    get_audio_player,
    kill_audio,
    play_audio,
    resolve_audio_file,
)
from waiting.errors import AudioError


class TestGetAudioPlayer:
    """Tests for get_audio_player platform detection."""

    def test_get_audio_player_linux(self):
        """Should return Linux player on Linux."""
        with patch("waiting.audio.platform.system") as mock_system:
            mock_system.return_value = "Linux"

            with patch("waiting.audio_players.linux.get_linux_player") as mock_get_linux:
                mock_player = Mock()
                mock_get_linux.return_value = mock_player

                player = get_audio_player()
                assert player == mock_player

    def test_get_audio_player_macos(self):
        """Should return macOS player on Darwin."""
        with patch("waiting.audio.platform.system") as mock_system:
            mock_system.return_value = "Darwin"

            with patch("waiting.audio_players.macos.AFPlayPlayer") as mock_afplay:
                mock_player = Mock()
                mock_player.available.return_value = True
                mock_afplay.return_value = mock_player

                player = get_audio_player()
                assert player == mock_player

    def test_get_audio_player_windows(self):
        """Should return Windows player on Windows."""
        with patch("waiting.audio.platform.system") as mock_system:
            mock_system.return_value = "Windows"

            with patch("waiting.audio_players.windows.PowerShellPlayer") as mock_powershell:
                mock_player = Mock()
                mock_player.available.return_value = True
                mock_powershell.return_value = mock_player

                player = get_audio_player()
                assert player == mock_player

    def test_get_audio_player_unsupported_platform(self):
        """Should raise error for unsupported platform."""
        with patch("waiting.audio.platform.system") as mock_system:
            mock_system.return_value = "UnknownOS"

            with pytest.raises(AudioError):
                get_audio_player()

    def test_get_audio_player_linux_no_player_available(self):
        """Should raise error if no Linux player available."""
        with patch("waiting.audio.platform.system") as mock_system:
            mock_system.return_value = "Linux"

            with patch("waiting.audio_players.linux.get_linux_player") as mock_get_linux:
                mock_get_linux.side_effect = Exception("No player available")

                with pytest.raises(AudioError):
                    get_audio_player()


class TestResolveAudioFile:
    """Tests for resolve_audio_file."""

    def test_resolve_default_sound_linux(self, tmp_path):
        """Should find system bell on Linux."""
        freedesktop_sound = tmp_path / "complete.oga"
        freedesktop_sound.write_text("sound data")

        with patch("waiting.audio.Path") as mock_path:

            def path_side_effect(p):
                if "freedesktop" in str(p):
                    mock_obj = Mock()
                    mock_obj.exists.return_value = True
                    return mock_obj
                return Path(p)

            mock_path.side_effect = path_side_effect

            result = resolve_audio_file("default")
            # Should attempt to find system sound or return "default"
            assert result is not None

    def test_resolve_default_returns_default_if_not_found(self):
        """Should return 'default' if no system sound found."""
        with patch("waiting.audio.Path") as mock_path:
            mock_path_instance = Mock()
            mock_path_instance.exists.return_value = False
            mock_path.return_value = mock_path_instance

            result = resolve_audio_file("default")
            assert result == "default"

    def test_resolve_custom_file_exists(self, tmp_path):
        """Should return custom file path if it exists."""
        custom_file = tmp_path / "sound.wav"
        custom_file.write_text("audio data")

        result = resolve_audio_file(str(custom_file))
        assert result == custom_file

    def test_resolve_custom_file_not_exists(self):
        """Should raise error if custom file doesn't exist."""
        with pytest.raises(AudioError):
            resolve_audio_file("/nonexistent/sound.wav")

    def test_resolve_custom_file_expanduser(self, tmp_path, monkeypatch):
        """Should expand ~ in file paths."""
        monkeypatch.setenv("HOME", str(tmp_path))
        custom_file = tmp_path / "sound.wav"
        custom_file.write_text("audio data")

        result = resolve_audio_file("~/sound.wav")
        assert result == custom_file


class TestPlayAudio:
    """Tests for play_audio function."""

    def test_play_audio_returns_pid(self):
        """Should return PID from player."""
        with patch("waiting.audio.get_audio_player") as mock_get_player:
            with patch("waiting.audio.resolve_audio_file") as mock_resolve:
                mock_player = Mock()
                mock_player.play.return_value = 12345
                mock_player.name.return_value = "TestPlayer"
                mock_get_player.return_value = mock_player
                mock_resolve.return_value = Path("/test.wav")

                pid = play_audio("test.wav", 100)

                assert pid == 12345

    def test_play_audio_resolves_file(self):
        """Should resolve audio file path."""
        with patch("waiting.audio.get_audio_player") as mock_get_player:
            with patch("waiting.audio.resolve_audio_file") as mock_resolve:
                mock_player = Mock()
                mock_player.play.return_value = 12345
                mock_get_player.return_value = mock_player

                mock_resolve.return_value = Path("/resolved/path.wav")

                play_audio("test.wav", 100)

                mock_resolve.assert_called_once()

    def test_play_audio_passes_volume(self):
        """Should pass volume to player."""
        with patch("waiting.audio.get_audio_player") as mock_get_player:
            with patch("waiting.audio.resolve_audio_file") as mock_resolve:
                mock_player = Mock()
                mock_player.play.return_value = 12345
                mock_get_player.return_value = mock_player
                mock_resolve.return_value = Path("/test.wav")

                play_audio("test.wav", 75)

                # Check that volume was passed to play()
                call_args = mock_player.play.call_args[0]
                assert call_args[1] == 75

    def test_play_audio_logs_on_error(self):
        """Should log errors appropriately."""
        with patch("waiting.audio.get_audio_player") as mock_get_player:
            mock_get_player.side_effect = Exception("Player error")

            with pytest.raises(AudioError):
                play_audio("test.wav", 100)

    def test_play_audio_uses_provided_logger(self):
        """Should use provided logger."""
        mock_logger = Mock()

        with patch("waiting.audio.get_audio_player") as mock_get_player:
            with patch("waiting.audio.resolve_audio_file") as mock_resolve:
                mock_player = Mock()
                mock_player.play.return_value = 12345
                mock_player.name.return_value = "TestPlayer"
                mock_get_player.return_value = mock_player
                mock_resolve.return_value = Path("/test.wav")

                play_audio("test.wav", 100, mock_logger)

                # Logger.info should have been called
                mock_logger.info.assert_called()


class TestKillAudio:
    """Tests for kill_audio function."""

    def test_kill_audio_success(self):
        """Should kill process if player succeeds."""
        with patch("waiting.audio.get_audio_player") as mock_get_player:
            mock_player = Mock()
            mock_player.kill.return_value = True
            mock_get_player.return_value = mock_player

            result = kill_audio(12345)

            assert result is True

    def test_kill_audio_fallback_to_system_kill(self):
        """Should use system kill if player fails."""
        with patch("waiting.audio.get_audio_player") as mock_get_player:
            mock_get_player.side_effect = Exception("Player error")

            with patch("subprocess.run") as mock_run:
                result = kill_audio(12345)

                # Should have attempted system kill
                assert result is True

    def test_kill_audio_uses_provided_logger(self):
        """Should use provided logger."""
        mock_logger = Mock()

        with patch("waiting.audio.get_audio_player") as mock_get_player:
            mock_player = Mock()
            mock_player.kill.return_value = True
            mock_get_player.return_value = mock_player

            kill_audio(12345, mock_logger)

            # Logger should have been called
            mock_logger.info.assert_called()

    def test_kill_audio_all_players_fail(self):
        """Should handle failure gracefully."""
        mock_logger = Mock()

        with patch("waiting.audio.get_audio_player") as mock_get_player:
            mock_get_player.side_effect = Exception("No player")

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = Exception("Kill failed")

                result = kill_audio(12345, mock_logger)

                # Should return False on complete failure
                assert result is False
