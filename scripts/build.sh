#!/usr/bin/env bash
#===============================================================================
# Devbench macOS Build & Deployment Script
# Runs on GX10 (Linux ARM64), orchestrates building on Mac Mini via SSH.
# Usage: ./build.sh [VERSION]
#   VERSION - version tag (default: 1.0.0)
#===============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

VERSION="${1:-1.0.0}"
BUILD_DIR="${PROJECT_DIR}/build"
DMG_NAME="Devbench-${VERSION}.dmg"
DMG_PATH="${BUILD_DIR}/${DMG_NAME}"

# Configurable via env vars with sensible defaults
MAC_MINI_HOST="${MAC_MINI_HOST:-macmini}"
MAC_MINI_USER="${MAC_MINI_USER:-builder}"
MAC_MINI_PATH="${MAC_MINI_PATH:-~/Devbench}"
REMOTE_BUILD_DIR="${MAC_MINI_PATH}/.build"
SIGNING_IDENTITY="${SIGNING_IDENTITY:-Developer ID Application: Your Name (TEAMID)}"
NOTARY_PROFILE="${NOTARY_PROFILE:-notary-profile}"
SCRIPT_MODE="${SCRIPT_MODE:-full}"  # full, build-only, notarize-only, dmg-only

# Colours for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Colour

info()    { echo -e "${CYAN}[INFO]${NC}  $(date '+%H:%M:%S')  $*"; }
ok()      { echo -e "${GREEN}[OK]${NC}    $(date '+%H:%M:%S')  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $(date '+%H:%M:%S')  $*"; }
fail()    { echo -e "${RED}[FAIL]${NC}   $(date '+%H:%M:%S')  $*"; exit 1; }
header()  { echo; echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"; echo -e "${BOLD}  $*${NC}"; echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"; }

#===============================================================================
# Step 0: Pre-flight checks
#===============================================================================
preflight() {
    header "Pre-flight Checks"

    # Check we're on Linux
    if [[ "$(uname -s)" != "Linux" ]]; then
        warn "This script is designed to run from Linux (GX10). You are on $(uname -s)."
        warn "It will attempt to proceed, but some assumptions may not hold."
    fi

    # Check required local tools
    for cmd in ssh rsync ping; do
        if ! command -v "${cmd}" &>/dev/null; then
            fail "Required tool '${cmd}' not found locally. Please install it first."
        fi
    done

    # Check source directory exists
    if [[ ! -d "${PROJECT_DIR}/Sources" ]] && [[ ! -f "${PROJECT_DIR}/Package.swift" ]]; then
        warn "No Sources/ or Package.swift found in ${PROJECT_DIR}."
        warn "Make sure this script is in devbench/scripts/ and the project root has a Swift package manifest."
    fi

    ok "Pre-flight checks passed. Building Devbench v${VERSION}"
}

#===============================================================================
# Step 1: Detect if Mac Mini is reachable
#===============================================================================
check_macmini() {
    header "Step 1: Checking Mac Mini reachability (${MAC_MINI_HOST})"

    # Try SSH connection first (most reliable indicator of usability)
    if ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
        "${MAC_MINI_USER}@${MAC_MINI_HOST}" "echo reachable" &>/dev/null; then
        ok "Mac Mini is reachable via SSH at ${MAC_MINI_USER}@${MAC_MINI_HOST}"
        return 0
    fi

    # Fall back to ping check for diagnostics
    if ping -c 1 -W 3 "${MAC_MINI_HOST}" &>/dev/null; then
        warn "Mac Mini responds to ping but SSH connection failed."
        warn "Check that:"
        warn "  1. SSH key-based auth is set up for ${MAC_MINI_USER}@${MAC_MINI_HOST}"
        warn "  2. The SSH service is running on the Mac Mini"
        warn "  3. The hostname '${MAC_MINI_HOST}' resolves to the correct IP"
        warn ""
        warn "To set up SSH access, run on the GX10:"
        warn "  ssh-copy-id ${MAC_MINI_USER}@${MAC_MINI_HOST}"
        warn "Or add to ~/.ssh/config:"
        warn "  Host macmini"
        warn "    HostName <IP_ADDRESS>"
        warn "    User ${MAC_MINI_USER}"
        warn "    IdentityFile ~/.ssh/id_ed25519"
    else
        warn "Mac Mini at '${MAC_MINI_HOST}' is not reachable."
        warn ""
        warn "To make the Mac Mini accessible, ensure:"
        warn "  1. Mac Mini is powered on and connected to the same network"
        warn "  2. Remote Login (SSH) is enabled in System Settings → General → Sharing"
        warn "  3. The hostname '${MAC_MINI_HOST}' resolves correctly"
        warn "     (add to /etc/hosts if needed: <IP> ${MAC_MINI_HOST})"
        warn "  4. The GX10 and Mac Mini can reach each other on the network"
        warn ""
        warn "Set the MAC_MINI_HOST env var if using a different hostname/IP:"
        warn "  export MAC_MINI_HOST=192.168.1.100"
    fi

    info "Mac Mini not available. Build skipped (not an error)."
    exit 0
}

