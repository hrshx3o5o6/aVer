# aVer — Version Control for AI Agent Configurations

**Stop rebuilding agent configs from scratch when they break.**

aVer is a git-like version control system purpose-built for AI agent configurations. It snapshots, diffs, deploys, and rolls back your agent configs across 5 frameworks — all from one CLI.

```bash
aver commit     # Snapshot ALL agent configs in this project
aver log        # Show history
aver checkout   # Restore everything from a previous snapshot
```

---

## Why aVer?

### The Problem

You spend hours tuning your agent — prompts, tools, model params, MCP servers, deployment environments. Then something breaks. Git can't help because it doesn't understand agent configs. You're left manually rebuilding from memory, hunting through terminal history, or praying a backup exists.

### The Solution

aVer understands agent configurations natively. It captures **the full structure** — prompts, tools, model parameters, MCP servers, framework settings — not just raw text. One command saves everything. One command restores everything.

```
aver commit    # Save
aver checkout  # Restore
```

Rollback takes milliseconds. No manual rebuilding. No lost work.

### What Makes aVer Different from Git

| Capability | Git | aVer |
|---|---|---|
| Object of versioning | Raw file text | Structured agent config (prompts, tools, params, metadata) |
| Diff | Line-level text diff | Structural diff — knows prompts from tools from params |
| Restore | Manual checkout + file copy | One-command checkout to any saved version |
| Framework awareness | None | 5 native bridges — reads/writes native config formats |
| Environment management | Branches only | Named environments (dev, staging, prod) with pinning |
| Cross-framework | N/A | Import Claude Code, export to Hermes (and vice versa) |
| Install size | ~1GB+ | ~200KB + dependencies (pyyaml) |

### Supported Frameworks

| Framework | Config Sources | Status |
|---|---|---|
| **Claude Code** | `.claude/settings.json`, `CLAUDE.md`, `.mcp.json` (project + home) | ✅ Stable |
| **OpenCode** | `opencode.json`, `.opencode/agents/*.md`, `.opencode/commands/*.md` | ✅ Stable |
| **Hermes** | `~/.hermes/config.yaml`, `~/.hermes/.env` | ✅ Stable |
| **Zen / Zenflow** | `zenflow.yaml`, `zenflow.yml`, `.zenflow/settings.json`, `zenagents.json`, `agents/*.{json,yaml,yml}` | ✅ Stable |
| **Phi (phi-code)** | `~/.phi/agent/settings.json`, `~/.phi/agent/agents/*.md`, `~/.phi/agent/models.json`, `~/.phi/agent/routing.json` | ✅ Stable |

---

## Quick Start

```bash
# Install (one line — works on macOS, Linux, WSL)
curl -fsSL https://github.com/hrshx3o5o6/aVer/raw/main/install.sh | bash

# Or with pip/pipx
pipx install aver

# Init in your project
cd my-project
aver init

# Snapshot all detected agent configs
aver commit -m "Working setup"

# Make changes, break something...
# Restore everything at once:
aver checkout main
```

---

## Installation

### One-liner (recommended)

```bash
curl -fsSL https://github.com/hrshx3o5o6/aVer/raw/main/install.sh | bash
```

The installer auto-detects your OS and package manager (brew, apt, dnf, yum, pacman, apk, zypper), installs `pipx` if missing, and installs aVer in an isolated virtual environment.

### pip / pipx

```bash
pipx install aver
```

### From source

```bash
git clone https://github.com/hrshx3o5o6/aVer.git
cd aVer
pipx install .
```

### Requirements

- Python 3.10+
- `pyyaml` (installed automatically with the package)

---

## Full CLI Guide

### `aver init`

Initialize a new aVer store in the current project.

```bash
cd my-project
aver init
# => Initialized empty agent-ver store in .agent-ver/
```

Creates a `.agent-ver/` directory with `versions/`, `tags/`, `environments/`, and `club/` subdirectories. This directory is your local version store — add it to `.gitignore` (not meant to be committed).

---

### `aver commit`

Snapshot ALL detected agent configs in one club commit.

```bash
aver commit -m "Working setup"
# => Committed a1b2c3d4e5f6 (3 frameworks: claude-code, hermes, opencode)
```

aVer scans your project and home directory for config files from all 5 frameworks:
- **Hermes**: `~/.hermes/config.yaml`
- **Claude Code**: `.claude/settings.json` + `CLAUDE.md` + `.mcp.json`
- **OpenCode**: `opencode.json` + `.opencode/agents/*.md`
- **Zen**: `zenflow.yaml`, `zenflow.yml`, `.zenflow/`, `zenagents.json`
- **Phi**: `~/.phi/agent/settings.json` + `~/.phi/agent/agents/*.md`

Every framework found is imported and bundled into a single **club commit** — one hash that represents the entire project's agent configuration state.

```bash
aver commit -m "New model" -t production,tested
# => Committed b2c3d4e5f6a7 (2 frameworks: claude-code, opencode)
```

