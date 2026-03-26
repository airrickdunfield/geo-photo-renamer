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

# ── Check Python ──────────────────────────────────────────────────────────────
heading "Checking requirements..."

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print(sys.version_info[:2])")
        if "$cmd" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    error "Python 3.8+ is required.\n  Install from https://python.org or via your system package manager."
fi

info "Python: $($PYTHON --version)"

# ── Check pip ─────────────────────────────────────────────────────────────────
if ! "$PYTHON" -m pip --version &>/dev/null; then
    error "pip is not available. Install it with: $PYTHON -m ensurepip --upgrade"
fi

# ── Install ───────────────────────────────────────────────────────────────────
heading "Installing geo-photo-renamer..."
info "Source: ${REPO}"

"$PYTHON" -m pip install --quiet --upgrade --user "${PACKAGE}" 2>/dev/null \
    || "$PYTHON" -m pip install --quiet --upgrade --user --break-system-packages "${PACKAGE}"

# ── Verify ────────────────────────────────────────────────────────────────────
heading "Verifying installation..."

if ! command -v geo-rename &>/dev/null; then
    # The script may be in a user-local bin that isn't on PATH
    USER_BIN="$($PYTHON -m site --user-base)/bin"
    if [ -f "${USER_BIN}/geo-rename" ]; then
        warn "'geo-rename' is installed at ${USER_BIN}/geo-rename"
        warn "but that directory is not on your PATH."
        warn ""
        warn "Add it permanently by adding this to your shell profile (~/.zshrc or ~/.bashrc):"
        warn "  export PATH=\"\$PATH:${USER_BIN}\""
        warn ""
        warn "Then reload your shell:  source ~/.zshrc"
    else
        warn "'geo-rename' command not found on PATH."
        warn "The pip install may have placed it somewhere unexpected."
        warn "Try running: $PYTHON -m geo_renamer.cli --help"
    fi
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
