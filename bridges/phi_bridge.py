"""
Phi (phi-code) ↔ AgentManifest bridge.
Imports from ~/.phi/agent/settings.json, ~/.phi/agent/agents/*.md and exports back.
"""
from __future__ import annotations

import json
import os
import re
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
PHI_DIR = Path.home() / ".phi" / "agent"


def _parse_agent_md(content: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    frontmatch = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
    if frontmatch:
        fm = frontmatch.group(1)
        body = frontmatch.group(2).strip()
        for line in fm.split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                result[k.strip()] = v.strip()
        result["body"] = body
    else:
        result["body"] = content.strip()
    return result


def import_from_phi(
    settings_path: Optional[str] = None,
    agents_dir: Optional[str] = None,
    models_path: Optional[str] = None,
    store: Optional[VersionStore] = None,
    version: str = "1.0.0",
    environment: str = "current",
    commit_message: str = "Imported from Phi config",
) -> Optional[AgentManifest]:
    settings: Dict[str, Any] = {}
    if settings_path:
        p = Path(settings_path)
        if p.exists():
            settings = json.loads(p.read_text())
    else:
        p = PHI_DIR / "settings.json"
        if p.exists():
            settings = json.loads(p.read_text())

    if not settings:
        print("No Phi settings found")
        return None

    models: Dict[str, Any] = {}
    if models_path:
        p = Path(models_path)
        if p.exists():
            models = json.loads(p.read_text())
    else:
        p = PHI_DIR / "models.json"
        if p.exists():
            models = json.loads(p.read_text())

    phi_agents_dir: Optional[Path] = None
    if agents_dir:
        phi_agents_dir = Path(agents_dir)
    elif PHI_DIR.is_dir():
        phi_agents_dir = PHI_DIR / "agents"
        if not phi_agents_dir.is_dir():
            phi_agents_dir = PHI_DIR

    routing: Dict[str, Any] = {}
    routing_path = PHI_DIR / "routing.json"
    if routing_path.exists():
        routing = json.loads(routing_path.read_text())

    model_name = settings.get("model", settings.get("defaultModel", ""))
    model_params = ModelParams(
        model=model_name,
    )

    prompts: Dict[str, PromptConfig] = {}
    if phi_agents_dir and phi_agents_dir.is_dir():
        for f in sorted(phi_agents_dir.iterdir()):
            if f.suffix == ".md":
                parsed = _parse_agent_md(f.read_text())
                agent_name = parsed.get("name", f.stem)
                body = parsed.get("body", "")
                if body:
                    prompts[agent_name] = PromptConfig(
                        system_prompt=body,
                        role=agent_name,
                    )

    default_prompt = settings.get("prompt", settings.get("systemPrompt", ""))
    if default_prompt and "default" not in prompts:
        prompts["default"] = PromptConfig(
            system_prompt=default_prompt,
            role="default",
        )

    tools: Dict[str, ToolDefinition] = {}
    for name, prompt_cfg in prompts.items():
        parsed = _parse_agent_md(prompt_cfg.system_prompt[:500])
        tool_str = parsed.get("tools", "")
        if tool_str:
            for t in tool_str.replace(",", " ").split():
                t = t.strip()
                if t:
                    key = f"phi_{t}"
                    if key not in tools:
                        tools[key] = ToolDefinition(
                            name=t,
                            description=f"Phi tool: {t}",
                            input_schema={"type": "object", "properties": {}},
                        )

    manifest = AgentManifest(
        name="phi-agent",
        framework=FrameworkType.PHI,
        version=version,
        environment=environment,
        model_params=model_params,
        prompts=prompts or None,
        tools=tools or None,
        metadata={
            "settings": settings,
            "models": models,
            "routing": routing,
            "agent_count": len(prompts),
        },
    )

    if store:
        h = store.commit(
            manifest,
            message=commit_message or "Imported from Phi config",
            tags=["phi-import"],
            author="agent-ver-import",
        )
        store.pin_environment(environment, h)

    return manifest


def export_to_phi(
    manifest: AgentManifest,
    output_dir: Optional[str] = None,
) -> str:
    output = Path(output_dir) if output_dir else PHI_DIR
    output.mkdir(parents=True, exist_ok=True)
    (output / "agents").mkdir(parents=True, exist_ok=True)

    agents_dir = output / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    settings: Dict[str, Any] = {}
    meta = manifest.metadata or {}
    if meta.get("settings"):
        settings = dict(meta["settings"])

    if manifest.model_params:
        settings["model"] = manifest.model_params.model

    prompts = manifest.prompts or {}
    for name, prompt in prompts.items():
        has_frontmatter = re.match(r"^---\s*\n", prompt.system_prompt)
        if not has_frontmatter:
            tool_names = []
            if manifest.tools:
                tool_names = [t.name for t in manifest.tools.values() if not t.name.startswith("mcp_")]
            tool_str = ", ".join(tool_names)
            content = f"---\nname: {name}\ndescription: Agent {name}\nmodel: default\ntools: {tool_str}\n---\n\n{prompt.system_prompt}"
        else:
            content = prompt.system_prompt
        agent_path = agents_dir / f"{name}.md"
        agent_path.write_text(content)
        print(f"Wrote {agent_path}")

    if settings:
        settings_path = output / "settings.json"
        settings_path.write_text(json.dumps(settings, indent=2))
        print(f"Wrote {settings_path}")

    return str(output)


def rollback_phi(
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
        export_to_phi(manifest, output_dir)
        print(f"Rollback to {resolved} (v{manifest.version}) complete")
    else:
        print(f"[DRY RUN] Would rollback to {resolved} (v{manifest.version})")

    return True
