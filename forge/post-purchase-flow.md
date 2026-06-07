# Post-Purchase Flow — ConfigForge / Devbench

## Overview

When a customer pays $19 for ConfigForge via Stripe (or Gumroad), they need:

1. A **license key** generated and delivered
2. A **download link** to get the macOS .app or pip package
3. **Machine activation** support (up to 3 machines per license)

This document describes the complete post-purchase infrastructure built into
`web/license.py` (crypto) and `web/license_server.py` (HTTP server).

---

## Architecture

```
Customer                    Stripe                License Server
   │                         │                        │
   │── pays $19 ────────────►│                        │
   │                         │── webhook ────────────►│
   │                         │   checkout.session     │
   │                         │   .completed           │
   │                         │                        │── generate HMAC key
   │                         │                        │── store in SQLite
   │                         │◄── license_key ────────│
   │                         │    + email delivery    │
   │◄──── email with ────────┤                        │
   │   license key + URL     │                        │
   │                         │                        │
   │── GET /download/<key> ──────────────────────────►│
   │◄── .dmg / .whl ──────────────────────────────────│
   │                         │                        │
   │── POST /license/activate ───────────────────────►│
   │   {"key":"CF.…",        │                        │
   │    "machine_id":"…"}    │                        │── store activation
   │◄── {"status":"ok"} ────┤                        │
```

---

## Components

### 1. License Key Module — `web/license.py`

Zero-dependency cryptographic license key system:

| Feature | Implementation |
|---------|---------------|
| Key format | `CF.<base64_body>.<HMAC_SHA256_sig>` |
| Self-validating | HMAC signature embedded in key — no DB needed for basic verify |
| Embedded metadata | Email, customer ID, payment intent, issued timestamp, expiry |
| Option DB backend | SQLite for activation tracking (3-machine limit) |
| Revocation | Set expiry to now (stored in DB) |

```python
# Example usage in production
from web.license import LicenseManager

lm = LicenseManager(
    secret=os.environ["DEVBENCH_LICENSE_SECRET"].encode(),
    db_path="/var/data/licenses.db",
)

# On successful payment:
key = lm.generate(
    email=customer_email,
    customer_id=customer_id,
    payment_intent=payment_intent_id,
    expiry=int(time.time()) + 365 * 86400,  # 1 year
)

# Verification (no DB needed):
is_valid = lm.verify(key)

# Decode metadata:
info = lm.decode(key)
print(f"Licensed to {info['email']}, issued {info['issued_at']}")
```

### 2. License Server — `web/license_server.py`

Zero-dependency HTTP server with these endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Liveness probe |
| `/` | GET | API summary |
| `/license/verify?key=...` | GET | Validate a license key |
| `/license/activate` | POST | Register machine activation |
| `/license/revoke` | POST | Revoke a license |
| `/webhook/stripe` | POST | Stripe webhook receiver |
| `/download/<key>` | GET | Download artifact (validates key) |

**Rate limiting:** 60 requests/minute per IP (in-memory).

**CORS:** Enabled on all responses for browser-based clients.

### 3. Stripe Webhook Processing

When Stripe sends a `checkout.session.completed` event:

1. Verify Stripe signature (HMAC with `STRIPE_WEBHOOK_SECRET`)
2. Extract `customer_email`, `customer`, `payment_intent` from event
3. Generate an HMAC-signed license key (1 year expiry)
4. Store license in SQLite database
5. Return license key in webhook response
6. (In production) Send email to customer with key + download instructions

In **development mode** (`DEVBENCH_DEV=1`, the default), signature verification
is skipped so you can test with `curl`.

---

## Deployment

### Step 1 — Set Environment Variables

```bash
export DEVBENCH_LICENSE_SECRET="your-32-byte-secret-key-here!!!"
export DEVBENCH_LICENSE_DB="/var/data/devbench/licenses.db"
export STRIPE_WEBHOOK_SECRET="whsec_..."  # from Stripe Dashboard
export DEVBENCH_DEV="0"  # Enable Stripe signature verification
```

### Step 2 — Start the Server

```bash
# Direct
python3 -m web.license_server --port 9001

# Via CLI
python3 -m core.cli license-server --port 9001
```

