# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**waiting** - A CLI utility that detects when interactive commands are waiting for user input and alerts the developer via terminal bell or desktop notifications.

## Commands

```bash
# Install in development mode
pip install -e .

# Run the tool
waiting <command>
python -m waiting <command>

# Run tests
python -m pytest tests/

# Run a specific test file
python -m pytest tests/test_detector.py -v
```

## Architecture

PTY wrapper that spawns commands in a pseudo-terminal:

```
waiting/
├── __init__.py      # Package init, version
├── __main__.py      # Entry: python -m waiting
├── cli.py           # Argument parsing (argparse)
├── runner.py        # PTY spawn + bidirectional I/O passthrough
├── detector.py      # Wait detection state machine (RUNNING/WAITING)
├── events.py        # Event types (dataclasses)
├── notifiers.py     # Bell + desktop notification handlers
└── utils.py         # ANSI stripping, prompt pattern matching
```

### Detection Logic
1. **Primary**: Raw mode detection via termios
2. **Secondary**: Output stall (2s) + prompt pattern matching (`?`, `:`, `>`, `[Y/n]`, etc.)

### Key Constants
- `STALL_THRESHOLD = 2.0` seconds
- `NAG_INTERVAL = 25` seconds (repeat alert while waiting)

## Conventions

- Python 3.10+
- No external dependencies (stdlib only)
- Use dataclasses for event types
- Transparent I/O passthrough (no visual changes to wrapped commands)
- Exit code passthrough from wrapped command

## Implementation Reference

See `PLAN.md` for detailed implementation steps and design decisions.
