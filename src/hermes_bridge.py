"""
Hermes ↔ AgentManifest bridge.
Imports Hermes config.yaml into AgentManifest and exports back.
"""
from __future__ import annotations

import copy
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:
    yaml = None

from .manifest import (
    AgentManifest,
    FrameworkType,
    ModelParams,
    PromptConfig,
    ToolDefinition,
)
from .version_store import VersionStore


HERMES_CONFIG = Path.home() / ".hermes" / "config.yaml"
HERMES_ENV = Path.home() / ".hermes" / ".env"
DEFAULT_STORE = ".agent-ver"


def import_from_hermes(
    config_path: Optional[str] = None,
    env_path: Optional[str] = None,
    store: Optional[VersionStore] = None,
    version: str = "1.0.0",
    environment: str = "current",
    commit_message: str = "Imported from Hermes config",
) -> Optional[AgentManifest]:
    if yaml is None:
        raise ImportError("pyyaml is required. Install with: pip install pyyaml")

    config_path = config_path or str(HERMES_CONFIG)
    if not os.path.exists(config_path):
        print(f"Hermes config not found at {config_path}")
        return None

    with open(config_path) as f:
        hermes = yaml.safe_load(f)

    if not hermes:
        print("Empty Hermes config")
        return None

    env_map = {}
    env_path = env_path or str(HERMES_ENV)
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_map[k.strip()] = v.strip()

    model = hermes.get("model", {})
    agent = hermes.get("agent", {})

    model_params = ModelParams(
        model=model.get("default", ""),
        max_tokens=model.get("max_tokens"),
    )

    prompts = {}
    personalities = agent.get("personalities", {})
    for name, prompt_text in personalities.items():
        prompts[name] = PromptConfig(
            system_prompt=prompt_text,
            role=name,
        )

    tools = {}
    disabled = set(agent.get("disabled_toolsets", []))

    mcp_servers = hermes.get("mcp_servers", {})
    for name, mcp in mcp_servers.items():
        tools[f"mcp_{name}"] = ToolDefinition(
            name=name,
            description=f"MCP server: {name}",
            input_schema={"type": "object", "properties": {}},
            implementation_ref=yaml.dump(mcp).strip() if mcp else None,
            enabled=name not in disabled,
        )

    for toolset_name, toolset_list in hermes.get("platform_toolsets", {}).items():
        for tool_name in toolset_list:
            tools[f"platform_{tool_name}"] = ToolDefinition(
                name=tool_name,
                description=f"Platform tool: {tool_name} ({toolset_name})",
                input_schema={"type": "object", "properties": {"toolset": {"type": "string", "default": toolset_name}}},
                enabled=f"platform:{tool_name}" not in disabled,
            )

    manifest = AgentManifest(
        name="hermes-agent",
        framework=FrameworkType.HERMES,
        framework_version=hermes.get("version", "unknown"),
        version=version,
        environment=environment,
        model_params=model_params,
        prompts=prompts,
        tools=tools or None,
        metadata={
            "model_provider": model.get("provider", "auto"),
            "model_base_url": model.get("base_url", ""),
            "agent_max_turns": agent.get("max_turns", 60),
            "agent_reasoning_effort": agent.get("reasoning_effort", "medium"),
            "agent_verbose": agent.get("verbose", False),
            "security_approval_mode": hermes.get("security", {}).get(
                "approval_mode", "smart"
            ),
            "terminal_backend": hermes.get("terminal", {}).get("backend", "local"),
            "terminal_timeout": hermes.get("terminal", {}).get("timeout", 180),
            "memory_enabled": hermes.get("memory", {}).get("memory_enabled", True),
            "streaming": hermes.get("streaming", {}).get("enabled", False),
            "delegation_max_iterations": hermes.get("delegation", {}).get(
                "max_iterations", 50
            ),
            "delegation_orchestrator": hermes.get("delegation", {}).get(
                "orchestrator_enabled", True
            ),
            "compression_enabled": hermes.get("compression", {}).get("enabled", True),
            "compression_threshold": hermes.get("compression", {}).get("threshold", 0.5),
            "compression_target_ratio": hermes.get("compression", {}).get("target_ratio", 0.2),
            "compression_protect_last_n": hermes.get("compression", {}).get("protect_last_n", 20),
            "secrets_defined": list(env_map.keys()) if env_map else [],
            "config_path": config_path,
            "env_path": env_path,
        },
    )

    if store:
        h = store.commit(
            manifest,
            message=commit_message or "Imported from Hermes config",
            tags=["hermes-import"],
            author="agent-ver-import",
        )
        store.pin_environment(environment, h)
        print(f"Committed: {h}")
        print(f"Pinned '{environment}' → {h}")

    return manifest


