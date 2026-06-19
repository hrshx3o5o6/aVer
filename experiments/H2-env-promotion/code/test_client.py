"""
Test runtime client integration with version store.
"""
import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.manifest import AgentManifest, FrameworkType, ModelParams, PromptConfig, ToolDefinition
from src.version_store import VersionStore
from src.client import set_store_path, load_config, get_system_prompt, get_model_params, get_tools


def test_runtime_client():
    print("=" * 60)
    print("Runtime Client Integration Test")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        store = VersionStore(tmpdir)
        store._save_index()

        manifest = AgentManifest(
            name="my-agent",
            framework=FrameworkType.CLAUDE_CODE,
            version="1.0.0",
            environment="prod",
            description="Test agent",
            model_params=ModelParams(model="claude-sonnet-4", temperature=0.3, max_tokens=4096),
            prompts={
                "system": PromptConfig(system_prompt="You are a helpful assistant."),
                "summary": PromptConfig(system_prompt="Summarize this text."),
            },
            tools={
                "search": ToolDefinition(
                    name="web_search",
                    description="Search the web",
                    input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
                ),
            },
        )

        h = store.commit(manifest, message="Initial", tags=["v1"])
        store.pin_environment("prod", h)
        store.pin_environment("dev", h)

        set_store_path(tmpdir)

        loaded = load_config(env="prod")
        assert loaded is not None
        assert loaded.name == "my-agent"
        assert loaded.framework == FrameworkType.CLAUDE_CODE
        print(f"  ✓ load_config(env='prod') — name={loaded.name}, framework={loaded.framework.value}")

        prompt = get_system_prompt("system", env="prod")
        assert prompt == "You are a helpful assistant."
        print(f"  ✓ get_system_prompt('system') — '{prompt[:40]}...'")

        params = get_model_params(env="prod")
        assert params is not None
        assert params["model"] == "claude-sonnet-4"
        assert params["temperature"] == 0.3
        print(f"  ✓ get_model_params() — model={params['model']}, temp={params['temperature']}")

        tools = get_tools(env="prod")
        assert "search" in tools
        assert tools["search"]["description"] == "Search the web"
        print(f"  ✓ get_tools() — {len(tools)} tool(s) loaded")

        loaded_dev = load_config(env="dev")
        assert loaded_dev is not None
        print(f"  ✓ load_config(env='dev') — works with multiple environments")

        loaded_tag = load_config(tag="v1")
        assert loaded_tag is not None
        print(f"  ✓ load_config(tag='v1') — tag resolution works")

        print(f"\n{'=' * 60}")
        print("All client tests passed ✓")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    test_runtime_client()