Flags:
- `-m, --message` — Commit message (auto-generated if omitted)
- `-t, --tag` — Comma-separated tags (e.g. `-t trial-a,production`)

---

### `aver checkout`

Restore ALL configs from a previous commit to their native locations.

```bash
aver checkout main
#   ✓ hermes → /Users/harsha/.hermes/config.agent-ver.yaml
#   ✓ claude-code → /Users/harsha/project
#   ✓ opencode → /Users/harsha/project
#
# Restored 3 framework configs
```

Takes any resolvable reference: commit hash (full or partial), branch name, tag, or environment name.

```bash
aver checkout a1b2c3d4e5f6    # by hash
aver checkout production       # by environment
aver checkout v1                # by tag
```

For each framework in the club commit, aVer calls the appropriate bridge exporter to write the config to its native location:
- **Hermes**: `~/.hermes/config.agent-ver.yaml`
- **Claude Code**: `.claude/settings.json` + `CLAUDE.md` + `.mcp.json`
- **OpenCode**: `opencode.json` + `.opencode/agents/*.md`
- **Zen**: `zenflow-export.yaml`
- **Phi**: `settings.json` + `agents/*.md`

---

### `aver log`

Show commit history for a branch.

```bash
aver log
# HASH           FRAMEWORKS                               DATE                 MESSAGE
# ------------------------------------------------------------------------------------------
# a1b2c3d4e5f6   claude-code, hermes, opencode            2026-06-21T05:33:44  Working setup
# f2e448187ee0   1.0.0                                    2026-06-21T05:33:44  Imported from OpenCode
```

```bash
aver log --branch main --count 5
```

Club commits show the member frameworks. Individual version entries show their semver tag.

Flags:
- `--branch` — Branch name (default: `main`)
- `-n, --count` — Max entries (default: 20)

---

### `aver diff`

Structurally diff two versions of a config.

```bash
aver diff a1b2c3d e5f6a7b8
# Diff: a1b2c3d → e5f6a7b8
# Changes: 3  Breaking: 0
#
#   [modified_changed] model_params.model
#     - claude-sonnet-4-20250514
#     + claude-sonnet-3-5-20241022
#   [modified_changed] prompts.default.system_prompt
#     - You are a helpful assistant...
#     + You are a coding expert...
#   [added] tools.mcp_my-server
#     - None
#     + {"command": "node", "args": ["server.js"]}
```

aVer's diff engine is **structure-aware**, not line-based. It knows the difference between a prompt change, a tool removal, and a model param tweak. It tracks three change types:
- `added` — new field that didn't exist before
- `removed` — **breaking change** (field that existed is gone)
- `modified_changed` / `modified_added` — values changed or added

---

### `aver deploy`

Point an environment to a specific version.

```bash
aver deploy staging main
# => Deployed a1b2c3d4e5f6 (claude-code, hermes, opencode) → environment 'staging'

aver deploy prod a1b2c3d
# => Deployed a1b2c3d4e5f6 (claude-code, hermes, opencode) → environment 'prod'
```

Environments are lightweight named pointers (like Git branches but immutable labels). They let you promote configs through a pipeline: `dev` → `staging` → `prod`.

---

### `aver rollback`

Restore an environment to a previous version.

```bash
aver rollback staging a1b2c3d
# => Rollback 'staging': e5f6a7b8 → a1b2c3d (claude-code, hermes, opencode)
```

Works with any resolvable ref — hash, tag, branch, or environment name. Partial hashes are supported as long as they're unique.

---

### `aver status`

Show the current state of the store.

```bash
aver status
# Environments:
#   current              → a1b2c3d4e5f6 (claude-code, hermes, opencode)
#   staging              → a1b2c3d4e5f6 (claude-code, hermes, opencode)
#
# Branches:
#   main                 → a1b2c3d4e5f6 (claude-code, hermes, opencode)
#
# Tags:
#   trial-a              → a1b2c3d4e5f6
#
# Total versions: 4
```

Shows all environments, branch heads, tags, and total version count.

---

### `aver import`

Import a config from a specific framework. Supports interactive mode and direct framework selection.

```bash
# Interactive mode — scans for detectable configs
aver import

# Direct — import a specific framework
aver import hermes --env prod -v 2.0.0
aver import claude-code --settings .claude/settings.json
aver import opencode --project-root /path/to/project
aver import zen --config zenflow.yaml
aver import phi --settings ~/.phi/agent/settings.json
```

Each framework has framework-specific flags. Run `aver import <framework> --help` for details.

---

### `aver export`

Export a stored version to native config files.

```bash
# Interactive mode
aver export main

# Direct — export to a specific format
aver export main hermes -o ~/.hermes/config.yaml
aver export a1b2c3d claude-code
aver export staging opencode
aver export prod zen
aver export v1 phi
```

---

### `aver init-manifest`

Generate a bare AgentManifest JSON from scratch — useful for creating configs without a source framework.

```bash
aver init-manifest --name my-agent --framework opencode -v 1.0.0 --env dev
# => Created manifest: my-agent-config.json
```

