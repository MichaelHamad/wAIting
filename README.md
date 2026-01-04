# waiting

🔔 Plays a sound notification when Claude Code needs your attention and you're not responding.

Perfect for when you step away from your desk while Claude is working on a long task. Waiting will alert you when Claude finishes, needs permission for a tool, or has been idle for too long.

## Quick Start

```bash
# Install
pip install -e .

# Enable notifications (default settings)
waiting

# Restart Claude Code for hooks to take effect
```

That's it! You'll now get audio alerts when Claude needs you.

## Usage

```bash
waiting                  # Enable notifications with current config
waiting disable          # Disable all notifications
waiting status           # View current config and hook status
waiting kill             # Stop current alert (doesn't disable notifications)
waiting configure --show # View full configuration as JSON
```

**Important:** Restart Claude Code after enabling/disabling to activate the hooks.

## Configuration

All configuration is stored in `~/.waiting.json`. You can modify settings in three ways:

1. **Via CLI** (easiest):
   ```bash
   waiting configure --volume 50 --interval 60
   ```

2. **Edit directly**:
   ```bash
   nano ~/.waiting.json
   ```

3. **View current settings**:
   ```bash
   waiting configure --show
   waiting status
   ```

### Configuration Reference

#### Sound Settings

| Option | Default | CLI Flag | Description | Example |
|--------|---------|----------|-------------|---------|
| `audio` | `"default"` | `--audio` | Sound file path or `"default"` for bundled bell | `waiting configure --audio /path/to/sound.wav` |
| `volume` | `100` | `--volume` | Volume percentage (1-100) | `waiting configure --volume 75` |

#### Timing Settings

| Option | Default | CLI Flag | Description | Example |
|--------|---------|----------|-------------|---------|
| `interval` | `30` | `--interval` | Seconds between bell repeats | `waiting configure --interval 45` |
| `max_nags` | `0` | `--max-nags` | Max bell repeats (0 = unlimited) | `waiting configure --max-nags 5` |
| `grace_period_stop` | `300` | `--grace-stop` | Seconds to wait after Claude finishes | `waiting configure --grace-stop 120` |
| `grace_period_permission` | `10` | `--grace-permission` | Seconds to wait after permission dialog | `waiting configure --grace-permission 5` |
| `grace_period_idle` | `0` | `--grace-idle` | Extra seconds after idle timeout | `waiting configure --grace-idle 10` |

#### Hook Control

| Option | Default | CLI Flags | Description | Example |
|--------|---------|-----------|-------------|---------|
| `enabled_hooks` | `["stop", "permission", "idle"]` | `--enable-hook`, `--disable-hook`, `--hooks` | Which event types trigger alerts | `waiting configure --disable-hook stop` |

### Configuration Examples

#### Scenario 1: Aggressive Alerts (Don't Miss Anything)
```bash
waiting configure \
  --grace-stop 30 \
  --grace-permission 5 \
  --grace-idle 0 \
  --interval 20 \
  --max-nags 0

# Result: Alerts quickly and frequently
```

#### Scenario 2: Gentle Alerts (Don't Annoy)
```bash
waiting configure \
  --grace-stop 600 \
  --grace-permission 30 \
  --grace-idle 30 \
  --interval 120 \
  --max-nags 3

# Result: Waits longer, alerts less frequently, stops after 3 rings
```

#### Scenario 3: Only Care About Permissions
```bash
waiting configure --hooks permission

# Result: Only alerts for permission dialogs, ignores stops and idle
```

#### Scenario 4: Only Alert When Idle
```bash
waiting configure --hooks idle

# Result: Only alerts for Claude being idle (waiting for input)
```

#### Scenario 5: Quiet Mode (Silent Notifications)
```bash
waiting configure --volume 20 --interval 90

# Result: Very quiet and infrequent alerts
```

### Complete Configuration File Example

```json
{
  "audio": "default",
  "interval": 30,
  "max_nags": 0,
  "volume": 100,
  "enabled_hooks": ["stop", "permission", "idle"],
  "grace_period_stop": 300,
  "grace_period_permission": 10,
  "grace_period_idle": 0
}
```

### How to Configure via CLI (All Options)

```bash
# AUDIO & VOLUME
waiting configure --audio /path/to/bell.wav    # Custom sound file
waiting configure --audio default              # Back to default bell
waiting configure --volume 50                  # Set to 50%

# TIMING
waiting configure --interval 45                # Bell every 45 seconds
waiting configure --max-nags 5                 # Max 5 bells total
waiting configure --grace-stop 180             # Wait 3 min after Claude stops
waiting configure --grace-permission 15        # Wait 15 sec after permission dialog
waiting configure --grace-idle 10              # Wait 10 sec after idle

# HOOKS
waiting configure --enable-hook stop           # Turn on stop alerts
waiting configure --disable-hook idle          # Turn off idle alerts
waiting configure --hooks stop,permission      # Only these hooks active
waiting configure --hooks ""                   # Disable all hooks (same as disable)

# RESET & VIEW
waiting configure --show                       # Display current config as JSON
waiting configure --reset                      # Restore factory defaults

# COMBINATIONS
waiting configure --volume 75 --interval 60 --grace-stop 120
```

