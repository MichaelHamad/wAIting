# User Stories - Waiting Audio Notification System

**Project:** Waiting - Audio Notification System for Claude Code
**Version:** MVP 1.0
**Date:** 2026-01-10

---

## Epics & Story Breakdown

### **EPIC 1: Installation & Setup**
Enable users to easily install and configure the Waiting notification system.

---

## USER STORIES

### **US-1: Install Waiting System**

**As a** developer
**I want** to install the Waiting notification system via pip
**so that** I can enable audio alerts for Claude Code permission dialogs

#### Acceptance Criteria
- [x] User can run `pip install -e .` to install the package
- [x] Installation completes without errors
- [x] The `waiting` command becomes available in the terminal
- [x] Installation guide documents the required restart of Claude Code
- [x] System creates `~/.waiting.json` with default configuration on first enable

---

### **US-2: Enable Notifications**

**As a** Claude Code user
**I want** to enable the Waiting notification system with a single command
**so that** I can start receiving audio alerts for unresponsive permission dialogs

#### Acceptance Criteria
- [x] User can run `waiting` command to enable notifications
- [x] Command installs hook scripts to `~/.claude/hooks/`
- [x] Command REGISTERS hooks in `~/.claude/settings.json` (hooks must be registered in settings, not just exist as files)
- [x] Confirmation message displays when hooks are successfully installed and registered
- [x] System creates default `~/.waiting.json` if it doesn't exist
- [x] User must restart Claude Code for hooks to take effect
- [x] Clear message instructs user to restart Claude Code
- [x] Hooks configuration is properly formatted as JSON with event matchers and command references

---

### **US-3: Disable Notifications**

**As a** a Claude Code user
**I want** to disable notifications when I don't want audio alerts
**so that** I can temporarily or permanently turn off the Waiting system

#### Acceptance Criteria
- [x] User can run `waiting disable` to deactivate notifications
- [x] Command removes hook REGISTRATION from `~/.claude/settings.json` (critical: must deregister from settings)
- [x] Command can optionally remove hook scripts from `~/.claude/hooks/` (or leave them for faster re-enable)
- [x] Confirmation message displays successful removal/deregistration
- [x] System does not remove `~/.waiting.json` configuration file
- [x] No audio alerts occur after disabling, even if permission dialogs appear (verified by checking settings.json)
- [x] User can re-enable notifications by running `waiting` again (re-registers hooks)

---

### **US-4: View System Status & Configuration**

**As a** Claude Code user
**I want** to check the current status and configuration of Waiting
**so that** I can verify settings and troubleshoot issues

#### Acceptance Criteria
- [x] User can run `waiting status` to display current configuration
- [x] Status output shows whether notifications are enabled/disabled (by checking hook registration in settings.json)
- [x] Status displays current `grace_period` value (default: 30 seconds)
- [x] Status displays current `volume` setting (default: 100%)
- [x] Status displays current `audio` file configuration
- [x] Status shows path to `~/.waiting.json` configuration file
- [x] Status clearly indicates which hooks are registered in `~/.claude/settings.json` (not just which files exist)
- [x] Status validates that `~/.claude/hooks/` directory exists and scripts are present
- [x] Status confirms hook configuration format matches expectations

---

### **US-4a: Correct Hook Registration in settings.json** (CRITICAL)

**As a** the Waiting system
**I want** to properly register and manage hooks in `~/.claude/settings.json`
**so that** Claude Code recognizes and executes the hooks

#### Acceptance Criteria
- [x] Hook registration follows Claude Code's official hook configuration format
- [x] PermissionRequest hook is registered under `hooks.PermissionRequest` key with matcher and command reference
- [x] Example: `{ "hooks": { "PermissionRequest": [{ "matcher": "*", "hooks": [{ "type": "command", "command": "~/.claude/hooks/waiting-notify-permission.sh" }]}]}}`
- [x] Hook commands use full paths or relative paths that resolve correctly
- [x] Hooks are properly escaped in JSON (quotes, backslashes, etc.)
- [x] Multiple hooks can coexist with other hooks in settings.json (no conflicts)
- [x] Hook configuration is validated before writing to settings.json
- [x] Enable command creates backup of existing settings.json before modifying
- [x] Disable command removes only Waiting hooks, preserving other user hooks

