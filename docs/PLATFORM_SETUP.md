# Platform-Specific Setup Guide for Waiting

This guide provides setup instructions for running the Waiting audio notification system on different platforms (Linux, macOS, and Windows).

## Overview

Waiting supports three major platforms with platform-specific audio players:

| Platform | Audio Player | Command | Notes |
|----------|-------------|---------|-------|
| **Linux** | PulseAudio (paplay) | `paplay` | Primary choice; excellent audio control |
| **Linux** | PipeWire (pw-play) | `pw-play` | Modern replacement for PulseAudio |
| **Linux** | ALSA (aplay) | `aplay` | Fallback if PulseAudio/PipeWire unavailable |
| **macOS** | AFPlay | `afplay` | Built-in native audio player |
| **Windows** | PowerShell | `powershell.exe` | Uses .NET System.Media.SoundPlayer |

The system automatically detects your platform and selects the best available audio player.

## Linux Setup

### Prerequisites

Linux requires at least one audio system installed. The system will try players in this order:

1. **PulseAudio** (preferred)
2. **PipeWire** (modern replacement)
3. **ALSA** (fallback)

### Installation

#### Ubuntu/Debian

```bash
# Install PulseAudio (most distributions have this by default)
sudo apt-get install pulseaudio

# Or install PipeWire (modern alternative)
sudo apt-get install pipewire wireplumber

# Or install ALSA (fallback, usually pre-installed)
sudo apt-get install alsa-utils
```

#### Fedora/RHEL

```bash
# Install PulseAudio
sudo dnf install pulseaudio

# Or install PipeWire
sudo dnf install pipewire

# Or install ALSA
sudo dnf install alsa-utils
```

#### Arch Linux

```bash
# Install PulseAudio
sudo pacman -S pulseaudio

# Or install PipeWire
sudo pacman -S pipewire

# Or install ALSA
sudo pacman -S alsa-utils
```

### Verification

Check which audio system is available:

```bash
# Check for PulseAudio
which paplay

# Check for PipeWire
which pw-play

# Check for ALSA
which aplay
```

### Troubleshooting Linux Audio

**No audio player found:**
```
AudioError: No audio player available. Tried: PulseAudio, PipeWire, ALSA
```

Solution:
1. Install at least one audio system above
2. Verify installation: `which paplay` (or pw-play/aplay)
3. Check if audio daemon is running:
   - PulseAudio: `pulseaudio --check`
   - PipeWire: `systemctl --user status pipewire`

**Sound plays but can't hear it:**

1. Check volume levels:
   - PulseAudio: `pactl list sinks | grep -A 5 "State: RUNNING"`
   - ALSA: `amixer sget Master`

2. Check default audio device is set correctly

3. Test with direct system audio:
   ```bash
   paplay /usr/share/sounds/freedesktop/stereo/complete.oga
   ```

**WSL2 Specific Issues:**

If running in WSL2, audio requires additional setup:

1. Install WSL audio drivers (Windows host):
   ```powershell
   winget install AudioDeviceCmdlets
   ```

2. Configure PulseAudio over TCP in WSL:
   ```bash
   # In WSL ~/.bashrc or ~/.zshrc
   export PULSE_SERVER=tcp:127.0.0.1
   ```

3. On Windows host, allow WSL to use audio:
   ```powershell
   Set-NetConnectionProfile -NetworkCategory Private
   ```

## macOS Setup

### Overview

macOS provides the `afplay` utility as a built-in audio player. No additional installation is required.

### Prerequisites

- macOS 10.5 or later (afplay is available on all modern macOS versions)
- Audio output device available (speakers, headphones, etc.)

### Verification

```bash
# Check if afplay is available
which afplay

# Test with system sound
afplay /System/Library/Sounds/Glass.aiff
```

### Troubleshooting macOS Audio

**AFPlay not found:**
```
AudioError: AFPlay not available on macOS
```

This should not occur on modern macOS. If it does:
1. Verify you're on macOS: `uname -s` (should print "Darwin")
2. Check if afplay exists: `ls -la /usr/bin/afplay`
3. System may be missing standard utilities - reinstall Xcode Command Line Tools:
   ```bash
   xcode-select --install
   ```

**Sound plays but can't hear it:**

1. Check system audio settings: System Preferences → Sound → Output
2. Verify volume is not muted
3. Test with direct command:
   ```bash
   afplay /System/Library/Sounds/Glass.aiff -v 1.0
   ```

**Permission Issues:**

If you get permission errors, verify your user has audio access. This is typically automatic, but you can check in System Preferences → Security & Privacy.

## Windows Setup

### Overview

Windows uses PowerShell (built-in) with the .NET `System.Media.SoundPlayer` class for audio playback.

### Prerequisites

- Windows 7 or later
- PowerShell 5.0 or later (included by default on Windows 10+)
- Audio output device available (speakers, headphones, USB audio, etc.)

### Verification

```powershell
# Check if PowerShell is available
Get-Command powershell.exe

# Test audio system
[System.Media.SystemSounds]::Beep.Play()
```

### Troubleshooting Windows Audio

**PowerShell not found:**
```
AudioError: PowerShell not available on Windows
```

This should not occur on modern Windows. If it does:
1. Verify PowerShell is installed: `powershell -Version`
2. PowerShell is built-in to Windows 7+, but may not be in PATH
3. Try full path: `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`

**Sound plays but can't hear it:**

1. Check Windows audio settings: Settings → Sound → Volume and device preferences
2. Verify Waiting is not muted in Volume mixer
3. Test with direct command:
   ```powershell
   (New-Object System.Media.SoundPlayer("C:\Windows\Media\notify.wav").PlaySync())
   ```

