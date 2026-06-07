#!/usr/bin/env bash
# =============================================================================
# Devbench — PyPI Publish Script
# =============================================================================
# Usage:
#   ./scripts/publish-pypi.sh              # interactive (asks for version)
#   ./scripts/publish-pypi.sh patch         # bump patch version (0.1.0 → 0.1.1)
#   ./scripts/publish-pypi.sh minor         # bump minor version (0.1.0 → 0.2.0)
#   ./scripts/publish-pypi.sh major         # bump major version (0.1.0 → 1.0.0)
#   ./scripts/publish-pypi.sh 0.2.0         # explicit version
#
# Prerequisites:
#   pip install build twine
#   python3 -m twine upload  # configured with PyPI API token or .pypirc
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYPROJECT="$PROJECT_DIR/pyproject.toml"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m  %s\n' "$*" >&2; }
die()  { printf '\033[1;31mxx\033[0m  %s\n' "$*" >&2; exit 1; }

cd "$PROJECT_DIR"

# --- Preflight ---------------------------------------------------------------
command -v python3 >/dev/null 2>&1 || die "python3 not found"
python3 -c "import build"  2>/dev/null || die "build package not installed — run: pip install build"
python3 -c "import twine"  2>/dev/null || die "twine not installed — run: pip install twine"

# --- Bump version ------------------------------------------------------------
BUMP="${1:-}"
CURRENT_VERSION="$(grep '^version = ' "$PYPROJECT" | head -1 | sed 's/version = "\(.*\)"/\1/')"
log "Current version: ${CURRENT_VERSION}"

if [ -z "$BUMP" ]; then
  read -r -p "New version (Enter for $CURRENT_VERSION): " NEW_VERSION
  NEW_VERSION="${NEW_VERSION:-$CURRENT_VERSION}"
elif [ "$BUMP" = "patch" ] || [ "$BUMP" = "minor" ] || [ "$BUMP" = "major" ]; then
  IFS='.' read -r MAJ MIN PAT <<< "$CURRENT_VERSION"
  case "$BUMP" in
    patch) NEW_VERSION="$MAJ.$MIN.$((PAT + 1))" ;;
    minor) NEW_VERSION="$MAJ.$((MIN + 1)).0" ;;
    major) NEW_VERSION="$((MAJ + 1)).0.0" ;;
  esac
else
  NEW_VERSION="$BUMP"
fi

if [ "$NEW_VERSION" != "$CURRENT_VERSION" ]; then
  log "Bumping version: ${CURRENT_VERSION} → ${NEW_VERSION}"
  sed -i "s/^version = \"${CURRENT_VERSION}\"/version = \"${NEW_VERSION}\"/" "$PYPROJECT"
  log "Version updated in pyproject.toml"
fi

# --- Clean old builds --------------------------------------------------------
log "Cleaning old builds..."
rm -rf dist/ build/ *.egg-info

# --- Run tests ---------------------------------------------------------------
log "Running test suite..."
python3 -m pytest tests/ -q --tb=line || die "Tests failed — aborting publish"

# --- Build wheel + sdist -----------------------------------------------------
log "Building wheel and sdist..."
python3 -m build
log "Build output:"
ls -lh dist/

# --- Check distribution ------------------------------------------------------
log "Checking distribution with twine..."
python3 -m twine check dist/*

# --- Confirm ----------------------------------------------------------------
log ""
log "Ready to publish devbench v${NEW_VERSION}"
log "  Package: dist/devbench-${NEW_VERSION}-py3-none-any.whl"
log "  Source:  dist/devbench-${NEW_VERSION}.tar.gz"
log ""

read -r -p "Publish to PyPI? (y/N) " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
  log "Aborted."
  exit 0
fi

# --- Publish to Test PyPI first --------------------------------------------
log "Publishing to Test PyPI..."
python3 -m twine upload --repository-url https://test.pypi.org/legacy/ dist/* --skip-existing || \
  warn "Test PyPI upload failed (non-fatal)"

# --- Publish to PyPI --------------------------------------------------------
log "Publishing to PyPI..."
python3 -m twine upload dist/*

# --- Git tag ----------------------------------------------------------------
log "Creating git tag v${NEW_VERSION}..."
git add "$PYPROJECT"
git commit -m "Bump version to ${NEW_VERSION}" || true
git tag -a "v${NEW_VERSION}" -m "Devbench release v${NEW_VERSION}"
git push origin "v${NEW_VERSION}" || warn "Git push failed — tag is local only"

log "✅ Published devbench v${NEW_VERSION} to PyPI!"
log "   https://pypi.org/project/devbench/${NEW_VERSION}/"