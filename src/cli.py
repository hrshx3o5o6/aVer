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

from .manifest import AgentManifest, FrameworkType
from .version_store import VersionStore


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


def main():
    parser = argparse.ArgumentParser(description="Agent configuration versioning tool")
    sub = parser.add_subparsers(dest="command")

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

    return cmd_map[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
