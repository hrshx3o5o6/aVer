# aVer Agent Guide

This document is for AI agents (Claude Code, OpenCode, Hermes, etc.) that want to read from, write to, or build on aVer's version store programmatically.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Python API Reference](#python-api-reference)
  - [Loading Configs at Runtime](#loading-configs-at-runtime)
  - [Working with the Version Store Directly](#working-with-the-version-store-directly)
  - [Using the Manifest Schema](#using-the-manifest-schema)
  - [Structural Diffs](#structural-diffs)
- [Adding a New Framework Bridge](#adding-a-new-framework-bridge)
- [CLI Protocol for Agents](#cli-protocol-for-agents)
- [Store Format Reference](#store-format-reference)

## Architecture Overview

```
┌─────────────────────┐
│   Agent Framework   │  (Claude Code, OpenCode, Hermes, Zen, Phi)
├─────────────────────┤
│  import_from_xxx()  │  Bridge reads native config → AgentManifest
│  export_to_xxx()    │  Bridge writes AgentManifest → native config
└─────────┬───────────┘
          │
┌─────────▼───────────┐
│    AgentManifest     │  Universal schema (framework-agnostic)
│  manifest.py         │
└─────────┬───────────┘
          │
┌─────────▼───────────┐
│    VersionStore      │  On-disk store (.agent-ver/)
│  version_store.py    │  Commits, club commits, tags, environments
└─────────┬───────────┘
          │
┌─────────▼───────────┐
│    client.py         │  Runtime SDK for agents to load configs
└─────────────────────┘
```

Key insight: aVer normalizes every framework's config into the `AgentManifest` schema. Bridges translate between native formats and the schema. Once config is stored, it can be exported to any other framework.

## Python API Reference

### Loading Configs at Runtime

The `client` module is the easiest way for an agent to load its own config from aVer at runtime:

```python
from client import load_config, get_prompts, get_tools, get_model_params, get_system_prompt

# Load full manifest by environment
manifest = load_config(env="production")

# Load by tag (for A/B testing)
manifest_a = load_config(tag="trial-a")
manifest_b = load_config(tag="trial-b")

# Load by explicit hash
manifest = load_config(ref="a1b2c3d4e5f6")

# Get specific parts
prompts = get_prompts(env="staging")
tools = get_tools(env="staging")
model_params = get_model_params(env="staging")
system_prompt = get_system_prompt("default", env="production")

# Get raw dict (for frameworks that prefer dicts)
config_dict = load_config_dict(tag="v1")
```

The store path defaults to `.agent-ver/` in the current working directory. Override with the `AGENT_VER_STORE` environment variable:

```bash
export AGENT_VER_STORE=/path/to/.agent-ver
```

### Working with the Version Store Directly

For more control, use `VersionStore` directly:

```python
from version_store import VersionStore

store = VersionStore(".agent-ver")

# Resolve any reference to a hash
hash = store.resolve("main")          # branch
hash = store.resolve("v1")            # tag
hash = store.resolve("production")    # environment
hash = store.resolve("a1b2c3d4")      # partial hash

# Get manifests (handles both club commits and individual)
manifests = store.get_manifests("main")
# => {"hermes": AgentManifest, "claude-code": AgentManifest, ...}

# Check if a hash is a club commit
if store.is_club_commit(hash):
    club = store.get_club_commit(hash)
    print(f"Members: {list(club.members.keys())}")
    for fw, fw_hash in club.members.items():
        m = store.get_manifest(fw_hash)
        # work with individual manifest

# Get a single manifest
manifest = store.get_manifest(hash)

# Get environment version
hash = store.get_environment_version("staging")

# Pin an environment
store.pin_environment("staging", hash)

# Log history
entries = store.log(branch="main", max_count=10)
for e in entries:
    if isinstance(e, ClubCommit):
        print(f"Club: {e.hash[:12]} — {', '.join(e.members.keys())}")
        print(f"  Message: {e.message}")
        print(f"  Tags: {e.tags}")
    else:
        print(f"Version: {e.hash[:12]} — v{e.version}")
```

### Creating Commits Programmatically

```python
from manifest import AgentManifest, FrameworkType, ModelParams, PromptConfig, ToolDefinition
from version_store import VersionStore

# Create a manifest
manifest = AgentManifest(
    name="my-agent",
    framework=FrameworkType.CLAUDE_CODE,
    version="2.0.0",
    environment="dev",
    model_params=ModelParams(
        model="claude-sonnet-4-20250514",
        temperature=0.7,
    ),
    prompts={
        "default": PromptConfig(
            system_prompt="You are a helpful AI coding assistant.",
            role="default",
        ),
        "code-reviewer": PromptConfig(
            system_prompt="Review code for bugs and style issues.",
            role="code-reviewer",
        ),
    },
    tools={
        "mcp_filesystem": ToolDefinition(
            name="filesystem",
            description="Read and write files",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            implementation_ref='{"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem"]}',
        ),
    },
    metadata={
        "permissions_allow": ["read", "write", "execute"],
    },
)

# Store it
store = VersionStore(".agent-ver")
version_hash = store.commit(
    manifest,
    message="Custom agent setup",
    tags=["my-tag"],
    author="my-agent",
)
```

### Club Commits

A club commit bundles multiple framework manifests under one hash:

```python
store = VersionStore(".agent-ver")

# Import manifests from different frameworks...
hermes_manifest = AgentManifest(name="h", framework=FrameworkType.HERMES, ...)
cc_manifest = AgentManifest(name="cc", framework=FrameworkType.CLAUDE_CODE, ...)
oc_manifest = AgentManifest(name="oc", framework=FrameworkType.OPENCODE, ...)

# Bundle them into one club commit
club_hash = store.club_commit(
    manifests={
        "hermes": hermes_manifest,
        "claude-code": cc_manifest,
        "opencode": oc_manifest,
    },
    message="Full project snapshot",
    tags=["sprint-3"],
)

# Restore all of them later
manifests = store.get_manifests(club_hash)
# => {"hermes": ..., "claude-code": ..., "opencode": ...}
```

### Using the Manifest Schema

```python
from manifest import AgentManifest, FrameworkType

# Create from scratch
m = AgentManifest(
    name="agent-name",
    framework=FrameworkType.HERMES,
    version="1.0.0",
)

# Serialize
json_str = m.to_json()
as_dict = m.to_dict()

# Deserialize
m2 = AgentManifest.from_json(json_str)
m3 = AgentManifest.from_dict(as_dict)

# Content hashing (for dedup)
content_hash = m.content_hash()   # hash of content fields only (excludes version/env)
commit_hash = m.commit_hash()     # hash of all fields
```

### Structural Diffs

Compare two configs semantically:

```python
from diff import diff_manifests

diff = diff_manifests(manifest_a, manifest_b)
print(f"Changes: {diff.change_count}")
print(f"Breaking: {len(diff.breaking_changes)}")  # removed fields

for entry in diff.entries:
    print(f"[{entry.change_type}] {entry.path}")
    print(f"  was: {entry.old}")
    print(f"  now: {entry.new}")

# Dict serialization for machine consumption
report = diff.to_dict()
# => {"version_a": "...", "version_b": "...", "change_count": 3,
#     "has_breaking_changes": False, "entries": [...]}
```

Or via the CLI:

```bash
aver diff main v1
```

## Adding a New Framework Bridge

If you're an agent that needs to add support for a new framework, follow this pattern.

### Step 1: Define Bridge Functions

Create `bridges/<framework>_bridge.py`:

```python
"""
<Name> ↔ AgentManifest bridge.
"""
from __future__ import annotations

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
    """Read native config files and return an AgentManifest.

    Auto-detect configs if no explicit paths given.
    If store is provided, commit and pin environment.
    Return None if no config found (never raise).
    """
    # 1. Find config files (project root, home dir, etc.)
    # 2. Parse into AgentManifest fields
    # 3. If store: store.commit(manifest, message=..., tags=[...])
    # 4. Return manifest (or None)
    ...


def export_to_<name>(
    manifest: AgentManifest,
    output_path: Optional[str] = None,
) -> str:
    """Write an AgentManifest to native config files.

    Default to the framework's standard location.
    Return the path where output was written.
    """
    # 1. Read manifest fields (manifest.model_params, manifest.prompts, etc.)
    # 2. Write to native format
    # 3. Return output path string
    ...
```

### Step 2: Register in the FrameworkType Enum

In `manifest.py`:

```python
class FrameworkType(str, Enum):
    # ... existing entries ...
    NEW_FRAMEWORK = "new-framework"
```

The string value is the framework key used throughout the codebase (in `cmd_commit` scan list, `cmd_checkout` exporters dict, etc.).

### Step 3: Wire Into the CLI

In `cli.py`, add to `cmd_commit`:

```python
from bridges.new_framework_bridge import import_from_new_framework
scan.append(("new-framework", "New Framework", lambda: import_from_new_framework(store=store)))
```

And to `cmd_checkout`:

```python
from bridges.new_framework_bridge import export_to_new_framework
exporters["new-framework"] = export_to_new_framework
```

Also add `import new-framework` and `export <ref> new-framework` subparsers in `main()`.

### Step 4: Update Interactive Detection

In `interactive.py`:

```python
DETECT_MAP["New Framework"] = "new-framework"
# Add to checks list in auto_detect_import()
# Add to FRAMEWORK_NAMES dict
# Add to EXPORT_FORMATS dict
```

### Bridge Contract Summary

| Aspect | Requirement |
|---|---|
| Import signature | `import_from_<name>(store=None, version="1.0.0", environment="current", commit_message="...", **fw_specific_kwargs) -> Optional[AgentManifest]` |
| Export signature | `export_to_<name>(manifest, output_path=None) -> str` |
| Auto-detection | Scan project root + home directory for native config files |
| Silent on miss | Return `None` if no config found — no tracebacks or errors |
| Round-trip fidelity | `export(import(config))` should produce the same effective config |


## CLI Protocol for Agents

Agents can invoke aVer as a subprocess:

```python
import subprocess, json

# Get current state
result = subprocess.run(["aver", "status"], capture_output=True, text=True)
print(result.stdout)

# Checkout a specific version
subprocess.run(["aver", "checkout", "production"])

# Deploy an environment
subprocess.run(["aver", "deploy", "staging", "a1b2c3d4e5f6"])

# Export a single framework from a commit
subprocess.run(["aver", "export", "main", "claude-code"])
```

Non-zero exit code means failure. Errors go to stderr.

## Store Format Reference

The `.agent-ver/` directory structure:

```
.agent-ver/
├── index.json           # Main index (versions, club_commits, heads)
├── versions/
│   ├── a1b2c3d4....json # Individual AgentManifest JSON files
│   └── e5f6a7b8....json
├── club/
│   └── cafe1234....json # ClubCommit JSON files (group references)
├── tags/
│   ├── v1               # File named after tag, content = version hash
│   └── trial-a
└── environments/
    ├── current           # File named after env, content = hash
    ├── staging
    └── prod
```

### index.json

```json
{
  "versions": {
    "a1b2c3d4e5f6a7b8": {
      "version": "1.0.0",
      "hash": "a1b2c3d4e5f6a7b8",
      "manifest_path": ".agent-ver/versions/a1b2c3d4e5f6a7b8.json",
      "message": "Initial import",
      "timestamp": "2026-06-21T05:33:44",
      "author": "agent-ver-import",
      "parent_hash": null,
      "tags": ["hermes-import"]
    }
  },
  "club_commits": {
    "cafe1234abcd5678": {
      "hash": "cafe1234abcd5678",
      "message": "Full snapshot",
      "timestamp": "2026-06-21T05:33:44",
      "members": {
        "hermes": "a1b2c3d4e5f6a7b8",
        "claude-code": "b2c3d4e5f6a7b8c9"
      },
      "tags": [],
      "parent": null
    }
  },
  "heads": {
    "main": "cafe1234abcd5678"
  }
}
```

### Club Commit JSON

```json
{
  "hash": "cafe1234abcd5678",
  "message": "Full snapshot",
  "timestamp": "2026-06-21T05:33:44",
  "members": {
    "hermes": "a1b2c3d4e5f6a7b8",
    "claude-code": "b2c3d4e5f6a7b8c9",
    "opencode": "c3d4e5f6a7b8c9d0"
  },
  "tags": ["sprint-3"],
  "parent": "d4e5f6a7b8c9d0e1"
}
```

The `members` dict maps framework keys to individual version hashes. This is what `checkout` uses to find each manifest.
