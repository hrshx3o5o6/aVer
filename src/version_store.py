"""
Version store: manages agent config versions with Git-like operations.
Provides commit, log, diff, rollback, and branch semantics.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .diff import ConfigDiff, diff_manifests
from .manifest import AgentManifest


class VersionEntry:
    def __init__(
        self,
        version: str,
        hash: str,
        manifest_path: str,
        message: str,
        timestamp: str,
        author: Optional[str] = None,
        parent_hash: Optional[str] = None,
        tags: List[str] = None,
    ):
        self.version = version
        self.hash = hash
        self.manifest_path = manifest_path
        self.message = message
        self.timestamp = timestamp
        self.author = author
        self.parent_hash = parent_hash
        self.tags = tags or []


class VersionStore:
    def __init__(self, store_dir: str):
        self.store_dir = Path(store_dir)
        self.versions_dir = self.store_dir / "versions"
        self.tags_dir = self.store_dir / "tags"
        self.environments_dir = self.store_dir / "environments"
        self.index_path = self.store_dir / "index.json"

        self.versions_dir.mkdir(parents=True, exist_ok=True)
        self.tags_dir.mkdir(parents=True, exist_ok=True)
        self.environments_dir.mkdir(parents=True, exist_ok=True)

        self._versions: Dict[str, VersionEntry] = {}
        self._heads: Dict[str, str] = {"main": None}
        self._load_index()

    def _load_index(self):
        if self.index_path.exists():
            data = json.loads(self.index_path.read_text())
            for v, entry in data.get("versions", {}).items():
                self._versions[v] = VersionEntry(**entry)
            self._heads = data.get("heads", {"main": None})

    def _save_index(self):
        data = {
            "versions": {v: entry.__dict__ for v, entry in self._versions.items()},
            "heads": self._heads,
        }
        self.index_path.write_text(json.dumps(data, indent=2))

    def commit(
        self,
        manifest: AgentManifest,
        message: str,
        branch: str = "main",
        tags: List[str] = None,
        author: Optional[str] = None,
    ) -> str:
        version_hash = manifest.commit_hash()
        content_hash = manifest.content_hash()

        if version_hash in self._versions:
            return version_hash

        manifest_path = self.versions_dir / f"{version_hash}.json"
        manifest_path.write_text(manifest.to_json())

        parent_hash = self._heads.get(branch)
        entry = VersionEntry(
            version=manifest.version,
            hash=version_hash,
            manifest_path=str(manifest_path),
            message=message,
            timestamp=datetime.utcnow().isoformat(),
            author=author or manifest.author,
            parent_hash=parent_hash,
            tags=tags or [],
        )

        self._versions[version_hash] = entry
        self._heads[branch] = version_hash

        for tag in (tags or []):
            tag_path = self.tags_dir / tag
            tag_path.write_text(version_hash)

        self._save_index()
        return version_hash

    def get_manifest(self, version_hash: str) -> Optional[AgentManifest]:
        if version_hash not in self._versions:
            return None
        entry = self._versions[version_hash]
        manifest_path = Path(entry.manifest_path)
        if not manifest_path.exists():
            return None
        return AgentManifest.from_json(manifest_path.read_text())

    def resolve(self, ref: str) -> Optional[str]:
        if ref in self._versions:
            return ref
        if ref in self._heads:
            return self._heads[ref]
        tag_path = self.tags_dir / ref
        if tag_path.exists():
            return tag_path.read_text().strip()
        env_path = self.environments_dir / ref
        if env_path.exists():
            return env_path.read_text().strip()
        return None

    def pin_environment(self, env: str, version_hash: str):
        env_path = self.environments_dir / env
        env_path.write_text(version_hash)

    def get_environment_version(self, env: str) -> Optional[str]:
        env_path = self.environments_dir / env
        if env_path.exists():
            return env_path.read_text().strip()
        return None

    def rollback(self, env: str, target_ref: str) -> Optional[str]:
        target_hash = self.resolve(target_ref)
        if target_hash is None:
            return None
        self.pin_environment(env, target_hash)
        return target_hash

    def diff(self, ref_a: str, ref_b: str) -> Optional[ConfigDiff]:
        hash_a = self.resolve(ref_a)
        hash_b = self.resolve(ref_b)
        if not hash_a or not hash_b:
            return None
        ma = self.get_manifest(hash_a)
        mb = self.get_manifest(hash_b)
        if not ma or not mb:
            return None
        return diff_manifests(ma, mb)

    def log(self, branch: str = "main", max_count: int = 20) -> List[VersionEntry]:
        entries = []
        current = self._heads.get(branch)
        while current and len(entries) < max_count:
            entry = self._versions.get(current)
            if not entry:
                break
            entries.append(entry)
            current = entry.parent_hash
        return entries

    def log_all(self) -> List[VersionEntry]:
        return sorted(
            self._versions.values(),
            key=lambda e: e.timestamp,
            reverse=True,
        )
