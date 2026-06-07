#!/usr/bin/env bash
#
# devbench installer — one-liner
# -------------------------------
#     curl -sSL https://naxiai.com/install.sh | bash
#
# Installs the devbench CLI tool and optionally sets up systemd services
# for the ConfigForge web demo and REST API.
#
# The real installer lives at scripts/install.sh; this root-level copy
# exists so that "curl https://naxiai.com/install.sh" finds it at the
# web root. Both files are kept in sync.
#
# Environment overrides:
#   DEVBENCH_REPO     git URL to clone        (default: GitHub apeters247/devbench)
#   DEVBENCH_REF      branch/tag/commit       (default: main)
#   DEVBENCH_HOME     checkout location       (default: ~/.local/share/devbench)
#   PYTHON            python interpreter      (default: python3)
#   PIP_USER=1        force `pip install --user`

set -euo pipefail

REPO="${DEVBENCH_REPO:-https://github.com/apeters247/devbench.git}"
REF="${DEVBENCH_REF:-main}"
HOME_DIR="${DEVBENCH_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/devbench}"
PYTHON="${PYTHON:-python3}"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m  %s\n' "$*" >&2; }
die()  { printf '\033[1;31mxx\033[0m  %s\n' "$*" >&2; exit 1; }

# --- preflight ---------------------------------------------------------------
command -v "$PYTHON" >/dev/null 2>&1 || die "$PYTHON not found. Install Python 3.10+ and retry."
command -v git       >/dev/null 2>&1 || die "git not found. Install git and retry."

PYV="$("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
log "Using Python $PYV ($("$PYTHON" -c 'import sys; print(sys.executable)'))"

# --- fetch source ------------------------------------------------------------
if [ -d "$HOME_DIR/.git" ]; then
    log "Updating existing checkout in $HOME_DIR"
    git -C "$HOME_DIR" fetch --depth 1 origin "$REF"
    git -C "$HOME_DIR" checkout -q FETCH_HEAD
else
    log "Cloning $REPO ($REF) into $HOME_DIR"
    mkdir -p "$(dirname "$HOME_DIR")"
    git clone --depth 1 --branch "$REF" "$REPO" "$HOME_DIR" 2>/dev/null \
        || git clone --depth 1 "$REPO" "$HOME_DIR"
fi

# --- install -----------------------------------------------------------------
PIP_ARGS=()
if [ "${PIP_USER:-0}" = "1" ]; then
    PIP_ARGS+=(--user)
elif [ -z "${VIRTUAL_ENV:-}" ] && ! "$PYTHON" -c 'import sys; sys.exit(0 if hasattr(sys,"real_prefix") or sys.base_prefix!=sys.prefix else 1)' 2>/dev/null; then
    # Not in a venv: PEP 668 environments need --user (or --break-system-packages).
    PIP_ARGS+=(--user)
fi

log "Installing devbench with pip ${PIP_ARGS[*]:-}"
"$PYTHON" -m pip install --upgrade "${PIP_ARGS[@]}" "$HOME_DIR"

# --- verify ------------------------------------------------------------------
if command -v devbench >/dev/null 2>&1; then
    log "Installed: $(command -v devbench)"
    devbench --list || warn "'devbench --list' returned non-zero."
else
    warn "'devbench' is installed but not on PATH."
    warn "Add your user bin dir to PATH, e.g.:"
    warn "    export PATH=\"\$($PYTHON -m site --user-base)/bin:\$PATH\""
fi

# --- systemd service setup (optional, sudo required) -------------------------
if command -v systemctl >/dev/null 2>&1 && [ "$(id -u)" = "0" ]; then
    log "Setting up ConfigForge REST API systemd service..."

    cat > /etc/systemd/system/configforge-api.service <<SYSUNIT
[Unit]
Description=ConfigForge REST API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=$HOME_DIR
ExecStart=/usr/bin/python3 $HOME_DIR/web/api.py --port 8081
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SYSUNIT

    systemctl daemon-reload
    systemctl enable configforge-api.service 2>/dev/null || \
        warn "Could not enable configforge-api.service (may need --user or sudo)."
    log "API service configured: systemctl start configforge-api.service"

    cat > /etc/systemd/system/configforge-demo.service <<SYSUNIT2
[Unit]
Description=ConfigForge Web Demo
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=$HOME_DIR
ExecStart=/usr/bin/python3 $HOME_DIR/web/serve.py --port 8080
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SYSUNIT2

    systemctl daemon-reload
    systemctl enable configforge-demo.service 2>/dev/null || \
        warn "Could not enable configforge-demo.service."
    log "Demo service configured: systemctl start configforge-demo.service"
elif command -v systemctl >/dev/null 2>&1; then
    warn "Not running as root — skipping systemd service setup."
    warn "To set up services manually, run: sudo systemctl enable configforge-api"
fi

log "Done."