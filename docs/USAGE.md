# Usage Guide

## Command Reference

### waiting (enable notifications)

Enable Waiting notifications by installing hooks.

**Syntax:**
```bash
waiting
waiting enable
```

**Description:**
Installs hook scripts to `~/.claude/hooks/` and registers them with Claude Code. Hooks take effect after restarting Claude Code.

**Output:**
```
✓ Waiting hooks installed to ~/.claude/hooks/
✓ Configuration: ~/.waiting.json

Next steps:
  1. Restart Claude Code for hooks to take effect
  2. Trigger a permission dialog to test
```

**Example:**
```bash
$ waiting
✓ Waiting hooks installed to ~/.claude/hooks/
✓ Configuration: ~/.waiting.json

Next steps:
  1. Restart Claude Code for hooks to take effect
  2. Trigger a permission dialog to test

$ # Restart Claude Code now
```

---

### waiting disable

Disable Waiting notifications by removing hooks.

**Syntax:**
```bash
waiting disable
```

**Description:**
Removes hook scripts from `~/.claude/hooks/` and unregisters them from Claude Code settings. Your configuration file is preserved.

**Output:**
```
✓ Waiting hooks removed
✓ Configuration file preserved at ~/.waiting.json
```

**Example:**
```bash
$ waiting disable
✓ Waiting hooks removed
✓ Configuration file preserved at ~/.waiting.json
```

---

### waiting status

Display current configuration and hook installation status.

**Syntax:**
```bash
waiting status
```

**Description:**
Shows the current state of Waiting including configuration values, whether hooks are installed, and paths to configuration and hook files.

**Output Format:**
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

If disabled:
```
Status:         DISABLED
...
No hooks installed. Run 'waiting' to enable.
```

**Example:**
```bash
$ waiting status
Waiting - Audio Notification System
========================================
Status:         ENABLED
Grace Period:   30s
Volume:         100%
Audio:          default
Config File:    /home/michael/.waiting.json

Hooks installed:
  ✓ waiting-notify-permission.sh
  ✓ waiting-activity-tooluse.sh
```

---

### waiting --help

Display help message with usage summary.

**Syntax:**
```bash
waiting --help
waiting help
waiting -h
```

**Example:**
```bash
$ waiting --help

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

More info: https://github.com/anthropics/waiting
```

## Configuration Options

All configuration is stored in `~/.waiting.json` as JSON. The file is created automatically with defaults on first use.

### grace_period

**Type:** Integer
**Default:** `30`
**Range:** 1-3600 (1 second to 1 hour)
**Unit:** Seconds

The number of seconds to wait after a permission dialog appears before playing the bell notification.

**Examples:**
```json
{ "grace_period": 10 }   # Quick notification
{ "grace_period": 30 }   # Standard (default)
{ "grace_period": 120 }  # 2 minute grace period
```

---

### volume

**Type:** Integer
**Default:** `100`
**Range:** 1-100
**Unit:** Percentage

The volume level for the bell notification.

**Examples:**
```json
{ "volume": 25 }   # Quiet
{ "volume": 50 }   # Medium
{ "volume": 100 }  # Full (default)
```

**Note:** Volume levels are subjective and depend on system volume settings. 100% is the loudest relative to your system volume.

---

### audio

**Type:** String
**Default:** `"default"`
**Values:** `"default"` or path to audio file

The audio file to play for notifications.

**Bundled Sound (Recommended):**
When set to `"default"`, Waiting plays the built-in notification sound (`Cool_bell_final.wav`) that is included with every installation. This provides:
- ✅ Works on all platforms (Linux, macOS, Windows/WSL) without additional setup
- ✅ Consistent notification sound across all installations
- ✅ No dependency on system sounds being available

**Custom Audio Files:**
You can use your own audio file by specifying a path:
```json
{ "audio": "~/Music/my-bell.wav" }
{ "audio": "/usr/share/sounds/notification.ogg" }
{ "audio": "C:\\Users\\User\\bell.wav" }
```

**Supported Formats:**
- WAV (all platforms) - **Recommended**
- OGG/FLAC (Linux with appropriate backend)
- AIFF (macOS)
- MP3 (depends on platform)

**Note:** Custom audio files must exist and be readable. If a custom file is not found, Waiting will log an error.

## Configuration Examples

### Basic Setup (defaults)

```json
{
  "grace_period": 30,
  "volume": 100,
  "audio": "default"
}
```

### Quiet Notifications

For a less intrusive setup:

```json
{
  "grace_period": 45,
  "volume": 30,
  "audio": "default"
}
```

### Aggressive Notifications

For users who step away frequently:

```json
{
  "grace_period": 10,
  "volume": 100,
  "audio": "default"
}
```

### Custom Audio File

Use a custom notification sound:

```json
{
  "grace_period": 30,
  "volume": 80,
  "audio": "~/Sounds/notification.wav"
}
```

### Long Grace Period

For deep work sessions where you often don't respond immediately:

```json
{
  "grace_period": 120,
  "volume": 60,
  "audio": "default"
}
```

## Common Use Cases

### Case 1: User Steps Away Frequently

**Problem:** You often step away from your desk for a few minutes.

**Solution:**
```json
{
  "grace_period": 20,
  "volume": 100,
  "audio": "default"
}
```

This gives you 20 seconds before the bell plays with full volume to ensure you hear it from adjacent areas.

### Case 2: Open Office Environment

**Problem:** You don't want to annoy colleagues with loud notifications.

**Solution:**
```json
{
  "grace_period": 30,
  "volume": 20,
  "audio": "default"
}
```