---

## EPIC 2: Audio Notification Trigger
Detect permission dialogs and play audio alerts when users don't respond.

---

### **US-5: Detect Permission Dialog**

**As a** the Waiting system
**I want** to detect when Claude Code triggers a PermissionRequest hook event
**so that** I can initiate the grace period timer

#### Acceptance Criteria
- [x] Hook script `waiting-notify-permission.sh` executes on `PermissionRequest` hook event
- [x] Hook is registered in `~/.claude/settings.json` under the `PermissionRequest` event
- [x] Hook uses a matcher pattern (e.g., "*" for all tools, or specific tool names like "Bash", "Read", "Write")
- [x] Script receives Claude's hook JSON input via stdin with `session_id` field
- [x] Script can parse session ID from JSON input (e.g., `jq -r '.session_id'`)
- [x] Script handles cases where session_id may not be present and provides fallback (MD5 hash of timestamp)
- [x] Script creates session-specific state tracking files in `/tmp` (e.g., `/tmp/waiting-state-{session}.tmp`)
- [x] Grace period timer starts immediately after permission dialog appears
- [x] Script exits with code 0 to allow hook to complete successfully
- [x] System logs permission request event for debugging

---

### **US-6: Grace Period Timer**

**As a** Claude Code user
**I want** the system to wait for a configurable grace period before playing a sound
**so that** I have time to respond to the permission dialog before being alerted

#### Acceptance Criteria
- [x] Grace period defaults to 30 seconds
- [x] User can configure grace period via `~/.waiting.json`
- [x] Grace period value is respected and enforced by hook script
- [x] Timer starts when permission dialog appears
- [x] Timer can be canceled if user responds before expiration
- [x] Timer value is logged for debugging

---

### **US-7: Play Audio Alert**

**As a** a Claude Code user
**I want** to hear a bell sound after the grace period expires
**so that** I'm alerted that a permission dialog requires my attention

#### Acceptance Criteria
- [x] Bell sound plays automatically after grace period elapses
- [x] Audio is played using the default system audio player (or custom file)
- [x] Volume level respects the configuration setting (default: 100%)
- [x] Audio playback works on Linux, macOS, and Windows (WSL)
- [x] System attempts audio playback in order: paplay → pw-play → aplay → afplay → powershell.exe
- [x] Graceful fallback if no audio player is available
- [x] Audio process PID is tracked in `/tmp/waiting-audio-{session}.pid`

---

### **US-8: Stop Alert on User Response**

**As a** Claude Code user
**I want** the bell sound to stop immediately when I respond to the permission dialog
**so that** I don't hear unnecessary alerts

#### Acceptance Criteria
- [x] System detects when user responds to permission dialog (via either PermissionRequest hook completion or subsequent PreToolUse hook)
- [x] When user approves/denies permission, response is detected and stop signal is created
- [x] Stop signal file `/tmp/waiting-stop-{session}` is created immediately upon user response
- [x] Permission hook script monitors stop signal file and cancels audio playback when detected
- [x] Audio process is killed/stopped immediately using stored PID from `/tmp/waiting-audio-{session}.pid`
- [x] Stop signal prevents bell from playing if user acts during grace period (before timeout)
- [x] Audio playback is stopped even if partially played
- [x] Cleanup of state files occurs after alert is canceled or played
- [x] Timing is accurate: bell plays only if no user response during entire grace period

---

## EPIC 3: Configuration Management
Allow users to customize notification behavior.

---

### **US-9: Configure Grace Period**

**As a** a Claude Code user
**I want** to customize the grace period duration
**so that** I can control how long to wait before hearing the bell