---

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                         CLI (cli.py)                      │
│  commit | checkout | log | diff | deploy | rollback      │
└────────────┬──────────────────────────────┬──────────────┘
             │                              │
     ┌───────▼───────┐            ┌─────────▼─────────┐
     │   Bridges/    │            │   VersionStore     │
     │  hermes, cc,  │◄──────────►│   .agent-ver/     │
     │  opencode,    │            │   versions/        │
     │  zen, phi     │            │   club/            │
     └───────────────┘            │   tags/            │
                                  │   environments/    │
                                  └───────────────────┘
```

### Club Commit Model

When you run `aver commit`, aVer:
1. Scans all 5 framework locations for config files
2. Each bridge reads the native config and produces an `AgentManifest` (JSON schema)
3. All manifests are bundled into a single **club commit** — a group commit with a unique hash

Each member framework's manifest is stored individually (deduplicated by content hash), and the club commit references them:

```
club commit (a1b2c3d4e5f6)
├── hermes → 47869a82f5f1 (individual manifest)
├── claude-code → 4877fb112d46 (individual manifest)
└── opencode → 7e865d7e6cda (individual manifest)
```

This means:
- `aver checkout a1b2c3d4e5f6` restores ALL 3 frameworks at once
- `aver diff 47869a82 a1b2c3d4` diffs an individual framework against a club commit
- Individual manifests can be exported separately via `aver export`

### Manifest Schema

Every agent config is normalized into an `AgentManifest` — a universal schema that captures the full configuration:

| Field | Type | Description |
|---|---|---|
| `name` | string | Agent name |
| `framework` | enum | `hermes`, `claude-code`, `opencode`, `zen`, `phi`, `custom` |
| `version` | string | Semver tag |
| `environment` | string | Deployment environment |
| `model_params` | object | Model name, temperature, max_tokens, etc. |
| `prompts` | map | Named prompts (system, personality, agent-specific) |
| `tools` | map | Named tools with JSON schemas, MCP server refs |
| `knowledge_bases` | list | Knowledge base references |
| `metadata` | map | Framework-specific metadata (settings, permissions, etc.) |

### Runtime Client

Applications can load configs at runtime using the `client` module:

```python
from client import load_config, get_prompts, get_tools, get_model_params

# Load by environment
manifest = load_config(env="staging")

# Load by tag
manifest = load_config(tag="trial-a")

# Get just the prompts
prompts = get_prompts(env="prod")

# Get tools
tools = get_tools(env="current")

# Get model params
model_params = get_model_params(env="staging")
```

Set `AGENT_VER_STORE` environment variable to override the default `.agent-ver/` path.

---

## Environment / Pipeline Workflow

aVer environments are lightweight named pointers. Combine them with `commit` → `deploy` → `rollback` for a CI/CD-like pipeline:

```bash
# 1. Save the current working state
aver commit -m "Iteration 3"

# 2. Deploy to staging for testing
aver deploy staging main

# 3. Test... find a bug...

# 4. Rollback staging to a known good version
aver rollback staging v1

# 5. When ready, promote to production
aver deploy prod staging
```

Environments can be used by the runtime client to load environment-specific configs:

```python
manifest = load_config(env="prod")
```

---

## Development

### Project Structure

```
aver/
├── cli.py                  # CLI entry point and command handlers
├── manifest.py             # AgentManifest schema (dataclasses + JSON)
├── version_store.py        # VersionStore, ClubCommit, storage/index
├── diff.py                 # Structural diff engine
├── client.py               # Runtime client for loading configs
├── interactive.py          # Interactive menus + auto-detection
├── bridges/
│   ├── hermes_bridge.py    # Hermes framework bridge
│   ├── claude_code_bridge.py  # Claude Code framework bridge
│   ├── opencode_bridge.py  # OpenCode framework bridge
│   ├── zen_bridge.py       # Zen/zenflow framework bridge
│   └── phi_bridge.py       # Phi framework bridge
├── pyproject.toml          # Package metadata + entry point
├── setup.cfg               # Flat module configuration
├── install.sh              # Cross-platform installer
├── README.md               # This file
├── CONTRIBUTING.md         # Contributor guide
└── AGENTS.md               # AI agent development guide
```

### CLI Entry Point

The `aver` command is registered in `pyproject.toml`:

```toml
[project.scripts]
aver = "cli:main"
```

### Adding a New Framework Bridge

See `AGENTS.md` for the full guide. In short:

1. Create `bridges/<name>_bridge.py` with `import_from_<name>()` and `export_to_<name>()` functions
2. Add the framework to `FrameworkType` enum in `manifest.py`
3. Wire it into `cmd_commit` and `cmd_checkout` in `cli.py`

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

## Links

- **GitHub**: [https://github.com/hrshx3o5o6/aVer](https://github.com/hrshx3o5o6/aVer)
- **Install**: `curl -fsSL https://github.com/hrshx3o5o6/aVer/raw/main/install.sh | bash`
- **Issues**: [https://github.com/hrshx3o5o6/aVer/issues](https://github.com/hrshx3o5o6/aVer/issues)
