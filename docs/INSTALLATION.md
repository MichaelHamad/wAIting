# Installation Guide

## System Requirements

### Minimum Requirements
- **Python**: 3.9 or higher
- **OS**: Linux, macOS, or Windows (WSL)
- **Space**: ~2 MB for installation
- **Permissions**: User-level (no sudo required for normal operation)

### Audio System Requirements

**Good news:** Waiting includes a bundled notification sound, so no additional audio packages are required to get started!

If you want to use custom audio files, you may need platform-specific audio tools (typically pre-installed):

#### Linux (Optional - for custom audio)
Waiting works with these audio systems:
- **PulseAudio**: `paplay` command (Ubuntu, Debian, Fedora default)
- **PipeWire**: `pw-play` command (newer systems)
- **ALSA**: `aplay` command (fallback for minimal systems)

Check what's available:
```bash
which paplay    # PulseAudio
which pw-play   # PipeWire
which aplay     # ALSA
```

#### macOS (Optional - for custom audio)
- **AFPlay**: Built-in (no installation needed)

#### Windows/WSL (Optional - for custom audio)
- **PowerShell**: Built-in Windows component

## Installation Steps

### 1. Install from Source

Clone the repository and install in development mode:

```bash
git clone <repository-url>
cd waiting_new
pip install -e .
```

The `-e` flag installs in editable mode, allowing you to modify code and see changes immediately.

### 2. Verify Installation

Check that the `waiting` command is available:

```bash
waiting --help
```

Expected output:
```
Waiting - Audio notification for Claude Code permission dialogs

Usage:
  waiting              Enable notifications (install hooks)
  waiting disable      Disable notifications (remove hooks)
  waiting status       Show current configuration
  waiting --help       Show this message

Configuration:
  Edit ~/.waiting.json to customize:
  - grace_period: seconds to wait before bell (default: 30)
  - volume: bell volume 1-100 (default: 100)
  - audio: path to audio file or "default" (default: "default")
```

### 3. Enable Notifications

Install the hook scripts:

```bash
waiting enable
```

Expected output:
```
✓ Waiting hooks installed to ~/.claude/hooks/
✓ Configuration: ~/.waiting.json
✓ Next steps:
  1. Restart Claude Code for hooks to take effect
  2. Trigger a permission dialog to test
```

### 4. Restart Claude Code

Close and restart Claude Code for the hooks to take effect. The hooks are registered in Claude's settings and will activate on next launch.

### 5. Verify Installation

Check installation status:

```bash
waiting status
```

Expected output:
```
Waiting - Audio Notification System
========================================
Status:         ENABLED
Grace Period:   30s
Volume:         100%
Audio:          default
Config File:    /home/user/.waiting.json

Hooks installed:
  ✓ waiting-notify-permission.sh
  ✓ waiting-activity-tooluse.sh
```

## Configuration

### Default Configuration

On first use, Waiting creates `~/.waiting.json` with defaults:

```json
{
  "grace_period": 30,
  "volume": 100,
  "audio": "default"
}
```

### Customizing Configuration

Edit `~/.waiting.json` with any text editor:

```bash
nano ~/.waiting.json
```

#### Grace Period

Change how long to wait before playing the bell (in seconds):

```json
{
  "grace_period": 45
}
```

Allowed values: 1-3600 seconds (1 second to 1 hour)

#### Volume

Adjust the bell volume (percentage):

```json
{
  "volume": 50
}
```

Allowed values: 1-100 (1% to 100%)

#### Audio File

Use a custom audio file instead of the system default:

```json
{
  "audio": "/path/to/bell.wav"
}
```

- Use `"default"` for system sounds
- Use absolute paths for custom files (use `~` for home directory)
- Supported formats: WAV, AIFF, OGG (depends on audio backend)

### Configuration Examples

**Quiet notifications (50% volume, 20 second wait):**
```json
{
  "grace_period": 20,
  "volume": 50,
  "audio": "default"
}
```

**Custom audio file:**
```json
{
  "grace_period": 30,
  "volume": 100,
  "audio": "~/Audio/notification.wav"
}
```

**Long grace period for busy work:**
```json
{
  "grace_period": 120,
  "volume": 80,
  "audio": "default"
}
```

### Applying Configuration Changes

Configuration changes take effect when:
1. You restart Claude Code, OR
2. You trigger a new permission dialog (new session)

Changes to active sessions require a Claude Code restart.

## Hook Registration

Waiting integrates with Claude Code's hook system by:

1. Copying hook scripts to `~/.claude/hooks/`
   - `waiting-notify-permission.sh` - Handles permission dialogs
   - `waiting-activity-tooluse.sh` - Handles user responses

2. Registering hooks in `~/.claude/settings.json`
   - Adds hook event subscriptions
   - Preserves existing Claude Code hooks

### Hook Files

Location: `~/.claude/hooks/`

```
waiting-notify-permission.sh    - Triggered on PermissionRequest event
waiting-activity-tooluse.sh     - Triggered on PreToolUse event
```

These are bash scripts that call the Waiting Python module.

### Verifying Hook Registration

Check that hooks are registered in Claude settings:

```bash
cat ~/.claude/settings.json | grep -i waiting
```

You should see references to `waiting-notify-permission` and `waiting-activity-tooluse`.

## Uninstallation

To disable and remove Waiting:

```bash
waiting disable
```

This:
- Removes hook scripts from `~/.claude/hooks/`
- Unregisters hooks from `~/.claude/settings.json`
- Preserves your configuration in `~/.waiting.json`

To completely remove Waiting:

```bash
waiting disable
pip uninstall waiting
rm ~/.waiting.json
```

## Troubleshooting Installation

### "waiting: command not found"

The installation didn't complete successfully. Try:

```bash
pip install --upgrade -e .
```

Or check that your Python environment is activated:

```bash
python --version  # Should show 3.9 or higher
which python
```

### "Error: ~/ .claude directory not found"

Claude Code hasn't created its hooks directory yet. You may need to:

1. Install Claude Code if not already done
2. Create the directory manually:
   ```bash
   mkdir -p ~/.claude/hooks
   ```
3. Try `waiting enable` again

### "Error: Failed to write configuration"

The `~/.waiting.json` file can't be created. Check:

```bash
ls -la ~/  # Check home directory permissions
touch ~/.waiting.json  # Try creating a test file
```

### Audio Not Playing

Verify your audio system is working:

**Linux:**
```bash
# Check available audio players
which paplay pw-play aplay

# Test audio playback
paplay /usr/share/sounds/freedesktop/stereo/complete.oga
```

**macOS:**
```bash
# Test audio playback
afplay /System/Library/Sounds/Glass.aiff
```

**WSL:**
```bash
# Verify PowerShell is available
powershell.exe -Command "Write-Host 'Test'"
```

### Hooks Not Triggering

1. Verify hooks are installed:
   ```bash
   ls -la ~/.claude/hooks/waiting-*.sh
   ```

2. Check they're registered in settings:
   ```bash
   cat ~/.claude/settings.json | grep waiting
   ```

3. Restart Claude Code
4. Try triggering a permission dialog again

## Next Steps

After installation:

1. **Test**: Trigger a permission dialog in Claude Code and wait for the bell
2. **Configure**: Edit `~/.waiting.json` to adjust settings
3. **Learn more**: See [USAGE.md](./USAGE.md) for all commands and options

## Support

For detailed usage instructions, see [USAGE.md](./USAGE.md).

For development setup, see [DEVELOPMENT.md](./DEVELOPMENT.md).