### Step 3 — Systemd Service

Create `/etc/systemd/system/configforge-license.service`:

```ini
[Unit]
Description=ConfigForge License Server
After=network.target

[Service]
Type=simple
User=devbench
WorkingDirectory=/opt/devbench
Environment=DEVBENCH_LICENSE_SECRET=...
Environment=DEVBENCH_LICENSE_DB=/var/data/devbench/licenses.db
Environment=STRIPE_WEBHOOK_SECRET=whsec_...
Environment=DEVBENCH_DEV=0
ExecStart=/usr/bin/python3 -m web.license_server --port 9001
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable configforge-license
sudo systemctl start configforge-license
systemctl status configforge-license
```

### Step 4 — Nginx Proxy (Optional)

Add to your nginx config:

```nginx
location /tools/devbench/license/ {
    proxy_pass http://127.0.0.1:9001/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

### Step 5 — Configure Stripe Webhook

1. Go to Stripe Dashboard → Developers → Webhooks
2. Add endpoint: `https://naxiai.com/tools/devbench/license/webhook/stripe`
3. Select events: `checkout.session.completed`, `invoice.paid`
4. Get signing secret (`whsec_...`) and set as `STRIPE_WEBHOOK_SECRET`

### Step 6 — Email Delivery (Production)

The license server generates keys and returns them in the webhook response.
For production, you'll want to email the key to the customer:

**Option A — Stripe built-in:** Add the license key to Stripe's
`payment_intent.description` or a custom metadata field, then use
Stripe's email receipts.

**Option B — SMTP integration:** Add a mailer function in
`web/license_server.py` (or a separate worker) that uses `smtplib`:

```python
import smtplib
from email.message import EmailMessage

def send_license_email(recipient: str, license_key: str):
    msg = EmailMessage()
    msg["Subject"] = "Your ConfigForge License Key"
    msg["From"] = "hi@naxiai.com"
    msg["To"] = recipient
    msg.set_content(f"""\
Thank you for purchasing ConfigForge!

Your license key: {license_key}

Download: https://naxiai.com/tools/devbench/download/{license_key}

To install:
  curl -sSL https://naxiai.com/install.sh | bash

To activate on this machine:
  devbench license activate {license_key}

Need help? Reply to this email.

— The Devbench Team
""")
    with smtplib.SMTP("smtp.example.com", 587) as s:
        s.starttls()
        s.login("user", "password")
        s.send_message(msg)
```

---

## Testing

### Manual curl commands

```bash
# Start server
python3 -m web.license_server --port 9001

# Health check
curl http://127.0.0.1:9001/health

# Verify a key
curl "http://127.0.0.1:9001/license/verify?key=CF.abc.def"

# Activate
curl -X POST http://127.0.0.1:9001/license/activate \
  -H "Content-Type: application/json" \
  -d '{"key":"CF.abc.def","machine_id":"macmini-001"}'

# Simulate Stripe webhook
curl -X POST http://127.0.0.1:9001/webhook/stripe \
  -H "Content-Type: application/json" \
  -d '{"type":"checkout.session.completed","data":{"object":{"customer_email":"buyer@example.com","customer":"cus_123","payment_intent":"pi_456"}}}'
```

### Python test suite

```bash
python3 -m pytest tests/test_license.py -v --tb=short
```

---

## Security Notes

1. **License secret** — Set a strong `DEVBENCH_LICENSE_SECRET` (32+ random bytes)
   in production. The auto-derived fallback is deterministic and should never
   be used for real licensing.

2. **Stripe webhook secret** — Always verify Stripe signatures in production.
   Set `STRIPE_WEBHOOK_SECRET` and `DEVBENCH_DEV=0`.

3. **Activation limit** — 3 machines by default. Adjust in
   `LicenseManager(max_activations=N)` or in the env config.

4. **No database, no persistence** — If `db_path` is not set, activations
   and key storage are not persisted. Keys remain self-validating via HMAC,
   but revocations cannot be enforced.

5. **HTTPS** — Always serve behind nginx with TLS in production. Direct
   HTTP exposes the license keys on the wire.