### Default Configuration Explanation

```json
{
  "audio": "default",                          // Use built-in bell.wav sound
  "interval": 30,                              // Bell repeats every 30 seconds
  "max_nags": 0,                               // No limit on bell repeats
  "volume": 100,                               // Full volume
  "enabled_hooks": ["stop", "permission", "idle"], // All alerts enabled
  "grace_period_stop": 300,                    // 5 min wait after Claude finishes
  "grace_period_permission": 10,               // 10 sec wait after permission prompt
  "grace_period_idle": 0                       // No extra wait after idle (60 sec built-in)
}
```

## Hooks Explained

Three types of Claude Code events can trigger notifications:

### Permission Hook (`permission`)
**Triggers when:** Claude shows a permission dialog (e.g., "Allow tool X?")

**Grace period:** 10 seconds (default)

**Use case:** You stepped away and Claude is waiting for approval. After 10 seconds of no response, bell plays.

### Stop Hook (`stop`)
**Triggers when:** Claude finishes responding

**Grace period:** 300 seconds / 5 minutes (default)

**Use case:** Claude finished a long task while you were AFK. If you don't interact within 5 minutes, bell plays to let you know it's done.

### Idle Hook (`idle`)
**Triggers when:** Claude's built-in `idle_prompt` fires (after 60s of inactivity)

**Grace period:** 0 seconds (default)

**Use case:** Claude has been waiting at a prompt for 60+ seconds. Bell plays immediately since the 60s wait is already built into Claude.

## How Grace Periods Work

Grace periods implement "wait and see" logic:

1. Hook fires (e.g., permission dialog appears)
2. Background process starts and waits for grace period
3. During wait, checks if you responded (sent message or approved tool)
4. If you responded → no bell, process exits silently
5. If no response after grace period → bell plays
6. Bell repeats every `interval` seconds until you respond (or `max_nags` reached)

This prevents annoying you when you're actively working - the bell only plays if you're actually AFK.

## Activity Tracking

Two events are tracked as "user activity":
- **UserPromptSubmit** - You sent a message to Claude
- **PreToolUse** - You approved a tool

When either occurs, any running nag process is killed immediately.

## Troubleshooting

### Notifications Not Working?

**Check status:**
```bash
waiting status
```

**Verify hooks are installed:**
```bash
waiting status  # Should say "Hooks: Installed"
```

**Did you restart Claude Code?**
Yes, really. Claude Code must be restarted after `waiting` command to load the new hooks.

**Check if audio player is available:**
```bash
# Linux
which paplay || which pw-play || which aplay

# macOS
which afplay

# WSL
which powershell.exe
```

If none found, install a PulseAudio or ALSA package for your system.

**Check config file:**
```bash
cat ~/.waiting.json
```

**Try disabling and re-enabling:**
```bash
waiting disable
waiting  # Re-enable with defaults
# Restart Claude Code
```

**Check logs (nag processes):**
```bash
ps aux | grep waiting-nag
```

### No Sound But Notifications Working?

- Check volume: `waiting configure --volume 100`
- Check audio file exists: `waiting configure --show` and verify audio path
- Try a different audio player installed on your system
- Check system audio isn't muted

### Too Many Alerts?

Increase grace periods or intervals:
```bash
waiting configure --grace-stop 600 --interval 120 --max-nags 3
```

### Too Few Alerts?

Decrease grace periods or intervals:
```bash
waiting configure --grace-stop 30 --interval 15
```

## How It Works

For a detailed explanation of the architecture, data flow, and implementation details, see [ARCHITECTURE.md](docs/reference/ARCHITECTURE.md).

**Quick overview:**
1. `waiting` CLI installs bash hook scripts to `~/.claude/hooks/`
2. Claude Code fires hooks on events (permission, stop, idle)
3. Hook scripts use audio playback and background processes for alerts
4. Activity detection (user responses) kills the alert process
5. Configuration is embedded in the hook scripts (no runtime overhead)

## Requirements

- Python 3.9+
- Audio player (auto-detected in order):
  - `paplay` (PulseAudio) - supports volume
  - `pw-play` (PipeWire) - supports volume
  - `aplay` (ALSA) - no volume control
  - `afplay` (macOS) - supports volume
  - `powershell.exe` (WSL) - Windows audio via PowerShell
