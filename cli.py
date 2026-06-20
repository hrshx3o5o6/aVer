#!/usr/bin/env python3
"""
agent-ver: CLI for agent configuration versioning.
Supports init, commit, log, diff, deploy, rollback, status.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional

from manifest import AgentManifest, FrameworkType
from version_store import VersionStore
from interactive import auto_detect_import, FRAMEWORK_NAMES, EXPORT_FORMATS


DEFAULT_STORE = ".agent-ver"


def find_store() -> Optional[VersionStore]:
    path = Path(DEFAULT_STORE)
    if path.exists() and (path / "index.json").exists():
        return VersionStore(str(path))
    return None


def cmd_init(args):
    store = VersionStore(DEFAULT_STORE)
    store._save_index()
    print(f"Initialized empty agent-ver store in {DEFAULT_STORE}/")
    return 0


def cmd_commit(args):
    store = find_store()
    if not store:
        print("Error: not an agent-ver store. Run 'agent-ver init' first.", file=sys.stderr)
        return 1

    if not args.file:
        print("Error: --file is required", file=sys.stderr)
        return 1

    manifest_path = Path(args.file)
    if not manifest_path.exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        return 1

    manifest = AgentManifest.from_json(manifest_path.read_text())

    if args.env:
        manifest.environment = args.env
    if args.version:
        manifest.version = args.version

    tags = args.tag.split(",") if args.tag else []
    h = store.commit(manifest, message=args.message, tags=tags, author=args.author)
    print(f"Committed: {h}")
    return 0


def cmd_log(args):
    store = find_store()
    if not store:
        print("Error: not an agent-ver store. Run 'agent-ver init' first.", file=sys.stderr)
        return 1

    entries = store.log(branch=args.branch, max_count=args.count)
    print(f"{'HASH':<20} {'VERSION':<12} {'DATE':<24} {'MESSAGE'}")
    print("-" * 80)
    for e in entries:
        ts = e.timestamp[:19] if e.timestamp else ""
        print(f"{e.hash:<20} {e.version:<12} {ts:<24} {e.message}")
    return 0


def cmd_diff(args):
    store = find_store()
    if not store:
        print("Error: not an agent-ver store. Run 'agent-ver init' first.", file=sys.stderr)
        return 1

    config_diff = store.diff(args.ref_a, args.ref_b)
    if not config_diff:
        print("Error: could not resolve references", file=sys.stderr)
        return 1

    print(f"Diff: {args.ref_a} → {args.ref_b}")
    print(f"Changes: {config_diff.change_count}  Breaking: {len(config_diff.breaking_changes)}")
    print()
    for e in config_diff.entries:
        print(f"  [{e.change_type}] {e.path}")
        if e.old is not None and e.new is not None:
            old_str = str(e.old)[:60]
            new_str = str(e.new)[:60]
            print(f"    - {old_str}")
            print(f"    + {new_str}")
    return 0


def cmd_deploy(args):
    store = find_store()
    if not store:
        print("Error: not an agent-ver store. Run 'agent-ver init' first.", file=sys.stderr)
        return 1

    resolved = store.resolve(args.ref)
    if not resolved:
        print(f"Error: could not resolve '{args.ref}'", file=sys.stderr)
        return 1

    store.pin_environment(args.environment, resolved)
    manifest = store.get_manifest(resolved)
    version = manifest.version if manifest else "?"
    print(f"Deployed {resolved} (v{version}) → environment '{args.environment}'")
    return 0


def cmd_rollback(args):
    store = find_store()
    if not store:
        print("Error: not an agent-ver store. Run 'agent-ver init' first.", file=sys.stderr)
        return 1

    resolved = store.resolve(args.ref)
    if not resolved:
        print(f"Error: could not resolve '{args.ref}'", file=sys.stderr)
        return 1

    current = store.get_environment_version(args.environment)
    rolled = store.rollback(args.environment, resolved)
    if not rolled:
        print(f"Error: rollback failed", file=sys.stderr)
        return 1

    manifest = store.get_manifest(rolled)
    version = manifest.version if manifest else "?"
    print(f"Rollback '{args.environment}': {current or 'none'} → {rolled} (v{version})")
    return 0


def cmd_status(args):
    store = find_store()
    if not store:
        print("Error: not an agent-ver store. Run 'agent-ver init' first.", file=sys.stderr)
        return 1

    envs_dir = Path(DEFAULT_STORE) / "environments"
    print("Environments:")
    if envs_dir.exists():
        for env_file in sorted(envs_dir.iterdir()):
            if env_file.is_file():
                h = env_file.read_text().strip()
                manifest = store.get_manifest(h)
                version = manifest.version if manifest else "?"
                print(f"  {env_file.name:<20} → {h[:12]} (v{version})")

    print(f"\nBranches:")
    for branch, head in store._heads.items():
        if head:
            manifest = store.get_manifest(head)
            version = manifest.version if manifest else "?"
            print(f"  {branch:<20} → {head[:12]} (v{version})")

    print(f"\nTags:")
    tags_dir = Path(DEFAULT_STORE) / "tags"
    if tags_dir.exists():
        for tag_file in sorted(tags_dir.iterdir()):
            if tag_file.is_file():
                h = tag_file.read_text().strip()
                print(f"  {tag_file.name:<20} → {h[:12]}")

    all_versions = store.log_all()
    print(f"\nTotal versions: {len(all_versions)}")
    return 0


def cmd_init_manifest(args):
    name = args.name or "my-agent"
    framework = args.framework or "custom"

    try:
        fw = FrameworkType(framework)
    except ValueError:
        print(f"Error: unknown framework '{framework}'. Options: {[e.value for e in FrameworkType]}",
              file=sys.stderr)
        return 1

    manifest = AgentManifest(
        name=name,
        framework=fw,
        version=args.version or "0.1.0",
        environment=args.env or "dev",
    )

    output = args.output or f"{name}-agent-config.json"
    Path(output).write_text(manifest.to_json())
    print(f"Created manifest: {output}")
    return 0


def cmd_import_hermes(args):
    from bridges.hermes_bridge import import_from_hermes

    store = find_store()
    if not store:
        store = VersionStore(DEFAULT_STORE)
        store._save_index()
        print(f"Auto-initialized agent-ver store")

    manifest = import_from_hermes(
        config_path=args.config,
        store=store,
        version=args.version or "1.0.0",
        environment=args.env or "current",
        commit_message=args.message or "Imported from Hermes config",
    )
    if manifest is None:
        return 1

    # Also export the manifest JSON so user can inspect/edit
    manifest_path = f"hermes-{manifest.version.replace('.', '-')}.json"
    Path(manifest_path).write_text(manifest.to_json())
    print(f"Manifest exported to {manifest_path}")
    print(f"Imported {len(manifest.prompts)} personalities, {len(manifest.tools or {})} tools")
    return 0


def cmd_export_hermes(args):
    from bridges.hermes_bridge import export_to_hermes

    store = find_store()
    if not store:
        print("Error: not an agent-ver store. Run 'agent-ver init' first.", file=sys.stderr)
        return 1

    resolved = store.resolve(args.ref)
    if not resolved:
        print(f"Error: could not resolve '{args.ref}'", file=sys.stderr)
        return 1

    manifest = store.get_manifest(resolved)
    if not manifest:
        print(f"Error: manifest not found for {resolved}", file=sys.stderr)
        return 1

    export_to_hermes(manifest, args.output)
    return 0


def cmd_import_claude_code(args):
    from bridges.claude_code_bridge import import_from_claude_code

    store = find_store()
    if not store:
        store = VersionStore(DEFAULT_STORE)
        store._save_index()
        print(f"Auto-initialized agent-ver store")

    manifest = import_from_claude_code(
        settings_path=args.settings,
        mcp_path=args.mcp,
        claude_md_path=args.claude_md,
        project_root=args.project_root,
        store=store,
        version=args.version or "1.0.0",
        environment=args.env or "current",
        commit_message=args.message or "Imported from Claude Code config",
    )
    if manifest is None:
        return 1

    manifest_path = f"claude-code-{manifest.version.replace('.', '-')}.json"
    Path(manifest_path).write_text(manifest.to_json())
    print(f"Manifest exported to {manifest_path}")
    prompt_count = len(manifest.prompts or {})
    tool_count = len(manifest.tools or {})
    print(f"Imported {prompt_count} prompts, {tool_count} tools")
    return 0


def cmd_export_claude_code(args):
    from bridges.claude_code_bridge import export_to_claude_code

    store = find_store()
    if not store:
        print("Error: not an agent-ver store. Run 'agent-ver init' first.", file=sys.stderr)
        return 1

    resolved = store.resolve(args.ref)
    if not resolved:
        print(f"Error: could not resolve '{args.ref}'", file=sys.stderr)
        return 1

    manifest = store.get_manifest(resolved)
    if not manifest:
        print(f"Error: manifest not found for {resolved}", file=sys.stderr)
        return 1

    export_to_claude_code(manifest, args.output_dir)
    return 0


def cmd_import_opencode(args):
    from bridges.opencode_bridge import import_from_opencode

    store = find_store()
    if not store:
        store = VersionStore(DEFAULT_STORE)
        store._save_index()
        print(f"Auto-initialized agent-ver store")

    manifest = import_from_opencode(
        config_path=args.config,
        opencode_dir=args.opencode_dir,
        project_root=args.project_root,
        store=store,
        version=args.version or "1.0.0",
        environment=args.env or "current",
        commit_message=args.message or "Imported from OpenCode config",
    )
    if manifest is None:
        return 1

    manifest_path = f"opencode-{manifest.version.replace('.', '-')}.json"
    Path(manifest_path).write_text(manifest.to_json())
    print(f"Manifest exported to {manifest_path}")
    print(f"Imported {len(manifest.prompts or {})} prompts, {len(manifest.tools or {})} tools")
    return 0


def cmd_export_opencode(args):
    from bridges.opencode_bridge import export_to_opencode

    store = find_store()
    if not store:
        print("Error: not an agent-ver store. Run 'agent-ver init' first.", file=sys.stderr)
        return 1

    resolved = store.resolve(args.ref)
    if not resolved:
        print(f"Error: could not resolve '{args.ref}'", file=sys.stderr)
        return 1

    manifest = store.get_manifest(resolved)
    if not manifest:
        print(f"Error: manifest not found for {resolved}", file=sys.stderr)
        return 1

    export_to_opencode(manifest, args.output_dir)
    return 0


def cmd_import_zen(args):
    from bridges.zen_bridge import import_from_zen

    store = find_store()
    if not store:
        store = VersionStore(DEFAULT_STORE)
        store._save_index()
        print(f"Auto-initialized agent-ver store")

    manifest = import_from_zen(
        config_path=args.config,
        project_root=args.project_root,
        store=store,
        version=args.version or "1.0.0",
        environment=args.env or "current",
        commit_message=args.message or "Imported from Zen config",
    )
    if manifest is None:
        return 1

    manifest_path = f"zen-{manifest.version.replace('.', '-')}.json"
    Path(manifest_path).write_text(manifest.to_json())
    print(f"Manifest exported to {manifest_path}")
    print(f"Imported {len(manifest.prompts or {})} agent prompts, {len(manifest.tools or {})} tools")
    return 0


def cmd_export_zen(args):
    from bridges.zen_bridge import export_to_zen

    store = find_store()
    if not store:
        print("Error: not an agent-ver store. Run 'agent-ver init' first.", file=sys.stderr)
        return 1

    resolved = store.resolve(args.ref)
    if not resolved:
        print(f"Error: could not resolve '{args.ref}'", file=sys.stderr)
        return 1

    manifest = store.get_manifest(resolved)
    if not manifest:
        print(f"Error: manifest not found for {resolved}", file=sys.stderr)
        return 1

    export_to_zen(manifest, args.output)
    return 0


def cmd_import_phi(args):
    from bridges.phi_bridge import import_from_phi

    store = find_store()
    if not store:
        store = VersionStore(DEFAULT_STORE)
        store._save_index()
        print(f"Auto-initialized agent-ver store")

    manifest = import_from_phi(
        settings_path=args.settings,
        agents_dir=args.agents_dir,
        models_path=args.models,
        store=store,
        version=args.version or "1.0.0",
        environment=args.env or "current",
        commit_message=args.message or "Imported from Phi config",
    )
    if manifest is None:
        return 1

    manifest_path = f"phi-{manifest.version.replace('.', '-')}.json"
    Path(manifest_path).write_text(manifest.to_json())
    print(f"Manifest exported to {manifest_path}")
    print(f"Imported {len(manifest.prompts or {})} prompts, {len(manifest.tools or {})} tools")
    return 0


def cmd_export_phi(args):
    from bridges.phi_bridge import export_to_phi

    store = find_store()
    if not store:
        print("Error: not an agent-ver store. Run 'agent-ver init' first.", file=sys.stderr)
        return 1

    resolved = store.resolve(args.ref)
    if not resolved:
        print(f"Error: could not resolve '{args.ref}'", file=sys.stderr)
        return 1

    manifest = store.get_manifest(resolved)
    if not manifest:
        print(f"Error: manifest not found for {resolved}", file=sys.stderr)
        return 1

    export_to_phi(manifest, args.output_dir)
    return 0


def cmd_import_interactive(args):

    frameworks = [
        ("hermes", FRAMEWORK_NAMES["hermes"], lambda: None),
        ("claude-code", FRAMEWORK_NAMES["claude-code"], lambda: None),
        ("opencode", FRAMEWORK_NAMES["opencode"], lambda: None),
        ("zen", FRAMEWORK_NAMES["zen"], lambda: None),
        ("phi", FRAMEWORK_NAMES["phi"], lambda: None),
    ]

    detected = auto_detect_import()
    if detected:
        print(f"\n  → Detected: {detected}")
        frameworks.insert(0, ("auto", f"Auto-detect → {detected}", lambda: None))

    store = find_store()
    if not store:
        store = VersionStore(DEFAULT_STORE)
        store._save_index()
        print(f"  Auto-initialized agent-ver store")

    choice = _interactive_select("Which framework are you importing from?", frameworks)
    if choice is None or choice == "q":
        print("  Cancelled.")
        return 1

    env = input("  Environment name [current]: ").strip() or "current"
    v = input("  Version [1.0.0]: ").strip() or "1.0.0"

    fw_key = "auto" if choice == "auto" else choice
    _run_import(fw_key, env, v, store)
    return 0


def _interactive_select(prompt: str, items: list, cancel: bool = True):
    items = list(items)
    if cancel:
        items.append(("q", "Cancel", lambda: None))
    print(f"\n  {prompt}")
    print(f"  {'-' * len(prompt)}")
    for i, (key, desc, _) in enumerate(items, 1):
        if key == "q":
            continue
        print(f"    {i}) {desc}")
    if cancel:
        print(f"    q) Cancel")
    while True:
        raw = input("\n  Choice: ").strip().lower()
        if cancel and raw == "q":
            return "q"
        try:
            idx = int(raw) - 1
            valid = [it for it in items if it[0] != "q"]
            if 0 <= idx < len(valid):
                return valid[idx][0]
        except (ValueError, IndexError):
            pass
        print("  Invalid choice.", file=sys.stderr)


def _run_import(framework_key: str, env: str, version: str, store):
    if framework_key == "auto":
        framework_key = auto_detect_import()
        if not framework_key:
            print("  Nothing detected.")
            return

    from bridges.hermes_bridge import import_from_hermes
    from bridges.claude_code_bridge import import_from_claude_code
    from bridges.opencode_bridge import import_from_opencode
    from bridges.zen_bridge import import_from_zen
    from bridges.phi_bridge import import_from_phi

    imports = {
        "hermes": ("Hermes", lambda: import_from_hermes(store=store, version=version, environment=env)),
        "claude-code": ("Claude Code", lambda: import_from_claude_code(store=store, version=version, environment=env)),
        "opencode": ("OpenCode", lambda: import_from_opencode(store=store, version=version, environment=env)),
        "zen": ("Zen", lambda: import_from_zen(store=store, version=version, environment=env)),
        "phi": ("Phi", lambda: import_from_phi(store=store, version=version, environment=env)),
    }

    name, fn = imports.get(framework_key.lower(), (None, None))
    if not fn:
        print(f"  Unknown framework: {framework_key}")
        return

    print(f"\n  → Importing {name} config...")
    manifest = fn()
    if manifest:
        print(f"  → Done! {len(manifest.prompts or {})} prompts, {len(manifest.tools or {})} tools imported")


def cmd_export_interactive(args):
    ref = args.ref

    store = find_store()
    if not store:
        print("Error: no agent-ver store found.")
        return 1

    resolved = store.resolve(ref)
    if not resolved:
        print(f"Error: could not resolve '{ref}'")
        return 1

    manifest = store.get_manifest(resolved)
    if not manifest:
        print(f"Error: manifest not found for {resolved}")
        return 1

    formats = [
        ("hermes", "Hermes (YAML config)", lambda: None),
        ("claude-code", "Claude Code (.claude/settings.json + CLAUDE.md + .mcp.json)", lambda: None),
        ("opencode", "OpenCode (opencode.json + .opencode/)", lambda: None),
        ("zen", "Zen (YAML workflow)", lambda: None),
        ("phi", "Phi (agents/*.md + settings.json)", lambda: None),
    ]

    fw_guess = manifest.framework.value if manifest.framework else None
    guess_label = EXPORT_FORMATS.get(fw_guess, "")
    print(f"\n  Exporting v{manifest.version} ({manifest.name})")

    choice = _interactive_select("Export to which format?", formats)
    if choice is None or choice == "q":
        print("  Cancelled.")
        return 1

    from bridges.hermes_bridge import export_to_hermes
    from bridges.claude_code_bridge import export_to_claude_code
    from bridges.opencode_bridge import export_to_opencode
    from bridges.zen_bridge import export_to_zen
    from bridges.phi_bridge import export_to_phi

    exporters = {
        "hermes": lambda: export_to_hermes(manifest),
        "claude-code": lambda: export_to_claude_code(manifest),
        "opencode": lambda: export_to_opencode(manifest),
        "zen": lambda: export_to_zen(manifest),
        "phi": lambda: export_to_phi(manifest),
    }

    fn = exporters.get(choice)
    if fn:
        result = fn()
        print(f"  → Exported to {result}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Agent configuration versioning tool")
    sub = parser.add_subparsers(dest="command")

    import_help = "Import config (interactive, or specify: hermes, claude-code, opencode, zen, phi)"
    p_import = sub.add_parser("import", help=import_help,
                               description="Import agent config from any supported framework. "
                                           "With no framework argument, runs interactive mode. "
                                           "Usage: aver import  (interactive) / aver import hermes  (direct)")
    import_sub = p_import.add_subparsers(dest="import_framework")

    ih = import_sub.add_parser("hermes", help="Import from Hermes config")
    ih.add_argument("--config", default=None, help="Path to Hermes config.yaml")
    ih.add_argument("--version", "-v", default="1.0.0", help="Version tag")
    ih.add_argument("--env", "-e", default="current", help="Environment name")
    ih.add_argument("--message", "-m", default="Imported from Hermes config", help="Commit message")

    icc = import_sub.add_parser("claude-code", help="Import from Claude Code config")
    icc.add_argument("--settings", default=None, help="Path to settings.json")
    icc.add_argument("--mcp", default=None, help="Path to .mcp.json")
    icc.add_argument("--claude-md", default=None, help="Path to CLAUDE.md")
    icc.add_argument("--project-root", default=None, help="Project root directory")
    icc.add_argument("--version", "-v", default="1.0.0", help="Version tag")
    icc.add_argument("--env", "-e", default="current", help="Environment name")
    icc.add_argument("--message", "-m", default="Imported from Claude Code config", help="Commit message")

    ioc = import_sub.add_parser("opencode", help="Import from OpenCode config")
    ioc.add_argument("--config", default=None, help="Path to opencode.json")
    ioc.add_argument("--opencode-dir", default=None, help="Path to .opencode directory")
    ioc.add_argument("--project-root", default=None, help="Project root directory")
    ioc.add_argument("--version", "-v", default="1.0.0", help="Version tag")
    ioc.add_argument("--env", "-e", default="current", help="Environment name")
    ioc.add_argument("--message", "-m", default="Imported from OpenCode config", help="Commit message")

    iz = import_sub.add_parser("zen", help="Import from Zen/zenflow config")
    iz.add_argument("--config", default=None, help="Path to zenflow.yaml or settings.json")
    iz.add_argument("--project-root", default=None, help="Project root directory")
    iz.add_argument("--version", "-v", default="1.0.0", help="Version tag")
    iz.add_argument("--env", "-e", default="current", help="Environment name")
    iz.add_argument("--message", "-m", default="Imported from Zen config", help="Commit message")

    ip = import_sub.add_parser("phi", help="Import from Phi config")
    ip.add_argument("--settings", default=None, help="Path to settings.json")
    ip.add_argument("--agents-dir", default=None, help="Path to agents directory")
    ip.add_argument("--models", default=None, help="Path to models.json")
    ip.add_argument("--version", "-v", default="1.0.0", help="Version tag")
    ip.add_argument("--env", "-e", default="current", help="Environment name")
    ip.add_argument("--message", "-m", default="Imported from Phi config", help="Commit message")

    export_help = "Export version (interactive, or specify: hermes, claude-code, opencode, zen, phi)"
    p_export = sub.add_parser("export", help=export_help,
                               description="Export version to native config files. "
                                           "Usage: aver export <ref>  (interactive) / aver export <ref> hermes  (direct)")
    p_export.add_argument("ref", help="Ref to export (hash, tag, or environment)")
    export_sub = p_export.add_subparsers(dest="export_framework")

    eh = export_sub.add_parser("hermes", help="Export to Hermes YAML config")
    eh.add_argument("--output", "-o", default=None, help="Output path")

    ecc = export_sub.add_parser("claude-code", help="Export to Claude Code config files")
    ecc.add_argument("--output-dir", "-o", default=None, help="Output directory")

    eoc = export_sub.add_parser("opencode", help="Export to OpenCode config files")
    eoc.add_argument("--output-dir", "-o", default=None, help="Output directory")

    ez = export_sub.add_parser("zen", help="Export to Zen YAML config")
    ez.add_argument("--output", "-o", default=None, help="Output path")

    ep = export_sub.add_parser("phi", help="Export to Phi config files")
    ep.add_argument("--output-dir", "-o", default=None, help="Output directory")

    p_init = sub.add_parser("init", help="Initialize agent-ver store")

    p_commit = sub.add_parser("commit", help="Commit an agent config manifest")
    p_commit.add_argument("--file", "-f", required=True, help="Path to manifest JSON file")
    p_commit.add_argument("--message", "-m", default="commit", help="Commit message")
    p_commit.add_argument("--tag", "-t", help="Comma-separated tags")
    p_commit.add_argument("--author", "-a", help="Author name")
    p_commit.add_argument("--version", help="Override version string")
    p_commit.add_argument("--env", help="Override environment")

    p_log = sub.add_parser("log", help="Show commit log")
    p_log.add_argument("--branch", default="main", help="Branch name")
    p_log.add_argument("--count", "-n", type=int, default=20, help="Max entries")

    p_diff = sub.add_parser("diff", help="Diff two versions")
    p_diff.add_argument("ref_a", help="First ref (hash, tag, branch, or env)")
    p_diff.add_argument("ref_b", help="Second ref")

    p_deploy = sub.add_parser("deploy", help="Deploy a version to an environment")
    p_deploy.add_argument("environment", help="Environment name (dev, staging, prod)")
    p_deploy.add_argument("ref", help="Ref to deploy (hash, tag)")

    p_rollback = sub.add_parser("rollback", help="Rollback an environment to a version")
    p_rollback.add_argument("environment", help="Environment name")
    p_rollback.add_argument("ref", help="Target ref for rollback")

    p_status = sub.add_parser("status", help="Show store status")

    p_gen = sub.add_parser("init-manifest", help="Generate a new agent config manifest")
    p_gen.add_argument("--name", "-n", help="Agent name")
    p_gen.add_argument("--framework", "-f", choices=[e.value for e in FrameworkType],
                       default="custom", help="Agent framework")
    p_gen.add_argument("--version", "-v", default="0.1.0", help="Initial version")
    p_gen.add_argument("--env", "-e", default="dev", help="Environment")
    p_gen.add_argument("--output", "-o", help="Output file path")



    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "import":
        if args.import_framework:
            return _run_import_framework(args)
        return cmd_import_interactive(args)

    if args.command == "export":
        if args.export_framework:
            return _run_export_framework(args)
        return cmd_export_interactive(args)

    cmd_map = {
        "init": cmd_init,
        "commit": cmd_commit,
        "log": cmd_log,
        "diff": cmd_diff,
        "deploy": cmd_deploy,
        "rollback": cmd_rollback,
        "status": cmd_status,
        "init-manifest": cmd_init_manifest,
    }

    fn = cmd_map.get(args.command)
    if not fn:
        print(f"Error: unknown command '{args.command}'", file=sys.stderr)
        return 1
    return fn(args)


def _run_import_framework(args):
    fw = args.import_framework
    import_fns = {
        "hermes": cmd_import_hermes,
        "claude-code": cmd_import_claude_code,
        "opencode": cmd_import_opencode,
        "zen": cmd_import_zen,
        "phi": cmd_import_phi,
    }
    fn = import_fns.get(fw)
    if not fn:
        print(f"Error: unknown framework '{fw}'", file=sys.stderr)
        return 1
    return fn(args)


def _run_export_framework(args):
    fw = args.export_framework
    export_fns = {
        "hermes": cmd_export_hermes,
        "claude-code": cmd_export_claude_code,
        "opencode": cmd_export_opencode,
        "zen": cmd_export_zen,
        "phi": cmd_export_phi,
    }
    fn = export_fns.get(fw)
    if not fn:
        print(f"Error: unknown framework '{fw}'", file=sys.stderr)
        return 1
    return fn(args)


if __name__ == "__main__":
    sys.exit(main())