#===============================================================================
# Step 2: Sync source code to Mac Mini
#===============================================================================
sync_source() {
    header "Step 2: Syncing source code to Mac Mini"

    info "Syncing ${PROJECT_DIR}/ → ${MAC_MINI_USER}@${MAC_MINI_HOST}:${MAC_MINI_PATH}"

    # Use rsync with archive mode, excluding build artefacts and git metadata
    rsync -avz --delete \
        --exclude '.build' \
        --exclude '.git' \
        --exclude 'build' \
        --exclude '.swiftpm' \
        --exclude '*.dmg' \
        --exclude '*.zip' \
        --exclude 'Packages' \
        -e "ssh -o StrictHostKeyChecking=accept-new" \
        "${PROJECT_DIR}/" \
        "${MAC_MINI_USER}@${MAC_MINI_HOST}:${MAC_MINI_PATH}/"

    ok "Source code synced successfully"
}

#===============================================================================
# Step 3: Build (swift build -c release)
#===============================================================================
build_release() {
    header "Step 3: Building release binary on Mac Mini"

    info "Running: swift build -c release on Mac Mini..."

    ssh -o StrictHostKeyChecking=accept-new \
        "${MAC_MINI_USER}@${MAC_MINI_HOST}" \
        "cd ${MAC_MINI_PATH} && swift build -c release 2>&1" \
        || fail "Swift build failed on Mac Mini"

    ok "Swift release build completed successfully"
}

#===============================================================================
# Step 4: Sign the .app bundle
#===============================================================================
sign_app() {
    header "Step 4: Codesigning Devbench.app"

    info "Signing with identity: ${SIGNING_IDENTITY}"

    ssh -o StrictHostKeyChecking=accept-new \
        "${MAC_MINI_USER}@${MAC_MINI_HOST}" \
        "cd ${MAC_MINI_PATH} && \
         codesign --force --options runtime --timestamp \
                  --sign '${SIGNING_IDENTITY}' \
                  .build/release/Devbench.app 2>&1" \
        || fail "Codesigning failed"

    # Verify the signature
    ssh -o StrictHostKeyChecking=accept-new \
        "${MAC_MINI_USER}@${MAC_MINI_HOST}" \
        "codesign -dvvv ${MAC_MINI_PATH}/.build/release/Devbench.app 2>&1 | head -20" \
        || warn "Could not verify signature (non-fatal)"

    ok "Devbench.app signed successfully"
}

#===============================================================================
# Step 5: Notarize the .app
#===============================================================================
notarize_app() {
    header "Step 5: Notarizing Devbench.app"

    local remote_app_path="${MAC_MINI_PATH}/.build/release/Devbench.app"
    local remote_zip_path="${MAC_MINI_PATH}/.build/release/Devbench.zip"

    info "Creating zip archive for notarization..."

    ssh -o StrictHostKeyChecking=accept-new \
        "${MAC_MINI_USER}@${MAC_MINI_HOST}" \
        "cd ${MAC_MINI_PATH}/.build/release && \
         ditto -c -k --keepParent 'Devbench.app' 'Devbench.zip' 2>&1" \
        || fail "Failed to create Devbench.zip"

    info "Submitting to Apple notary service (this may take a few minutes)..."

    ssh -o StrictHostKeyChecking=accept-new \
        "${MAC_MINI_USER}@${MAC_MINI_HOST}" \
        "xcrun notarytool submit '${remote_zip_path}' \
         --keychain-profile '${NOTARY_PROFILE}' \
         --wait 2>&1" \
        || fail "Notarization submission failed"

    ok "Devbench.app notarized successfully"
}