#### Acceptance Criteria
- [x] User can edit `~/.waiting.json` and set `grace_period` to any positive integer
- [x] Default grace period is 30 seconds
- [x] Configuration takes effect after Claude Code is restarted
- [x] Invalid values (zero, negative, non-integer) are rejected with error message
- [x] User receives clear guidance on valid range and format
- [x] Configuration is documented in project README

---

### **US-10: Configure Audio Volume**

**As a** a Claude Code user
**I want** to adjust the volume of the bell sound
**so that** I can control how loud the alert is

#### Acceptance Criteria
- [x] User can set `volume` in `~/.waiting.json` to a value between 1-100
- [x] Default volume is 100%
- [x] Volume setting is passed to the audio player command
- [x] Configuration takes effect after Claude Code is restarted
- [x] Invalid values (outside 1-100) are rejected with error message
- [x] User can set volume to 1 for minimal audio or 100 for maximum
- [x] Volume control method varies by platform (--volume, -v, etc.)

---

### **US-11: Configure Custom Audio File**

**As a** a Claude Code user
**I want** to use a custom audio file instead of the default bell sound
**so that** I can personalize my notification experience

#### Acceptance Criteria
- [x] User can set `audio` field in `~/.waiting.json` to a file path
- [x] Default value is "default" (system bell)
- [x] Custom audio file must exist and be readable
- [x] System validates audio file format (WAV, MP3, OGG, etc.)
- [x] System validates that specified file path exists before playback
- [x] Error message displays if custom file is not found
- [x] Fallback to default bell if custom file is invalid
- [x] Absolute and relative paths are both supported

---

## EPIC 4: Cross-Platform Support
Ensure the system works reliably across different operating systems.

---

### **US-12: Support Linux Audio Playback**

**As a** a Linux user
**I want** the bell sound to play reliably using available Linux audio systems
**so that** I receive notifications regardless of my audio setup

#### Acceptance Criteria
- [x] System attempts PulseAudio (`paplay`) first
- [x] Falls back to PipeWire (`pw-play`) if PulseAudio unavailable
- [x] Falls back to ALSA (`aplay`) if PipeWire unavailable
- [x] Works with both default system bell and custom audio files
- [x] Respects volume setting on each audio player
- [x] Audio playback is tested on at least one Linux distribution

---

### **US-13: Support macOS Audio Playback**

**As a** a macOS user
**I want** the bell sound to play using macOS native audio
**so that** I receive notifications on my Mac

#### Acceptance Criteria
- [x] System uses `afplay` command on macOS
- [x] afplay command respects volume configuration
- [x] Works with both default system bell and custom audio files
- [x] Audio playback is tested on macOS

---

### **US-14: Support Windows (WSL) Audio Playback**

**As a** a Windows user running WSL
**I want** the bell sound to play through Windows audio
**so that** I receive notifications even in WSL environment

#### Acceptance Criteria
- [x] System detects WSL environment
- [x] Uses PowerShell audio playback command when other players unavailable
- [x] Works with both default system bell and custom audio files
- [x] Volume setting is respected via PowerShell audio player
- [x] Audio playback is tested on WSL2

---

## EPIC 5: State Management & Cleanup
Manage temporary files and process state reliably.

---

### **US-15: Track Audio Process State**

**As a** the Waiting system
**I want** to track audio playback process information
**so that** I can stop playback when the user responds

#### Acceptance Criteria
- [x] Audio process PID is stored in `/tmp/waiting-audio-{session}.pid`
- [x] Session ID is extracted from Claude's hook JSON
- [x] Fallback session ID is MD5 hash of timestamp/hostname if JSON doesn't provide it
- [x] PID file is created before audio playback begins
- [x] PID file is deleted after audio playback completes or is stopped
- [x] System can retrieve PID to kill audio process if needed

---

### **US-16: Create Stop Signal for Cancellation**

