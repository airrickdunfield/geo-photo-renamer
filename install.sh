#!/usr/bin/env bash
# geo-photo-renamer installer
# Usage: curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/geo-photo-renamer/main/install.sh | bash

set -euo pipefail

REPO="https://github.com/airrickdunfield/geo-photo-renamer"
PACKAGE="git+${REPO}.git"

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

# ── Check pipx ────────────────────────────────────────────────────────────────
heading "Checking requirements..."

if ! command -v pipx &>/dev/null; then
    info "pipx not found — installing via Homebrew..."
    if ! command -v brew &>/dev/null; then
        error "Homebrew is required to install pipx.\n  Install from https://brew.sh, then re-run this script."
    fi
    brew install pipx
    pipx ensurepath
    # Make pipx available in this shell session
    export PATH="$PATH:$HOME/.local/bin"
fi

info "pipx: $(pipx --version)"

# ── Install ───────────────────────────────────────────────────────────────────
heading "Installing geo-photo-renamer..."
info "Source: ${REPO}"

pipx install --force "${PACKAGE}"

# ── Verify ────────────────────────────────────────────────────────────────────
heading "Verifying installation..."

# pipx ensurepath may have updated PATH; source it if needed
if ! command -v geo-rename &>/dev/null; then
    export PATH="$PATH:$HOME/.local/bin"
fi

if ! command -v geo-rename &>/dev/null; then
    warn "'geo-rename' command not found on PATH."
    warn "pipx may need to update your PATH. Run:"
    warn "  pipx ensurepath"
    warn "Then open a new terminal and try: geo-rename --help"
else
    VER=$(geo-rename --version 2>&1 || echo "unknown")
    info "Installed: ${VER}"
fi

# ── Optional: exiftool ────────────────────────────────────────────────────────
heading "Optional dependencies..."

if command -v exiftool &>/dev/null; then
    info "exiftool: $(exiftool -ver)  (video GPS enabled)"
else
    warn "exiftool not found — video files without JSON sidecars will be skipped."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        warn "Install with: brew install exiftool"
    else
        warn "Install with: sudo apt install libimage-exiftool-perl   # Debian/Ubuntu"
        warn "           or: sudo dnf install perl-Image-ExifTool      # Fedora/RHEL"
    fi
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}Done!${RESET} Run  geo-rename --help  to get started."
echo ""
echo "Quick start:"
echo "  geo-rename ~/Downloads/vacation-photos"
echo "  geo-rename --dry-run ~/Pictures/unsorted"
echo "  geo-rename --help"
echo ""
