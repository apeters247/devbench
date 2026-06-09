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
from web.api import RateLimiter

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


# Reject request bodies larger than this to avoid trivial memory-exhaustion
# from a huge Content-Length. 1 MB is far above any real webhook/activation
# payload.
MAX_BODY_SIZE = 1 * 1024 * 1024  # 1 MB


class _BodyTooLarge(Exception):
    """Raised when a request body exceeds MAX_BODY_SIZE."""


def _read_body(handler: BaseHTTPRequestHandler) -> str | None:
    try:
        length = int(handler.headers.get("Content-Length", 0))
    except (TypeError, ValueError):
        length = 0
    if length == 0:
        return None
    if length > MAX_BODY_SIZE:
        raise _BodyTooLarge(length)
    return handler.rfile.read(length).decode("utf-8")


# ── Rate Limiter (thread-safe, imported from api.py) ─────────────────────────

_rate_limiter = RateLimiter(max_requests=60, window=60)


def _check_rate(ip: str) -> bool:
    return _rate_limiter.allow(ip)


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
        path = urllib.parse.urlparse(self.path).path.rstrip("/")
        client_ip = self.client_address[0]

        if not _check_rate(client_ip):
            self._respond(*_error(429, "Rate limit exceeded (60/min)"))
            return

        try:
            body_text = _read_body(self)
        except _BodyTooLarge:
            self._respond(*_error(413, f"Request body too large (limit is {MAX_BODY_SIZE} bytes)"))
            return
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

        elif path == "/license/trial":
            self._handle_trial(body_text)
        else:
            self._respond(*_error(404, f"Unknown path: {path}"))

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

        # Production by default: signatures are verified unless DEVBENCH_DEV=1
        # is explicitly set to accept unsigned events for local development.
        is_dev = os.environ.get("DEVBENCH_DEV", "0") == "1"
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
            self._process_renewal(session)
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

    def _process_renewal(self, session: dict) -> None:
        """Renew an existing license on ``invoice.paid`` (recurring payment).

        The customer already received a key from the original
        ``checkout.session.completed`` event, so minting a fresh key on every
        renewal would leave them with a pile of duplicate licenses. Instead,
        look up their existing license by email and extend its expiry by a
        year. Only fall back to issuing a new key if no prior license exists.
        """
        customer_email = (
            session.get("customer_email")
            or session.get("customer_details", {}).get("email", "")
        )
        one_year_seconds = 365 * 86400

        existing = lm.find_keys_by_email(customer_email) if customer_email else []
        if existing:
            latest = existing[0]
            new_expiry = lm.extend_expiry(latest["key"], one_year_seconds)
            self._respond(*_json_response(200, {
                "received": True,
                "type": "invoice.paid",
                "license_key": latest["key"],
                "customer_email": customer_email,
                "customer_id": latest["customer_id"],
                "expires_at": new_expiry,
                "renewed": True,
                "delivery": "Existing license renewed (expiry extended by 1 year).",
            }))
            return

        # No prior license for this customer — issue a fresh one.
        self._process_checkout(session)

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


    def _handle_trial(self, body_text: str | None) -> None:
        """Generate a 14-day trial license key."""
        if not body_text:
            body_text = '{}'
        try:
            data = json.loads(body_text)
        except json.JSONDecodeError:
            self._respond(*_error(400, "Invalid JSON"))
            return

        email = data.get("email", "trial@example.com")
        trial_days = 14
        expiry = int(time.time()) + trial_days * 86400
        try:
            license_key = lm.generate(
                email=email,
                customer_id=f"trial_{int(time.time())}",
                payment_intent="",
                expiry=expiry,
            )
        except Exception as e:
            self._respond(*_error(500, f"Failed to generate trial key: {e}"))
            return

        self._respond(*_json_response(200, {
            "received": True,
            "type": "trial",
            "license_key": license_key,
            "email": email,
            "expires_at": expiry,
            "message": f"Trial license key generated. Valid for {trial_days} days.",
        }))

    # ── Response Helper ──────────────────────────────────────────────────────

    def _respond(self, body: str, code: int, headers: dict) -> None:
        # Webhook endpoints (Stripe/Gumroad) are server-to-server only and must
        # never be browser-callable, so strip the permissive CORS header from
        # their responses. A leaked `Access-Control-Allow-Origin: *` here would
        # let any website read webhook responses cross-origin.
        request_path = urllib.parse.urlparse(self.path).path.rstrip("/")
        if request_path.startswith("/webhook/"):
            headers = {k: v for k, v in headers.items() if k != "Access-Control-Allow-Origin"}
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
    print(f"[license] dev mode: {os.environ.get('DEVBENCH_DEV', '0')}")
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