**As a** the Waiting system
**I want** to signal the permission hook to cancel audio playback
**so that** playback stops immediately when user responds

#### Acceptance Criteria
- [x] Stop signal file `/tmp/waiting-stop-{session}` is created by activity hook
- [x] Permission hook monitors for this signal file
- [x] Hook checks signal file periodically during grace period
- [x] Hook kills audio process immediately upon detecting signal
- [x] Stop signal file is cleaned up after use
- [x] Multiple rapid responses don't create duplicate signals

---

### **US-17: Clean Up Temporary Files**

**As a** the Waiting system
**I want** to remove temporary state files after each notification cycle
**so that** the system doesn't accumulate temporary files

#### Acceptance Criteria
- [x] Temporary files are cleaned up after bell plays
- [x] Temporary files are cleaned up after user response cancels alert
- [x] System doesn't leave orphaned PID files
- [x] System doesn't leave orphaned stop signal files
- [x] Cleanup occurs even if audio playback fails
- [x] Old temporary files (> 1 hour) are automatically pruned

---

## EPIC 6: Reliability & Error Handling
Ensure system is robust and handles failures gracefully.

---

### **US-18: Handle Missing Audio Player**

**As a** a user with unusual system configuration
**I want** the system to fail gracefully if no audio player is available
**so that** missing audio doesn't break Claude Code workflow

#### Acceptance Criteria
- [x] System logs warning if no audio player is found
- [x] Permission dialog continues to function normally
- [x] No error messages appear in Claude Code output
- [x] User can continue working even if audio fails
- [x] `waiting status` indicates audio player availability
- [x] Documentation suggests installing audio player

---

### **US-19: Handle Invalid Configuration**

**As a** a Claude Code user
**I want** invalid configuration to be caught and reported clearly
**so that** I can fix configuration issues easily

#### Acceptance Criteria
- [x] Invalid `grace_period` values are rejected with helpful error
- [x] Invalid `volume` values (outside 1-100) are rejected
- [x] Invalid audio file paths are detected before playback
- [x] Configuration is validated on Claude Code startup
- [x] `waiting status` validates configuration and reports issues
- [x] Validation errors include suggestions for valid values

---

### **US-20: Prevent Duplicate Alerts for Same Dialog**

**As a** a Claude Code user
**I want** to ensure only one bell plays per permission dialog
**so that** I don't get multiple alerts for the same request

#### Acceptance Criteria
- [x] Each permission dialog gets unique session ID
- [x] Only one alert timer runs per session ID
- [x] Duplicate permission requests get different session IDs
- [x] System prevents multiple audio processes for single dialog
- [x] State is tracked per session to prevent duplicate alerts

---

## EPIC 7: Logging & Debugging
Provide visibility into system operation.

---

### **US-21: Log Permission Request Events**

**As a** a developer troubleshooting issues
**I want** permission request events to be logged
**so that** I can debug why alerts don't appear

#### Acceptance Criteria
- [x] Each permission request is logged with timestamp
- [x] Log includes session ID and grace period value
- [x] Log indicates when grace period expires
- [x] Logs are written to `.waiting.log` or similar
- [x] Logs don't accumulate excessively (rotation/pruning)
- [x] User can enable verbose logging mode for troubleshooting

---

### **US-22: Log Audio Playback Events**

**As a** a developer troubleshooting audio issues
**I want** audio playback events to be logged
**so that** I can debug why sounds don't play

#### Acceptance Criteria
- [x] Audio player selection is logged
- [x] Audio playback start and completion are logged
- [x] Failed playback attempts are logged with error details
- [x] Logs indicate which audio player was used
- [x] Volume and audio file settings are logged
- [x] Logs help diagnose audio system issues

---

## Business Value & Success Metrics

### Key Success Metrics
1. **Usability:** Users can enable/disable in < 1 minute
2. **Reliability:** Audio plays 95%+ of the time on supported platforms
3. **User Satisfaction:** 80%+ of users find alerts helpful
4. **Support:** < 5% of installations report audio-related issues

