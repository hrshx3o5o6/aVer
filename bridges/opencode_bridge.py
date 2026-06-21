"""
OpenCode ↔ AgentManifest bridge.
Imports from opencode.json, .opencode/ and exports back.
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
OPENCODE_GLOBAL = Path.home() / ".config" / "opencode" / "opencode.json"
OPENCODE_GLOBAL_DIR = Path.home() / ".config" / "opencode"


def _find_opencode_json(project_root: Optional[Path] = None, local_only: bool = False) -> Optional[Dict[str, Any]]:
    if project_root:
        for name in ("opencode.json", "opencode.jsonc"):
            p = project_root / name
            if p.exists():
                return json.loads(p.read_text())
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        for name in ("opencode.json", "opencode.jsonc"):
            p = parent / name
            if p.exists():
                return json.loads(p.read_text())
    if not local_only and OPENCODE_GLOBAL.exists():
        return json.loads(OPENCODE_GLOBAL.read_text())
    return None


def _find_opencode_dir(project_root: Optional[Path] = None, local_only: bool = False) -> Optional[Path]:
    if project_root:
        d = project_root / ".opencode"
        if d.is_dir():
            return d
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        d = parent / ".opencode"
        if d.is_dir():
            return d
    if not local_only and OPENCODE_GLOBAL_DIR.is_dir():
        return OPENCODE_GLOBAL_DIR
    return None


def _read_md_files(directory: Path, subdir: str) -> Dict[str, str]:
    result = {}
    d = directory / subdir
    if d.is_dir():
        for f in sorted(d.iterdir()):
            if f.suffix == ".md":
                result[f.stem] = f.read_text()
    return result


def import_from_opencode(
    config_path: Optional[str] = None,
    opencode_dir: Optional[str] = None,
    project_root: Optional[str] = None,
    store: Optional[VersionStore] = None,
    version: str = "1.0.0",
    environment: str = "current",
    commit_message: str = "Imported from OpenCode config",
    local_only: bool = False,
) -> Optional[AgentManifest]:
    root = Path(project_root) if project_root else None

    config: Dict[str, Any] = {}
    if config_path:
        c = _read_json(Path(config_path))
        if c:
            config = c
    else:
        c = _find_opencode_json(root, local_only=local_only)
        if c:
            config = c

    if not config:
        return None

    opencode_path: Optional[Path] = None
    if opencode_dir:
        opencode_path = Path(opencode_dir)
    else:
        opencode_path = _find_opencode_dir(root, local_only=local_only)

    model_name = config.get("model", "")
    small_model = config.get("small_model", "")

    model_params = ModelParams(
        model=model_name,
    )

    prompts: Dict[str, PromptConfig] = {}

    instructions = config.get("instructions", [])
    if isinstance(instructions, list) and instructions:
        combined = "\n\n".join(instructions)
        prompts["default"] = PromptConfig(
            system_prompt=combined,
            role="default",
        )

    agents_config = config.get("agent", {})
    if isinstance(agents_config, dict):
        for agent_name, agent_cfg in agents_config.items():
            if isinstance(agent_cfg, dict):
                agent_prompt = agent_cfg.get("prompt", "")
                if agent_prompt:
                    prompts[agent_name] = PromptConfig(
                        system_prompt=agent_prompt,
                        role=agent_name,
                    )

    tools: Dict[str, ToolDefinition] = {}
    mcp_config = config.get("mcp", {})
    if isinstance(mcp_config, dict):
        for name, mcp in mcp_config.items():
            if isinstance(mcp, dict):
                tools[f"mcp_{name}"] = ToolDefinition(
                    name=name,
                    description=f"MCP server: {name}",
                    input_schema={"type": "object", "properties": {}},
                    implementation_ref=json.dumps(mcp) if mcp else None,
                    enabled=mcp.get("enabled", True),
                )

    tools_config = config.get("tools", {})
    if isinstance(tools_config, dict):
        for tool_name, enabled in tools_config.items():
            tools[f"builtin_{tool_name}"] = ToolDefinition(
                name=tool_name,
                description=f"Builtin tool: {tool_name}",
                input_schema={"type": "object", "properties": {}},
                enabled=bool(enabled) if isinstance(enabled, bool) else True,
            )

    agent_files: Dict[str, str] = {}
    command_files: Dict[str, str] = {}
    if opencode_path:
        agent_files = _read_md_files(opencode_path, "agents")
        command_files = _read_md_files(opencode_path, "commands")

    for agent_name, content in agent_files.items():
        if agent_name not in prompts:
            prompts[agent_name] = PromptConfig(
                system_prompt=content,
                role=agent_name,
            )

    manifest = AgentManifest(
        name="opencode-agent",
        framework=FrameworkType.OPENCODE,
        version=version,
        environment=environment,
        model_params=model_params,
        prompts=prompts or None,
        tools=tools or None,
        metadata={
            "config": config,
            "opencode_dir": str(opencode_path) if opencode_path else None,
            "small_model": small_model,
            "agent_files": list(agent_files.keys()),
            "command_files": list(command_files.keys()),
        },
    )

    if not config and not prompts and not tools:
        return None

    if store:
        h = store.commit(
            manifest,
            message=commit_message or "Imported from OpenCode config",
            tags=["opencode-import"],
            author="agent-ver-import",
        )
        store.pin_environment(environment, h)

    return manifest


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def export_to_opencode(
    manifest: AgentManifest,
    output_dir: Optional[str] = None,
) -> str:
    root = Path(output_dir) if output_dir else Path.cwd()
    root.mkdir(parents=True, exist_ok=True)

    config: Dict[str, Any] = {}
    config["$schema"] = "https://opencode.ai/config.json"

    if manifest.model_params:
        config["model"] = manifest.model_params.model

    meta = manifest.metadata or {}
    if meta.get("small_model"):
        config["small_model"] = meta["small_model"]

    prompts = manifest.prompts or {}
    if prompts:
        instructions = []
        agents_config: Dict[str, Any] = {}
        for name, prompt in prompts.items():
            if name == "default":
                instructions.append(prompt.system_prompt)
            else:
                agents_config[name] = {
                    "description": f"Agent: {name}",
                    "prompt": prompt.system_prompt,
                }
        if instructions:
            config["instructions"] = instructions
        if agents_config:
            config["agent"] = agents_config

    tools: Dict[str, Any] = {}
    tools_config: Dict[str, Any] = {}
    if manifest.tools:
        for name, tool in manifest.tools.items():
            if name.startswith("mcp_") and tool.implementation_ref:
                try:
                    tools[tool.name] = json.loads(tool.implementation_ref)
                except json.JSONDecodeError:
                    pass
            elif name.startswith("builtin_"):
                tools_config[tool.name] = tool.enabled

    if tools:
        config["mcp"] = tools
    if tools_config:
        config["tools"] = tools_config

    existing = meta.get("config", {})
    for k, v in existing.items():
        if k not in config and k != "$schema":
            config[k] = v

    config_path = root / "opencode.json"
    config_path.write_text(json.dumps(config, indent=2))
    print(f"Wrote {config_path}")

    opencode_dir = root / ".opencode"
    if prompts:
        agents_dir = opencode_dir / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        for name, prompt in prompts.items():
            agent_path = agents_dir / f"{name}.md"
            agent_path.write_text(prompt.system_prompt)
            print(f"Wrote {agent_path}")

    return str(root)


def rollback_opencode(
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
        export_to_opencode(manifest, output_dir)
        print(f"Rollback to {resolved} (v{manifest.version}) complete")
    else:
        print(f"[DRY RUN] Would rollback to {resolved} (v{manifest.version})")

    return True
