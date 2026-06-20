"""
Claude Code ↔ AgentManifest bridge.
Imports from .claude/settings.json, CLAUDE.md, .mcp.json and exports back.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from manifest import (
    AgentManifest,
    FrameworkType,
    ModelParams,
    PromptConfig,
    ToolDefinition,
)
from version_store import VersionStore


DEFAULT_STORE = ".agent-ver"


def _find_project_root() -> Optional[Path]:
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / ".git").exists() or (parent / ".claude").exists():
            return parent
    return cwd


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _find_claude_md(project_root: Path) -> Optional[str]:
    for name in ("CLAUDE.md", ".claude/CLAUDE.md"):
        p = project_root / name
        if p.exists():
            return p.read_text()
    user_claude = Path.home() / ".claude" / "CLAUDE.md"
    if user_claude.exists():
        return user_claude.read_text()
    return None


def import_from_claude_code(
    settings_path: Optional[str] = None,
    mcp_path: Optional[str] = None,
    claude_md_path: Optional[str] = None,
    project_root: Optional[str] = None,
    store: Optional[VersionStore] = None,
    version: str = "1.0.0",
    environment: str = "current",
    commit_message: str = "Imported from Claude Code config",
) -> Optional[AgentManifest]:
    root = Path(project_root) if project_root else _find_project_root()

    settings: Dict[str, Any] = {}
    if settings_path:
        s = _read_json(Path(settings_path))
        if s:
            settings = s
    else:
        for p in [
            root / ".claude" / "settings.json",
            Path.home() / ".claude" / "settings.json",
        ]:
            s = _read_json(p)
            if s:
                settings = s
                break

    mcp_servers: Dict[str, Any] = {}
    if mcp_path:
        m = _read_json(Path(mcp_path))
        if m:
            mcp_servers = m
    else:
        m = _read_json(root / ".mcp.json")
        if m:
            mcp_servers = m

    claude_md_text: Optional[str] = None
    if claude_md_path:
        p = Path(claude_md_path)
        if p.exists():
            claude_md_text = p.read_text()
    else:
        claude_md_text = _find_claude_md(root)

    model_name = settings.get("model", "")
    prompts: Dict[str, PromptConfig] = {}
    if claude_md_text:
        prompts["default"] = PromptConfig(
            system_prompt=claude_md_text,
            role="default",
        )

    model_params = ModelParams(
        model=model_name,
    )

    tools: Dict[str, ToolDefinition] = {}
    mcp_map = mcp_servers.get("mcpServers", mcp_servers)
    for name, config in mcp_map.items():
        if isinstance(config, dict):
            tools[f"mcp_{name}"] = ToolDefinition(
                name=name,
                description=f"MCP server: {name}",
                input_schema={"type": "object", "properties": {}},
                implementation_ref=json.dumps(config) if config else None,
            )

    allow_perms = settings.get("permissions", {}).get("allow", [])
    deny_perms = settings.get("permissions", {}).get("deny", [])

    manifest = AgentManifest(
        name="claude-code-agent",
        framework=FrameworkType.CLAUDE_CODE,
        version=version,
        environment=environment,
        model_params=model_params,
        prompts=prompts or None,
        tools=tools or None,
        metadata={
            "settings": settings,
            "mcp_servers": mcp_servers,
            "claude_md_length": len(claude_md_text) if claude_md_text else 0,
            "project_root": str(root),
            "permissions_allow": allow_perms,
            "permissions_deny": deny_perms,
        },
    )

    if store:
        h = store.commit(
            manifest,
            message=commit_message or "Imported from Claude Code config",
            tags=["claude-code-import"],
            author="agent-ver-import",
        )
        store.pin_environment(environment, h)
        print(f"Committed: {h}")
        print(f"Pinned '{environment}' → {h}")

    return manifest


def export_to_claude_code(
    manifest: AgentManifest,
    output_dir: Optional[str] = None,
) -> str:
    root = Path(output_dir) if output_dir else Path.cwd()
    root.mkdir(parents=True, exist_ok=True)

    claude_dir = root / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    settings: Dict[str, Any] = {}
    meta = manifest.metadata or {}

    if manifest.model_params:
        settings["model"] = manifest.model_params.model

    if meta.get("permissions_allow") or meta.get("permissions_deny"):
        settings["permissions"] = {}
        if meta.get("permissions_allow"):
            settings["permissions"]["allow"] = meta["permissions_allow"]
        if meta.get("permissions_deny"):
            settings["permissions"]["deny"] = meta["permissions_deny"]

    if meta.get("settings"):
        stored = meta["settings"]
        for k, v in stored.items():
            if k not in settings:
                settings[k] = v

    if not settings.get("$schema"):
        settings["$schema"] = "https://json.schemastore.org/claude-code-settings.json"

    settings_path = claude_dir / "settings.json"
    settings_path.write_text(json.dumps(settings, indent=2))
    print(f"Wrote {settings_path}")

    prompts = manifest.prompts or {}
    if prompts:
        prompt = next(iter(prompts.values()))
        claude_md_path = root / "CLAUDE.md"
        claude_md_path.write_text(prompt.system_prompt)
        print(f"Wrote {claude_md_path}")

    mcp_servers = meta.get("mcp_servers", {})
    if not mcp_servers and manifest.tools:
        mcp_servers = {"mcpServers": {}}
        for name, tool in manifest.tools.items():
            if name.startswith("mcp_") and tool.implementation_ref:
                try:
                    config = json.loads(tool.implementation_ref)
                    mcp_servers["mcpServers"][tool.name] = config
                except json.JSONDecodeError:
                    pass

    if mcp_servers:
        mcp_path = root / ".mcp.json"
        mcp_path.write_text(json.dumps(mcp_servers, indent=2))
        print(f"Wrote {mcp_path}")

    return str(root)


def rollback_claude_code(
    ref: str,
    store: Optional[VersionStore] = None,
    output_dir: Optional[str] = None,
    dry_run: bool = False,
) -> bool:
    if store is None:
        path = Path(DEFAULT_STORE)
        if path.exists() and (path / "index.json").exists():
            store = VersionStore(DEFAULT_STORE)
        else:
            print("Error: no agent-ver store found. Run 'agent-ver init' first.")
            return False

    resolved = store.resolve(ref)
    if not resolved:
        print(f"Error: could not resolve '{ref}'")
        return False

    manifest = store.get_manifest(resolved)
    if not manifest:
        print(f"Error: manifest not found for {resolved}")
        return False

    if not dry_run:
        export_to_claude_code(manifest, output_dir)
        print(f"Rollback to {resolved} (v{manifest.version}) complete")
    else:
        print(f"[DRY RUN] Would rollback to {resolved} (v{manifest.version})")

    return True
