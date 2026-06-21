"""
Interactive menus for agent-ver CLI.
Drop-in helpers — zero deps, just print + input.
Works cross-platform (macOS, Linux, WSL, Windows).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple


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


def _getch() -> str:
    """Read a single keypress without waiting for Enter. Cross-platform."""
    if sys.platform == "win32":
        import msvcrt
        return msvcrt.getch().decode("utf-8", errors="replace")
    else:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                more = sys.stdin.read(2)
                ch += more
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def commit_picker(frameworks: List[Dict]) -> List[str]:
    """Show an interactive picker to select which frameworks to snapshot.

    Args:
        frameworks: list of dicts with keys: key, label, detected (bool)

    Returns:
        List of selected framework keys (e.g. ["hermes", "opencode"])
    """
    if not sys.stdin.isatty():
        return [fw["key"] for fw in frameworks if fw.get("detected")]

    state = [fw.get("detected", False) for fw in frameworks]
    idx = 0

    FRAME_TOP = f"  Select frameworks to snapshot (↑↓: move, SPACE: toggle, ENTER: confirm, q: all)"
    FRAME_FMT = "  {mark} {label}"
    _hide_cursor = "\x1b[?25l"
    _show_cursor = "\x1b[?25h"

    def render():
        lines = [FRAME_TOP, ""]
        for i, fw in enumerate(frameworks):
            mark = "\x1b[7m" + ("[✓]" if state[i] else "[ ]") + "\x1b[0m" if i == idx else ("[✓]" if state[i] else "[ ]")
            note = "" if fw.get("detected") else " (no config found in current directory)"
            label = fw["label"]
            sel = " \x1b[7m>\x1b[0m" if i == idx else "  "
            lines.append(f"  {sel} {mark} {label}{note}")
        lines.append("")
        lines.append(f"  Selected: {sum(state)}/{len(state)}  |  q = select all")
        sys.stdout.write("\x1b[J" + "\n".join(lines))
        sys.stdout.flush()

    sys.stdout.write(_hide_cursor)
    try:
        while True:
            sys.stdout.write("\x1b[H")
            render()
            ch = _getch()
            if ch == "\r" or ch == "\n":
                break
            elif ch == "q":
                state = [True] * len(state)
                break
            elif ch == " ":
                state[idx] = not state[idx]
            elif ch == "\x1b[A" and idx > 0:
                idx -= 1
            elif ch == "\x1b[B" and idx < len(state) - 1:
                idx += 1
    finally:
        sys.stdout.write(_show_cursor + "\x1b[J")

    return [frameworks[i]["key"] for i, s in enumerate(state) if s]


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