**Permission Issues:**

If you get access denied errors:
1. Run command prompt as Administrator
2. Check audio file permissions
3. Verify user has audio device access

### WSL2 on Windows

If running in WSL2, audio playback should work automatically, but you can optimize it:

1. Install PulseAudio in WSL2:
   ```bash
   sudo apt-get install pulseaudio-utils
   ```

2. Configure to use Windows audio:
   ```bash
   export PULSE_SERVER=tcp:127.0.0.1
   ```

## Cross-Platform Audio File Paths

### Supported Format

Waiting supports WAV, MP3, OGA, and AIFF audio files, though actual support depends on the audio player:

| Format | Linux (PA) | Linux (ALSA) | macOS | Windows |
|--------|-----------|-------------|-------|---------|
| WAV    | ✓         | ✓           | ✓     | ✓       |
| MP3    | ✓         | ✗           | ✓     | ✓       |
| OGA    | ✓         | ✗           | ✓     | ✗       |
| AIFF   | ✗         | ✗           | ✓     | ✗       |

### Path Syntax

Use absolute paths or paths with `~` for home directory:

```python
# Absolute path
/path/to/sound.wav
C:\Users\Username\sound.wav

# Home directory
~/sounds/bell.wav
```

### System Default Sounds

Waiting will use system default sounds if "default" is configured:

- **Linux**: `/usr/share/sounds/freedesktop/stereo/complete.oga` or system bell
- **macOS**: `/System/Library/Sounds/Glass.aiff`
- **Windows**: `C:\Windows\Media\notify.wav`

## Volume Control

Volume is configured as 1-100 (percentage). Each platform handles this differently:

| Platform | Internal Scale | Details |
|----------|----------------|---------|
| PulseAudio | 0-65536 | Linear volume scale |
| PipeWire | 0.0-1.0 | Floating point scale |
| ALSA | 0-100 | Percentage scale |
| AFPlay | 0.0-1.0 | Floating point scale |
| PowerShell | 0.0-1.0 | Floating point scale |

The Waiting system automatically converts from 1-100 to the appropriate scale for each player.

## Testing Audio Setup

### CLI Test

Test audio directly:

```bash
# Test audio playback
python -m waiting.audio default 100

# Test with custom file
python -m waiting.audio ~/sounds/bell.wav 75
```

### Docker/Container Testing

When testing in containers or minimal environments:

```bash
# Install minimal audio system
apt-get install -y alsa-utils pulseaudio

# Test ALSA directly
aplay /usr/share/sounds/freedesktop/stereo/complete.oga
```

## Configuration Reference

### Audio Configuration

In `~/.waiting.json`:

```json
{
  "audio": "default",    // "default" or path to audio file
  "volume": 80,          // 1-100 (percentage)
  "grace_period": 30     // seconds before audio notification
}
```

### Environment Variables

Waiting respects standard audio environment variables:

- `PULSE_SERVER`: PulseAudio server address (Linux)
- `ALSA_CARD`: Default ALSA audio card (Linux)
- `PIPEWIRE_REMOTE`: PipeWire socket path (Linux)

## Known Issues and Workarounds

### Linux

**Issue**: No audio output on WSL2
- **Workaround**: Use TCP connection to host PulseAudio or install Windows audio tools

**Issue**: PulseAudio daemon not running
- **Workaround**: Start manually: `pulseaudio --daemonize`

**Issue**: Permission denied on audio device
- **Workaround**: Add user to audio group: `sudo usermod -a -G audio $USER`

### macOS

**Issue**: Gatekeeper blocking afplay
- **Workaround**: This is rare but if it occurs, open System Preferences → Security & Privacy

**Issue**: Audio plays at wrong volume
- **Workaround**: Adjust system volume separately; afplay respects system volume

### Windows

**Issue**: PowerShell execution policy blocks scripts
- **Workaround**: Set execution policy: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

**Issue**: Audio in WSL2 not working
- **Workaround**: Ensure PulseAudio bridge is configured, or use Windows PowerShell player instead

## Debugging

Enable debug logging to troubleshoot audio issues:

```bash
# Set debug logging
WAITING_LOG_LEVEL=DEBUG waiting start

# Check logs
tail -f ~/.claude/waiting.log
```

Debug output will show:
- Platform detection results
- Available audio players
- Selected audio player
- Audio file resolution
- Audio command execution

## Performance Notes

- **Startup**: Audio player initialization is lazy (only on first use)
- **Audio latency**: ~200-500ms typical depending on system
- **Resource usage**: Minimal when not playing audio
- **Process lifecycle**: Audio processes are cleaned up automatically

## Platform Compatibility Matrix

| Feature | Linux | macOS | Windows |
|---------|-------|-------|---------|
| Audio playback | ✓ | ✓ | ✓ |
| Default sounds | ✓ | ✓ | ✓ |
| Custom files | ✓ | ✓ | ✓ |
| Volume control | ✓ | ✓ | ✓ |
| Kill/stop audio | ✓ | ✓ | ✓ |
| Process detection | ✓ | ✓ | ✓ |

## Additional Resources

- [PulseAudio Documentation](https://www.freedesktop.org/wiki/Software/PulseAudio/)
- [PipeWire Documentation](https://docs.pipewire.org/)
- [ALSA Documentation](https://www.alsa-project.org/)
- [macOS Audio Overview](https://developer.apple.com/documentation/avfaudio)
- [PowerShell Media.SoundPlayer](https://docs.microsoft.com/en-us/dotnet/api/system.media.soundplayer)
