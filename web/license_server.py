#!/usr/bin/env python3
"""ConfigForge License Server — Stripe webhook + license delivery + download.

Zero external dependencies (stdlib only — http.server, json, sqlite3).

Endpoints::

    POST /webhook/stripe          Stripe checkout.session.completed -> license
    POST /webhook/gumroad         Gumroad sale -> license key generation
    GET  /license/verify?key=XX   Validate a license key
    POST /license/activate        Register a machine activation
    GET  /download/<key>          Download artifact (validates key)

Run via the CLI::

    python3 -m core.cli license-server       # integrated in devbench
    python3 web/license_server.py --port 9001

Or as a systemd service (see ``forge/post-purchase-flow.md``).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Make ``core`` importable no matter the working directory.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from web.license import LicenseManager, LicenseError, InvalidKey, ActivationLimit

log = logging.getLogger(__name__)

DEFAULT_PORT = 9001
LICENSE_DB = _PROJECT_ROOT / "var" / "licenses.db"
ARTIFACT_DIR = _PROJECT_ROOT / "dist"

# ── License Manager (singleton) ──────────────────────────────────────────────

SECRET = os.environ.get("DEVBENCH_LICENSE_SECRET", "").encode("utf-8") or None
DB_PATH = os.environ.get("DEVBENCH_LICENSE_DB", str(LICENSE_DB))
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
CONTACT_EMAIL = os.environ.get("DEVBENCH_CONTACT_EMAIL", "hi@naxiai.com")

lm = LicenseManager(secret=SECRET, db_path=DB_PATH)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _json_response(code: int, data: dict) -> tuple[str, int, dict]:
    body = json.dumps(data, indent=2) + "\n"
    return body, code, {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Stripe-Signature",
    }


def _error(code: int, message: str) -> tuple[str, int, dict]:
    return _json_response(code, {"error": True, "message": message})


def _read_body(handler: BaseHTTPRequestHandler) -> str | None:
    length = int(handler.headers.get("Content-Length", 0))
    if length == 0:
        return None
    return handler.rfile.read(length).decode("utf-8")


# ── Rate Limiter (simple in-memory per-IP) ──────────────────────────────────

_RATE_LIMIT = 60  # requests per minute
_RATE_WINDOW = 60  # seconds
_rates: dict[str, list[float]] = {}


def _check_rate(ip: str) -> bool:
    now = time.time()
    if ip not in _rates:
        _rates[ip] = []
    # Prune old entries
    _rates[ip] = [t for t in _rates[ip] if now - t < _RATE_WINDOW]
    if len(_rates[ip]) >= _RATE_LIMIT:
        return False
    _rates[ip].append(now)
    return True


# ── Request Handler ──────────────────────────────────────────────────────────

class LicenseHandler(BaseHTTPRequestHandler):
    """HTTP request handler for license server endpoints."""

    def log_message(self, fmt: str, *args: object) -> None:
        """Quiet logging — just timestamp + path."""
        print(f"[license] {self.log_date_time_string()} {args[0] if args else ''}")

    # ── CORS preflight ──────────────────────────────────────────────────────

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Stripe-Signature")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    # ── GET ──────────────────────────────────────────────────────────────────

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        qs = urllib.parse.parse_qs(parsed.query)

        # Rate limit check
        client_ip = self.client_address[0]
        if not _check_rate(client_ip):
            self._respond(*_error(429, "Rate limit exceeded (60/min)"))

        elif path == "/health":
            self._respond(*_json_response(200, {
                "status": "healthy",
                "db": str(lm.db_path) if lm.db_path else None,
            }))

        elif path == "/license/verify" and "key" in qs:
            key = qs["key"][0]
            valid = lm.verify(key)
            if valid:
                info = lm.decode(key)
                self._respond(*_json_response(200, {
                    "valid": True,
                    "email": info["email"],
                    "customer_id": info["customer_id"],
                    "issued_at": info["issued_at"],
                    "activations": len(lm.list_activations(key)) if lm.db_path else 0,
                }))
            else:
                self._respond(*_json_response(200, {"valid": False}))

        elif path.startswith("/download/"):
            key = path.split("/download/", 1)[1]
            if not key or not lm.verify(key):
                self._respond(*_error(403, "Invalid or expired license key"))
                return

            # Serve the download landing page (HTML)
            download_html = _PROJECT_ROOT / "web" / "download.html"
            if download_html.exists():
                try:
                    html = download_html.read_text(encoding="utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(html)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    self.wfile.write(html.encode("utf-8"))
                    return
                except OSError as e:
                    self._respond(*_error(500, f"Error reading download page: {e}"))
                    return

            # Fallback: find the latest artifact
            artifact = _find_artifact()
            if not artifact:
                self._respond(*_error(404, "No download available. macOS build coming soon."))
                return

            artifact_path = Path(artifact)
            try:
                data = artifact_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition",
                                 f'attachment; filename="{artifact_path.name}"')
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)
            except OSError as e:
                self._respond(*_error(500, f"Error reading artifact: {e}"))

        else:
            self._respond(*_json_response(200, {
                "service": "ConfigForge License Server",
                "endpoints": [
                    "GET  /health",
                    "GET  /license/verify?key=...",
                    "GET  /download/<key>",
                    "POST /webhook/stripe",
                    "POST /webhook/gumroad",
                    "POST /license/activate",
                    "POST /license/revoke",
                ],
                "docs": "https://naxiai.com/tools/devbench/purchase",
            }))

    # ── POST ─────────────────────────────────────────────────────────────────

    def do_POST(self) -> None:
        path = self.path.rstrip("/")
        client_ip = self.client_address[0]

        if not _check_rate(client_ip):
            self._respond(*_error(429, "Rate limit exceeded (60/min)"))
            return

        body_text = _read_body(self)
        if body_text is None and path not in ("/webhook/stripe", "/webhook/gumroad"):
            self._respond(*_error(400, "Request body required"))
            return

        if path == "/webhook/stripe":
            self._handle_stripe_webhook(body_text)

        elif path == "/webhook/gumroad":
            self._handle_gumroad_webhook(body_text)

        elif path == "/license/activate":
            self._handle_activate(body_text)

        elif path == "/license/revoke":
            self._handle_revoke(body_text)

        else:
            log.debug("Unknown path: %s", path)
            self._respond(*_error(404, "Resource not found"))

    # ── Endpoint Handlers ───────────────────────────────────────────────────

    def _handle_gumroad_webhook(self, body: str | None = None) -> None:
        """Process Gumroad ``sale`` webhook event.

        When Gumroad sends a sale notification, generate a CF-prefixed license
        key via our LicenseManager and store the Gumroad sale info.

        Gumroad payload::

            {
                "sale_id": "abc123",
                "email": "customer@example.com",
                "product_name": "Devbench",
                "price": 19.00,
                "currency": "USD"
            }
        """
        if body is None:
            body = _read_body(self)

        if not body:
            self._respond(*_error(400, "Empty request body"))
            return

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._respond(*_error(400, "Invalid JSON"))
            return

        email = data.get("email", "")
        sale_id = data.get("sale_id", "")

        if not email:
            self._respond(*_error(400, "Missing 'email' in Gumroad sale payload"))
            return

        # Generate our own CF-prefixed license key
        customer_id = f"gum_{sale_id}" if sale_id else f"gum_{int(time.time())}"
        one_year = int(time.time()) + 365 * 86400
        cf_license_key = lm.generate(
            email=email,
            customer_id=customer_id,
            payment_intent=f"gr_{sale_id}" if sale_id else "",
            expiry=one_year,
        )

        # Store Gumroad sale info if DB is available
        if lm.db_path:
            import sqlite3
            try:
                conn = sqlite3.connect(str(lm.db_path))
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS gumroad_sales ("
                    "sale_id TEXT PRIMARY KEY,"
                    "email TEXT NOT NULL,"
                    "product_name TEXT DEFAULT '',"
                    "gumroad_license_key TEXT DEFAULT '',"
                    "cf_license_key TEXT NOT NULL,"
                    "price REAL DEFAULT 0.0,"
                    "currency TEXT DEFAULT 'USD',"
                    "sale_time INTEGER DEFAULT 0,"
                    "created_at INTEGER DEFAULT (strftime('%s','now'))"
                    ")"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO gumroad_sales "
                    "(sale_id, email, product_name, gumroad_license_key, cf_license_key, price, sale_time) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (sale_id, email,
                     data.get("product_name", "Devbench"),
                     data.get("license_key", ""),
                     cf_license_key,
                     float(data.get("price", 19.0)),
                     int(time.time())),
                )
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[license] Warning: could not store Gumroad sale: {e}")

        self._respond(*_json_response(200, {
            "received": True,
            "type": "sale",
            "license_key": cf_license_key,
            "customer_email": email,
            "customer_id": customer_id,
            "gumroad_sale_id": sale_id,
            "expires_at": one_year,
            "message": "License key generated from Gumroad sale",
        }))

    def _handle_stripe_webhook(self, body: str | None = None) -> None:
        """Process Stripe ``checkout.session.completed`` event."""
        if body is None:
            body = _read_body(self)
        sig = self.headers.get("Stripe-Signature", "")

        # In development mode, accept unsigned events
        is_dev = os.environ.get("DEVBENCH_DEV", "1") == "1"
        if STRIPE_WEBHOOK_SECRET and not is_dev:
            # Verify Stripe signature (simple HMAC match)
            if not _verify_stripe_sig(body or "", sig):
                self._respond(*_error(401, "Invalid Stripe signature"))
                return

        if not body:
            self._respond(*_error(400, "Empty request body"))
            return

        try:
            event = json.loads(body)
        except json.JSONDecodeError:
            self._respond(*_error(400, "Invalid JSON"))
            return

        # Handle the event
        event_type = event.get("type", "")
        if event_type == "checkout.session.completed":
            session = event.get("data", {}).get("object", {})
            self._process_checkout(session)
        elif event_type == "invoice.paid":
            session = event.get("data", {}).get("object", {})
            self._process_checkout(session)
        else:
            # Acknowledge but don't process unknown event types
            self._respond(*_json_response(200, {
                "received": True,
                "type": event_type,
                "note": "Unhandled event type (acknowledged)",
            }))

    def _process_checkout(self, session: dict) -> None:
        """Generate and return a license key for a completed checkout."""
        customer_email = session.get("customer_email") or session.get("customer_details", {}).get("email", "unknown@checkout")
        customer_id = session.get("customer", f"cus_{int(time.time())}")
        payment_intent = session.get("payment_intent", f"pi_{int(time.time())}")

        # Generate license key (1 year expiry by default)
        one_year = int(time.time()) + 365 * 86400
        license_key = lm.generate(
            email=customer_email,
            customer_id=customer_id,
            payment_intent=payment_intent,
            expiry=one_year,
        )

        self._respond(*_json_response(200, {
            "received": True,
            "type": "checkout.session.completed",
            "license_key": license_key,
            "customer_email": customer_email,
            "customer_id": customer_id,
            "expires_at": one_year,
            "delivery": "License key generated. Sent via email (configure SMTP in production).",
        }))

    def _handle_activate(self, body_text: str | None) -> None:
        """Activate a license key on a specific machine."""
        if not body_text:
            self._respond(*_error(400, "Request body required"))
            return
        try:
            data = json.loads(body_text)
        except json.JSONDecodeError:
            self._respond(*_error(400, "Invalid JSON"))
            return

        key = data.get("key", "")
        machine_id = data.get("machine_id", "")

        if not key or not machine_id:
            self._respond(*_error(400, "Both 'key' and 'machine_id' are required"))
            return

        try:
            result = lm.activate(key, machine_id)
            self._respond(*_json_response(200, result))
        except InvalidKey:
            self._respond(*_error(403, "Invalid license key"))
        except ActivationLimit as e:
            self._respond(*_error(403, str(e)))

    def _handle_revoke(self, body_text: str | None) -> None:
        """Revoke a license key."""
        if not body_text:
            self._respond(*_error(400, "Request body required"))
            return
        try:
            data = json.loads(body_text)
        except json.JSONDecodeError:
            self._respond(*_error(400, "Invalid JSON"))
            return

        key = data.get("key", "")
        if not key:
            self._respond(*_error(400, "'key' field required"))
            return

        ok = lm.revoke(key)
        self._respond(*_json_response(200, {
            "revoked": ok,
            "message": "License revoked" if ok else "Key not found in database",
        }))

    # ── Response Helper ──────────────────────────────────────────────────────

    def _respond(self, body: str, code: int, headers: dict) -> None:
        self.send_response(code)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))


# ── Stripe Signature Verification ────────────────────────────────────────────

import hmac
import hashlib


def _verify_stripe_sig(body: str, sig_header: str) -> bool:
    """Verify Stripe webhook signature (simplified — production should use
    ``stripe.Webhook.construct_event()`` with the ``stripe`` pip package)."""
    if not sig_header:
        return False
    # Stripe sends: t=<timestamp>,v1=<signature>,v0=<signature>...
    # We check v1 only (the current version)
    try:
        pairs = {}
        for part in sig_header.split(","):
            kv = part.split("=", 1)
            if len(kv) == 2:
                pairs[kv[0]] = kv[1]
        expected_sig = pairs.get("v1", "")
        if not expected_sig:
            return False
        # Compute HMAC
        computed = hmac.new(
            STRIPE_WEBHOOK_SECRET.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(computed, expected_sig)
    except Exception:
        return False


# ── Artifact Discovery ───────────────────────────────────────────────────────

def _find_artifact() -> str | None:
    """Find the latest distributable artifact in ``dist/``."""
    if not ARTIFACT_DIR.exists():
        return None
    candidates = sorted(ARTIFACT_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return None
    # Prefer .dmg (macOS) or .tar.gz / .whl (pip)
    extensions = [".dmg", ".tar.gz", ".whl", ".zip"]
    for ext in extensions:
        for c in candidates:
            if c.name.endswith(ext):
                return str(c)
    # Fall back to newest anything
    return str(candidates[0]) if candidates else None


# ── Server Entrypoint ────────────────────────────────────────────────────────

def run_server(host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> None:
    """Start the license server."""
    # Ensure directories exist
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    server = ThreadingHTTPServer((host, port), LicenseHandler)
    print(f"[license] server listening on http://{host}:{port}")
    print(f"[license] license DB: {DB_PATH}")
    print(f"[license] dev mode: {os.environ.get('DEVBENCH_DEV', '1')}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


def _main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="ConfigForge License Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Port (default: {DEFAULT_PORT})")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Bind address (default: 127.0.0.1)")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    _main()