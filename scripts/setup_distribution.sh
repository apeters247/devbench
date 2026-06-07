#!/usr/bin/env bash
# ================================================================
# Devbench — Distribution Setup Script
# ================================================================
# This script:
#   1. Creates a Stripe product + price via forge-stripe CLI
#   2. Provides manual instructions for Gumroad product creation
#   3. Generates SEO meta tag reminders for landing pages
#   4. Prints a checklist of remaining manual steps
#
# Usage:  ./setup_distribution.sh
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WEB_DIR="${PROJECT_DIR}/web"

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║            Devbench — Distribution Setup                     ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# ----------------------------------------------------------------
# 1. Stripe Product via forge-stripe
# ----------------------------------------------------------------
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 1: Stripe Product Creation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if command -v forge-stripe &>/dev/null; then
  echo "  forge-stripe CLI found. Creating Stripe product..."

  STRIPE_OUTPUT=$(forge-stripe product create \
    --name="Devbench" \
    --description="8 essential developer tools in your macOS menubar. Includes clipboard auto-detect, JSON formatter, base64 encoder/decoder, UUID generator, timestamp converter, HTML entity encoder, URL encoder/decoder, color converter, and regex tester." \
    --url="https://toxscreen.ai/tools/devbench/" \
    --images="https://toxscreen.ai/tools/devbench/og-image.png" \
    2>&1 || true)

  if echo "$STRIPE_OUTPUT" | grep -qi "error\|failed\|not found\|unauthorized"; then
    echo "  ⚠️  forge-stripe encountered an issue:"
    echo "     $STRIPE_OUTPUT"
    echo ""
    echo "  → Manual steps:"
    echo "    1. Log in to Stripe Dashboard: https://dashboard.stripe.com/"
    echo "    2. Go to Products → Add Product"
    echo "    3. Name: Devbench"
    echo "    4. Description: 8 essential developer tools in your macOS menubar"
    echo "    5. URL: https://toxscreen.ai/tools/devbench/"
    echo "    6. Create a one-time price: \$19.00 USD"
    echo "    7. Copy the Price ID (e.g., price_abc123)"
    echo ""
  else
    echo "  ✅ Stripe product created successfully."
    echo "     $STRIPE_OUTPUT"
    echo ""
    # Extract price ID for later use
    PRICE_ID=$(echo "$STRIPE_OUTPUT" | grep -oP 'price_[a-zA-Z0-9]+' | head -1)
    if [ -n "$PRICE_ID" ]; then
      echo "  Price ID: $PRICE_ID"
    fi
    echo ""
  fi
else
  echo "  ⚠️  forge-stripe CLI not found. Install it from:"
  echo "     https://github.com/forge-stripe/forge-stripe"
  echo ""
  echo "  → Until then, create the product manually:"
  echo "    1. Log in to Stripe Dashboard: https://dashboard.stripe.com/"
  echo "    2. Go to Products → Add Product"
  echo "    3. Name: Devbench"
  echo "    4. Description: 8 essential developer tools in your macOS menubar"
  echo "    5. URL: https://toxscreen.ai/tools/devbench/"
  echo "    6. Create a one-time price: \$19.00 USD"
  echo ""
fi

# ----------------------------------------------------------------
# 2. Gumroad Product (manual)
# ----------------------------------------------------------------
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 2: Gumroad Product"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Gumroad does not provide an API for product creation via"
echo "  CLI. You'll need to create it manually."
echo ""
echo "  → Instructions:"
echo "    1. Log in to https://app.gumroad.com/"
echo "    2. Click 'New Product'"
echo "    3. Product name: Devbench"
echo "    4. Description:"
echo "       ---------------------------------------------------"
echo "       8 essential developer tools in your macOS menubar."
echo ""
echo "       Features:"
echo "       - JSON Formatter with syntax highlighting"
echo "       - Base64 Encoder / Decoder"
echo "       - UUID Generator (single + bulk)"
echo "       - Timestamp Converter (Unix, ISO 8601, timezones)"
echo "       - HTML Entity Encoder / Decoder"
echo "       - URL Encoder / Decoder"
echo "       - Color Converter (hex, RGB, HSL, named colors)"
echo "       - Regex Tester with real-time matching"
echo "       - Clipboard Auto-Detect ★"
echo ""
echo "       Requires macOS 13+. Apple Silicon & Intel."
echo "       One-time purchase — \$19. All future updates free."
echo "       ---------------------------------------------------"
echo "    5. Price: \$19.00 USD"
echo "    6. Upload: Devbench.dmg or Devbench.app.zip"
echo "    7. Set 'Redirect URL' to: https://toxscreen.ai/tools/devbench/thanks"
echo "    8. Set License Key: Auto-generate or use your own"
echo "    9. Publish"
echo ""
echo "  → After creation, update the Gumroad link in:"
echo "     ${WEB_DIR}/index.html"
echo "     Look for: id=\"buy-gumroad\" and set the href"
echo ""

