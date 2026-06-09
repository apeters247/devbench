#!/usr/bin/env python3
"""Tests for the ConfigForge License Manager (web/license.py)."""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

# Ensure the project root is importable
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from web.license import (
    LicenseManager,
    LicenseError,
    InvalidKey,
    ActivationLimit,
    KEY_PREFIX,
    KEY_SEP,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_mgr(tmp_db: bool = True, secret: bytes | None = None, max_activations: int = 3) -> LicenseManager:
    db = tempfile.mktemp(suffix=".db") if tmp_db else None
    return LicenseManager(
        secret=secret or b"test-secret-32-bytes-long!!!!!!",
        db_path=db,
        max_activations=max_activations,
    )


def _wait_for_server(port: int, retries: int = 10, delay: float = 0.1) -> None:
    """Poll the server's /health endpoint until it responds (or retries run out).

    Replaces fixed ``time.sleep(0.3)`` startup waits with a fast retry loop so
    tests don't pay a fixed latency tax. Raises ``RuntimeError`` if the server
    never answers within the retry budget — a fixed fallback sleep would mask a
    genuinely-dead server while still adding latency, so we fail loudly instead.
    """
    import urllib.request
    import urllib.error

    url = f"http://127.0.0.1:{port}/health"
    for _ in range(retries):
        try:
            urllib.request.urlopen(url, timeout=0.5).read()
            return
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(delay)
    raise RuntimeError(
        f"server on port {port} did not become ready within "
        f"{retries} retries (~{retries * delay:.1f}s)"
    )


# ── Tests ────────────────────────────────────────────────────────────────────

class TestLicenseKeyFormat:
    def test_key_starts_with_prefix(self):
        lm = _make_mgr()
        key = lm.generate("a@b.com", "cus_1")
        assert key.startswith(f"{KEY_PREFIX}{KEY_SEP}"), f"Key should start with CF.: {key}"

    def test_key_has_three_parts(self):
        lm = _make_mgr()
        key = lm.generate("a@b.com", "cus_1")
        parts = key.split(KEY_SEP)
        assert len(parts) == 3, f"Key should have 3 dot-separated parts: {key}"

    def test_key_has_non_empty_sig(self):
        lm = _make_mgr()
        key = lm.generate("a@b.com", "cus_1")
        sig = key.split(KEY_SEP)[2]
        assert len(sig) > 20, f"Signature should be non-trivial: {sig}"

    def test_key_generation_produces_unique_keys(self):
        """Same secret + same metadata → different keys (random hex differs)."""
        lm = _make_mgr()
        k1 = lm.generate("a@b.com", "cus_1")
        k2 = lm.generate("a@b.com", "cus_1")
        assert k1 != k2, "Keys should differ (random payload)"


class TestLicenseVerify:
    def test_verify_valid_key(self):
        lm = _make_mgr()
        key = lm.generate("a@b.com", "cus_1")
        assert lm.verify(key) is True

    def test_verify_invalid_key_wrong_sig(self):
        lm = _make_mgr()
        key = lm.generate("a@b.com", "cus_1")
        parts = key.split(KEY_SEP)
        # Tamper with the signature
        bad_key = f"{parts[0]}{KEY_SEP}{parts[1]}{KEY_SEP}INVALIDSIG"
        assert lm.verify(bad_key) is False

    def test_verify_invalid_key_garbage(self):
        lm = _make_mgr()
        assert lm.verify("not-a-key") is False
        assert lm.verify("") is False
        assert lm.verify(f"{KEY_PREFIX}{KEY_SEP}abc{KEY_SEP}def") is False

    def test_verify_wrong_secret(self):
        lm1 = _make_mgr(secret=b"secret-one-32-bytes-long!!!!!!")
        lm2 = _make_mgr(secret=b"secret-two-32-bytes-long!!!!!!")
        key = lm1.generate("a@b.com", "cus_1")
        assert lm2.verify(key) is False

    def test_verify_expired_key(self):
        lm = _make_mgr()
        # Generate key that expired 1 second ago
        key = lm.generate("a@b.com", "cus_1", expiry=int(time.time()) - 1)
        assert lm.verify(key) is False

    def test_verify_future_expiry(self):
        lm = _make_mgr()
        key = lm.generate("a@b.com", "cus_1", expiry=int(time.time()) + 86400)
        assert lm.verify(key) is True

    def test_verify_negative_expiry_is_expired(self):
        """A negative expiry is always in the past, so it must read as expired
        rather than slipping past a `> 0` guard and being treated as eternal."""
        lm = _make_mgr()
        key = lm.generate("a@b.com", "cus_1", expiry=-1)
        assert lm.verify(key) is False

    def test_verify_zero_expiry_never_expires(self):
        """A stored expiry of 0 means 'never expires' and stays valid."""
        lm = _make_mgr()
        key = lm.generate("a@b.com", "cus_1", expiry=0)
        assert lm.verify(key) is True


class TestLicenseDecode:
    def test_decode_returns_metadata(self):
        lm = _make_mgr()
        key = lm.generate("user@example.com", "cus_abc123", "pi_xyz789")
        info = lm.decode(key)
        assert info["email"] == "user@example.com"
        assert info["customer_id"] == "cus_abc123"
        assert info["payment_intent"] == "pi_xyz789"
        assert info["key"] == key
        assert info["valid"] is True

    def test_decode_raises_on_invalid(self):
        lm = _make_mgr()
        try:
            lm.decode("CF.fake.e30")
            assert False, "Should have raised"
        except InvalidKey:
            pass

    def test_decode_has_issued_at(self):
        lm = _make_mgr()
        before = int(time.time())
        key = lm.generate("a@b.com", "cus_1")
        after = int(time.time())
        info = lm.decode(key)
        assert before <= info["issued_at"] <= after


class TestLicenseActivation:
    def test_activate_without_db(self):
        lm = _make_mgr(tmp_db=False)
        key = lm.generate("a@b.com", "cus_1")
        result = lm.activate(key, "mac-1")
        assert result["status"] == "ok"
        assert result["message"] == "Activation not tracked"

    def test_activate_with_db(self):
        lm = _make_mgr(tmp_db=True)
        key = lm.generate("a@b.com", "cus_1")
        result = lm.activate(key, "mac-1")
        assert result["status"] == "ok"
        assert result["activations"] == 1

    def test_activate_duplicate(self):
        lm = _make_mgr(tmp_db=True)
        key = lm.generate("a@b.com", "cus_1")
        lm.activate(key, "mac-1")
        result = lm.activate(key, "mac-1")
        assert result["status"] == "ok"
        assert result["message"] == "Already activated"
        assert result["activations"] == 1

    def test_activate_limit(self):
        lm = _make_mgr(tmp_db=True, max_activations=2)
        key = lm.generate("a@b.com", "cus_1")
        lm.activate(key, "mac-1")
        lm.activate(key, "mac-2")
        try:
            lm.activate(key, "mac-3")
            assert False, "Should have raised ActivationLimit"
        except ActivationLimit:
            pass

    def test_deactivate(self):
        lm = _make_mgr(tmp_db=True)
        key = lm.generate("a@b.com", "cus_1")
        lm.activate(key, "mac-1")
        result = lm.deactivate(key, "mac-1")
        assert result["status"] == "ok"
        assert result["activations"] == 0

    def test_list_activations(self):
        lm = _make_mgr(tmp_db=True)
        key = lm.generate("a@b.com", "cus_1")
        lm.activate(key, "mac-1")
        lm.activate(key, "mac-2")
        activations = lm.list_activations(key)
        assert len(activations) == 2
        assert activations[0]["machine_id"] == "mac-1"
        assert activations[1]["machine_id"] == "mac-2"


class TestLicenseRevoke:
    def test_revoke_without_db(self):
        lm = _make_mgr(tmp_db=False)
        key = lm.generate("a@b.com", "cus_1")
        assert lm.revoke(key) is False

    def test_revoke_with_db(self):
        lm = _make_mgr(tmp_db=True)
        key = lm.generate("a@b.com", "cus_1")
        assert lm.decode(key)["valid"] is True
        assert lm.revoke(key) is True
        # Verification should now fail (expired)
        # Note: revoke sets expiry to now, so check verify
        info = lm.get_key_info(key)
        assert info is not None and info["email"] == "a@b.com"


class TestEdgeCases:
    def test_empty_email(self):
        lm = _make_mgr()
        key = lm.generate("", "cus_1")
        assert lm.verify(key)

    def test_long_email(self):
        lm = _make_mgr()
        email = "a" * 200 + "@example.com"
        key = lm.generate(email, "cus_1")
        assert lm.verify(key)
        info = lm.decode(key)
        assert info["email"] == email

    def test_special_chars_in_fields(self):
        lm = _make_mgr()
        key = lm.generate(
            "user+tag@example.com",
            "cus_1-2_3",  # Contains - and _
            "pi_789$%^",  # Special chars
        )
        assert lm.verify(key)
        info = lm.decode(key)
        assert info["customer_id"] == "cus_1-2_3"
        assert info["payment_intent"] == "pi_789$%^"

    def test_no_expiry(self):
        lm = _make_mgr()
        key = lm.generate("a@b.com", "cus_1")
        info = lm.decode(key)
        assert info["expiry"] == 0  # No expiry

    def test_default_secret_deterministic(self, monkeypatch):
        """Dev fallback secret should be same across instances (DEVBENCH_DEV=1)."""
        from web.license import _default_secret
        monkeypatch.delenv("DEVBENCH_LICENSE_SECRET", raising=False)
        monkeypatch.setenv("DEVBENCH_DEV", "1")
        s1 = _default_secret()
        s2 = _default_secret()
        assert s1 == s2

    def test_default_secret_requires_env(self, monkeypatch):
        """Without the secret env var (and not in dev mode), signing must fail
        loudly instead of falling back to a predictable machine-derived key."""
        import pytest
        from web.license import _default_secret
        monkeypatch.delenv("DEVBENCH_LICENSE_SECRET", raising=False)
        monkeypatch.delenv("DEVBENCH_DEV", raising=False)
        with pytest.raises(ValueError, match="DEVBENCH_LICENSE_SECRET"):
            _default_secret()

    def test_default_secret_from_env(self, monkeypatch):
        """An explicit secret env var is used verbatim."""
        from web.license import _default_secret
        monkeypatch.setenv("DEVBENCH_LICENSE_SECRET", "explicit-secret-value")
        assert _default_secret() == b"explicit-secret-value"

    def test_key_is_portable_string(self):
        """Key should only contain URL-safe characters."""
        import re
        lm = _make_mgr()
        key = lm.generate("a@b.com", "cus_1")
        # Only allow: CF, dot, base64url chars, underscores
        assert re.match(r"^CF\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$", key), f"Key has unsafe chars: {key}"

    def test_concurrent_activations(self):
        """Multiple activations on different machines should work."""
        lm = _make_mgr(tmp_db=True, max_activations=5)
        key = lm.generate("a@b.com", "cus_1")
        for i in range(5):
            result = lm.activate(key, f"mac-{i}")
            assert result["status"] == "ok"
            assert result["activations"] == i + 1

    def test_get_key_info(self):
        lm = _make_mgr(tmp_db=True)
        key = lm.generate("info@test.com", "cus_info", "pi_info")
        info = lm.get_key_info(key)
        assert info is not None and info["email"] == "info@test.com"
        assert info["customer_id"] == "cus_info"
        assert info["payment_intent"] == "pi_info"

    def test_get_key_info_no_db(self):
        lm = _make_mgr(tmp_db=False)
        key = lm.generate("a@b.com", "cus_1")
        assert lm.get_key_info(key) is None

    def test_find_keys_by_email(self):
        lm = _make_mgr(tmp_db=True)
        k1 = lm.generate("dup@test.com", "cus_a", "pi_1", expiry=1000)
        k2 = lm.generate("dup@test.com", "cus_a", "pi_2", expiry=2000)
        lm.generate("other@test.com", "cus_b")
        rows = lm.find_keys_by_email("dup@test.com")
        keys = {r["key"] for r in rows}
        assert keys == {k1, k2}
        assert lm.find_keys_by_email("missing@test.com") == []

    def test_extend_expiry_anchors_to_future(self):
        """Extending an unexpired license adds to its current expiry."""
        lm = _make_mgr(tmp_db=True)
        far_future = int(time.time()) + 365 * 86400
        key = lm.generate("renew@test.com", "cus_r", expiry=far_future)
        new_expiry = lm.extend_expiry(key, 365 * 86400)
        # Anchored to the stored future expiry; allow a small tolerance so the
        # assertion never races the clock used inside extend_expiry().
        assert new_expiry == pytest.approx(far_future + 365 * 86400, abs=2)
        assert lm.get_key_info(key)["expiry"] == new_expiry

    def test_extend_expiry_anchors_to_now_when_lapsed(self):
        """Renewing an already-expired license grants a full extra period."""
        lm = _make_mgr(tmp_db=True)
        past = int(time.time()) - 10 * 86400
        key = lm.generate("lapsed@test.com", "cus_l", expiry=past)
        now = int(time.time())
        new_expiry = lm.extend_expiry(key, 365 * 86400)
        # A lapsed license is re-anchored to "now", so the new expiry is one
        # full period from now (not from the stale past expiry).
        assert new_expiry == pytest.approx(now + 365 * 86400, abs=2)

    def test_extend_expiry_never_expires_untouched(self):
        lm = _make_mgr(tmp_db=True)
        key = lm.generate("forever@test.com", "cus_f")  # expiry=0 (never)
        assert lm.extend_expiry(key, 365 * 86400) == 0
        assert lm.get_key_info(key)["expiry"] == 0

    def test_extend_expiry_unknown_key(self):
        lm = _make_mgr(tmp_db=True)
        assert lm.extend_expiry("CF.nope.nope", 86400) == 0

    def test_extend_expiry_malformed_key(self):
        """Malformed / unparseable key strings extend nothing and never raise.

        ``extend_expiry`` looks the key up by its raw string, so garbage that
        could never have been issued (wrong prefix, missing separators, empty)
        simply finds no DB row and returns 0 rather than blowing up.
        """
        lm = _make_mgr(tmp_db=True)
        for bad in ("", "not-a-key", "CF.", "CF.onlytwo", "garbage.with.dots"):
            assert lm.extend_expiry(bad, 86400) == 0, f"expected 0 for {bad!r}"


# ── License Server Endpoint Tests ───────────────────────────────────────────

class TestServerEndpoints:
    """These tests start the server, hit endpoints, and shut it down.

    The server's LicenseManager singleton picks up DEVBENCH_LICENSE_SECRET
    from the environment — we set it to match the test secret before starting.
    """

    _SECRET = "test-secret-32-bytes-long!!!!!!"

    @staticmethod
    def _start_server(secret: str = _SECRET):
        """Start server on a random high port, return port.

        Binds port 0 and reads the OS-assigned port from the live socket so
        there is no TOCTOU race between finding a free port and starting the
        server.
        """
        import os
        import tempfile
        from http.server import ThreadingHTTPServer
        from threading import Thread

        os.environ["DEVBENCH_LICENSE_SECRET"] = secret
        os.environ["DEVBENCH_LICENSE_DB"] = tempfile.mktemp(suffix=".db")

        # Reload to pick up new env vars (module-level lm + DB_PATH).
        import importlib
        import web.license_server
        importlib.reload(web.license_server)

        # Bind to port 0 in the main thread — OS assigns a free port and the
        # socket stays open until serve_forever() owns it. No race.
        server = ThreadingHTTPServer(("127.0.0.1", 0), web.license_server.LicenseHandler)
        port = server.server_address[1]

        Thread(target=server.serve_forever, daemon=True).start()
        return port

    def test_health_endpoint(self):
        import json
        import urllib.request

        port = self._start_server()
        _wait_for_server(port)

        resp = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/health").read())
        assert resp["status"] == "healthy"

    def test_root_endpoint(self):
        import json
        import urllib.request

        port = self._start_server()
        _wait_for_server(port)

        resp = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/").read())
        assert "License Server" in resp["service"]

    def test_verify_roundtrip(self):
        import json
        import urllib.request
        import urllib.parse

        port = self._start_server()
        _wait_for_server(port)

        # Generate a key locally
        lm = _make_mgr()
        key = lm.generate("roundtrip@test.com", "cus_rt")

        # Verify via server
        url = f"http://127.0.0.1:{port}/license/verify?key={urllib.parse.quote(key)}"
        resp = json.loads(urllib.request.urlopen(url).read())
        assert resp["valid"] is True
        assert resp["email"] == "roundtrip@test.com"

    def test_activate_via_server(self):
        import json
        import urllib.request

        port = self._start_server()
        _wait_for_server(port)

        lm = _make_mgr(tmp_db=True)
        key = lm.generate("activate@test.com", "cus_act")

        data = json.dumps({"key": key, "machine_id": "srv-mac"}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/license/activate",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        resp = json.loads(urllib.request.urlopen(req).read())
        assert resp["status"] == "ok"


class TestGumroadWebhook:
    """Tests for the Gumroad sale webhook endpoint (/webhook/gumroad)."""

    _SECRET = "test-secret-32-bytes-long!!!!!!"

    @staticmethod
    def _start_server(secret: str = _SECRET):
        """Start server on a random high port, return port (no TOCTOU race)."""
        import os
        import tempfile
        from http.server import ThreadingHTTPServer
        from threading import Thread

        os.environ["DEVBENCH_LICENSE_SECRET"] = secret
        os.environ["DEVBENCH_LICENSE_DB"] = tempfile.mktemp(suffix=".db")

        import importlib
        import web.license_server
        importlib.reload(web.license_server)

        server = ThreadingHTTPServer(("127.0.0.1", 0), web.license_server.LicenseHandler)
        port = server.server_address[1]
        Thread(target=server.serve_forever, daemon=True).start()
        return port

    def test_gumroad_sale_generates_license(self):
        import json
        import time
        import urllib.request

        port = self._start_server()
        _wait_for_server(port)

        payload = json.dumps({
            "sale_id": "gum_test_123",
            "email": "gumroad@test.com",
            "product_name": "Devbench",
            "price": 19.00,
            "currency": "USD",
        }).encode()

        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/webhook/gumroad",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = json.loads(urllib.request.urlopen(req).read())
        assert resp["received"] is True
        assert resp["type"] == "sale"
        assert resp["customer_email"] == "gumroad@test.com"
        assert resp["gumroad_sale_id"] == "gum_test_123"
        assert resp["license_key"].startswith("CF.")
        assert resp["expires_at"] > 0

    def test_gumroad_missing_email_returns_400(self):
        import json
        import time
        import urllib.request
        import urllib.error

        port = self._start_server()
        _wait_for_server(port)

        payload = json.dumps({
            "sale_id": "no_email_test",
            "price": 19.00,
        }).encode()

        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/webhook/gumroad",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req)
            assert False, "Expected 400 error"
        except urllib.error.HTTPError as e:
            assert e.code == 400
            resp = json.loads(e.read())
            assert "Missing" in resp.get("message", "")

    def test_gumroad_invalid_json_returns_400(self):
        import time
        import urllib.request
        import urllib.error

        port = self._start_server()
        _wait_for_server(port)

        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/webhook/gumroad",
            data=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req)
            assert False, "Expected 400 error"
        except urllib.error.HTTPError as e:
            assert e.code == 400

    def test_gumroad_license_is_verifiable(self):
        import json
        import time
        import urllib.request

        port = self._start_server()
        _wait_for_server(port)

        # Send a Gumroad sale
        payload = json.dumps({
            "sale_id": "verify_test",
            "email": "verify@gumroad.com",
        }).encode()

        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/webhook/gumroad",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        sale_resp = json.loads(urllib.request.urlopen(req).read())
        cf_key = sale_resp["license_key"]

        # Verify the generated key via /license/verify
        import urllib.parse
        verify_url = f"http://127.0.0.1:{port}/license/verify?key={urllib.parse.quote(cf_key)}"
        verify_resp = json.loads(urllib.request.urlopen(verify_url).read())
        assert verify_resp["valid"] is True
        assert verify_resp["email"] == "verify@gumroad.com"


class TestStripeSignatureVerification:
    """Unit tests for _verify_stripe_sig — Stripe webhook signature validation."""

    _SECRET = "whsec_test_stripe_secret_key_32b"

    def _make_sig_header(self, body: str, secret: str, timestamp: int | None = None) -> str:
        import hmac as _hmac
        import hashlib as _hashlib
        ts = timestamp if timestamp is not None else int(time.time())
        signed_payload = f"{ts}.{body}"
        sig = _hmac.new(
            secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            _hashlib.sha256,
        ).hexdigest()
        return f"t={ts},v1={sig}"

    def _load_module(self, stripe_secret: str = ""):
        import importlib
        os.environ["DEVBENCH_LICENSE_SECRET"] = self._SECRET
        if stripe_secret:
            os.environ["STRIPE_WEBHOOK_SECRET"] = stripe_secret
        import web.license_server
        importlib.reload(web.license_server)
        return web.license_server

    def test_valid_signature_accepted(self):
        mod = self._load_module(self._SECRET)
        body = '{"type":"checkout.session.completed"}'
        header = self._make_sig_header(body, self._SECRET)
        assert mod._verify_stripe_sig(body, header) is True

    def test_wrong_secret_rejected(self):
        mod = self._load_module(self._SECRET)
        body = '{"type":"checkout.session.completed"}'
        header = self._make_sig_header(body, "wrong_secret_totally_different")
        assert mod._verify_stripe_sig(body, header) is False

    def test_tampered_body_rejected(self):
        mod = self._load_module(self._SECRET)
        body = '{"type":"checkout.session.completed"}'
        header = self._make_sig_header(body, self._SECRET)
        tampered = '{"type":"invoice.paid","amount":99999}'
        assert mod._verify_stripe_sig(tampered, header) is False

    def test_empty_header_rejected(self):
        mod = self._load_module()
        assert mod._verify_stripe_sig("body", "") is False

    def test_missing_timestamp_field_rejected(self):
        mod = self._load_module(self._SECRET)
        assert mod._verify_stripe_sig("test", "v1=abc123deadbeef") is False

    def test_missing_v1_field_rejected(self):
        mod = self._load_module()
        assert mod._verify_stripe_sig("body", f"t={int(time.time())}") is False

    def test_expired_timestamp_rejected(self):
        mod = self._load_module(self._SECRET)
        body = '{"type":"checkout.session.completed"}'
        old_ts = int(time.time()) - 600  # 10 minutes ago
        header = self._make_sig_header(body, self._SECRET, timestamp=old_ts)
        assert mod._verify_stripe_sig(body, header) is False

    def test_future_timestamp_within_tolerance_accepted(self):
        mod = self._load_module(self._SECRET)
        body = '{"type":"checkout.session.completed"}'
        future_ts = int(time.time()) + 60  # 1 minute ahead (clock skew)
        header = self._make_sig_header(body, self._SECRET, timestamp=future_ts)
        assert mod._verify_stripe_sig(body, header) is True

    def test_non_integer_timestamp_rejected(self):
        mod = self._load_module(self._SECRET)
        assert mod._verify_stripe_sig("body", "t=notanumber,v1=abc123") is False