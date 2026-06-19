"""
Structural diff engine for AgentManifest.
Compares two agent config versions and reports meaningful changes.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple


class DiffEntry:
    def __init__(self, path: str, change_type: str, old: Any, new: Any):
        self.path = path
        self.change_type = change_type
        self.old = old
        self.new = new

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "change_type": self.change_type,
            "old": self.old,
            "new": self.new,
        }

    def __repr__(self) -> str:
        return f"[{self.change_type}] {self.path}: {self.old!r} -> {self.new!r}"


SKIP_METADATA_KEYS = {"created_at", "author", "description"}


class ConfigDiff:
    def __init__(self, version_a: str, version_b: str):
        self.version_a = version_a
        self.version_b = version_b
        self.entries: List[DiffEntry] = []

    def add(self, path: str, change_type: str, old: Any, new: Any):
        self.entries.append(DiffEntry(path, change_type, old, new))

    @property
    def has_changes(self) -> bool:
        return len(self.entries) > 0

    @property
    def change_count(self) -> int:
        return len(self.entries)

    @property
    def breaking_changes(self) -> List[DiffEntry]:
        return [e for e in self.entries if e.change_type == "removed"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_a": self.version_a,
            "version_b": self.version_b,
            "entries": [e.to_dict() for e in self.entries],
            "change_count": len(self.entries),
            "has_breaking_changes": len(self.breaking_changes) > 0,
        }

    def summary(self) -> str:
        lines = [f"Diff: {self.version_a} → {self.version_b}"]
        for e in self.entries:
            lines.append(f"  {e}")
        return "\n".join(lines)


def diff_manifests(manifest_a: Any, manifest_b: Any) -> ConfigDiff:
    diff = ConfigDiff(
        getattr(manifest_a, 'version', '?'),
        getattr(manifest_b, 'version', '?')
    )
    _diff_dict("", asdict(manifest_a), asdict(manifest_b), diff)
    return diff


def _diff_dict(
    prefix: str,
    old: Dict[str, Any],
    new: Dict[str, Any],
    diff: ConfigDiff,
):
    all_keys = set(old.keys()) | set(new.keys())
    for key in sorted(all_keys):
        if key in SKIP_METADATA_KEYS:
            continue
        path = f"{prefix}.{key}" if prefix else key
        if key not in old:
            diff.add(path, "added", None, new[key])
        elif key not in new:
            diff.add(path, "removed", old[key], None)
        else:
            old_val, new_val = old[key], new[key]
            if isinstance(old_val, dict) and isinstance(new_val, dict):
                _diff_dict(path, old_val, new_val, diff)
            elif isinstance(old_val, list) and isinstance(new_val, list):
                _diff_list(path, old_val, new_val, diff)
            else:
                if old_val != new_val:
                    if old_val is None or new_val is None:
                        change_type = "modified_added"
                    else:
                        change_type = "modified_changed"
                    diff.add(path, change_type, old_val, new_val)


def _diff_list(prefix: str, old: List, new: List, diff: ConfigDiff):
    max_len = max(len(old), len(new))
    for i in range(max_len):
        path = f"{prefix}[{i}]"
        if i >= len(old):
            diff.add(path, "added", None, new[i])
        elif i >= len(new):
            diff.add(path, "removed", old[i], None)
        elif isinstance(old[i], dict) and isinstance(new[i], dict):
            _diff_dict(path, old[i], new[i], diff)
        elif old[i] != new[i]:
            diff.add(path, "changed", old[i], new[i])
