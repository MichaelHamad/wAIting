# Distribution Options for waiting

This document outlines the available options for distributing the `waiting` tool so others can easily install and use it.

## Current State

As of January 2025, there is no centralized "Claude plugin store" or marketplace for Claude Code extensions. Tools like `waiting` that use Claude Code's hook system must be distributed through standard package distribution channels.

## Option 1: PyPI (Python Package Index)

**Recommended** - The standard way to distribute Python packages.

### User Experience
```bash
pip install waiting-notify
```

### Requirements
- Account at [pypi.org](https://pypi.org)
- Unique package name (check availability first)
- Package metadata in `pyproject.toml`

### How to Publish
```bash
# Install build tools
pip install build twine

# Build the package
python -m build

# Upload to TestPyPI first (optional, for testing)
twine upload --repository testpypi dist/*

# Upload to PyPI
twine upload dist/*
```

### Considerations
- The name `waiting` is likely already taken on PyPI
- Consider alternative names: `waiting-notify`, `claude-waiting`, `claude-code-notify`
- Once published, users get easy installation and updates via pip
- Requires maintaining version numbers for releases

---

## Option 2: GitHub Installation

Users can install directly from a GitHub repository without PyPI publication.

### User Experience
```bash
# Install from main branch
pip install git+https://github.com/USERNAME/waiting.git

# Install from specific branch
pip install git+https://github.com/USERNAME/waiting.git@branch-name

# Install from specific tag/release
pip install git+https://github.com/USERNAME/waiting.git@v1.0.0
```

### Requirements
- Public GitHub repository
- Valid `pyproject.toml` with package metadata

### Considerations
- No PyPI account needed
- Longer installation command for users
- Can still use GitHub releases for versioning
- Good option for testing before PyPI publication

---

## Option 3: GitHub Releases with Wheels

Distribute pre-built wheel files via GitHub releases.

### User Experience
```bash
# Download wheel from releases page, then:
pip install waiting-1.0.0-py3-none-any.whl
```

### How to Create
1. Build the wheel: `python -m build`
2. Create a GitHub release
3. Attach the `.whl` file from `dist/` to the release

### Considerations
- Users must manually download the wheel
- Good for users who want a specific version
- Can be combined with Option 2

---

## Option 4: Homebrew Tap (macOS/Linux)

Create a Homebrew formula for easy installation on macOS and Linux.

### User Experience
```bash
brew tap USERNAME/tools
brew install waiting
```

### Requirements
- Create a separate GitHub repository for the tap (e.g., `homebrew-tools`)
- Write a Homebrew formula (Ruby file)
- Host the source tarball (GitHub releases work well)

### Example Formula
```ruby
class Waiting < Formula
  desc "Audio notifications when Claude Code needs user input"
  homepage "https://github.com/USERNAME/waiting"
  url "https://github.com/USERNAME/waiting/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "SHA256_OF_TARBALL"
  license "MIT"

  depends_on "python@3.11"

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/waiting", "--help"
  end
end
```

### Considerations
- More complex setup
- Great user experience for Homebrew users
- Requires maintaining the tap repository
- Popular for CLI tools

---

## Option 5: pipx Installation

Recommend users install with `pipx` for isolated CLI tools.

### User Experience
```bash
# If published to PyPI
pipx install waiting-notify

# From GitHub
pipx install git+https://github.com/USERNAME/waiting.git
```

### Considerations
- `pipx` installs CLI tools in isolated environments
- Prevents dependency conflicts
- Users need `pipx` installed first
- Good recommendation to include in documentation

---

## Comparison Table

| Option | Ease of Use | Setup Complexity | Update Mechanism |
|--------|-------------|------------------|------------------|
| PyPI | Excellent | Medium | `pip install --upgrade` |
| GitHub Direct | Good | Low | Reinstall from repo |
| GitHub Releases | Fair | Low | Manual download |
| Homebrew | Excellent | High | `brew upgrade` |
| pipx + PyPI | Excellent | Medium | `pipx upgrade` |

---

## Recommended Approach

For maximum reach and ease of use:

1. **Start with GitHub** - Make the repository public with clear README instructions
2. **Publish to PyPI** - Once stable, publish with a unique name
3. **Document pipx** - Recommend pipx installation in README for CLI tool best practices
4. **Consider Homebrew later** - Add if there's demand from macOS users

---

## About MCP Servers

Claude Code also supports **MCP (Model Context Protocol) servers** for extending functionality. However, `waiting` uses the **hooks system** rather than MCP, which is the appropriate choice for notification functionality.

The community maintains a list of MCP servers at:
https://github.com/modelcontextprotocol/servers

This is specifically for MCP servers, not hook-based tools like `waiting`.

---

## Community Channels

To promote the tool once distributed:

- Share on GitHub discussions/issues related to Claude Code
- Post in relevant developer communities (Reddit, Discord, etc.)
- Add to awesome-lists if applicable
- Write a blog post or tutorial explaining the tool