#===============================================================================
# Step 6: Staple the notarization ticket
#===============================================================================
staple_app() {
    header "Step 6: Stapling notarization ticket to Devbench.app"

    local remote_app_path="${MAC_MINI_PATH}/.build/release/Devbench.app"

    ssh -o StrictHostKeyChecking=accept-new \
        "${MAC_MINI_USER}@${MAC_MINI_HOST}" \
        "xcrun stapler staple '${remote_app_path}' 2>&1" \
        || fail "Stapling failed"

    # Verify the staple
    ssh -o StrictHostKeyChecking=accept-new \
        "${MAC_MINI_USER}@${MAC_MINI_HOST}" \
        "xcrun stapler validate '${remote_app_path}' 2>&1" \
        || warn "Staple validation produced warnings (check output above)"

    ok "Notarization ticket stapled to Devbench.app"
}

#===============================================================================
# Step 7: Create DMG
#===============================================================================
create_dmg() {
    header "Step 7: Creating DMG from stapled Devbench.app"

    local remote_app_path="${MAC_MINI_PATH}/.build/release/Devbench.app"
    local remote_dmg_dir="${MAC_MINI_PATH}/.build/release"
    local remote_dmg_path="${remote_dmg_dir}/Devbench-${VERSION}.dmg"

    info "Creating DMG: Devbench-${VERSION}.dmg"

    # Use create-dmg if available, otherwise fall back to hdiutil
    ssh -o StrictHostKeyChecking=accept-new \
        "${MAC_MINI_USER}@${MAC_MINI_HOST}" \
        "cd '${remote_dmg_dir}' && \
         if command -v create-dmg &>/dev/null; then \
           create-dmg \
             --volname 'Devbench ${VERSION}' \
             --window-pos 200 120 \
             --window-size 600 400 \
             --icon-size 100 \
             --icon 'Devbench.app' 150 190 \
             --hide-extension 'Devbench.app' \
             --app-drop-link 450 190 \
             'Devbench-${VERSION}.dmg' \
             'Devbench.app' 2>&1; \
         else \
           hdiutil create -volname 'Devbench ${VERSION}' \
             -srcfolder 'Devbench.app' \
             -ov -format UDZO \
             'Devbench-${VERSION}.dmg' 2>&1; \
         fi" \
        || fail "DMG creation failed"

    ok "DMG created: Devbench-${VERSION}.dmg"
}

#===============================================================================
# Step 8: Notarize the DMG
#===============================================================================
notarize_dmg() {
    header "Step 8: Notarizing the DMG"

    local remote_dmg_path="${MAC_MINI_PATH}/.build/release/Devbench-${VERSION}.dmg"

    info "Submitting DMG to Apple notary service..."

    ssh -o StrictHostKeyChecking=accept-new \
        "${MAC_MINI_USER}@${MAC_MINI_HOST}" \
        "xcrun notarytool submit '${remote_dmg_path}' \
         --keychain-profile '${NOTARY_PROFILE}' \
         --wait 2>&1" \
        || fail "DMG notarization failed"

    # Staple the DMG as well
    info "Stapling notarization ticket to DMG..."

    ssh -o StrictHostKeyChecking=accept-new \
        "${MAC_MINI_USER}@${MAC_MINI_HOST}" \
        "xcrun stapler staple '${remote_dmg_path}' 2>&1" \
        || warn "DMG stapling produced warnings (non-fatal)"

    ok "DMG notarized and stapled successfully"
}

