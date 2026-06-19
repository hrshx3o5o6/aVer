"""
Agent Configuration Manifest Schema.
Captures the full agent configuration for versioning, diff, and rollback.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class FrameworkType(str, Enum):
    CLAUDE_CODE = "claude-code"
    OPENAI_AGENTS = "openai-agents"
    HERMES = "hermes"
    CUSTOM = "custom"


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    implementation_ref: Optional[str] = None
    enabled: bool = True


@dataclass
class ModelParams:
    model: str
    temperature: float = 0.7
    top_p: float = 1.0
    max_tokens: Optional[int] = None
    stop_sequences: List[str] = field(default_factory=list)


@dataclass
class PromptConfig:
    system_prompt: str
    role: Optional[str] = None
    few_shot_examples: List[Dict[str, str]] = field(default_factory=list)
    output_schema: Optional[Dict[str, Any]] = None


@dataclass
class KnowledgeBaseRef:
    name: str
    type: str
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentManifest:
    name: str
    framework: FrameworkType
    framework_version: Optional[str] = None

    prompts: Dict[str, PromptConfig] = field(default_factory=dict)
    tools: Dict[str, ToolDefinition] = field(default_factory=dict)
    model_params: Optional[ModelParams] = None
    knowledge_bases: List[KnowledgeBaseRef] = field(default_factory=list)

    version: str = "0.1.0"
    environment: str = "dev"
    author: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    description: Optional[str] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    def _content_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        for key in ("version", "environment", "author", "created_at", "description", "metadata"):
            d.pop(key, None)
        return d

    def content_hash(self) -> str:
        return hashlib.sha256(
            json.dumps(self._content_dict(), sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

    def commit_hash(self) -> str:
        return hashlib.sha256(
            json.dumps(asdict(self), sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentManifest":
        framework = FrameworkType(data["framework"])
        prompts = {
            k: PromptConfig(**v) for k, v in data.get("prompts", {}).items()
        }
        tools = {
            k: ToolDefinition(**v) for k, v in data.get("tools", {}).items()
        }
        model_params = (
            ModelParams(**data["model_params"]) if data.get("model_params") else None
        )
        knowledge_bases = [
            KnowledgeBaseRef(**kb) for kb in data.get("knowledge_bases", [])
        ]
        return cls(
            name=data["name"],
            framework=framework,
            framework_version=data.get("framework_version"),
            prompts=prompts,
            tools=tools,
            model_params=model_params,
            knowledge_bases=knowledge_bases,
            version=data.get("version", "0.1.0"),
            environment=data.get("environment", "dev"),
            author=data.get("author"),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            description=data.get("description"),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "AgentManifest":
        return cls.from_dict(json.loads(json_str))
