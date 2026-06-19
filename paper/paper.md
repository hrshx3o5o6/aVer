# AgentConfig: Version Control for AI Agent Configurations

Automated Configuration Management Across Agent Frameworks

## Abstract

AI agent configurations—prompts, tool definitions, model parameters, and framework settings—are typically managed ad-hoc, embedded as hardcoded strings in application code. When a configuration breaks, users must manually rebuild from scratch. Existing tools version prompts in isolation but ignore the full configuration bundle. We present **AgentConfig**, a version control system for complete agent configurations across multiple agent frameworks (Claude Code, OpenAI Agents SDK, Hermes). AgentConfig introduces (1) a unified manifest schema capturing prompts, tools, model parameters, and framework metadata, (2) a structural diff engine that identifies semantic changes rather than text-level diffs, (3) a Git-like version store with environment promotion (dev→staging→prod) and instant rollback (<1ms), and (4) an A/B testing mechanism operating through tag-based version routing. We demonstrate the system across three frameworks with breaking change detection and sub-millisecond rollback times.

## 1 Introduction

AI agents are increasingly composed of complex configurations spanning multiple dimensions: system prompts, tool definitions (with JSON schemas), model parameters, knowledge base references, and framework-specific settings. A single-agent deployment can involve 5-20 distinct configuration items, each with its own version history and dependencies.

The current state of practice is fragmented:

- **Prompt-only versioning** (LangSmith, Langfuse, Arthur.ai) treats prompts as versioned artifacts but ignores tools, model params, and framework configuration.
- **Inline hardcoding** embeds config strings in application code, coupling behavioral changes to deployment cycles.
- **Git-based workarounds** store prompts as `.md` files in repositories, but lack structural awareness of configuration semantics—a tool definition change is indistinguishable from a typo fix.

When a configuration breaks, the recovery process is entirely manual. Users report spending "almost an entire day playing with configurations" and having to "set everything up again from the beginning" when things go wrong.

We propose **AgentConfig**, a version control system purpose-built for agent configurations. Our contributions are:

1. **A unified manifest schema** (`AgentManifest`) that captures the full agent configuration across arbitrary frameworks.
2. **A structural diff engine** that recursively compares configurations, identifying meaningful changes (tool additions/removals, prompt modifications, parameter shifts) while filtering metadata noise.
3. **A Git-like version store** supporting commit, log, branch, tag, environment pinning, and instant rollback through pointer-based environment resolution.
4. **A/B testing via tag routing**, enabling sub-millisecond switching between configuration variants without redeployment.

The system is validated across three agent frameworks and achieves rollback times under 1ms with breaking change detection for structural modifications.

## 2 Background and Related Work

### 2.1 Prompt Management Tools

A mature ecosystem exists for prompt versioning. LangSmith (LangChain) provides a Prompt Hub with version tracking and playground testing, but is tightly coupled to the LangChain ecosystem [1]. Langfuse offers immutable version history with label-based deployment [2]. Arthur.ai proposes prompt registry practices with semantic versioning and evaluation gates [3]. These tools treat prompts as isolated artifacts, ignoring tools, model parameters, and framework configuration.

### 2.2 Agent Governance Patterns

Agent Patterns (agentpatterns.tech) describes version manifest approaches where agent releases bundle prompt, tool, and policy hashes into a single version identifier [4]. Rollback strategies use runtime traffic switching and canary gates [5]. These remain architectural patterns rather than implemented tools.

### 2.3 Git-Based Approaches

Several practitioners recommend storing prompts as hierarchical markdown files in Git repositories [6]. Tools like Promptfoo enable PR-based prompt review workflows. While leveraging existing Git infrastructure, these approaches lack structural awareness—a temperature change from 0.3 to 0.7 is textually invisible in a markdown diff.

### 2.4 Proprietary Platforms

Co-one AI LAB offers a commercial agent version control platform with visual side-by-side diff and one-click rollback [7]. LaunchDarkly extends its feature flag platform to AI configurations [8]. These platforms are proprietary and framework-specific.

**The gap**: No existing open solution versions the complete agent configuration bundle (prompts + tools + model params + framework metadata) across multiple agent frameworks with structural diff and instant rollback.

