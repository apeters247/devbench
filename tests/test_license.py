#!/usr/bin/env python3
"""Tests for the ConfigForge License Manager (web/license.py)."""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

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

    def test_key_is_deterministic_secret(self):
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
        assert info is not None


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

    def test_default_secret_deterministic(self):
        """Auto-derived secret should be same across instances."""
        from web.license import _default_secret
        s1 = _default_secret()
        s2 = _default_secret()
        assert s1 == s2

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
        assert info is not None
        assert info["email"] == "info@test.com"
        assert info["customer_id"] == "cus_info"
        assert info["payment_intent"] == "pi_info"

    def test_get_key_info_no_db(self):
        lm = _make_mgr(tmp_db=False)
        key = lm.generate("a@b.com", "cus_1")
        assert lm.get_key_info(key) is None


# ── License Server Endpoint Tests ───────────────────────────────────────────

class TestServerEndpoints:
    """These tests start the server, hit endpoints, and shut it down.

    The server's LicenseManager singleton picks up DEVBENCH_LICENSE_SECRET
    from the environment — we set it to match the test secret before starting.
    """

    _SECRET = "test-secret-32-bytes-long!!!!!!"

    @staticmethod
    def _start_server(secret: str = _SECRET):
        """Start server on a random high port, return (proc, port)."""
        import os
        import socket
        import tempfile
        from threading import Thread

        os.environ["DEVBENCH_LICENSE_SECRET"] = secret
        os.environ["DEVBENCH_LICENSE_DB"] = tempfile.mktemp(suffix=".db")

        # Force re-import to pick up new env vars
        import importlib
        import web.license_server
        importlib.reload(web.license_server)

        # Find free port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()

        # Start in thread
        server_thread = Thread(
            target=web.license_server.run_server,
            args=("127.0.0.1", port),
            daemon=True,
        )
        server_thread.start()
        return port

    def test_health_endpoint(self):
        import json
        import urllib.request

        port = self._start_server()
        import time; time.sleep(0.3)

        resp = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/health").read())
        assert resp["status"] == "healthy"

    def test_root_endpoint(self):
        import json
        import urllib.request

        port = self._start_server()
        import time; time.sleep(0.3)

        resp = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/").read())
        assert "License Server" in resp["service"]

    def test_verify_roundtrip(self):
        import json
        import urllib.request
        import urllib.parse

        port = self._start_server()
        import time; time.sleep(0.3)

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
        import time; time.sleep(0.3)

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
        import os
        import socket
        import tempfile
        from threading import Thread

        os.environ["DEVBENCH_LICENSE_SECRET"] = secret
        os.environ["DEVBENCH_LICENSE_DB"] = tempfile.mktemp(suffix=".db")

        import importlib
        import web.license_server
        importlib.reload(web.license_server)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()

        server_thread = Thread(
            target=web.license_server.run_server,
            args=("127.0.0.1", port),
            daemon=True,
        )
        server_thread.start()
        return port

    def test_gumroad_sale_generates_license(self):
        import json
        import time
        import urllib.request

        port = self._start_server()
        time.sleep(0.3)

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
        time.sleep(0.3)

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
        time.sleep(0.3)

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
        time.sleep(0.3)

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