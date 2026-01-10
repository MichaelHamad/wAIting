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

    def test_afplay_volume_conversion(self):
        """Should convert volume to 0.0-1.0 scale."""
        with patch("waiting.audio_players.macos.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = AFPlayPlayer()
            player.play("test.wav", 50)

            call_args = mock_popen.call_args[0][0]
            # 50% = 0.5
            assert "0.5" in call_args

    def test_afplay_volume_100_percent(self):
        """Should handle 100% volume correctly."""
        with patch("waiting.audio_players.macos.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = AFPlayPlayer()
            player.play("test.wav", 100)

            call_args = mock_popen.call_args[0][0]
            assert "1.0" in call_args

    def test_afplay_volume_low(self):
        """Should handle low volume correctly."""
        with patch("waiting.audio_players.macos.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = AFPlayPlayer()
            player.play("test.wav", 10)

            call_args = mock_popen.call_args[0][0]
            assert "0.1" in call_args

    def test_afplay_kill_success(self):
        """Kill should succeed."""
        with patch("waiting.audio_players.macos.subprocess.run") as mock_run:
            player = AFPlayPlayer()
            result = player.kill(12345)

            assert result is True
            mock_run.assert_called_once()

    def test_afplay_kill_with_exception(self):
        """Kill should handle exceptions gracefully."""
        with patch("waiting.audio_players.macos.subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Kill failed")

            player = AFPlayPlayer()
            result = player.kill(12345)

            assert result is False

    def test_afplay_play_includes_volume_flag(self):
        """Play should include volume flag."""
        with patch("waiting.audio_players.macos.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = AFPlayPlayer()
            player.play("test.wav", 100)

            call_args = mock_popen.call_args[0][0]
            assert "-v" in call_args


class TestPulseAudioPlayerEdgeCases:
    """Edge case tests for PulseAudio player."""

    def test_pulseaudio_kill_exception_handling(self):
        """Kill should handle exceptions and return False."""
        with patch("waiting.audio_players.linux.subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Kill failed")

            player = PulseAudioPlayer()
            result = player.kill(12345)

            assert result is False

    def test_pulseaudio_volume_boundary_low(self):
        """Should handle minimum volume."""
        with patch("waiting.audio_players.linux.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = PulseAudioPlayer()
            player.play("test.wav", 1)

            call_args = mock_popen.call_args[0][0]
            # 1% = 655 (1/100 * 65536)
            assert "655" in call_args

    def test_pulseaudio_volume_boundary_high(self):
        """Should handle maximum volume."""
        with patch("waiting.audio_players.linux.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = PulseAudioPlayer()
            player.play("test.wav", 100)

            call_args = mock_popen.call_args[0][0]
            # 100% = 65536
            assert "65536" in call_args


class TestPipeWirePlayerEdgeCases:
    """Edge case tests for PipeWire player."""

    def test_pipewire_kill_exception_handling(self):
        """Kill should handle exceptions and return False."""
        with patch("waiting.audio_players.linux.subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Kill failed")

            player = PipeWirePlayer()
            result = player.kill(12345)

            assert result is False

    def test_pipewire_play_with_volume(self):
        """Play should include volume control."""
        with patch("waiting.audio_players.linux.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = PipeWirePlayer()
            player.play("test.wav", 75)

            call_args = mock_popen.call_args[0][0]
            assert "--volume" in call_args
            assert "0.75" in call_args


class TestALSAPlayerEdgeCases:
    """Edge case tests for ALSA player."""

    def test_alsa_kill_exception_handling(self):
        """Kill should handle exceptions and return False."""
        with patch("waiting.audio_players.linux.subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Kill failed")

            player = ALSAPlayer()
            result = player.kill(12345)

            assert result is False

    def test_alsa_play_with_volume(self):
        """Play should include volume control."""
        with patch("waiting.audio_players.linux.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = ALSAPlayer()
            player.play("test.wav", 50)

            call_args = mock_popen.call_args[0][0]
            # aplay uses -v for volume
            assert "-v" in call_args


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

    def test_powershell_kill_exception_handling(self):
        """Kill should handle exceptions and return False."""
        with patch("waiting.audio_players.windows.subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Kill failed")

            player = PowerShellPlayer()
            result = player.kill(12345)

            assert result is False


class TestPowerShellPlayerSecurity:
    """Security tests for PowerShell player - injection prevention."""

    def test_rejects_path_with_single_quote(self):
        """Should reject file paths containing single quotes."""
        player = PowerShellPlayer()

        with pytest.raises(ValueError, match="Invalid characters"):
            player.play("/path/with'quote.wav", 100)

    def test_rejects_path_with_semicolon(self):
        """Should reject file paths containing semicolons."""
        player = PowerShellPlayer()

        with pytest.raises(ValueError, match="Invalid characters"):
            player.play("/path/with;semicolon.wav", 100)

    def test_rejects_path_with_backtick(self):
        """Should reject file paths containing backticks."""
        player = PowerShellPlayer()

        with pytest.raises(ValueError, match="Invalid characters"):
            player.play("/path/with`backtick.wav", 100)

    def test_rejects_path_with_dollar(self):
        """Should reject file paths containing dollar signs."""
        player = PowerShellPlayer()

        with pytest.raises(ValueError, match="Invalid characters"):
            player.play("/path/with$dollar.wav", 100)

    def test_rejects_path_with_parentheses(self):
        """Should reject file paths containing parentheses."""
        player = PowerShellPlayer()

        with pytest.raises(ValueError, match="Invalid characters"):
            player.play("/path/with(parens).wav", 100)

    def test_rejects_path_with_braces(self):
        """Should reject file paths containing braces."""
        player = PowerShellPlayer()

        with pytest.raises(ValueError, match="Invalid characters"):
            player.play("/path/with{braces}.wav", 100)

    def test_rejects_injection_attempt(self):
        """Should reject obvious injection attempts."""
        player = PowerShellPlayer()

        with pytest.raises(ValueError, match="Invalid characters"):
            player.play("'; Remove-Item -Recurse C:\\; '", 100)

    def test_accepts_default_keyword(self):
        """Should accept 'default' as a safe sentinel value."""
        with patch("waiting.audio_players.windows.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = PowerShellPlayer()
            pid = player.play("default", 100)

            assert pid == 12345

    def test_accepts_safe_windows_path(self):
        """Should accept standard Windows paths."""
        with patch("waiting.audio_players.windows.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = PowerShellPlayer()
            pid = player.play("C:\\Users\\Test User\\sounds\\bell.wav", 100)

            assert pid == 12345

    def test_accepts_safe_wsl_path(self):
        """Should accept WSL-style paths."""
        with patch("waiting.audio_players.windows.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = PowerShellPlayer()
            pid = player.play("/mnt/c/Users/test/sound.wav", 100)

            assert pid == 12345

    def test_accepts_path_with_spaces(self):
        """Should accept paths with spaces (common in Windows)."""
        with patch("waiting.audio_players.windows.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = PowerShellPlayer()
            pid = player.play("C:\\Program Files\\app\\sound.wav", 100)

            assert pid == 12345

    def test_accepts_path_with_hyphens_underscores(self):
        """Should accept paths with hyphens and underscores."""
        with patch("waiting.audio_players.windows.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = PowerShellPlayer()
            pid = player.play("/path/to/my-sound_file.wav", 100)

            assert pid == 12345


class TestPipeWirePlayerDefaultSound:
    """Tests for PipeWire default sound handling."""

    def test_pipewire_default_uses_system_sound(self):
        """Should use system sound file for 'default'."""
        with patch("waiting.audio_players.linux.subprocess.Popen") as mock_popen:
            with patch("waiting.audio_players.linux._find_system_sound") as mock_find:
                mock_find.return_value = "/usr/share/sounds/freedesktop/stereo/bell.oga"
                mock_proc = Mock()
                mock_proc.pid = 12345
                mock_popen.return_value = mock_proc

                player = PipeWirePlayer()
                pid = player.play("default", 100)

                assert pid == 12345
                # Verify the system sound path was used in command
                call_args = mock_popen.call_args[0][0]
                assert "/usr/share/sounds/freedesktop/stereo/bell.oga" in call_args

    def test_pipewire_default_raises_when_no_system_sound(self):
        """Should raise AudioError if no system sound found."""
        with patch("waiting.audio_players.linux._find_system_sound") as mock_find:
            mock_find.return_value = None

            player = PipeWirePlayer()

            with pytest.raises(AudioError, match="No system sound"):
                player.play("default", 100)

    def test_pipewire_custom_file_still_works(self):
        """Should still work with custom file paths."""
        with patch("waiting.audio_players.linux.subprocess.Popen") as mock_popen:
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            player = PipeWirePlayer()
            pid = player.play("/custom/sound.wav", 80)

            assert pid == 12345
            call_args = mock_popen.call_args[0][0]
            assert "/custom/sound.wav" in call_args


class TestFindSystemSound:
    """Tests for _find_system_sound helper."""

    def test_find_system_sound_returns_first_existing(self):
        """Should return first existing system sound."""
        from waiting.audio_players.linux import _find_system_sound

        with patch("waiting.audio_players.linux.Path") as mock_path:
            # First sound doesn't exist, second does
            mock_instance1 = Mock()
            mock_instance1.exists.return_value = False
            mock_instance2 = Mock()
            mock_instance2.exists.return_value = True

            def side_effect(path):
                if "bell.oga" in path:
                    return mock_instance1
                return mock_instance2

            mock_path.side_effect = side_effect

            result = _find_system_sound()
            assert result is not None

    def test_find_system_sound_returns_none_when_no_sounds(self):
        """Should return None if no system sounds found."""
        from waiting.audio_players.linux import _find_system_sound

        with patch("waiting.audio_players.linux.Path") as mock_path:
            mock_instance = Mock()
            mock_instance.exists.return_value = False
            mock_path.return_value = mock_instance

            result = _find_system_sound()
            assert result is None
