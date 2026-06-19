"""
H1 Experiment: Test agent config manifest across 3 frameworks.
Tests: serialization, deserialization, hashing, diffing, rollback.
"""
import json
import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.manifest import (
    AgentManifest,
    FrameworkType,
    ModelParams,
    PromptConfig,
    ToolDefinition,
    KnowledgeBaseRef,
)
from src.version_store import VersionStore


def make_claude_code_agent():
    return AgentManifest(
        name="research-agent",
        framework=FrameworkType.CLAUDE_CODE,
        framework_version="2.1.182",
        version="1.0.0",
        environment="dev",
        author="researcher",
        description="Autonomous research agent for literature surveys",
        model_params=ModelParams(
            model="claude-sonnet-4-20250514",
            temperature=0.3,
            max_tokens=8192,
            stop_sequences=["</answer>"],
        ),
        prompts={
            "system": PromptConfig(
                system_prompt="You are a research assistant. Search literature, summarize findings, and generate hypotheses.",
                role="research-assistant",
            ),
            "summary": PromptConfig(
                system_prompt="Summarize the following paper in 3-5 sentences.",
                few_shot_examples=[
                    {"input": "...", "output": "This paper proposes..."}
                ],
            ),
        },
        tools={
            "web_search": ToolDefinition(
                name="web_search",
                description="Search the web for papers and articles",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "num_results": {"type": "integer", "default": 10},
                    },
                },
                enabled=True,
            ),
            "read_paper": ToolDefinition(
                name="read_paper",
                description="Read and extract content from a paper URL",
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "format": "uri"},
                    },
                },
                enabled=True,
            ),
        },
        knowledge_bases=[
            KnowledgeBaseRef(
                name="arxiv-index",
                type="vector-store",
                config={"path": "./data/arxiv_index", "top_k": 5},
            )
        ],
    )


def make_openai_agent():
    return AgentManifest(
        name="customer-support-agent",
        framework=FrameworkType.OPENAI_AGENTS,
        framework_version="0.1.0",
        version="1.0.0",
        environment="dev",
        author="team",
        description="Customer support agent with ticket management",
        model_params=ModelParams(
            model="gpt-4o",
            temperature=0.5,
            max_tokens=4096,
        ),
        prompts={
            "system": PromptConfig(
                system_prompt="You are a helpful customer support agent. Be concise and accurate.",
                role="support-agent",
            ),
            "triage": PromptConfig(
                system_prompt="Classify the customer issue: billing, technical, or general.",
                output_schema={
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "enum": ["billing", "technical", "general"]},
                        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                    },
                },
            ),
        },
        tools={
            "search_kb": ToolDefinition(
                name="search_kb",
                description="Search the knowledge base for articles",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                },
            ),
            "create_ticket": ToolDefinition(
                name="create_ticket",
                description="Create a support ticket",
                input_schema={
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"},
                        "issue": {"type": "string"},
                        "priority": {"type": "string"},
                    },
                    "required": ["customer_id", "issue"],
                },
            ),
            "refund_order": ToolDefinition(
                name="refund_order",
                description="Process a refund for an order",
                input_schema={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "amount": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["order_id", "amount"],
                },
            ),
        },
    )


def make_hermes_agent():
    return AgentManifest(
        name="code-review-agent",
        framework=FrameworkType.HERMES,
        framework_version="0.3.0",
        version="1.0.0",
        environment="staging",
        author="dev-team",
        description="Automated code review agent",
        model_params=ModelParams(
            model="hermes-3-70b",
            temperature=0.2,
            max_tokens=2048,
        ),
        prompts={
            "system": PromptConfig(
                system_prompt="Review the following code diff. Check for bugs, style issues, and security vulnerabilities.",
                role="code-reviewer",
            ),
            "security": PromptConfig(
                system_prompt="Focus on security vulnerabilities: injection, XSS, auth bypass, secrets exposure.",
                few_shot_examples=[
                    {
                        "input": "eval(user_input)",
                        "output": "CRITICAL: eval() on user input allows code injection"
                    },
                ],
            ),
        },
        tools={
            "run_linter": ToolDefinition(
                name="run_linter",
                description="Run linter on the codebase",
                input_schema={
                    "type": "object",
                    "properties": {
                        "file_pattern": {"type": "string"},
                        "linter": {"type": "string", "enum": ["ruff", "eslint", "pylint"]},
                    },
                },
            ),
        },
    )