#===============================================================================
# Step 9: Copy DMG back to GX10
#===============================================================================
copy_dmg_home() {
    header "Step 9: Copying DMG back to GX10"

    local remote_dmg_path="${MAC_MINI_PATH}/.build/release/Devbench-${VERSION}.dmg"
    local local_dmg_path="${DMG_PATH}"

    mkdir -p "${BUILD_DIR}"

    info "Copying from Mac Mini..."
    rsync -avz --progress \
        -e "ssh -o StrictHostKeyChecking=accept-new" \
        "${MAC_MINI_USER}@${MAC_MINI_HOST}:${remote_dmg_path}" \
        "${local_dmg_path}" \
        || fail "Failed to copy DMG back from Mac Mini"

    ok "DMG copied to ${local_dmg_path}"
}

#===============================================================================
# Step 10: Version tagging
#===============================================================================
version_tag() {
    header "Step 10: Version tagging (v${VERSION})"

    # Check if we're in a git repository
    if git -C "${PROJECT_DIR}" rev-parse --git-dir &>/dev/null; then
        local tag_name="v${VERSION}"
        local existing_tag

        existing_tag="$(git -C "${PROJECT_DIR}" tag -l "${tag_name}" 2>/dev/null)"

        if [[ -n "${existing_tag}" ]]; then
            warn "Tag '${tag_name}' already exists locally. Skipping tag creation."
        else
            git -C "${PROJECT_DIR}" tag -a "${tag_name}" \
                -m "Devbench release v${VERSION}" \
                || warn "Failed to create git tag (non-fatal)"
            ok "Created git tag: ${tag_name}"
        fi

        # Optionally push tag if remote is configured
        if git -C "${PROJECT_DIR}" remote -v | grep -q 'origin'; then
            info "Pushing tag '${tag_name}' to origin..."
            git -C "${PROJECT_DIR}" push origin "${tag_name}" 2>&1 || \
                warn "Failed to push tag to origin (non-fatal — may need 'git push origin ${tag_name}' manually)"
        else
            info "No git remote 'origin' configured — tag is local only."
        fi
    else
        warn "Not a git repository — skipping version tagging."
    fi

    ok "Version tagging complete"
}

#===============================================================================
# Summary
#===============================================================================
print_summary() {
    header "Build Summary"
    echo -e "  ${BOLD}Version:${NC}     ${VERSION}"
    echo -e "  ${BOLD}DMG:${NC}         ${DMG_PATH}"
    echo -e "  ${BOLD}Host:${NC}        ${MAC_MINI_USER}@${MAC_MINI_HOST}"
    echo -e "  ${BOLD}Remote path:${NC} ${MAC_MINI_PATH}"
    echo

    if [[ -f "${DMG_PATH}" ]]; then
        local size
        size="$(du -h "${DMG_PATH}" | cut -f1)"
        echo -e "  ${GREEN}✓ Build artifact ready:${NC}"
        echo -e "    ${DMG_PATH} (${size})"
        echo
        echo -e "  To distribute, upload ${DMG_PATH} to your release channel."
    else
        echo -e "  ${YELLOW}⚠ DMG not found locally — check remote path for artifacts.${NC}"
    fi

    echo
    echo -e "  ${BOLD}Next steps:${NC}"
    echo -e "    • Verify notarization:  spctl -a -v ${DMG_PATH}"
    echo -e "    • Create release on GitHub and attach the DMG"
    echo -e "    • Or distribute directly to testers"
    echo
}

#===============================================================================
# Main
#===============================================================================
main() {
    echo
    echo -e "${BOLD}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║       Devbench macOS Build & Deployment v${VERSION}        ║${NC}"
    echo -e "${BOLD}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo

    preflight
    check_macmini

    case "${SCRIPT_MODE}" in
        full)
            sync_source
            build_release
            sign_app
            notarize_app
            staple_app
            create_dmg
            notarize_dmg
            copy_dmg_home
            version_tag
            ;;
        build-only)
            sync_source
            build_release
            ;;
        notarize-only)
            sign_app
            notarize_app
            staple_app
            ;;
        dmg-only)
            create_dmg
            notarize_dmg
            copy_dmg_home
            ;;
        *)
            fail "Unknown SCRIPT_MODE='${SCRIPT_MODE}'. Use: full, build-only, notarize-only, dmg-only"
            ;;
    esac

    print_summary
    echo -e "${GREEN}✅ Devbench build pipeline completed successfully!${NC}"
    echo
}

main
