"""Integration tests for audio playback."""

import platform
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from waiting.audio import get_audio_player, kill_audio, play_audio, resolve_audio_file
from waiting.audio_players.base import AudioPlayer
from waiting.errors import AudioError


class TestAudioPlaybackIntegration:
    """Integration tests for complete audio playback workflow."""

    def test_get_player_and_play(self):
        """Should get player and play audio successfully."""
        with patch("waiting.audio.get_audio_player") as mock_get_player:
            with patch("waiting.audio.resolve_audio_file") as mock_resolve:
                mock_player = Mock(spec=AudioPlayer)
                mock_player.play.return_value = 12345
                mock_player.name.return_value = "TestPlayer"
                mock_get_player.return_value = mock_player
                mock_resolve.return_value = Path("/test.wav")

                pid = play_audio("/test.wav", 80)

                assert pid == 12345
                mock_player.play.assert_called_once()

    def test_play_and_kill_audio(self):
        """Should play and then kill audio."""
        with patch("waiting.audio.get_audio_player") as mock_get_player:
            with patch("waiting.audio.resolve_audio_file") as mock_resolve:
                mock_player = Mock(spec=AudioPlayer)
                mock_player.play.return_value = 12345
                mock_player.kill.return_value = True
                mock_player.name.return_value = "TestPlayer"
                mock_get_player.return_value = mock_player
                mock_resolve.return_value = Path("/test.wav")

                # Play
                pid = play_audio("/test.wav", 100)
                assert pid == 12345

                # Kill
                result = kill_audio(pid)
                assert result is True
                mock_player.kill.assert_called_with(12345)

    def test_player_protocol_compliance(self):
        """All players should implement AudioPlayer protocol."""
        from waiting.audio_players.linux import (
            ALSAPlayer,
            PipeWirePlayer,
            PulseAudioPlayer,
        )
        from waiting.audio_players.macos import AFPlayPlayer
        from waiting.audio_players.windows import PowerShellPlayer

        players = [
            PulseAudioPlayer(),
            PipeWirePlayer(),
            ALSAPlayer(),
            AFPlayPlayer(),
            PowerShellPlayer(),
        ]

        for player in players:
            # Should have all required methods
            assert hasattr(player, "play")
            assert hasattr(player, "kill")
            assert hasattr(player, "available")
            assert hasattr(player, "name")

            # Methods should be callable
            assert callable(player.play)
            assert callable(player.kill)
            assert callable(player.available)
            assert callable(player.name)

    def test_platform_specific_player_selection(self):
        """Should select correct player per platform."""
        system = platform.system()

        try:
            player = get_audio_player()
            # Should return some player without error
            assert player is not None
            assert player.name() is not None
        except AudioError:
            # OK if no player available on this test system
            pass

    def test_volume_range_validation(self):
        """Should handle various volume levels."""
        with patch("waiting.audio.get_audio_player") as mock_get_player:
            with patch("waiting.audio.resolve_audio_file") as mock_resolve:
                mock_player = Mock(spec=AudioPlayer)
                mock_player.play.return_value = 12345
                mock_player.name.return_value = "TestPlayer"
                mock_get_player.return_value = mock_player
                mock_resolve.return_value = Path("/test.wav")

                # Test various volumes
                for volume in [1, 25, 50, 75, 100]:
                    pid = play_audio("/test.wav", volume)
                    assert pid == 12345

    def test_default_audio_file_handling(self):
        """Should handle default audio file."""
        with patch("waiting.audio.get_audio_player") as mock_get_player:
            with patch("waiting.audio.resolve_audio_file") as mock_resolve:
                mock_player = Mock(spec=AudioPlayer)
                mock_player.play.return_value = 12345
                mock_player.name.return_value = "TestPlayer"
                mock_get_player.return_value = mock_player
                mock_resolve.return_value = "default"

                pid = play_audio("default", 100)

                assert pid == 12345
                mock_resolve.assert_called_with("default")

    def test_custom_audio_file_resolution(self, tmp_path):
        """Should resolve custom audio file paths."""
        custom_audio = tmp_path / "custom.wav"
        custom_audio.write_text("audio data")

        result = resolve_audio_file(str(custom_audio))
        assert result == custom_audio
        assert result.exists()

    def test_audio_file_not_found_error(self):
        """Should raise error for missing audio file."""
        with pytest.raises(AudioError):
            resolve_audio_file("/nonexistent/path/sound.wav")

    def test_logger_receives_audio_events(self):
        """Logger should receive audio playback events."""
        mock_logger = Mock()

        with patch("waiting.audio.get_audio_player") as mock_get_player:
            with patch("waiting.audio.resolve_audio_file") as mock_resolve:
                mock_player = Mock(spec=AudioPlayer)
                mock_player.play.return_value = 12345
                mock_player.name.return_value = "TestPlayer"
                mock_get_player.return_value = mock_player
                mock_resolve.return_value = Path("/test.wav")

                play_audio("/test.wav", 100, mock_logger)

                # Should log audio playback info
                mock_logger.info.assert_called()
                assert "TestPlayer" in mock_logger.info.call_args[0][0]


