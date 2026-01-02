# waiting

**Never miss a prompt again.** A CLI wrapper that rings a bell when your command needs input.

## The Problem

You run a command, switch to another window, and come back 20 minutes later to find:

```
Building project...
Compiling assets...
Installing dependencies...
Enter password: █   <-- Been sitting here for 15 minutes
```

## The Solution

Wrap your command with `waiting`:

```bash
waiting ./build.sh
```

Now you'll hear a bell the moment it asks for input - even if you're in another window.

## Quick Start

```bash
git clone https://github.com/yourusername/waiting.git
cd waiting
pip install .
```

Then wrap any command:

```bash
waiting <your-command>
```

## Examples

```bash
# AI assistants - get alerted when they need your response
waiting claude

# Package managers - catch those license/config prompts
waiting npm install
waiting pip install -e .

# Git operations - know when the editor opens or auth is needed
waiting git commit
waiting git push

# System commands - never miss sudo prompts
waiting sudo apt update

# Interactive REPLs - bell at each prompt
waiting python3
waiting node

# Build scripts - catch any interactive prompts
waiting make install
waiting ./configure
```

## How It Works

```
┌─────────────────────────────────────────────────────┐
│  $ waiting ./my-script.sh                           │
├─────────────────────────────────────────────────────┤
│                                                     │
│  waiting wraps your command in a PTY (pseudo-       │
│  terminal) and monitors for input prompts:          │
│                                                     │
│  1. Raw mode detection (single keypress input)      │
│  2. Prompt patterns (?, :, >, [Y/n], password, etc) │
│                                                     │
│  When detected → Terminal bell rings (🔔)           │
│                                                     │
│  Your command runs EXACTLY as normal:               │
│  ✓ Same colors                                      │
│  ✓ Same interactivity                               │
│  ✓ Same exit code                                   │
│  ✓ Ctrl+C works                                     │
│  ✓ Arrow keys work                                  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Requirements

- Python 3.10+
- Unix-like OS (macOS, Linux)
- Terminal with bell support (most terminals)

## Verify Bell Works

Test that your terminal can play the bell sound:

```bash
printf '\a'
```

If you don't hear anything, check your terminal settings:
- **macOS Terminal**: Settings → Profiles → Advanced → Audible bell
- **iTerm2**: Settings → Profiles → Terminal → Notifications → Enable bell
- **VS Code**: Check system sound is on

## Install Options

```bash
# Standard install
pip install .

# Development install (includes pytest)
pip install -e ".[dev]"

# Using Make
make install      # Standard
make dev          # Development
make test         # Run tests
```

## License

MIT