### User Value Propositions
- **Productivity:** Never miss permission dialogs while away from desk
- **User Control:** Full configurability for alert timing and volume
- **Simplicity:** One command to install and enable
- **Compatibility:** Works across Linux, macOS, and WSL

---

## Dependencies & Assumptions

### Technical Dependencies
- Claude Code hook system with:
  - **PermissionRequest event**: Runs when permission dialog is shown (defined in hooks reference documentation)
  - **Hook configuration via settings.json**: Hooks MUST be registered in `~/.claude/settings.json` to be active (critical!)
  - **Hook JSON input/output**: Hooks receive session_id and other context via stdin
  - **Exit codes**: Hook exit code 0 = success, code 2 = blocking error
- Cross-platform audio playback tools (paplay, afplay, aplay, pw-play, powershell.exe)
- Bash shell for hook scripts
- jq for JSON parsing in bash scripts (or equivalent)

### Assumptions
- Users restart Claude Code after enabling hooks (required for settings.json to take effect)
- User has at least one audio player available on their system
- `/tmp` directory is writable for state files
- `~/.claude/` and `~/.claude/hooks/` directories exist or can be created
- Users can manually edit JSON in `~/.waiting.json` (or CLI abstracts this)
- `~/.claude/settings.json` exists or can be created
- Users have permission to write to `~/.claude/settings.json`

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Hooks not registered in settings.json | HIGH | HIGH | Ensure enable command WRITES hook config to settings.json, test thoroughly, document clearly |
| Hook configuration JSON is malformed | Medium | High | Validate JSON before writing, use JSON schema validation, provide clear error messages |
| Audio player unavailable on some systems | Medium | Low | Graceful fallback, user guidance in docs |
| Hook events don't fire as expected | Low | High | Thorough testing on supported platforms, verify settings.json after enable |
| Hooks conflict with user's other hooks | Low | Medium | Carefully choose hook names, provide backup/restore, check for existing hooks before registering |
| State files accumulate over time | Low | Low | Automatic cleanup and pruning logic |
| Configuration errors cause confusion | Medium | Medium | Clear error messages and validation |
| Permission dialog missed despite bell | Low | Medium | Ensure audio is loud enough, allow volume control |
| Claude Code not restarted after enable | Medium | Medium | Clear messaging, provide restart prompt, detect when hooks aren't active |

---

## Roadmap (Future Enhancements)

**Not in MVP:**
- **Multiple notification triggers using additional hook events:**
  - `Notification` event with `idle_prompt` matcher for idle alerts (Claude Code sends this when idle > 60s)
  - `Stop` event for additional stop-related notifications
  - `PreCompact` event for context window alerts
- Repeating alerts ("nag" functionality - bell repeats every N seconds if dialog still unresponded)
- Prompt-based hooks for intelligent permission decisions (alternative to simple allow/deny)
- Web UI for configuration
- Advanced scheduling (quiet hours, etc.)
- Integration with desktop notifications (system notification APIs)
- Sound selection/preview from UI
- Usage analytics
- Configuration profiles (work mode, focus mode, etc.)

---

## Documentation Requirements

- [ ] Installation guide with system prerequisites
- [ ] **CRITICAL: Hook Configuration documentation:**
  - [ ] Explain that hooks MUST be registered in `~/.claude/settings.json` to work
  - [ ] Show exact JSON format for PermissionRequest hook registration
  - [ ] Explain the difference between hook scripts in `~/.claude/hooks/` and hook registration in settings.json
  - [ ] Include troubleshooting: "Hooks installed but not working? Check settings.json"
  - [ ] Document that Claude Code must be restarted after enabling hooks
- [ ] Configuration guide with examples for `~/.waiting.json`
- [ ] Troubleshooting guide for common audio issues
- [ ] Platform-specific setup instructions
- [ ] Hook system integration guide (for developers)
- [ ] Security best practices for hook scripts