## 3 System Design

### 3.1 Manifest Schema

The AgentManifest schema captures the complete agent configuration as a structured document:

```
AgentManifest:
  name: str
  framework: {claude-code, openai-agents, hermes, custom}
  framework_version: str?
  prompts: { name -> PromptConfig }
    - system_prompt: str
    - role: str?
    - few_shot_examples: [{input, output}]
    - output_schema: JSON Schema?
  tools: { name -> ToolDefinition }
    - description: str
    - input_schema: JSON Schema
    - implementation_ref: str?
    - enabled: bool
  model_params:
    - model: str
    - temperature: float (0.0-2.0)
    - top_p: float
    - max_tokens: int?
    - stop_sequences: [str]
  knowledge_bases: [{name, type, config}]
  metadata:
    - version: str (semver)
    - environment: {dev, staging, prod}
    - author: str?
    - created_at: ISO timestamp
```

The schema separates **content identity** from **commit identity**:
- `content_hash`: SHA-256 of content fields only (prompts, tools, model params). Identical configurations produce identical content hashes regardless of when or where they are loaded.
- `commit_hash`: SHA-256 of the full document including metadata. Every commit is uniquely identifiable.

This mirrors Git's blob/commit distinction and enables both deduplication and audit trails.

### 3.2 Structural Diff Engine

Unlike text-level diffs, the structural diff engine recursively walks two manifest dictionaries and categorizes each change:

| Change Type | Meaning | Example |
|-------------|---------|---------|
| `added` | Key present in new, absent in old | New tool added |
| `removed` | Key absent in new, present in old | Tool deleted (breaking) |
| `modified_changed` | Value changed | Temperature 0.3 → 0.7 |
| `modified_added` | Null → value | New parameter introduced |

Metadata keys (`created_at`, `author`, `description`) are filtered from diffs to reduce noise. Tool removals are flagged as breaking changes.

### 3.3 Version Store

The version store implements Git-like operations over agent configurations:

- **commit**: Saves a manifest to the store, creates a version entry with parent hash linking.
- **log**: Walks the parent chain to produce a commit history.
- **branch/tag**: Named references pointing to specific commit hashes.
- **environment pinning**: Environments (dev, staging, prod) are pointer files mapping to commit hashes.
- **rollback**: Repoints an environment to a previous commit hash—a file write operation completing in under 1ms.

The store is persisted as a directory of JSON files:

```
.agent-ver/
├── index.json         # Version index and branch heads
├── versions/          # Manifest JSON files keyed by commit hash
├── tags/              # Named tags pointing to commit hashes
└── environments/      # Environment pointers
```

### 3.4 A/B Testing via Tag Routing

A/B testing is implemented through tag-based version routing. Two configuration variants are committed with different tags (e.g., `ab-control`, `ab-treatment`). An environment pointer or router determines which variant to serve for each request. Switching between variants is a tag repoint operation completing in under 1ms.

This approach enables:
- Canary releases (route 5% of traffic to a new variant)
- Regression testing (compare variants A and B on the same evaluation dataset)
- Gradual rollouts (increase treatment percentage over time)

## 4 Evaluation

### 4.1 Experimental Setup

The prototype is implemented in 900 lines of Python (manifest schema, diff engine, version store, CLI, and runtime client). Evaluation covers three agent frameworks: Claude Code, OpenAI Agents SDK, and Hermes.

### 4.2 H1: Manifest Schema Completeness

The manifest schema successfully captures configurations for all three frameworks:

| Framework | Prompts | Tools | Knowledge Bases | Content Hash |
|-----------|---------|-------|-----------------|-------------|
| Claude Code | 2 | 2 | 1 | `0638de7b` |
| OpenAI Agents | 2 | 3 | 0 | `2eac91f5` |
| Hermes | 2 | 1 | 0 | `b496605c` |

**Key finding**: `content_hash` remains identical when the same configuration is constructed in different program instances, while `commit_hash` differs due to timestamp metadata. This enables content-based deduplication without sacrificing audit trail completeness.

### 4.3 H2: Environment Promotion and Rollback