Lower volume keeps notifications subtle while still audible to you.

### Case 3: Coding Sessions

**Problem:** You enter flow state and forget about permission dialogs.

**Solution:**
```json
{
  "grace_period": 60,
  "volume": 50,
  "audio": "~/Sounds/chime.wav"
}
```

Longer grace period prevents interruption during deep focus, but still notifies you eventually.

### Case 4: Remote Work with Multiple Monitors

**Problem:** You're away from main screen frequently.

**Solution:**
```json
{
  "grace_period": 15,
  "volume": 100,
  "audio": "default"
}
```

Short grace period with maximum volume ensures you hear it regardless of location.

## Troubleshooting

### Bell Not Playing

**Problem:** Waiting is enabled but you don't hear the bell.

**Solutions:**

1. **Verify system audio works:**
   ```bash
   # Linux
   paplay /usr/share/sounds/freedesktop/stereo/bell.oga

   # macOS
   afplay /System/Library/Sounds/Glass.aiff
   ```

2. **Check system volume:**
   - Ensure system volume is not muted
   - Check volume mixer settings
   - Test audio in other applications

3. **Verify Waiting is enabled:**
   ```bash
   waiting status
   # Should show: Status: ENABLED
   ```

4. **Check audio configuration:**
   ```bash
   cat ~/.waiting.json
   # Verify "audio" field is set correctly
   ```

5. **Test with custom audio file:**
   ```json
   { "audio": "/path/to/known/working/sound.wav" }
   ```

6. **Check logs:**
   ```bash
   tail ~/.waiting.log
   ```

### Hooks Not Triggering

**Problem:** Permission dialogs appear but no bell plays.

**Solutions:**

1. **Restart Claude Code:**
   After enabling Waiting, Claude Code must be restarted for hooks to take effect.
   ```bash
   waiting enable
   # Then restart Claude Code completely
   ```

2. **Verify hooks are installed:**
   ```bash
   ls -la ~/.claude/hooks/waiting-*.sh
   # Should show two files
   ```

3. **Check hook registration:**
   ```bash
   grep -i waiting ~/.claude/settings.json
   # Should show hook registrations
   ```

4. **Trigger a permission dialog:**
   - In Claude Code, run a command that requires permission
   - Don't respond to the dialog
   - Wait for the grace period to elapse

### Configuration Changes Not Applying

**Problem:** Changed configuration but still getting old behavior.

**Solutions:**

1. **Restart Claude Code:**
   Configuration is loaded when hooks execute, which happens on new permission dialogs. Restarting Claude ensures clean state.

2. **Trigger new permission dialog:**
   New sessions load new configuration. Triggering a fresh permission dialog may apply changes.

3. **Verify file is saved:**
   ```bash
   cat ~/.waiting.json
   ```

### "grace_period must be a positive integer" Error

**Problem:** Configuration validation failed.

**Solutions:**

1. **Check JSON syntax:**
   ```bash
   cat ~/.waiting.json
   # Ensure valid JSON with proper quotes and commas
   ```

2. **Use valid value:**
   - `grace_period` must be a positive integer: 1-3600
   - Correct: `"grace_period": 30`
   - Incorrect: `"grace_period": -5` or `"grace_period": "30"`

3. **Reset to defaults:**
   ```bash
   rm ~/.waiting.json
   waiting enable
   ```

### "volume must be an integer between 1 and 100" Error

**Problem:** Volume configuration is invalid.

**Solutions:**

1. **Use valid value:**
   - Range: 1-100
   - Correct: `"volume": 75`
   - Incorrect: `"volume": 150` or `"volume": "75"`

2. **Reset to defaults:**
   ```bash
   rm ~/.waiting.json
   waiting enable
   ```

### "Audio file not found" Error

**Problem:** Custom audio file doesn't exist.

**Solutions:**

1. **Use absolute or expanded paths:**
   ```json
   { "audio": "/absolute/path/to/file.wav" }
   { "audio": "~/relative/to/home.wav" }
   ```

2. **Verify file exists:**
   ```bash
   ls -la ~/Music/notification.wav
   ```

3. **Use system default:**
   ```json
   { "audio": "default" }
   ```

### Waiting Doesn't Work After Update

**Problem:** After updating, hooks or configuration don't work.

**Solutions:**

1. **Reinstall hooks:**
   ```bash
   waiting disable
   waiting enable
   # Then restart Claude Code
   ```

2. **Clear old state files:**
   ```bash
   rm /tmp/waiting-* 2>/dev/null
   ```

3. **Verify installation:**
   ```bash
   waiting status
   ```

## Tips and Best Practices

1. **Start with defaults** - Use the default configuration first, then adjust based on your workflow.

2. **Test in isolation** - Trigger a permission dialog and wait to verify everything works before adjusting settings.

3. **Use descriptive audio files** - If using custom audio, choose a sound distinctly different from other notifications so you immediately recognize it.

4. **Adjust grace period to your habits** - If you usually respond quickly, use 20-30 seconds. If you often step away, use 60+ seconds.

5. **Monitor logs for debugging** - Check `~/.waiting.log` when something isn't working as expected.

6. **Keep configuration backed up** - If you have custom settings, save them before reinstalling or updating.

## Getting Help

- Check logs: `tail ~/.waiting.log`
- Review configuration: `cat ~/.waiting.json`
- Check status: `waiting status`
- See installation issues: See [INSTALLATION.md](./INSTALLATION.md)
- For development questions: See [DEVELOPMENT.md](./DEVELOPMENT.md)