def test_h1():
    results = []

    print("=" * 60)
    print("H1 Experiment: Agent Config Manifest")
    print("=" * 60)

    agents = {
        "Claude Code": make_claude_code_agent(),
        "OpenAI Agents": make_openai_agent(),
        "Hermes": make_hermes_agent(),
    }

    for name, agent in agents.items():
        print(f"\n--- {name} ---")
        print(f"  Version: {agent.version}")
        print(f"  Framework: {agent.framework.value}")
        ch = agent.content_hash()
        print(f"  Content hash: {ch}")
        print(f"  Commit hash: {agent.commit_hash()}")
        print(f"  Prompts: {len(agent.prompts)}")
        print(f"  Tools: {len(agent.tools)}")
        print(f"  Knowledge bases: {len(agent.knowledge_bases)}")
        print(f"  Model: {agent.model_params.model}")
        print(f"  Temp: {agent.model_params.temperature}")

        json_str = agent.to_json()
        restored = AgentManifest.from_json(json_str)
        assert restored.name == agent.name
        assert restored.framework == agent.framework
        assert restored.content_hash() == ch
        assert restored.commit_hash() == agent.commit_hash()
        print(f"  ✓ content_hash and commit_hash stable across serialize→deserialize")

        clone = make_claude_code_agent() if name == "Claude Code" else \
                make_openai_agent() if name == "OpenAI Agents" else make_hermes_agent()
        assert clone.content_hash() == ch, f"Same config → same content_hash"
        assert clone.commit_hash() != agent.commit_hash(), "But different commit_hash (metadata)"
        print(f"  ✓ Same config across instances → same content_hash, different commit_hash")

        results.append({
            "name": name,
            "hash": ch,
            "prompts": len(agent.prompts),
            "tools": len(agent.tools),
            "kb": len(agent.knowledge_bases),
            "model": agent.model_params.model,
        })

    print(f"\n{'=' * 60}")
    print("Version Store Tests")
    print(f"{'=' * 60}")

    with tempfile.TemporaryDirectory() as tmpdir:
        store = VersionStore(tmpdir)

        v1 = make_claude_code_agent()
        h1 = store.commit(v1, message="Initial agent config", tags=["v1.0.0"])
        print(f"  Committed v1: {h1}")

        v2 = make_claude_code_agent()
        v2.version = "1.1.0"
        v2.model_params.temperature = 0.5
        v2.prompts["system"].system_prompt = "You are a research assistant. Be thorough."
        h2 = store.commit(v2, message="Lower temp, improve system prompt")
        print(f"  Committed v2: {h2}")

        diff = store.diff(h1, h2)
        print(f"\n  Diff ({h1} → {h2}):")
        print(f"    Changes: {diff.entries}")
        print(f"    Breaking: {diff.breaking_changes}")

        store.pin_environment("production", h2)
        print(f"\n  Pinned production → {h2}")

        rolled_back = store.rollback("production", h1)
        print(f"  Rollback production → {rolled_back}")
        assert store.get_environment_version("production") == h1
        print(f"  ✓ Production is now at {h1}")

        log = store.log("main")
        print(f"\n  Log entries: {len(log)}")
        for entry in log:
            print(f"    [{entry.hash[:8]}] {entry.message}")

    print(f"\n{'=' * 60}")
    print("RESULTS SUMMARY")
    print(f"{'=' * 60}")
    for r in results:
        print(f"  {r['name']}: hash={r['hash'][:8]}, "
              f"prompts={r['prompts']}, tools={r['tools']}, model={r['model']}")
    print("\nAll tests passed ✓")
    return results


if __name__ == "__main__":
    test_h1()
