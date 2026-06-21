"""
Zen (zenflow) ↔ AgentManifest bridge.
Imports from zenflow YAML configs, .zenflow/settings.json and exports back.
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

try:
    import yaml
except ImportError:
    yaml = None


def _find_zenflow_yaml(project_root: Optional[Path] = None, local_only: bool = False) -> Optional[Dict[str, Any]]:
    search_dirs = [project_root] if project_root else []
    search_dirs.append(Path.cwd())
    if not local_only:
        search_dirs.append(Path.home() / ".zenflow")
    for base in search_dirs:
        if base is None:
            continue
        for name in ("zenflow.yaml", "zenflow.yml", ".zenflow/config.yaml", ".zenflow/settings.json", "zenagents.json"):
            p = Path(base) / name
            if p.exists():
                try:
                    if name.endswith(".json"):
                        return json.loads(p.read_text())
                    return yaml.safe_load(p.read_text())
                except Exception:
                    continue
    return None


def _find_zen_agents(project_root: Optional[Path] = None, local_only: bool = False) -> List[Dict[str, Any]]:
    agents = []
    search_dirs = [project_root] if project_root else []
    search_dirs.append(Path.cwd())
    if not local_only:
        search_dirs.append(Path.home() / ".zenflow")
    for base in search_dirs:
        if base is None:
            continue
        agents_dir = base / "agents"
        if agents_dir.is_dir():
            for f in sorted(agents_dir.iterdir()):
                if f.suffix in (".json", ".yaml", ".yml"):
                    try:
                        if f.suffix == ".json":
                            agents.append(json.loads(f.read_text()))
                        elif yaml:
                            agents.append(yaml.safe_load(f.read_text()))
                    except Exception:
                        continue
    return agents


def import_from_zen(
    config_path: Optional[str] = None,
    project_root: Optional[str] = None,
    store: Optional[VersionStore] = None,
    version: str = "1.0.0",
    environment: str = "current",
    commit_message: str = "Imported from Zen/zenflow config",
    local_only: bool = False,
) -> Optional[AgentManifest]:
    root = Path(project_root) if project_root else None

    config: Dict[str, Any] = {}
    if config_path:
        p = Path(config_path)
        if p.exists():
            if p.suffix == ".json":
                config = json.loads(p.read_text())
            elif yaml:
                config = yaml.safe_load(p.read_text())
    else:
        c = _find_zenflow_yaml(root, local_only=local_only)
        if c:
            config = c

    if not config:
        return None

    agent_configs = config.get("agents", config.get("agents", {}))
    if isinstance(agent_configs, list):
        agent_configs = {a.get("name", f"agent-{i}"): a for i, a in enumerate(agent_configs)}

    prompts: Dict[str, PromptConfig] = {}
    tools: Dict[str, ToolDefinition] = {}
    first_model = ""

    for name, agent_cfg in agent_configs.items():
        if isinstance(agent_cfg, dict):
            prompt_text = agent_cfg.get("prompt", agent_cfg.get("instructions", ""))
            if prompt_text:
                prompts[name] = PromptConfig(
                    system_prompt=prompt_text,
                    role=name,
                )

            tool_list = agent_cfg.get("tools", [])
            for tool_name in tool_list:
                if isinstance(tool_name, str):
                    key = f"zen_{tool_name}"
                    if key not in tools:
                        tools[key] = ToolDefinition(
                            name=tool_name,
                            description=f"Zenflow tool: {tool_name}",
                            input_schema={"type": "object", "properties": {}},
                        )

            if not first_model:
                first_model = agent_cfg.get("model", agent_cfg.get("model", ""))

    model_params = ModelParams(
        model=first_model or config.get("model", config.get("model", "")),
    )

    for agent in _find_zen_agents(root, local_only=local_only):
        name = agent.get("name", agent.get("id", "unnamed"))
        if name not in prompts:
            prompt_text = agent.get("prompt", agent.get("instructions", agent.get("system_prompt", "")))
            if prompt_text:
                prompts[name] = PromptConfig(
                    system_prompt=prompt_text,
                    role=name,
                )
        tool_list = agent.get("tools", [])
        for tool_name in tool_list:
            if isinstance(tool_name, str):
                key = f"zen_{tool_name}"
                if key not in tools:
                    tools[key] = ToolDefinition(
                        name=tool_name,
                        description=f"Zen tool: {tool_name}",
                        input_schema={"type": "object", "properties": {}},
                    )

    manifest = AgentManifest(
        name="zen-agent",
        framework=FrameworkType.ZEN,
        version=version,
        environment=environment,
        model_params=model_params,
        prompts=prompts or None,
        tools=tools or None,
        metadata={
            "config": config,
            "agent_count": len(agent_configs) if isinstance(agent_configs, dict) else 0,
        },
    )

    if store:
        h = store.commit(
            manifest,
            message=commit_message or "Imported from Zen/zenflow config",
            tags=["zen-import"],
            author="agent-ver-import",
        )
        store.pin_environment(environment, h)

    return manifest


def export_to_zen(
    manifest: AgentManifest,
    output_path: Optional[str] = None,
) -> str:
    if yaml is None:
        raise ImportError("pyyaml is required. Install with: pip install pyyaml")

    config: Dict[str, Any] = {}

    agents: Dict[str, Any] = {}
    prompts = manifest.prompts or {}
    for name, prompt in prompts.items():
        agent_def: Dict[str, Any] = {
            "description": f"Agent: {name}",
            "prompt": prompt.system_prompt,
        }
        if manifest.model_params:
            agent_def["model"] = manifest.model_params.model
        if manifest.tools:
            agent_def["tools"] = [
                t.name for t in manifest.tools.values() if not t.name.startswith("mcp_")
            ]
        agents[name] = agent_def

    if agents:
        config["agents"] = agents

    if manifest.model_params:
        config["model"] = manifest.model_params.model

    meta = manifest.metadata or {}
    if meta.get("config"):
        stored = meta["config"]
        for k, v in stored.items():
            if k not in config and k != "agents":
                config[k] = v

    output_path = output_path or "zenflow-export.yaml"

    with open(output_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    print(f"Exported Zen config to {output_path}")
    return output_path


def rollback_zen(
    ref: str,
    store: Optional[VersionStore] = None,
    output_path: Optional[str] = None,
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
        export_to_zen(manifest, output_path)
        print(f"Rollback to {resolved} (v{manifest.version}) complete")
    else:
        print(f"[DRY RUN] Would rollback to {resolved} (v{manifest.version})")

    return True