# ----------------------------------------------------------------
# 3. Stripe Checkout Link Placeholder
# ----------------------------------------------------------------
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 3: Stripe Checkout Link"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  After creating the Stripe product, create a Checkout"
echo "  session or Payment Link:"
echo ""
echo "  → Payment Link (easiest):"
echo "    1. Stripe Dashboard → Products → Devbench"
echo "    2. Click 'Create payment link'"
echo "    3. Copy the link (e.g., https://buy.stripe.com/xxx)"
echo "    4. Update it in: ${WEB_DIR}/index.html"
echo "       Look for: id=\"buy-stripe\" and set the href"
echo ""
echo "  → OR use the Stripe CLI to create a checkout session:"
echo "     stripe checkout sessions create \\"
echo "       --mode=payment \\"
echo "       --line-items=\"price=YOUR_PRICE_ID:1\" \\"
echo "       --success-url=\"https://toxscreen.ai/tools/devbench/thanks\" \\"
echo "       --cancel-url=\"https://toxscreen.ai/tools/devbench/\""
echo ""

# ----------------------------------------------------------------
# 4. Mac App Store
# ----------------------------------------------------------------
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 4: Mac App Store Preparation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  For Mac App Store submission, you'll need:"
echo ""
echo "  Prerequisites:"
echo "    □ Apple Developer Program enrollment (\$99/year)"
echo "    ✅ Privacy policy: ${WEB_DIR}/privacy.html"
echo "    □ App icon (1024x1024 PNG)"
echo "    □ Screenshots (1280x800 or 1920x1200)"
echo "    □ App description (copy from index.html)"
echo ""
echo "  Submission steps:"
echo "    1. Build with Xcode (archive + notarize)"
echo "    2. Sign the app with Developer ID"
echo "    3. Upload to App Store Connect via Xcode or Transporter"
echo "    4. Fill in metadata (description, keywords, support URL)"
echo "    5. Submit for review"
echo ""
echo "  Support URL: https://toxscreen.ai/tools/devbench/support.html"
echo "  Privacy URL: https://toxscreen.ai/tools/devbench/privacy.html"
echo "  Marketing URL: https://toxscreen.ai/tools/devbench/"
echo ""

# ----------------------------------------------------------------
# 5. SEO Meta Reminders
# ----------------------------------------------------------------
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 5: SEO & Meta Tag Verification"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

check_meta() {
  local file="$1"
  local label="$2"
  if [ -f "$file" ]; then
    echo "  ✅ ${label}: ${file}"
  else
    echo "  ❌ ${label}: ${file} — MISSING"
  fi
}

check_meta "${WEB_DIR}/index.html"       "Landing page"
check_meta "${WEB_DIR}/privacy.html"     "Privacy policy"
check_meta "${WEB_DIR}/support.html"     "Support page"
check_meta "${WEB_DIR}/style.css"       "Stylesheet"

echo ""

# Check SEO tags in landing page
echo "  SEO tag check for index.html:"
echo ""

for tag in "description" "og:title" "og:description" "og:image" "twitter:card" "application/ld+json"; do
  if grep -q "$tag" "${WEB_DIR}/index.html" 2>/dev/null; then
    echo "    ✅ <meta $tag> found"
  else
    echo "    ❌ <meta $tag> MISSING"
  fi
done

echo ""

echo "  → Recommended next steps for SEO:"
echo "    1. Replace placeholder OG image with actual screenshot"
echo "       Update: ${WEB_DIR}/index.html"
echo "       Search for: og-image.png"
echo ""
echo "    2. Submit to Google Search Console:"
echo "       https://search.google.com/search-console"
echo "       Property: https://toxscreen.ai/tools/devbench/"
echo ""
echo "    3. Generate a sitemap.xml for the devbench pages"
echo ""
echo "    4. Verify JSON-LD renders correctly:"
echo "       https://search.google.com/test/rich-results"
echo ""

# ----------------------------------------------------------------
# 6. Final Checklist
# ----------------------------------------------------------------
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  FINAL CHECKLIST — Manual Steps Remaining"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  □ Create Stripe product (if forge-stripe failed above)"
echo "  □ Create Stripe Payment Link"
echo "  □ Update Stripe checkout href in index.html (#buy-stripe)"
echo "  □ Create Gumroad product"
echo "  □ Update Gumroad href in index.html (#buy-gumroad)"
echo "  □ Upload actual app screenshots (replace placeholders)"
echo "  □ Replace OG image placeholder (og-image.png)"
echo "  □ Set up domain: toxscreen.ai/tools/devbench/"
echo "  □ Configure HTTPS (Let's Encrypt / Cloudflare)"
echo "  □ Submit to Google Search Console"
echo "  □ Prepare Xcode archive for Mac App Store"
echo "  □ Sign & notarize app binary"
echo "  □ Submit to Mac App Store (via App Store Connect)"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Devbench distribution setup complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Need help? Contact: support@toxscreen.ai"
echo ""