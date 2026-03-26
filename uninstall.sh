#!/usr/bin/env bash
# geo-photo-renamer uninstaller
# Usage: curl -fsSL https://raw.githubusercontent.com/airrickdunfield/geo-photo-renamer/main/uninstall.sh | bash

set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
    BOLD="\033[1m"; GREEN="\033[32m"; YELLOW="\033[33m"; RED="\033[31m"; RESET="\033[0m"
else
    BOLD=""; GREEN=""; YELLOW=""; RED=""; RESET=""
fi

info()    { echo -e "${GREEN}[geo-rename]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[geo-rename]${RESET} $*"; }
error()   { echo -e "${RED}[geo-rename] ERROR:${RESET} $*" >&2; exit 1; }
heading() { echo -e "\n${BOLD}$*${RESET}"; }

# ── Find Python ───────────────────────────────────────────────────────────────
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        if "$cmd" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
            PYTHON="$cmd"
            break
        fi
    fi
done

# ── Uninstall pip package ─────────────────────────────────────────────────────
heading "Uninstalling geo-photo-renamer..."

if [ -n "$PYTHON" ] && "$PYTHON" -m pip show geo-photo-renamer &>/dev/null 2>&1; then
    "$PYTHON" -m pip uninstall --yes geo-photo-renamer
    info "Python package removed."
else
    warn "geo-photo-renamer pip package not found (already removed or never installed)."
fi

# ── Remove leftover geo-rename binary (if pip left one behind) ────────────────
if [ -n "$PYTHON" ]; then
    USER_BIN="$($PYTHON -m site --user-base)/bin"
    if [ -f "${USER_BIN}/geo-rename" ]; then
        rm -f "${USER_BIN}/geo-rename"
        info "Removed binary: ${USER_BIN}/geo-rename"
    fi
fi

if command -v geo-rename &>/dev/null; then
    LEFTOVER=$(command -v geo-rename)
    warn "geo-rename still found at: ${LEFTOVER}"
    warn "You may need to remove it manually."
fi

# ── Optional: remove data directory ──────────────────────────────────────────
DATA_DIR="$HOME/.geo-photo-renamer"

heading "Application data..."

if [ -d "$DATA_DIR" ]; then
    echo -e "${YELLOW}Found data directory:${RESET} ${DATA_DIR}"
    echo "  Contains: rename_counts.json and rename_log.txt"
    printf "  Remove it? [y/N] "
    read -r answer < /dev/tty
    if [[ "$answer" =~ ^[Yy]$ ]]; then
        rm -rf "$DATA_DIR"
        info "Removed ${DATA_DIR}"
    else
        info "Kept ${DATA_DIR}"
    fi
else
    info "No data directory found at ${DATA_DIR}"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}Done!${RESET} geo-photo-renamer has been uninstalled."
echo ""
echo "Note: output photos in ~/Pictures/geo-renamed/ were not touched."
echo ""