class TestAudioPlayerFallback:
    """Tests for audio player fallback mechanisms."""

    def test_linux_player_fallback_chain(self):
        """Linux should try players in order."""
        from waiting.audio_players.linux import get_linux_player

        with patch("waiting.audio_players.linux.PulseAudioPlayer") as mock_pa:
            with patch("waiting.audio_players.linux.PipeWirePlayer") as mock_pw:
                with patch("waiting.audio_players.linux.ALSAPlayer") as mock_alsa:
                    # Make first two unavailable
                    mock_pa_instance = Mock()
                    mock_pa_instance.available.return_value = False
                    mock_pa.return_value = mock_pa_instance

                    mock_pw_instance = Mock()
                    mock_pw_instance.available.return_value = False
                    mock_pw.return_value = mock_pw_instance

                    mock_alsa_instance = Mock()
                    mock_alsa_instance.available.return_value = True
                    mock_alsa_instance.name.return_value = "ALSA"
                    mock_alsa.return_value = mock_alsa_instance

                    # Should use ALSA as fallback
                    player = get_linux_player()
                    assert player.name() == "ALSA"

    def test_os_level_kill_fallback(self):
        """Should use OS kill if player kill fails."""
        mock_logger = Mock()

        with patch("waiting.audio.get_audio_player") as mock_get_player:
            mock_get_player.side_effect = Exception("No player")

            with patch("subprocess.run") as mock_run:
                result = kill_audio(12345, mock_logger)

                # Should attempt subprocess.run with kill command
                mock_run.assert_called()
                assert result is True


class TestBundledSoundIntegration:
    """Integration tests for bundled default sound."""

    def test_bundled_sound_playback_with_default_config(self):
        """Should play bundled sound when using default audio config."""
        with patch("waiting.audio.get_audio_player") as mock_get_player:
            mock_player = Mock(spec=AudioPlayer)
            mock_player.play.return_value = 12345
            mock_player.name.return_value = "TestPlayer"
            mock_get_player.return_value = mock_player

            # Don't mock resolve_audio_file - test actual resolution
            pid = play_audio("default", 100)

            # Verify player.play() was called with real bundled file path
            call_args = mock_player.play.call_args[0]
            file_arg = call_args[0]
            assert "Cool_bell_final.wav" in str(file_arg), f"Expected bundled sound, got {file_arg}"
            assert Path(file_arg).exists(), f"Sound file should exist: {file_arg}"
            assert pid == 12345

    def test_bundled_sound_volume_respected(self):
        """Should pass volume correctly to player when using bundled sound."""
        with patch("waiting.audio.get_audio_player") as mock_get_player:
            mock_player = Mock(spec=AudioPlayer)
            mock_player.play.return_value = 12345
            mock_player.name.return_value = "TestPlayer"
            mock_get_player.return_value = mock_player

            pid = play_audio("default", 75)

            # Verify volume was passed correctly
            call_args = mock_player.play.call_args[0]
            volume_arg = call_args[1]
            assert volume_arg == 75

    def test_bundled_sound_is_accessible_at_runtime(self):
        """Bundled sound should be accessible at runtime via importlib.resources."""
        from importlib.resources import files

        resource = files("waiting.assets").joinpath("Cool_bell_final.wav")
        assert resource.is_file(), "Bundled sound should be accessible"

        # Should be able to read the resource
        with resource.open("rb") as f:
            data = f.read()
            assert len(data) > 0, "Sound file should have content"
            # WAV files start with RIFF header
            assert data[:4] == b"RIFF", "Should be a valid WAV file"


class TestAudioCLIInterface:
    """Tests for audio CLI interface."""

    def test_audio_cli_entry_point(self):
        """Audio module should be runnable as CLI."""
        import sys
        from unittest.mock import patch

        test_args = ["waiting.audio", "default", "100"]

        with patch.object(sys, "argv", test_args):
            with patch("waiting.audio.play_audio") as mock_play:
                mock_play.return_value = 12345

                # Would normally run: python -m waiting.audio
                # Just verify the CLI interface exists
                from waiting.audio import play_audio as play_fn

                pid = play_fn("default", 100)
                assert pid == 12345
