# Contributing to aVer

Thanks for your interest in contributing to aVer. This document covers how to set up a development environment, understand the codebase, make changes, and submit them.

## Table of Contents

- [Development Setup](#development-setup)
- [Code Structure](#code-structure)
- [Coding Conventions](#coding-conventions)
- [How to Add a New Framework Bridge](#how-to-add-a-new-framework-bridge)
- [How to Add a New CLI Command](#how-to-add-a-new-cli-command)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Release Process](#release-process)

## Development Setup

### Prerequisites

- Python 3.10+
- `pipx` (recommended) or `pip`

### Clone and Install in Editable Mode

```bash
git clone https://github.com/hrshx3o5o6/aVer.git
cd aVer
pip install --editable .
```

Editable (`-e`) mode means any changes you make to `.py` files take effect immediately — no reinstall needed.

### Verify It Works

```bash
aver --help
aver init  # creates .agent-ver/ in current dir
```

### Install dev dependencies (optional)

aVer has minimal dependencies (just `pyyaml`). For development you may want:

```bash
pip install pytest  # for running tests
```

## Code Structure

```
aver/
├── cli.py                  # CLI entry point — argparse setup + command handlers
├── manifest.py             # AgentManifest schema — framework-agnostic config representation
├── version_store.py        # VersionStore — on-disk storage, commits, club commits, refs
├── diff.py                 # Structural diff engine — compares manifests semantically
├── client.py               # Runtime SDK — load configs by env/tag from running agents
├── interactive.py          # Interactive menus + auto-detection logic
├── bridges/
│   ├── hermes_bridge.py    # Hermes ↔ AgentManifest
│   ├── claude_code_bridge.py  # Claude Code ↔ AgentManifest
│   ├── opencode_bridge.py  # OpenCode ↔ AgentManifest
│   ├── zen_bridge.py       # Zen/zenflow ↔ AgentManifest
│   └── phi_bridge.py       # Phi ↔ AgentManifest
├── pyproject.toml          # Build config + entry point
├── setup.cfg               # Flat module declarations
├── install.sh              # Cross-platform installer script
├── CONTRIBUTING.md
└── AGENTS.md
```

### Key Files Explained

| File | Responsibility | Key Classes/Functions |
|---|---|---|
| `cli.py` | User-facing CLI | `cmd_commit`, `cmd_checkout`, `cmd_log`, `cmd_diff`, `main()` |
| `manifest.py` | Data model | `AgentManifest`, `FrameworkType`, `PromptConfig`, `ToolDefinition`, `ModelParams` |
| `version_store.py` | Storage engine | `VersionStore`, `ClubCommit`, `VersionEntry` |
| `diff.py` | Comparison | `ConfigDiff`, `diff_manifests()` |
| `client.py` | Runtime API | `load_config()`, `get_prompts()`, `get_tools()` |
| `bridges/*.py` | Framework adapters | `import_from_<name>()`, `export_to_<name>()` |

## Coding Conventions

### Style

- Python 3.10+ type annotations on all function signatures and public methods
- No type annotation comments (use PEP 604 union syntax: `X \| Y` not `Optional[Union[X, Y]]`)
- Use `__future__` annotations at the top of every module
- 4-space indentation, ~100 char line length
- Descriptive variable names — avoid single-letter names except in list comprehensions
- No docstrings on trivial getters/setters; docstrings on public API functions and classes

### Imports

Order: standard library → third-party → aVer modules. One blank line between groups.

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional

from manifest import AgentManifest, FrameworkType
from version_store import VersionStore
```

### Error Handling

- CLI commands return `0` for success, `1` for failure
- Print errors to `sys.stderr`
- Raise `ImportError` for missing optional dependencies (e.g. `pyyaml`)
- Do not raise exceptions for expected user-facing errors (missing config, etc.) — return `None` or print and return

### Bridge Pattern

Every framework bridge follows this exact contract:

```python
def import_from_<name>(
    store: Optional[VersionStore] = None,
    version: str = "1.0.0",
    environment: str = "current",
    commit_message: str = "Imported from <Name> config",
    **framework_specific_kwargs,
) -> Optional[AgentManifest]:

def export_to_<name>(
    manifest: AgentManifest,
    output_path: Optional[str] = None,
) -> str:
```

The import function must:
1. Auto-detect config files if no explicit paths are given
2. Return `None` if no config is found (never print a traceback)
3. Call `store.commit()` and `store.pin_environment()` only if `store` is provided

The export function must:
1. Accept an `AgentManifest` and write it to the framework's native format
2. Default to the framework's standard config location (or current working directory)
3. Return the path where output was written

### Commit Messages

Use conventional commits:

```
type: brief description

Longer description if needed.
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `bridge`

## How to Add a New Framework Bridge

This is the most common contribution. Here's the step-by-step.

### 1. Understand the Target Framework

Identify:
- Where does the framework store its config? (file paths, formats)
- What does a config contain? (prompts? tools? model params? MCP servers?)
- Can multiple config files exist? (project-level vs user-level)

### 2. Create the Bridge File

Create `bridges/<name>_bridge.py` following the existing pattern:

```python
"""
<Name> ↔ AgentManifest bridge.
Imports from <native paths> and exports back.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from manifest import AgentManifest, FrameworkType, PromptConfig, ToolDefinition
from version_store import VersionStore


def import_from_<name>(
    store: Optional[VersionStore] = None,
    version: str = "1.0.0",
    environment: str = "current",
    commit_message: str = "Imported from <Name> config",
) -> Optional[AgentManifest]:
    # 1. Auto-detect config files
    # 2. Parse into AgentManifest
    # 3. Optional: store.commit() if store is provided
    # 4. Return the manifest (or None)
    pass


def export_to_<name>(
    manifest: AgentManifest,
    output_path: Optional[str] = None,
) -> str:
    # 1. Read manifest fields
    # 2. Write to native format
    # 3. Return the output path
    pass
```

### 3. Register the Framework

In `manifest.py`, add to the `FrameworkType` enum:

```python
class FrameworkType(str, Enum):
    # ... existing ...
    YOUR_FRAMEWORK = "your-framework"
```

### 4. Wire It Into the CLI

In `cli.py`:

- Add the import in `cmd_commit`:
  ```python
  from bridges.your_framework_bridge import import_from_your_framework
  scan.append(("your-framework", "Your Framework", lambda: import_from_your_framework(store=store)))
  ```

- Add the export in `cmd_checkout`:
  ```python
  from bridges.your_framework_bridge import export_to_your_framework
  exporters["your-framework"] = export_to_your_framework
  ```

- Add import/export subcommands in `main()` (following the existing pattern)

- Add to the interactive menu in `interactive.py`:
  ```python
  DETECT_MAP["<Name>"] = "your-framework"
  # Add checks in auto_detect_import()
  # Add to FRAMEWORK_NAMES
  # Add to EXPORT_FORMATS
  ```

### 5. Test

```bash
# Create a test config file for your framework
# Run import
aver import your-framework

# Check it was stored
aver log
aver status

# Export it back
aver export main your-framework
```

## Testing

Tests are in the `tests/` directory. Run them with:

```bash
pytest
```

### Test Philosophy

- **Test the storage engine** (`version_store.py`) — commits, club commits, resolve, log, diff
- **Test the diff engine** (`diff.py`) — structural diff correctness
- **Test bridges** — create temp config files, import, export, verify round-trip
- **No network tests** — everything should work offline
- **No CLI integration tests** (yet) — test the Python functions directly

### Writing Tests

```python
def test_club_commit_creates_group():
    store = VersionStore(tmp_path)
    m1 = AgentManifest(name="a", framework=FrameworkType.HERMES)
    m2 = AgentManifest(name="b", framework=FrameworkType.CLAUDE_CODE)
    h = store.club_commit({"hermes": m1, "claude-code": m2}, message="test")
    assert store.is_club_commit(h)
    club = store.get_club_commit(h)
    assert "hermes" in club.members
    assert "claude-code" in club.members
```

## Pull Request Process

1. **Fork** the repository on GitHub
2. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```
3. **Make your changes** following the conventions above
4. **Run tests** (if any exist):
   ```bash
   pytest
   ```
5. **Commit** with a descriptive message:
   ```bash
   git commit -m "feat: add support for <framework>"
   ```
6. **Push** to your fork:
   ```bash
   git push origin feat/my-feature
   ```
7. **Open a pull request** on GitHub against `main`

### PR Checklist

- [ ] Code follows style conventions
- [ ] New bridge files follow the import/export contract
- [ ] `FrameworkType` enum updated
- [ ] CLI wired up (commit scan + checkout export)
- [ ] Interactive menus updated
- [ ] Tests pass (if any)
- [ ] Manual round-trip test passes (import → export → compare)

## Release Process

1. Update version in `pyproject.toml`
2. Update `install.sh` default tag if needed
3. Commit: `chore: bump to v0.x.x`
4. Tag: `git tag v0.x.x && git push --tags`
5. Build: `python -m build`
6. Publish: `python -m twine upload dist/*`

## Questions?

Open an issue on GitHub: [https://github.com/hrshx3o5o6/aVer/issues](https://github.com/hrshx3o5o6/aVer/issues)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
