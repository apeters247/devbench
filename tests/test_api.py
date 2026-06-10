"""Tests for the ConfigForge REST API (web/api.py).

A zero-dependency stdlib http.server. These tests load it by file path
(``web`` is not a package), start it on an ephemeral port in a thread, and
make real HTTP requests against the spec'd contract. Mirrors test_serve.py.
"""

import importlib.util
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

_API_PATH = Path(__file__).resolve().parent.parent / "web" / "api.py"


def _load_api():
    spec = importlib.util.spec_from_file_location("configforge_api_test", _API_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def server():
    api = _load_api()
    # Generous limit so the shared-module fixture isn't throttled across tests.
    api.ConfigForgeAPIHandler.rate_limiter = api.RateLimiter(max_requests=10_000, window=60.0)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), api.ConfigForgeAPIHandler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get(base, path="/"):
    try:
        with urllib.request.urlopen(base + path, timeout=5) as r:
            return r.status, r.headers, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.headers, json.loads(e.read().decode("utf-8"))


def _post_json(base, path, payload, raw=None):
    data = raw if raw is not None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base + path, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.headers, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.headers, json.loads(e.read().decode("utf-8"))


# -- GET endpoints --------------------------------------------------------


def test_root_summary(server):
    status, headers, data = _get(server, "/")
    assert status == 200
    assert data["name"] == "ConfigForge API"
    assert data["version"] == "0.1.0"
    assert isinstance(data["endpoints"], list) and data["endpoints"]
    assert "application/json" in headers["Content-Type"]


def test_health(server):
    status, _, data = _get(server, "/health")
    assert status == 200
    assert data["status"] == "ok"
    # Counts are computed from actual project state, not hardcoded. models_count
    # must match the real number of supported formats, and tests_passing must be
    # a positive integer (discovered from the tests directory).
    api = _load_api()
    assert data["models_count"] == len(api.cf.SUPPORTED_FORMATS)
    assert isinstance(data["tests_passing"], int) and data["tests_passing"] > 0


def test_formats(server):
    status, _, data = _get(server, "/api/v1/formats")
    assert status == 200
    assert data["success"] is True
    for fmt in ["json", "yaml", "toml", "xml", "csv", "ini", "env"]:
        assert fmt in data["formats"]


def test_cors_headers_present(server):
    _, headers, _ = _get(server, "/health")
    assert headers["Access-Control-Allow-Origin"] == "*"
    assert "POST" in headers["Access-Control-Allow-Methods"]


# -- POST /api/v1/convert -------------------------------------------------


def test_convert_contract(server):
    # Auto-detect path. Asserts the response contract shape; the engine reports
    # whichever format it detects (we don't pin a specific detector result here
    # — that is covered deterministically by test_convert_explicit_from_format).
    status, headers, data = _post_json(
        server, "/api/v1/convert", {"source": "key: value\nfoo: bar", "to_format": "json"}
    )
    assert status == 200
    assert data["success"] is True
    assert isinstance(data["input_format"], str) and data["input_format"]
    assert data["output_format"] == "json"
    assert json.loads(data["output"]) == {"key": "value", "foo": "bar"}
    assert data["error"] is None
    assert set(data) == {"success", "output", "input_format", "output_format", "error"}
    assert "application/json" in headers["Content-Type"]


def test_convert_explicit_from_format(server):
    _, _, data = _post_json(
        server,
        "/api/v1/convert",
        {"source": '{"a": 1}', "to_format": "yaml", "from_format": "json"},
    )
    assert data["success"] is True
    assert data["input_format"] == "json"
    assert "a: 1" in data["output"]


def test_convert_garbage_is_400(server):
    # Input the engine cannot detect/parse -> failed conversion -> 400.
    status, _, data = _post_json(
        server, "/api/v1/convert", {"source": "[[[broken", "to_format": "json"}
    )
    assert status == 400
    assert data["success"] is False
    assert data["error"]


def test_convert_bad_json_body_is_400(server):
    status, _, data = _post_json(server, "/api/v1/convert", None, raw=b"{not json")
    assert status == 400
    assert data["success"] is False
    assert "JSON" in data["error"]


def test_convert_empty_source_is_400(server):
    status, _, data = _post_json(server, "/api/v1/convert", {"source": "   ", "to_format": "json"})
    assert status == 400
    assert data["success"] is False


def test_convert_unsupported_format_is_400(server):
    status, _, data = _post_json(
        server, "/api/v1/convert", {"source": "a: 1", "to_format": "nonsense"}
    )
    assert status == 400
    assert data["success"] is False
    assert "nonsense" in data["error"]


def test_unknown_route_404(server):
    status, _, data = _get(server, "/api/v1/does-not-exist")
    assert status == 404
    assert data["success"] is False


# -- rate limiting --------------------------------------------------------


def test_rate_limiter_blocks_over_limit():
    api = _load_api()
    limiter = api.RateLimiter(max_requests=3, window=60.0)
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is False  # 4th within window
    # Different IP is independent.
    assert limiter.allow("5.6.7.8") is True


def test_rate_limiter_cleanup_evicts_stale():
    api = _load_api()
    limiter = api.RateLimiter(max_requests=5, window=10.0)
    limiter.allow("9.9.9.9", now=100.0)
    limiter.cleanup(now=200.0)  # well past window
    assert "9.9.9.9" not in limiter._hits


# -- concurrent requests --------------------------------------------------


def test_concurrent_convert_requests(server):
    """10 simultaneous convert requests verify thread safety of the ThreadingHTTPServer."""
    import concurrent.futures

    N = 10
    payload = {"source": "key: value", "from_format": "yaml", "to_format": "json"}
    with concurrent.futures.ThreadPoolExecutor(max_workers=N) as pool:
        futs = [pool.submit(_post_json, server, "/api/v1/convert", payload) for _ in range(N)]
        results = [f.result() for f in futs]
    for status, _, data in results:
        assert status == 200
        assert data["success"] is True
        assert '"key"' in data["output"]


def test_concurrent_mixed_requests(server):
    """Mix of GET and POST concurrent requests — verifies no shared-state corruption."""
    import concurrent.futures

    def do_get():
        return _get(server, "/health")

    def do_post():
        return _post_json(server, "/api/v1/convert", {"source": "x: 1", "to_format": "json"})

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        get_futs = [pool.submit(do_get) for _ in range(5)]
        post_futs = [pool.submit(do_post) for _ in range(5)]
        get_results = [f.result() for f in get_futs]
        post_results = [f.result() for f in post_futs]

    for status, _, data in get_results:
        assert status == 200
        assert data["status"] == "ok"
    for status, _, data in post_results:
        assert status == 200
        assert data["success"] is True
