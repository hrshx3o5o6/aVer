<p align="center">
  <!-- Replace with your logo: <img src="assets/logo.png" width="200" alt="aVer logo"> -->
  <img src="https://raw.githubusercontent.com/hrshx3o5o6/aVer/main/assets/aver-logo.png" width="200" alt="aVer">
</p>

<h1 align="center">aVer</h1>

<p align="center">
  <em>Agent Versioning — snapshot, roll back, and promote configs across AI frameworks.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/pypi/v/aver-cli?style=flat-square&color=111111&label=version" alt="PyPI">
  <img src="https://img.shields.io/github/stars/hrshx3o5o6/aVer?style=flat-square&color=111111&label=stars" alt="Stars">
  <img src="https://img.shields.io/badge/license-MIT-111111?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/python-3.10%2B-111111?style=flat-square" alt="Python 3.10+">
</p>

<p align="center">
  <strong>Hermes · Claude Code · OpenCode · Zen · Phi</strong>
</p>

---

## Quick start

```bash
# Init in your project
cd my-project
aver init

# Snapshot all detected agent configs
aver commit -m "Working setup"

# See what's stored
aver log
aver status

# Restore a previous snapshot
aver checkout HEAD~1

# Deploy to staging/production
aver deploy staging e0529330d5ba

# Rollback if something breaks
aver rollback staging

# Compare two versions
aver diff main v1

# Diff against current configs
aver diff main
```

## Commands

| Command | Description |
|---|---|
| `init` | Create a new store in the current directory |
| `commit` | Snapshot all detected framework configs into one club commit |
| `checkout` | Restore all configs from a commit to their native locations |
| `log` | Show commit history |
| `status` | Show head, environment versions, framework counts |
| `import <framework>` | Import a single framework's config into the store |
| `export <ref> <framework>` | Export a single framework's config from the store |
| `diff [a] [b]` | Structural diff between two versions (or HEAD vs current) |
| `deploy <env> <ref>` | Pin an environment to a specific version |
| `rollback <env>` | Rollback an environment to the previous version |
| `tag <name> <ref>` | Tag a commit with a human-readable name |

### `aver init`

Creates a `.agent-ver/` store in the current directory. Run this once per project.

### `aver commit`

Scans the current project for config files across all supported frameworks. Shows per-framework status, then opens an interactive picker — arrow keys to navigate, space to toggle, enter to confirm.

```
Scanning for config files...
  ✓ Hermes
  ✓ Claude Code
  ✓ OpenCode
  - Zen (no config found in current directory)
  - Phi (no config found in current directory)
```

After commit, every tool's config is retrievable by the same hash.

```
$ aver checkout main
  ✓ Hermes → ~/.hermes/config.agent-ver.yaml
  ✓ Claude Code → .claude/settings.json
  ✓ OpenCode → opencode.json
```

### `aver import <framework>`

Import a single framework's config into the store without committing. Useful for one-off imports. Supported frameworks: `hermes`, `claude-code`, `opencode`, `zen`, `phi`.

### `aver export <ref> <framework>`

Export a single framework's config from a stored commit to its native config file location. Use when you only want to restore one framework at a time.

### `aver diff [a] [b]`

Without arguments, diffs the current working configs against HEAD. With one argument, diffs against that ref. With two, diffs the two refs against each other.

```
$ aver diff production main
Changes: 3 (0 breaking)

[temperature] 0.2 → 0.0
[tools.mcp_filesystem]  added
[prompts.code-reviewer.system_prompt]  changed (198 chars → 412 chars)
```

### `aver deploy <env> <ref>`

Pin an environment alias — like `staging` or `production` — to a specific commit. Agents can then load configs by environment name at runtime.

```bash
aver deploy staging a1b2c3d4
aver deploy production a1b2c3d4

# In Python:
from client import load_config
config = load_config(env="staging")
```

### `aver rollback <env>`

Roll an environment back one commit. Uses the parent chain. Prints before/after hashes.

### `aver tag <name> <ref>`

Tag a commit with a human-friendly name like `v1`, `trial-a`, or `release-1`.

## Supported frameworks

| Framework | Config files | Pre-commit scan | Post-checkout restore |
|---|---|---|---|
| **Claude Code** | `.claude/settings.json`, `.mcp.json`, `CLAUDE.md` | ✓ | ✓ |
| **OpenCode** | `opencode.json`, `.opencode/agents/*.md` | ✓ | ✓ |
| **Hermes** | `~/.hermes/config.yaml` | ✓ | ✓ |
| **Zen (zenflow)** | `zenflow.yaml`, `.zenflow/`, `zenagents.json` | ✓ | ✓ |
| **Phi** | `~/.phi/agent/settings.json`, `agents/*.md` | ✓ | ✓ |

## Runtime config loading (for agents)

```python
from client import load_config, get_prompts, get_tools, get_model_params

# Load by environment
config = load_config(env="production")
prompts = get_prompts(env="staging")

# Load by tag
config = load_config(tag="v1")

# Load by commit hash
config = load_config(ref="a1b2c3d4e5f6")
```

## CLI protocol for agents

```python
import subprocess

subprocess.run(["aver", "checkout", "production"], check=True)
subprocess.run(["aver", "deploy", "staging", "a1b2c3d4"], check=True)
result = subprocess.run(["aver", "status"], capture_output=True, text=True)
print(result.stdout)
```

## Adding a new framework bridge

See [AGENTS.md](AGENTS.md) for the full guide. In short:

1. Create `bridges/<name>_bridge.py` with `import_from_<name>()` and `export_to_<name>()`
2. Add to `FrameworkType` enum in `manifest.py`
3. Wire into `cli.py` (`cmd_commit` scan list + `cmd_checkout` exporters dict)
4. Register in `interactive.py` (detection map + export formats)

## Store format

```
.agent-ver/
├── index.json            # Main index (versions, club_commits, heads)
├── versions/
│   └── a1b2c3d4....json  # Individual AgentManifest JSON
├── club/
│   └── cafe1234....json  # ClubCommit (members → individual hashes)
├── tags/
│   └── v1                # File content = version hash
└── environments/
    └── staging            # File content = version hash
```

## Architecture

```
┌─────────────────────┐
│   Agent Framework   │
├─────────────────────┤
│  import_from_xxx()  │  Bridge reads native config → AgentManifest
│  export_to_xxx()    │  Bridge writes AgentManifest → native config
└─────────┬───────────┘
          │
┌─────────▼───────────┐
│    AgentManifest     │  Universal schema (framework-agnostic)
└─────────┬───────────┘
          │
┌─────────▼───────────┐
│    VersionStore      │  On-disk store (.agent-ver/)
└─────────┬───────────┘
          │
┌─────────▼───────────┐
│    client.py         │  Runtime SDK for agents
└─────────────────────┘
```
