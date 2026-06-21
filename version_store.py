from __future__ import annotations

import json
import os
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

from diff import ConfigDiff, diff_manifests
from manifest import AgentManifest


CLUB_TYPE = "club"


class ClubCommit:
    def __init__(
        self,
        hash: str,
        message: str,
        timestamp: str,
        members: Dict[str, str],
        tags: List[str] = None,
        parent: Optional[str] = None,
    ):
        self.hash = hash
        self.message = message
        self.timestamp = timestamp
        self.members = members
        self.tags = tags or []
        self.parent = parent


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
        self.club_dir = self.store_dir / "club"
        self.index_path = self.store_dir / "index.json"

        self.versions_dir.mkdir(parents=True, exist_ok=True)
        self.tags_dir.mkdir(parents=True, exist_ok=True)
        self.environments_dir.mkdir(parents=True, exist_ok=True)
        self.club_dir.mkdir(parents=True, exist_ok=True)

        self._versions: Dict[str, VersionEntry] = {}
        self._club_commits: Dict[str, ClubCommit] = {}
        self._heads: Dict[str, str] = {"main": None}
        self._load_index()

    def _load_index(self):
        if self.index_path.exists():
            data = json.loads(self.index_path.read_text())
            for v, entry in data.get("versions", {}).items():
                self._versions[v] = VersionEntry(**entry)
            for h, c in data.get("club_commits", {}).items():
                self._club_commits[h] = ClubCommit(**c)
            self._heads = data.get("heads", {"main": None})

    def _save_index(self):
        data = {
            "versions": {v: e.__dict__ for v, e in self._versions.items()},
            "club_commits": {h: c.__dict__ for h, c in self._club_commits.items()},
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
        if version_hash in self._versions:
            self._heads[branch] = version_hash
            self._save_index()
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

    def club_commit(
        self,
        manifests: Dict[str, AgentManifest],
        message: str,
        branch: str = "main",
        tags: List[str] = None,
    ) -> str:
        members: Dict[str, str] = {}
        for fw, m in manifests.items():
            fw_hash = m.commit_hash()
            if fw_hash not in self._versions:
                mpath = self.versions_dir / f"{fw_hash}.json"
                mpath.write_text(m.to_json())
                parent = self._heads.get(branch)
                entry = VersionEntry(
                    version=m.version,
                    hash=fw_hash,
                    manifest_path=str(mpath),
                    message=f"{fw} snapshot",
                    timestamp=datetime.utcnow().isoformat(),
                    parent_hash=parent,
                )
                self._versions[fw_hash] = entry
            members[fw] = fw_hash

        club_id = hashlib.sha256(
            json.dumps(members, sort_keys=True).encode()
        ).hexdigest()[:16]

        if club_id in self._club_commits:
            self._heads[branch] = club_id
            self.pin_environment("current", club_id)
            self._save_index()
            return club_id

        club = ClubCommit(
            hash=club_id,
            message=message,
            timestamp=datetime.utcnow().isoformat(),
            members=members,
            tags=tags or [],
            parent=self._heads.get(branch),
        )

        club_path = self.club_dir / f"{club_id}.json"
        club_path.write_text(json.dumps(club.__dict__, indent=2))

        self._club_commits[club_id] = club
        self._heads[branch] = club_id
        self.pin_environment("current", club_id)

        for tag in (tags or []):
            tag_path = self.tags_dir / tag
            tag_path.write_text(club_id)

        self._save_index()
        return club_id

    def get_club_commit(self, hash: str) -> Optional[ClubCommit]:
        if hash in self._club_commits:
            return self._club_commits[hash]
        club_path = self.club_dir / f"{hash}.json"
        if club_path.exists():
            return ClubCommit(**json.loads(club_path.read_text()))
        return None

    def is_club_commit(self, hash: str) -> bool:
        return hash in self._club_commits or (self.club_dir / f"{hash}.json").exists()

    def get_manifest(self, version_hash: str) -> Optional[AgentManifest]:
        if version_hash not in self._versions:
            return None
        entry = self._versions[version_hash]
        manifest_path = Path(entry.manifest_path)
        if not manifest_path.exists():
            return None
        return AgentManifest.from_json(manifest_path.read_text())

    def get_manifests(self, ref: str) -> Dict[str, AgentManifest]:
        resolved = self.resolve(ref)
        if not resolved:
            return {}
        if self.is_club_commit(resolved):
            club = self.get_club_commit(resolved)
            if not club:
                return {}
            result = {}
            for fw, h in club.members.items():
                m = self.get_manifest(h)
                if m:
                    result[fw] = m
            return result
        m = self.get_manifest(resolved)
        if m:
            return {m.framework.value: m}
        return {}

    def resolve(self, ref: str) -> Optional[str]:
        if ref in self._versions or ref in self._club_commits:
            return ref
        for h in self._club_commits:
            if h.startswith(ref):
                return h
        for h in self._versions:
            if h.startswith(ref):
                return h
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

    def log(self, branch: str = "main", max_count: int = 20) -> List[Union[VersionEntry, ClubCommit]]:
        entries = []
        current = self._heads.get(branch)
        while current and len(entries) < max_count:
            if self.is_club_commit(current):
                club = self.get_club_commit(current)
                if club:
                    entries.append(club)
                    current = club.parent
            else:
                entry = self._versions.get(current)
                if not entry:
                    break
                entries.append(entry)
                current = entry.parent_hash
        return entries

    def log_all(self) -> List[Union[VersionEntry, ClubCommit]]:
        result = list(self._versions.values())
        result.extend(self._club_commits.values())
        return sorted(result, key=lambda e: e.timestamp, reverse=True)
