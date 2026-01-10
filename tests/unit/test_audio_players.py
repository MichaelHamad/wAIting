"""Tests for audio player implementations."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from waiting.audio_players.base import AudioPlayer
from waiting.audio_players.linux import (
    ALSAPlayer,
    PipeWirePlayer,
    PulseAudioPlayer,
    get_linux_player,
)
from waiting.audio_players.macos import AFPlayPlayer
from waiting.audio_players.windows import PowerShellPlayer
from waiting.errors import AudioError


class TestPulseAudioPlayer:
    """Tests for PulseAudio player."""

    def test_pulseaudio_name(self):
        """Should return correct player name."""
        player = PulseAudioPlayer()
        assert player.name() == "PulseAudio"

    def test_pulseaudio_available_true(self):
        """Should return True if paplay is available."""
        with patch("waiting.audio_players.linux.which") as mock_which:
            mock_which.return_value = "/usr/bin/paplay"
            player = PulseAudioPlayer()
            assert player.available() is True

    def test_pulseaudio_available_false(self):
        """Should return False if paplay not available."""
        with patch("waiting.audio_players.linux.which") as mock_which:
            mock_which.return_value = None
            player = PulseAudioPlayer()
            assert player.available() is False

    def test_pulseaudio_play_returns_pid(self):
        """Play should return process ID."""
        with patch("waiting.audio_players.linux.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = PulseAudioPlayer()
            pid = player.play("test.wav", 100)

            assert pid == 12345

    def test_pulseaudio_play_custom_file(self):
        """Play should include custom file in command."""
        with patch("waiting.audio_players.linux.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = PulseAudioPlayer()
            player.play("/path/to/sound.wav", 80)

            call_args = mock_popen.call_args[0][0]
            assert "/path/to/sound.wav" in call_args

    def test_pulseaudio_play_default_sound(self):
        """Play should use alert role for default sound."""
        with patch("waiting.audio_players.linux.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = PulseAudioPlayer()
            player.play("default", 100)

            call_args = mock_popen.call_args[0][0]
            assert "media.role=alert" in call_args

    def test_pulseaudio_volume_conversion(self):
        """Volume should be converted correctly."""
        with patch("waiting.audio_players.linux.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = PulseAudioPlayer()
            player.play("test.wav", 50)

            call_args = mock_popen.call_args[0][0]
            # Volume 50% = 32768 (50% of 65536)
            assert "--volume" in call_args

    def test_pulseaudio_kill(self):
        """Kill should execute kill command."""
        with patch("waiting.audio_players.linux.subprocess.run") as mock_run:
            player = PulseAudioPlayer()
            result = player.kill(12345)

            assert result is True
            mock_run.assert_called()


class TestPipeWirePlayer:
    """Tests for PipeWire player."""

    def test_pipewire_name(self):
        """Should return correct player name."""
        player = PipeWirePlayer()
        assert player.name() == "PipeWire"

    def test_pipewire_available_true(self):
        """Should return True if pw-play is available."""
        with patch("waiting.audio_players.linux.which") as mock_which:
            mock_which.return_value = "/usr/bin/pw-play"
            player = PipeWirePlayer()
            assert player.available() is True

    def test_pipewire_available_false(self):
        """Should return False if pw-play not available."""
        with patch("waiting.audio_players.linux.which") as mock_which:
            mock_which.return_value = None
            player = PipeWirePlayer()
            assert player.available() is False

    def test_pipewire_play_returns_pid(self):
        """Play should return process ID."""
        with patch("waiting.audio_players.linux.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = PipeWirePlayer()
            pid = player.play("test.wav", 100)

            assert pid == 12345


class TestALSAPlayer:
    """Tests for ALSA player."""

    def test_alsa_name(self):
        """Should return correct player name."""
        player = ALSAPlayer()
        assert player.name() == "ALSA"

    def test_alsa_available_true(self):
        """Should return True if aplay is available."""
        with patch("waiting.audio_players.linux.which") as mock_which:
            mock_which.return_value = "/usr/bin/aplay"
            player = ALSAPlayer()
            assert player.available() is True

    def test_alsa_available_false(self):
        """Should return False if aplay not available."""
        with patch("waiting.audio_players.linux.which") as mock_which:
            mock_which.return_value = None
            player = ALSAPlayer()
            assert player.available() is False

    def test_alsa_play_returns_pid(self):
        """Play should return process ID."""
        with patch("waiting.audio_players.linux.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = ALSAPlayer()
            pid = player.play("test.wav", 100)

            assert pid == 12345


class TestGetLinuxPlayer:
    """Tests for get_linux_player fallback chain."""

    def test_get_linux_player_pulseaudio(self):
        """Should return PulseAudio if available."""
        with patch("waiting.audio_players.linux.PulseAudioPlayer") as mock_pa:
            mock_pa_instance = Mock()
            mock_pa_instance.available.return_value = True
            mock_pa.return_value = mock_pa_instance

            player = get_linux_player()
            assert player.available() is True

    def test_get_linux_player_fallback_to_pipewire(self):
        """Should fall back to PipeWire if PulseAudio unavailable."""
        with patch("waiting.audio_players.linux.PulseAudioPlayer") as mock_pa:
            with patch("waiting.audio_players.linux.PipeWirePlayer") as mock_pw:
                mock_pa_instance = Mock()
                mock_pa_instance.available.return_value = False
                mock_pa.return_value = mock_pa_instance

                mock_pw_instance = Mock()
                mock_pw_instance.available.return_value = True
                mock_pw.return_value = mock_pw_instance

                player = get_linux_player()
                assert player.available() is True

    def test_get_linux_player_fallback_to_alsa(self):
        """Should fall back to ALSA if PulseAudio and PipeWire unavailable."""
        with patch("waiting.audio_players.linux.PulseAudioPlayer") as mock_pa:
            with patch("waiting.audio_players.linux.PipeWirePlayer") as mock_pw:
                with patch("waiting.audio_players.linux.ALSAPlayer") as mock_alsa:
                    mock_pa_instance = Mock()
                    mock_pa_instance.available.return_value = False
                    mock_pa.return_value = mock_pa_instance

                    mock_pw_instance = Mock()
                    mock_pw_instance.available.return_value = False
                    mock_pw.return_value = mock_pw_instance

                    mock_alsa_instance = Mock()
                    mock_alsa_instance.available.return_value = True
                    mock_alsa.return_value = mock_alsa_instance

                    player = get_linux_player()
                    assert player.available() is True

    def test_get_linux_player_none_available(self):
        """Should raise error if no player available."""
        with patch("waiting.audio_players.linux.PulseAudioPlayer") as mock_pa:
            with patch("waiting.audio_players.linux.PipeWirePlayer") as mock_pw:
                with patch("waiting.audio_players.linux.ALSAPlayer") as mock_alsa:
                    for mock in [mock_pa, mock_pw, mock_alsa]:
                        mock_instance = Mock()
                        mock_instance.available.return_value = False
                        mock.return_value = mock_instance

                    with pytest.raises(Exception):
                        get_linux_player()


class TestAFPlayPlayer:
    """Tests for macOS AFPlay player."""

    def test_afplay_name(self):
        """Should return correct player name."""
        player = AFPlayPlayer()
        assert player.name() == "AFPlay"

    def test_afplay_available_true(self):
        """Should return True if afplay is available."""
        with patch("waiting.audio_players.macos.which") as mock_which:
            mock_which.return_value = "/usr/bin/afplay"
            player = AFPlayPlayer()
            assert player.available() is True

    def test_afplay_available_false(self):
        """Should return False if afplay not available."""
        with patch("waiting.audio_players.macos.which") as mock_which:
            mock_which.return_value = None
            player = AFPlayPlayer()
            assert player.available() is False

    def test_afplay_play_returns_pid(self):
        """Play should return process ID."""
        with patch("waiting.audio_players.macos.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = AFPlayPlayer()
            pid = player.play("test.wav", 100)

            assert pid == 12345

    def test_afplay_default_uses_glass_sound(self):
        """Should use Glass.aiff for default sound."""
        with patch("waiting.audio_players.macos.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = AFPlayPlayer()
            player.play("default", 100)

            call_args = mock_popen.call_args[0][0]
            # Check that Glass.aiff is in the command args
            assert any("Glass.aiff" in str(arg) for arg in call_args)


class TestPowerShellPlayer:
    """Tests for Windows PowerShell player."""

    def test_powershell_name(self):
        """Should return correct player name."""
        player = PowerShellPlayer()
        assert player.name() == "PowerShell"

    def test_powershell_available_true(self):
        """Should return True if powershell.exe is available."""
        with patch("waiting.audio_players.windows.which") as mock_which:
            mock_which.return_value = "powershell.exe"
            player = PowerShellPlayer()
            assert player.available() is True

    def test_powershell_available_false(self):
        """Should return False if powershell.exe not available."""
        with patch("waiting.audio_players.windows.which") as mock_which:
            mock_which.return_value = None
            player = PowerShellPlayer()
            assert player.available() is False

    def test_powershell_play_returns_pid(self):
        """Play should return process ID."""
        with patch("waiting.audio_players.windows.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = PowerShellPlayer()
            pid = player.play("test.wav", 100)

            assert pid == 12345

    def test_powershell_kill(self):
        """Kill should execute taskkill."""
        with patch("waiting.audio_players.windows.subprocess.run") as mock_run:
            player = PowerShellPlayer()
            result = player.kill(12345)

            assert result is True
            mock_run.assert_called()
