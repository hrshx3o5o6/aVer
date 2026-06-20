"""
Runtime client for loading agent configs from the version store.
Agent runtimes can import this to fetch their config by environment or tag.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from manifest import AgentManifest
from version_store import VersionStore


_STORE_PATH = os.environ.get("AGENT_VER_STORE", ".agent-ver")


def _get_store() -> Optional[VersionStore]:
    path = Path(_STORE_PATH)
    if path.exists() and (path / "index.json").exists():
        return VersionStore(str(path))
    return None


def load_config(
    env: Optional[str] = None,
    tag: Optional[str] = None,
    ref: Optional[str] = None,
    agent_name: Optional[str] = None,
) -> Optional[AgentManifest]:
    store = _get_store()
    if not store:
        return None

    resolved = None
    if ref:
        resolved = store.resolve(ref)
    elif tag:
        resolved = store.resolve(tag)
    elif env:
        resolved = store.get_environment_version(env)

    if not resolved:
        return None

    manifest = store.get_manifest(resolved)
    if agent_name and manifest and manifest.name != agent_name:
        return None

    return manifest


def load_config_dict(
    env: Optional[str] = None,
    tag: Optional[str] = None,
    ref: Optional[str] = None,
    agent_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    manifest = load_config(env=env, tag=tag, ref=ref, agent_name=agent_name)
    if manifest:
        return manifest.to_dict()
    return None


def get_prompts(
    env: Optional[str] = None,
    tag: Optional[str] = None,
    agent_name: Optional[str] = None,
) -> Dict[str, str]:
    manifest = load_config(env=env, tag=tag, agent_name=agent_name)
    if not manifest:
        return {}
    return {name: p.system_prompt for name, p in manifest.prompts.items()}


def get_tools(
    env: Optional[str] = None,
    tag: Optional[str] = None,
    agent_name: Optional[str] = None,
) -> Dict[str, Any]:
    manifest = load_config(env=env, tag=tag, agent_name=agent_name)
    if not manifest:
        return {}
    return {name: t.__dict__ for name, t in manifest.tools.items()}


def get_model_params(
    env: Optional[str] = None,
    tag: Optional[str] = None,
    agent_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    manifest = load_config(env=env, tag=tag, agent_name=agent_name)
    if not manifest or not manifest.model_params:
        return None
    return manifest.model_params.__dict__


def get_system_prompt(
    prompt_key: str = "system",
    env: Optional[str] = None,
    tag: Optional[str] = None,
    agent_name: Optional[str] = None,
) -> Optional[str]:
    manifest = load_config(env=env, tag=tag, agent_name=agent_name)
    if not manifest or prompt_key not in manifest.prompts:
        return None
    return manifest.prompts[prompt_key].system_prompt


def set_store_path(path: str):
    global _STORE_PATH
    _STORE_PATH = path