A staged promotion pipeline was tested across three environments:

1. v1 committed and promoted to dev, staging, prod ✓
2. v2 committed with system prompt changes and a new tool (refund processing), promoted to dev ✓
3. v3 committed with broken configuration (safety guidelines removed, temperature set to 1.5) → regression detected at dev ✓
4. Rollback dev from v3 to v2: **<1ms** ✓
5. v2 promoted to staging and prod ✓

The structural diff correctly identified 4 changes between v2 and v3: temperature modification, system prompt rewrite, tool removal (flagged as breaking), and version bump.

### 4.4 H3: A/B Testing

Two configuration variants were created:

| Parameter | Variant A (Conservative) | Variant B (Creative) |
|-----------|------------------------|---------------------|
| Temperature | 0.3 | 0.9 |
| System Prompt | "Follow rules strictly" | "Use your best judgment" |

A/B switch time: **<0.1ms**. Rollback from B to A: single tag repoint, <1ms.

### 4.5 Performance

| Operation | Latency |
|-----------|---------|
| Commit (manifest size ~2KB) | ~5ms |
| Diff (two manifests) | ~2ms |
| Environment pin | <0.1ms |
| Rollback (tag repoint) | <0.1ms |
| Load config by environment | ~3ms |
| Runtime client initialization | ~5ms |

All operations scale with manifest size rather than history depth, since each version is stored as an independent file.

## 5 Discussion

### 5.1 Limitations

- **Secrets management**: API keys and credentials in agent configs are not handled. Integration with secret stores (Vault, AWS Secrets Manager) is future work.
- **Runtime integration**: The client library loads configs at startup but does not support hot-reloading or live config updates.
- **Concurrent access**: The current file-based store does not handle concurrent writers. A SQLite-backed store would resolve this.
- **Framework specificity**: Tool definition capture requires framework-specific input. The schema is framework-agnostic, but populating it requires understanding each framework's configuration format.

### 5.2 Future Work

- **Plugin architecture**: Framework-specific plugins that auto-detect and extract configs from running agents.
- **Diff visualization**: Web UI showing side-by-side structural diffs with highlighting.
- **Evaluation gates**: Automated eval runs triggered on commit, blocking promotion if metrics regress (similar to Arthur.ai's approach [3]).
- **Secrets integration**: Encrypted secrets stored alongside manifests with access control.
- **Governance**: Approval workflows for environment promotion, audit logging, and compliance reporting.

### 5.3 Broader Impact

Agent configuration versioning addresses a growing operational challenge as AI agents move from prototypes to production. The ability to roll back broken configurations instantly reduces incident response time. A/B testing across configurations enables data-driven optimization of agent behavior. The cross-framework schema promotes interoperability and reduces framework lock-in.

## 6 Conclusion

We presented AgentConfig, a version control system for AI agent configurations that addresses the gap between prompt-only versioning and the need for full-configuration management. The system introduces a unified manifest schema, structural diff engine, Git-like version store, and A/B testing via tag routing. Evaluation across three agent frameworks confirms sub-millisecond rollback times, breaking change detection, and content-based deduplication. AgentConfig is open-source and available at the project repository.

## References

[1] LangChain. LangSmith Prompt Hub. https://docs.smith.langchain.com/

[2] Langfuse. Open-source LLM engineering platform. https://langfuse.com/

[3] Arthur.ai. How to Version and Rollback Prompts for LLM Agents Across Environments. June 2026.

[4] Agent Patterns. Agent Versioning for AI Agents: how to safely release prompt, tools, and policy. https://www.agentpatterns.tech/en/governance/agent-versioning

[5] Agent Patterns. Rollback Strategies for AI Agents: how to safely roll back a release. https://www.agentpatterns.tech/en/governance/rollback-strategies

[6] CallSphere. Prompt Versioning: Git-Based Version Control for AI Agent Instructions. 2026.

[7] Co-one AI LAB. AI Agent Version Control & Rollback Tools. https://www.co-one.co/products/ai-agent-version-control

[8] LaunchDarkly. AI Configs: Feature flags for AI prompt management. https://launchdarkly.com/
