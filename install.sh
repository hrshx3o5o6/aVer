#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/hrshx3o5o6/aVer.git"
TAG="${1:-main}"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: curl -fsSL https://github.com/you/aver/raw/main/install.sh | bash"
    echo "       curl -fsSL https://github.com/you/aver/raw/main/install.sh | bash -s v0.1.0"
    echo ""
    echo "Installs 'aver' — version control for AI agent configurations."
    echo "Requires Python 3.10+ and pipx (installed automatically if missing)."
    exit 0
fi

echo "==> Checking Python version..."
if ! command -v python3 &>/dev/null; then
    echo "Error: Python 3.10+ required but not found." >&2
    exit 1
fi

echo "==> Ensuring pipx is available..."
if ! command -v pipx &>/dev/null; then
    echo "  pipx not found. Installing..."
    if command -v brew &>/dev/null; then
        brew install pipx
    elif command -v apt &>/dev/null; then
        sudo apt update && sudo apt install -y pipx
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y pipx
    else
        python3 -m pip install --user pipx
    fi
    python3 -m pipx ensurepath
    echo "  pipx installed. You may need to restart your shell for PATH changes."
fi

echo "==> Installing aver from $REPO ($TAG)..."
TMP_DIR=$(mktemp -d)
git clone --depth=1 --branch "$TAG" "$REPO" "$TMP_DIR" 2>/dev/null || {
    echo "Warning: tag '$TAG' not found, cloning default branch..."
    git clone --depth=1 "$REPO" "$TMP_DIR"
}

pipx install "$TMP_DIR"
rm -rf "$TMP_DIR"

echo ""
echo "  ✅ aver installed!"
echo ""
echo "  Quick start:"
echo "    aver init              Initialize a new store"
echo "    aver import            Import config from a framework"
echo "    aver import hermes     Import Hermes config directly"
echo "    aver status            Show store status"
echo "    aver --help            Show all commands"
