# Gumroad Product Setup — ConfigForge / Devbench

## Product Configuration

### Step 1: Create the Product

Go to [gumroad.com/products/new](https://gumroad.com/products/new) and configure:

**Basic Info:**
- **Product Name:** Devbench — 9 Developer Tools + ConfigForge Config Converter
- **Description:** (use content from producthunt-description.md)
- **Price:** $19 (one-time)
- **Currency:** USD
- **Cover Image:** Use web/demo-screenshot.png or a clean product mockup

**URL:** `https://gumroad.com/l/devbench` (custom short link)

### Step 2: License Keys

Enable license key generation:

1. Go to Product → Settings → License Keys
2. Enable "Generate license keys on purchase"
3. Set format: `DEVBENCH-XXXX-XXXX-XXXX` (uppercase, groups of 4)
4. Enable "Allow license key verification via API"

This enables:
- Post-purchase license key delivery via email
- License verification endpoint: `https://api.gumroad.com/v2/licenses/verify`
- App-side validation in the macOS menubar app

### Step 3: Post-Purchase Flow

Configure the post-purchase redirect:

1. Product → Settings → After purchase
2. Set redirect to: `https://naxiai.com/tools/devbench/download`
3. Or set to a direct download page with license key display

**License Key + Download Page** (`/tools/devbench/download.html`):
```html
<!DOCTYPE html>
<html>
<head>
  <title>Devbench — Download</title>
  <meta name="robots" content="noindex">
</head>
<body>
  <h1>Thank you for your purchase!</h1>
  <p>Your license key: <strong id="license">DEVBENCH-XXXX-XXXX-XXXX</strong></p>
  <h2>Downloads</h2>
  <ul>
    <li><a href="/downloads/devbench-1.0.0.dmg">Devbench macOS App (1.0.0)</a></li>
    <li><a href="https://github.com/apeters247/devbench/releases">Source Code (GitHub)</a></li>
  </ul>
  <p>Or install the CLI: <code>pip install devbench</code></p>
</body>
</html>
```

### Step 4: Rich Text Description

```markdown
**Devbench puts 9 essential developer tools right in your macOS menubar.**

**Includes ConfigForge** — the 9-format config file converter (JSON, YAML, TOML, XML, CSV, INI, .env, HCL, .properties) with comment preservation, batch mode, and built-in web UI.

### What's included:

**ConfigForge CLI** (all platforms):
- 9-format bidirectional config conversion
- YAML comment preservation through JSON round-trips
- INI→TOML type inference (booleans, numbers, dates)
- Batch glob mode with streaming (10K+ files)
- Built-in web UI (`devbench cf --serve`)
- Built-in REST API (`devbench cf --api`)

**macOS Menubar App** (macOS 13+):
- 9 one-click tools in your menubar
- ConfigForge with paste-and-convert UI
- JSON formatter with syntax highlighting
- Base64 encoder/decoder
- UUID generator (v4, v7, NanoID)
- Timestamp converter (Unix ↔ ISO 8601 ↔ human)
- JWT decoder
- IP address calculator
- Clipboard auto-detect (paste any data, it guesses the tool)
- Clipboard history with search

### System Requirements
- **CLI:** Python 3.10+ (macOS, Linux, Windows)
- **Menubar App:** macOS 13+ (Apple Silicon or Intel)

### License
One-time purchase. Lifetime access includes all updates for version 1.x.
```

### Step 5: Offer Codes

None to start. Consider offering:
- Launch week 20% off: `LAUNCH20`
- HN/Product Hunt readers: `HN20`

### Step 6: Publish

- **Visibility:** Public (listed on Gumroad)
- **Sales page:** Use Gumroad's hosted page or embed
- **Checkout:** Enable Gumroad's internal checkout (no Stripe needed — Gumroad handles it)

### Step 7: Affiliate Program

Enable affiliates at 10% commission:
- Product → Settings → Affiliates
- Set commission: 10%
- This encourages dev tool reviewers to link to the product

---

## Post-Sale Integration

### Gumroad API License Verification (for app-side validation)

```python
import requests

def verify_license(license_key, product_permalink="devbench"):
    """Verify a Gumroad license key."""
    resp = requests.post("https://api.gumroad.com/v2/licenses/verify", data={
        "product_permalink": product_permalink,
        "license_key": license_key,
    })
    data = resp.json()
    if data.get("success") and data.get("uses", 0) <= 5:
        return True, data
    return False, data
```

### Webhook Setup (for post-purchase automation)

1. Go to Settings → API → Webhooks
2. Add endpoint: `https://naxiai.com/api/gumroad-webhook`
3. Subscribe to: `sale` events
4. The webhook receives:
```json
{
  "sale_id": "abc123",
  "email": "customer@example.com",
  "product_name": "Devbench",
  "license_key": "DEVBENCH-XXXX-XXXX-XXXX",
  "price": 19.00,
  "currency": "USD",
  "timestamp": "2026-06-07T12:00:00Z"
}
```

### Post-Purchase Email

Configure Gumroad's automatic email:
1. Settings → Emails → Sale confirmation
2. Customize subject: "Your Devbench License Key & Download Links"
3. Include:
   - License key
   - Download link (DMG)
   - `pip install devbench` instructions
   - Link to documentation: https://naxiai.com/tools/devbench/
   - Link to GitHub: https://github.com/apeters247/devbench
   - Support email