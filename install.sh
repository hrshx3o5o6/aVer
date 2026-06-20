#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/hrshx3o5o6/aVer.git"
TAG="${1:-main}"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: curl -fsSL https://github.com/hrshx3o5o6/aVer/raw/main/install.sh | bash"
    echo "       curl -fsSL https://github.com/hrshx3o5o6/aVer/raw/main/install.sh | bash -s v0.1.0"
    echo ""
    echo "Installs 'aver' — version control for AI agent configurations."
    echo "Requires Python 3.10+ (pipx installed automatically if missing)."
    echo "Supports: macOS, Linux, WSL"
    exit 0
fi

# --- Python version check ---
echo "==> Checking Python version..."
if ! command -v python3 &>/dev/null; then
    echo "Error: Python 3.10+ required but not found." >&2
    echo "  Install from: https://www.python.org/downloads/" >&2
    exit 1
fi

PY_VER=$(python3 --version 2>&1 | awk '{print $2}')
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || [ "$PY_MAJOR" -eq 3 -a "$PY_MINOR" -lt 10 ]; then
    echo "Error: Python 3.10+ required (found $PY_VER)" >&2
    exit 1
fi
echo "  Found Python $PY_VER"

# --- pipx ---
PIPX_CMD="pipx"
if ! command -v pipx &>/dev/null; then
    echo "==> Installing pipx..."
    if python3 -m pip install --user pipx 2>/dev/null || \
       python3 -m pip install --user --break-system-packages pipx 2>/dev/null; then
        pipx ensurepath 2>/dev/null || true
        # pipx may not be on PATH yet after --user install
        if ! command -v pipx &>/dev/null; then
            if [ -f "$HOME/.local/bin/pipx" ]; then
                PIPX_CMD="$HOME/.local/bin/pipx"
            else
                # fallback: use python module
                PIPX_CMD="python3 -m pipx"
            fi
        fi
        echo "  pipx installed."
    elif command -v brew &>/dev/null; then
        brew install pipx
    elif command -v apt &>/dev/null; then
        sudo apt update -qq && sudo DEBIAN_FRONTEND=noninteractive apt install -y -qq pipx
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y pipx
    elif command -v yum &>/dev/null; then
        sudo yum install -y pipx
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm python-pipx
    elif command -v apk &>/dev/null; then
        sudo apk add py3-pipx
    elif command -v zypper &>/dev/null; then
        sudo zypper install -y python-pipx
    else
        echo "Error: could not install pipx." >&2
        echo "  Try: python3 -m pip install --user pipx" >&2
        exit 1
    fi
    echo "  Done."
fi

# --- git ---
if ! command -v git &>/dev/null; then
    echo "==> Installing git..."
    if command -v apt &>/dev/null; then
        sudo apt update -qq && sudo DEBIAN_FRONTEND=noninteractive apt install -y -qq git
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y git
    elif command -v brew &>/dev/null; then
        brew install git
    else
        echo "Error: git required. Install from: https://git-scm.com/downloads" >&2
        exit 1
    fi
    echo "  Done."
fi

# --- install aver ---
echo "==> Installing aver from $REPO ($TAG)..."
TMP_DIR=$(mktemp -d)
git clone --depth=1 --branch "$TAG" "$REPO" "$TMP_DIR" 2>/dev/null || \
git clone --depth=1 "$REPO" "$TMP_DIR"

$PIPX_CMD install "$TMP_DIR"
rm -rf "$TMP_DIR"

echo ""
echo "  ✓ aver installed!"
echo ""
echo "  Quick start:"
echo "    aver init              Initialize a new store"
echo "    aver import            Import config from a framework"
echo "    aver import hermes     Import Hermes config directly"
echo "    aver status            Show store status"
echo "    aver --help            Show all commands"
