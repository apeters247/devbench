"""Tests for the ConfigForge web demo server (web/serve.py).

The server is a zero-dependency stdlib http.server. These tests load it by
file path (web is not a package), start it on an ephemeral port in a thread,
and make real HTTP requests against the spec'd contract.
"""

import importlib.util
import json
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

_SERVE_PATH = Path(__file__).resolve().parent.parent / "web" / "serve.py"


def _load_serve():
    spec = importlib.util.spec_from_file_location("configforge_serve_test", _SERVE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def server():
    serve = _load_serve()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), serve.ConfigForgeHandler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get(base, path="/"):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return r.status, r.read().decode("utf-8")


def _post_json(base, path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base + path, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def test_index_serves_html(server):
    status, body = _get(server, "/")
    assert status == 200
    assert "<!DOCTYPE html>" in body
    assert "<textarea" in body


def test_index_has_required_controls(server):
    _, body = _get(server, "/")
    # output-format dropdown with every supported format
    for fmt in ["json", "yaml", "toml", "xml", "csv", "ini", "env"]:
        assert fmt in body.lower()
    # the three action buttons and the auto-detect badge
    assert "Convert" in body
    assert "Copy" in body
    assert "Swap" in body
    assert "badge" in body.lower()


def test_convert_endpoint_spec_contract(server):
    status, data = _post_json(
        server, "/convert", {"source": "key: value\nfoo: bar", "to_format": "json"}
    )
    assert status == 200
    assert data["success"] is True
    assert data["input_format"] == "yaml"
    assert data["output_format"] == "json"
    assert json.loads(data["output"]) == {"key": "value", "foo": "bar"}
    assert data["error"] is None


def test_convert_respects_explicit_from_format(server):
    _, data = _post_json(
        server,
        "/convert",
        {"source": '{"a": 1}', "to_format": "yaml", "from_format": "json"},
    )
    assert data["success"] is True
    assert data["input_format"] == "json"
    assert data["output_format"] == "yaml"
    assert "a: 1" in data["output"]


def test_convert_reports_error_on_garbage(server):
    _, data = _post_json(
        server, "/convert", {"source": "{not valid : json :", "to_format": "toml"}
    )
    # Either detection fails or parsing fails — either way it's a clean error,
    # not a crash, and the contract keys are all present.
    assert data["success"] is False
    assert data["error"]
    assert "output_format" in data


def test_convert_empty_source_is_error(server):
    _, data = _post_json(server, "/convert", {"source": "   ", "to_format": "json"})
    assert data["success"] is False
    assert data["error"]


def test_convert_unsupported_target_is_error(server):
    _, data = _post_json(
        server, "/convert", {"source": "a: 1", "to_format": "nonsense"}
    )
    assert data["success"] is False
    assert data["error"]


def test_unknown_route_404(server):
    try:
        _get(server, "/does-not-exist")
        assert False, "expected 404"
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_demo_symlink_returns_403(server, tmp_path):
    """Symlink inside demo/static/ returns 403 to block path traversal."""
    demo_static = Path(__file__).resolve().parent.parent / "demo" / "static"
    sensitive = tmp_path / "sensitive.txt"
    sensitive.write_text("secret-data")
    link = demo_static / "_test_symlink_traversal.txt"
    try:
        link.symlink_to(sensitive)
        _get(server, "/demo/_test_symlink_traversal.txt")
        assert False, "expected 403"
    except urllib.error.HTTPError as e:
        assert e.code == 403
    finally:
        link.unlink(missing_ok=True)