def export_to_hermes(
    manifest: AgentManifest,
    output_path: Optional[str] = None,
) -> str:
    if yaml is None:
        raise ImportError("pyyaml is required. Install with: pip install pyyaml")

    hermes: Dict[str, Any] = {}

    hermes["model"] = {
        "default": manifest.model_params.model if manifest.model_params else "",
        "max_tokens": manifest.model_params.max_tokens if manifest.model_params else None,
    }

    meta = manifest.metadata or {}
    if "model_provider" in meta:
        hermes["model"]["provider"] = meta["model_provider"]
    if meta.get("model_base_url"):
        hermes["model"]["base_url"] = meta["model_base_url"]

    hermes["agent"] = {
        "personalities": {
            name: p.system_prompt
            for name, p in manifest.prompts.items()
        },
        "max_turns": meta.get("agent_max_turns", 60),
        "reasoning_effort": meta.get("agent_reasoning_effort", "medium"),
        "verbose": meta.get("agent_verbose", False),
    }

    if "security_approval_mode" in meta:
        hermes["security"] = {
            "approval_mode": meta["security_approval_mode"]
        }

    if "terminal_backend" in meta:
        hermes["terminal"] = {
            "backend": meta["terminal_backend"],
            "timeout": meta.get("terminal_timeout", 180),
        }

    if "memory_enabled" in meta:
        hermes["memory"] = {"memory_enabled": meta["memory_enabled"]}

    if "streaming" in meta:
        val = meta["streaming"]
        hermes["streaming"] = {"enabled": val} if isinstance(val, bool) else val

    if "delegation_max_iterations" in meta:
        hermes["delegation"] = {
            "max_iterations": meta["delegation_max_iterations"],
            "orchestrator_enabled": meta.get("delegation_orchestrator", True),
        }

    if "compression_enabled" in meta:
        hermes["compression"] = {
            "enabled": meta["compression_enabled"],
        }
        if "compression_threshold" in meta:
            hermes["compression"]["threshold"] = meta["compression_threshold"]

    mcp_tools = {}
    platform_tools: Dict[str, list] = {}
    for name, tool in (manifest.tools or {}).items():
        if name.startswith("mcp_") and tool.implementation_ref:
            try:
                mcp_tools[tool.name] = yaml.safe_load(tool.implementation_ref)
            except Exception:
                mcp_tools[tool.name] = tool.implementation_ref
        elif name.startswith("platform_"):
            toolset = tool.input_schema.get("properties", {}).get("toolset", {})
            ts_name = toolset.get("default", "cli") if isinstance(toolset, dict) else "cli"
            platform_tools.setdefault(ts_name, []).append(tool.name)
        elif not name.startswith("mcp_") and not name.startswith("platform_"):
            platform_tools.setdefault("cli", []).append(tool.name)

    if mcp_tools:
        hermes["mcp_servers"] = mcp_tools
    if platform_tools:
        hermes["platform_toolsets"] = platform_tools

    output_path = output_path or str(
        HERMES_CONFIG.parent / "config.agent-ver.yaml"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        yaml.dump(hermes, f, default_flow_style=False, sort_keys=False)

    print(f"Exported Hermes config to {output_path}")
    return output_path


def rollback_hermes(
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
        export_to_hermes(manifest, output_path)
        print(f"Rollback to {resolved} (v{manifest.version}) complete")

        output_path = output_path or str(
            HERMES_CONFIG.parent / "config.agent-ver.yaml"
        )
        print(f"\nTo apply: cp {output_path} ~/.hermes/config.yaml")
    else:
        print(f"[DRY RUN] Would rollback to {resolved} (v{manifest.version})")

    return True
