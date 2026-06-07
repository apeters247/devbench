#!/usr/bin/env bash
# =============================================================================
# Devbench — Full Release Pipeline
# =============================================================================
# Orchestrates: test → build → tag → publish to PyPI → publish to GitHub
#
# Usage:
#   ./scripts/release.sh patch    # 0.1.0 → 0.1.1
#   ./scripts/release.sh minor    # 0.1.0 → 0.2.0
#   ./scripts/release.sh major    # 0.1.0 → 1.0.0
#   ./scripts/release.sh 0.2.0    # explicit version
#
# Requires:
#   - GitHub CLI (gh): authenticated and with write access
#   - PyPI token: set TWINE_PASSWORD or configure ~/.pypirc
#   - GPG key: for signed git tags (optional, skips if missing)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32mOK\033[0m  %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m  %s\n' "$*" >&2; }
die()  { printf '\033[1;31mxx\033[0m  %s\n' "$*" >&2; exit 1; }

cd "$PROJECT_DIR"

# --- Parse version bump ---
BUMP="${1:-}"
[ -z "$BUMP" ] && die "Usage: $0 {patch|minor|major|<version>}"

CURRENT_VERSION="$(grep '^version = ' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/')"
log "Current version: $CURRENT_VERSION"

if [ "$BUMP" = "patch" ] || [ "$BUMP" = "minor" ] || [ "$BUMP" = "major" ]; then
  IFS='.' read -r MAJ MIN PAT <<< "$CURRENT_VERSION"
  case "$BUMP" in
    patch) NEW_VERSION="$MAJ.$MIN.$((PAT + 1))" ;;
    minor) NEW_VERSION="$MAJ.$((MIN + 1)).0" ;;
    major) NEW_VERSION="$((MAJ + 1)).0.0" ;;
  esac
else
  NEW_VERSION="$BUMP"
fi

log "Target version: $NEW_VERSION"

# --- Step 1: Run full test suite ---
log "Step 1: Running full test suite..."
python3 -m pytest tests/ -q --tb=line || die "Tests failed — aborting release"

# --- Step 2: Build wheel + sdist ---
log "Step 2: Building wheel and sdist..."
rm -rf dist/ build/ *.egg-info
python3 -m build
python3 -m twine check dist/* || die "twine check failed"

ok "Build artifacts:"
ls -lh dist/

# --- Step 3: Bump version and commit ---
log "Step 3: Bumping version to $NEW_VERSION..."
sed -i "s/^version = \"${CURRENT_VERSION}\"/version = \"${NEW_VERSION}\"/" pyproject.toml
git add pyproject.toml
git commit -m "Bump version to ${NEW_VERSION}" || true

# --- Step 4: Create git tag ---
log "Step 4: Creating git tag v$NEW_VERSION..."
if command -v gpg &>/dev/null && gpg --list-keys &>/dev/null 2>&1; then
  git tag -s "v${NEW_VERSION}" -m "Devbench release v${NEW_VERSION}"
  ok "Signed tag v${NEW_VERSION}"
else
  git tag -a "v${NEW_VERSION}" -m "Devbench release v${NEW_VERSION}"
  ok "Unsigned tag v${NEW_VERSION} (no GPG key found — consider signing future releases)"
fi

# --- Step 5: Push to GitHub ---
log "Step 5: Pushing to GitHub..."
git push origin main || warn "Push failed — continuing anyway (may need manual push)"
git push origin "v${NEW_VERSION}" || warn "Tag push failed — continuing anyway"

# --- Step 6: Publish to PyPI ---
log "Step 6: Publishing to PyPI..."
python3 -m twine upload dist/* || die "PyPI upload failed"
ok "Published to https://pypi.org/project/devbench/${NEW_VERSION}/"

# --- Step 7: Create GitHub Release ---
log "Step 7: Creating GitHub release..."
if command -v gh &>/dev/null; then
  gh release create "v${NEW_VERSION}" \
    --title "Devbench v${NEW_VERSION}" \
    --notes "$(cat <<RELEASE
# Devbench v${NEW_VERSION}

## What's New
- See [CHANGELOG.md](CHANGELOG.md) for full details

## Installation
\`\`\`bash
pip install devbench
\`\`\`

Or with Homebrew:
\`\`\`bash
brew tap apeters247/devbench
brew install devbench
\`\`\`

## macOS App
Download the Devbench.dmg from this release and drag to Applications.
RELEASE
    )" \
    dist/* || warn "GitHub release creation failed — create manually at https://github.com/apeters247/devbench/releases"
else
  warn "GitHub CLI (gh) not found — skipping GitHub release"
  warn "Create release manually at: https://github.com/apeters247/devbench/releases/new"
fi

# --- Done ---
echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║         Devbench v${NEW_VERSION} Released!                    ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "  PyPI:       https://pypi.org/project/devbench/${NEW_VERSION}/"
echo "  GitHub:     https://github.com/apeters247/devbench/releases/tag/v${NEW_VERSION}"
echo "  Install:    pip install devbench"
echo "  Homebrew:   brew tap apeters247/devbench && brew install devbench"
echo "  macOS App:  Download from GitHub releases"
echo ""