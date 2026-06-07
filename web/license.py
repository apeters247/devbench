#!/usr/bin/env python3
"""ConfigForge license key generation and validation.

Self-validating HMAC-signed license keys (no DB needed for basic
verification) plus optional SQLite-backed activation tracking for
multi-machine limits.

Key format::

    CF-<32-char-hex-payload>-<44-char-base64url-HMAC>

Usage::

    from web.license import LicenseManager

    lm = LicenseManager(secret=b"my-secret-key")
    key = lm.generate("customer@example.com", "cus_xxx", "pi_xxx")
    assert lm.verify(key)       # True
    info = lm.decode(key)       # {email, customer_id, payment_intent, issued_at}
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import struct
import time
from pathlib import Path
from typing import Any

__version__ = "1.0.0"

# ── Constants ────────────────────────────────────────────────────────────────

KEY_PREFIX = "CF"
KEY_SEP = "."            # separator character (never in hex or base64url chars)
PAYLOAD_BYTES = 32       # 32 hex chars = 16 bytes of entropy
HMAC_BYTES = 32          # 32 bytes → 43 base64 chars (44 with = padding)
MAX_ACTIVATIONS = 3      # default activations per license

# ── Exceptions ───────────────────────────────────────────────────────────────

class LicenseError(Exception):
    """Base license error."""

class InvalidKey(LicenseError):
    """Key format or HMAC validation failed."""

class ExpiredKey(LicenseError):
    """Key has expired."""

class ActivationLimit(LicenseError):
    """Too many machines activated on this license."""

# ── Core License Manager ─────────────────────────────────────────────────────

class LicenseManager:
    """HMAC-signed license key generation and validation.

    Parameters
    ----------
    secret:
        HMAC signing secret (at least 32 bytes recommended).
    db_path:
        Optional path to SQLite database for activation tracking.
        If None, activations are not tracked (one-key-many-machines allowed).
    max_activations:
        Max machines per license key (default 3). Only used when db_path set.
    """

    def __init__(
        self,
        secret: bytes | None = None,
        db_path: str | Path | None = None,
        max_activations: int = MAX_ACTIVATIONS,
    ):
        self.secret = secret or _default_secret()
        self.max_activations = max_activations

        if db_path:
            self.db_path = Path(db_path)
            self._init_db()
        else:
            self.db_path = None

    # ── Key Generation ───────────────────────────────────────────────────────

    def generate(
        self,
        email: str,
        customer_id: str,
        payment_intent: str = "",
        expiry: int = 0,
    ) -> str:
        """Generate a new HMAC-signed license key.

        Parameters
        ----------
        email:
            Purchaser email (stored in payload for audit).
        customer_id:
            Stripe customer ID or equivalent.
        payment_intent:
            Stripe payment intent ID (optional audit trail).
        expiry:
            Unix timestamp after which the key expires (0 = never).

        Returns
        -------
        License key string like ``CF.<base64_body>.<sig>``.
        """
        random_hex = secrets.token_hex(PAYLOAD_BYTES)
        metadata = json.dumps(
            {
                "e": email,
                "c": customer_id,
                "p": payment_intent,
                "i": int(time.time()),
                "x": expiry,
            },
            separators=(",", ":"),
        )
        # The body is hex_random + colon + json_metadata, base64-encoded
        body = f"{random_hex}:{metadata}"
        payload = base64.urlsafe_b64encode(body.encode("utf-8")).rstrip(b"=").decode("ascii")
        sig = self._sign(payload)

        key = f"{KEY_PREFIX}{KEY_SEP}{payload}{KEY_SEP}{sig}"

        # Store in DB if available
        if self.db_path:
            self._store_key(key, email, customer_id, payment_intent, expiry)

        return key

    # ── Verification ─────────────────────────────────────────────────────────

    def verify(self, key: str, *, check_activations: bool = False) -> bool:
        """Verify a license key's HMAC signature and expiry.

        Parameters
        ----------
        key:
            License key string.
        check_activations:
            If True, also checks the activation limit (requires db_path).

        Returns
        -------
        True if valid, False otherwise.
        """
        try:
            payload, metadata, _ = self._parse(key)
            expected_sig = self._sign(payload)
            actual_sig = self._parse(key)[2]

            if not hmac.compare_digest(expected_sig, actual_sig):
                return False

            # Check expiry
            meta = json.loads(metadata)
            if meta.get("x") and meta["x"] > 0 and time.time() > meta["x"]:
                return False

            # Check activation limit
            if check_activations and self.db_path:
                return self._check_activation_limit(key)

            return True
        except (LicenseError, ValueError, json.JSONDecodeError):
            return False

    def decode(self, key: str) -> dict[str, Any]:
        """Decode a license key and return its metadata.

        Returns
        -------
        Dict with keys: email, customer_id, payment_intent, issued_at, expiry.
        """
        payload, metadata, sig = self._parse(key)
        expected = self._sign(payload)
        if not hmac.compare_digest(expected, sig):
            raise InvalidKey("Invalid signature")

        meta = json.loads(metadata)
        return {
            "email": meta["e"],
            "customer_id": meta["c"],
            "payment_intent": meta.get("p", ""),
            "issued_at": meta["i"],
            "expiry": meta.get("x", 0),
            "key": key,
            "valid": True,
        }

    # ── Activation Tracking ──────────────────────────────────────────────────

    def activate(self, key: str, machine_id: str) -> dict[str, Any]:
        """Register a machine activation for a license key.

        Parameters
        ----------
        key:
            Valid license key.
        machine_id:
            Unique machine identifier (e.g., hostname + MAC hash).

        Returns
        -------
        Dict with status, message, and activations count.

        Raises
        ------
        InvalidKey if key is invalid.
        ActivationLimit if max activations reached.
        """
        if not self.verify(key):
            raise InvalidKey("Invalid license key")

        if not self.db_path:
            return {"status": "ok", "message": "Activation not tracked", "activations": 0}

        conn = sqlite3.connect(str(self.db_path))
        try:
            # Check if this machine already activated
            cur = conn.execute(
                "SELECT id FROM activations WHERE license_key = ? AND machine_id = ?",
                (key, machine_id),
            )
            if cur.fetchone():
                return {"status": "ok", "message": "Already activated", "activations": self._count_activations(key)}

            # Check limit
            count = self._count_activations(key)
            if count >= self.max_activations:
                raise ActivationLimit(
                    f"Activation limit of {self.max_activations} reached "
                    f"(currently {count} activations)"
                )

            conn.execute(
                "INSERT INTO activations (license_key, machine_id, activated_at) VALUES (?, ?, ?)",
                (key, machine_id, int(time.time())),
            )
            conn.commit()
            return {
                "status": "ok",
                "message": "Activated",
                "activations": count + 1,
            }
        finally:
            conn.close()

    def deactivate(self, key: str, machine_id: str) -> dict[str, Any]:
        """Remove a machine activation."""
        if not self.db_path:
            return {"status": "ok", "message": "Activation not tracked"}

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "DELETE FROM activations WHERE license_key = ? AND machine_id = ?",
                (key, machine_id),
            )
            conn.commit()
            return {
                "status": "ok",
                "message": "Deactivated",
                "activations": self._count_activations(key),
            }
        finally:
            conn.close()

    def list_activations(self, key: str) -> list[dict[str, Any]]:
        """List all activations for a license key."""
        if not self.db_path:
            return []

        conn = sqlite3.connect(str(self.db_path))
        try:
            cur = conn.execute(
                "SELECT machine_id, activated_at FROM activations WHERE license_key = ? ORDER BY activated_at",
                (key,),
            )
            return [{"machine_id": r[0], "activated_at": r[1]} for r in cur.fetchall()]
        finally:
            conn.close()

    # ── Database Management ──────────────────────────────────────────────────

    def revoke(self, key: str) -> bool:
        """Revoke a license key by setting its expiry to now."""
        if not self.db_path:
            return False
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "UPDATE licenses SET expiry = ? WHERE license_key = ?",
                (int(time.time()), key),
            )
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    def get_key_info(self, key: str) -> dict[str, Any] | None:
        """Get stored info for a key (from DB)."""
        if not self.db_path:
            return None
        conn = sqlite3.connect(str(self.db_path))
        try:
            cur = conn.execute(
                "SELECT email, customer_id, payment_intent, issued_at, expiry FROM licenses WHERE license_key = ?",
                (key,),
            )
            row = cur.fetchone()
            if row:
                return {
                    "email": row[0],
                    "customer_id": row[1],
                    "payment_intent": row[2],
                    "issued_at": row[3],
                    "expiry": row[4],
                    "activations": self._count_activations(key),
                }
            return None
        finally:
            conn.close()

    def find_keys_by_email(self, email: str) -> list[dict[str, Any]]:
        """Return stored license rows for ``email``, newest first.

        Used to renew an existing customer's license rather than minting a
        brand-new key on every recurring payment.
        """
        if not self.db_path:
            return []
        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute(
                "SELECT license_key, email, customer_id, payment_intent, issued_at, expiry "
                "FROM licenses WHERE email = ? ORDER BY issued_at DESC, created_at DESC",
                (email,),
            ).fetchall()
            return [
                {
                    "key": r[0],
                    "email": r[1],
                    "customer_id": r[2],
                    "payment_intent": r[3],
                    "issued_at": r[4],
                    "expiry": r[5],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def extend_expiry(self, key: str, additional_seconds: int) -> int:
        """Extend a stored license's expiry by ``additional_seconds``.

        The extension is anchored to the later of the current expiry or now, so
        renewing an already-lapsed license still grants a full extra period. A
        stored expiry of 0 (never expires) is left untouched.

        Returns the new expiry timestamp, or 0 if the key is unknown / has no
        DB row / never expires.
        """
        if not self.db_path:
            return 0
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(
                "SELECT expiry FROM licenses WHERE license_key = ?", (key,)
            ).fetchone()
            if row is None:
                return 0
            current = row[0] or 0
            if current == 0:
                return 0  # never expires — nothing to extend
            new_expiry = max(current, int(time.time())) + additional_seconds
            conn.execute(
                "UPDATE licenses SET expiry = ? WHERE license_key = ?",
                (new_expiry, key),
            )
            conn.commit()
            return new_expiry
        finally:
            conn.close()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _sign(self, data: str) -> str:
        """HMAC-SHA256 signature, base64-url encoded (no padding)."""
        h = hmac.new(self.secret, data.encode("utf-8"), hashlib.sha256)
        return base64.urlsafe_b64encode(h.digest()).rstrip(b"=").decode("ascii")

    def _parse(self, key: str) -> tuple[str, str, str]:
        """Split a key into (payload_b64, metadata_json, signature).

        ``payload_b64`` is the base64url-encoded component (this is what
        gets HMAC-signed — the decoded metadata is returned separately).
        """
        parts = key.strip().split(KEY_SEP, 2)
        if len(parts) != 3 or parts[0] != KEY_PREFIX:
            raise InvalidKey(f"Invalid key format (expected {KEY_PREFIX}{KEY_SEP}payload{KEY_SEP}sig)")

        payload_b64 = parts[1]
        sig = parts[2]

        # Decode base64 body to extract metadata
        try:
            padded = payload_b64 + "=" * (4 - len(payload_b64) % 4) if len(payload_b64) % 4 else payload_b64
            body = base64.urlsafe_b64decode(padded).decode("utf-8")
        except Exception as e:
            raise InvalidKey(f"Cannot decode payload: {e}") from e

        # body = "random_hex:json_metadata"
        if ":" not in body:
            raise InvalidKey("Payload missing metadata separator")

        _, metadata = body.split(":", 1)
        return payload_b64, metadata, sig

    def _init_db(self) -> None:
        """Create SQLite tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS licenses (
                    license_key TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    customer_id TEXT NOT NULL,
                    payment_intent TEXT DEFAULT '',
                    issued_at INTEGER NOT NULL,
                    expiry INTEGER DEFAULT 0,
                    created_at INTEGER DEFAULT (strftime('%s','now'))
                );
                CREATE TABLE IF NOT EXISTS activations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    license_key TEXT NOT NULL REFERENCES licenses(license_key),
                    machine_id TEXT NOT NULL,
                    activated_at INTEGER NOT NULL,
                    UNIQUE(license_key, machine_id)
                );
                CREATE INDEX IF NOT EXISTS idx_activations_key ON activations(license_key);
            """)
            conn.commit()
        finally:
            conn.close()

    def _store_key(
        self,
        key: str,
        email: str,
        customer_id: str,
        payment_intent: str,
        expiry: int,
    ) -> None:
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "INSERT OR IGNORE INTO licenses (license_key, email, customer_id, payment_intent, issued_at, expiry) VALUES (?, ?, ?, ?, ?, ?)",
                (key, email, customer_id, payment_intent, int(time.time()), expiry),
            )
            conn.commit()
        finally:
            conn.close()

    def _count_activations(self, key: str) -> int:
        if not self.db_path:
            return 0
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM activations WHERE license_key = ?",
                (key,),
            ).fetchone()
            return row[0] if row else 0
        finally:
            conn.close()


def _default_secret() -> bytes:
    """Return the HMAC signing secret from the environment.

    The secret MUST be supplied via ``DEVBENCH_LICENSE_SECRET``. A
    machine-derived fallback would let anyone who knows the hostname forge
    valid license keys, so it is only permitted when ``DEVBENCH_DEV=1`` is
    explicitly set (local development / tests). In every other case a missing
    secret is a hard error rather than a silent downgrade to weak signing.
    """
    env_secret = os.environ.get("DEVBENCH_LICENSE_SECRET", "")
    if env_secret:
        return env_secret.encode("utf-8")

    if os.environ.get("DEVBENCH_DEV") == "1":
        # Dev-only fallback: derive from machine info. NOT cryptographically
        # strong (predictable from the hostname) — never use in production.
        raw = f"{os.uname().nodename}-{os.uname().machine}-ConfigForge-v1"
        return hashlib.sha256(raw.encode()).digest()

    raise ValueError(
        "DEVBENCH_LICENSE_SECRET is required to sign license keys. Set it to a "
        "strong random secret in production. For local development only, set "
        "DEVBENCH_DEV=1 to use an insecure machine-derived fallback secret."
    )


# ── CLI ──────────────────────────────────────────────────────────────────────

def _main() -> None:
    """Minimal CLI for testing license key operations."""
    import argparse

    parser = argparse.ArgumentParser(description="ConfigForge License Manager CLI")
    parser.add_argument("action", choices=["generate", "verify", "decode"])
    parser.add_argument("--email", default="test@example.com")
    parser.add_argument("--customer", default="cus_test")
    parser.add_argument("--payment", default="pi_test")
    parser.add_argument("--secret", default="",
                        help="HMAC secret (default: auto-derive)")
    parser.add_argument("key", nargs="?", help="License key (for verify/decode)")
    parser.add_argument("--db", default="", help="SQLite DB path")

    args = parser.parse_args()

    secret = args.secret.encode("utf-8") if args.secret else None
    db = args.db or None
    lm = LicenseManager(secret=secret, db_path=db)

    if args.action == "generate":
        key = lm.generate(args.email, args.customer, args.payment)
        info = lm.decode(key)
        print(f"License key: {key}")
        print(f"Customer:    {info['email']} ({info['customer_id']})")
        print(f"Issued at:   {info['issued_at']}")
    elif args.action == "verify":
        if not args.key:
            parser.error("verify requires a key argument")
        valid = lm.verify(args.key)
        print(f"Key:   {args.key}")
        print(f"Valid: {valid}")
    elif args.action == "decode":
        if not args.key:
            parser.error("decode requires a key argument")
        try:
            info = lm.decode(args.key)
            for k, v in info.items():
                print(f"{k}: {v}")
        except LicenseError as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    _main()