#!/usr/bin/env bash
# Create and publish the custom Homebrew tap for devbench.
#
# Prerequisites:
#   - gh CLI installed and authenticated (brew install gh)
#   - git configured with your GitHub identity
#   - devbench published to PyPI (run `python3 -m twine upload dist/*` first)
#
# Usage:
#   bash scripts/create-homebrew-tap.sh [VERSION]
#   bash scripts/create-homebrew-tap.sh 0.1.0

set -euo pipefail

VERSION="${1:-0.1.0}"
REPO="apeters247/homebrew-devbench"
FORMULA_DIR="homebrew-tap"

echo "=== Devbench Homebrew Tap Setup (v${VERSION}) ==="

# 1 — Fetch SHA256 from PyPI
echo ""
echo "Step 1: Fetching SHA256 from PyPI for devbench ${VERSION}..."
PYPI_SHA256=$(curl -s "https://pypi.org/pypi/devbench/${VERSION}/json" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
for f in data['urls']:
    if f['packagetype'] == 'sdist':
        print(f['digests']['sha256'])
        break
" 2>/dev/null || echo "")

if [[ -z "$PYPI_SHA256" ]]; then
  echo "  WARNING: Could not fetch SHA256 from PyPI — package may not be published yet."
  echo "  Upload to PyPI first: python3 -m twine upload dist/devbench-${VERSION}.tar.gz"
  PYPI_SHA256="FILL_IN_AFTER_PYPI_UPLOAD"
else
  echo "  SHA256: ${PYPI_SHA256}"
fi

# 2 — Update formula with real SHA256 and version
echo ""
echo "Step 2: Updating formula..."
FORMULA_FILE="${FORMULA_DIR}/Formula/devbench.rb"
sed -i "s|FILL_IN_AFTER_PYPI_UPLOAD|${PYPI_SHA256}|g" "$FORMULA_FILE"
sed -i "s|devbench-0.1.0|devbench-${VERSION}|g" "$FORMULA_FILE"
echo "  Updated ${FORMULA_FILE}"

# 3 — Create / update the GitHub repo
echo ""
echo "Step 3: Setting up GitHub repository..."
if gh repo view "$REPO" &>/dev/null 2>&1; then
  echo "  Repository ${REPO} already exists."
else
  echo "  Creating repository ${REPO}..."
  gh repo create "$REPO" \
    --public \
    --description "Custom Homebrew tap for devbench (ConfigForge — 11-format config converter)" \
    --clone=false
  echo "  Created ${REPO}"
fi

# 4 — Push the tap to GitHub
echo ""
echo "Step 4: Pushing tap to GitHub..."
TMPDIR=$(mktemp -d)
cp -r "$FORMULA_DIR/." "$TMPDIR/"
cd "$TMPDIR"
git init -b main
git add .
git commit -m "Add devbench v${VERSION} formula"

REMOTE_URL="https://github.com/${REPO}.git"
if git remote get-url origin &>/dev/null 2>&1; then
  git remote set-url origin "$REMOTE_URL"
else
  git remote add origin "$REMOTE_URL"
fi
git push -u origin main --force

cd - > /dev/null
rm -rf "$TMPDIR"
echo "  Pushed to ${REMOTE_URL}"

# 5 — Done
echo ""
echo "=== DONE ==="
echo ""
echo "Users can now install devbench with:"
echo ""
echo "  brew tap apeters247/devbench"
echo "  brew install devbench"
echo ""
echo "Or in one command:"
echo "  brew install apeters247/devbench/devbench"
