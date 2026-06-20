"""
Interactive menus for agent-ver CLI.
Drop-in helpers — zero deps, just print + input.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional


DETECT_MAP: Dict[str, str] = {
    "Hermes": "hermes",
    "Claude Code": "claude-code",
    "OpenCode": "opencode",
    "Zen": "zen",
    "Phi": "phi",
}


def auto_detect_import() -> Optional[str]:
    cwd = Path.cwd()
    home = Path.home()

    checks: List[Tuple[str, List[Path]]] = [
        ("Hermes", [home / ".hermes" / "config.yaml"]),
        ("Claude Code", [cwd / ".claude" / "settings.json", cwd / "CLAUDE.md", cwd / ".mcp.json",
                         home / ".claude" / "settings.json"]),
        ("OpenCode", [cwd / "opencode.json", cwd / "opencode.jsonc",
                      home / ".config" / "opencode" / "opencode.json"]),
        ("Zen", [cwd / "zenflow.yaml", cwd / "zenflow.yml",
                 cwd / ".zenflow" / "settings.json", cwd / "zenagents.json"]),
        ("Phi", [home / ".phi" / "agent" / "settings.json"]),
    ]
    found: List[str] = []
    for name, paths in checks:
        if any(p.exists() for p in paths):
            found.append(name)

    if not found:
        return None
    if len(found) == 1:
        return DETECT_MAP[found[0]]

    print("  Detected multiple configs:", ", ".join(found))
    return None


FRAMEWORK_NAMES: Dict[str, str] = {
    "hermes": "Hermes (~/.hermes/config.yaml)",
    "claude-code": "Claude Code (.claude/settings.json + CLAUDE.md + .mcp.json)",
    "opencode": "OpenCode (opencode.json + .opencode/)",
    "zen": "Zen (zenflow.yaml / .zenflow/)",
    "phi": "Phi (~/.phi/agent/)",
}

EXPORT_FORMATS: Dict[str, str] = {
    "hermes": "export-hermes",
    "claude-code": "export-claude-code",
    "opencode": "export-opencode",
    "zen": "export-zen",
    "phi": "export-phi",
}
