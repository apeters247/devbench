"""ConfigForge — HCL (HashiCorp Configuration Language) support tests.

python-hcl2 is only installed in a side venv (/tmp/devbench_venv), so the
module is expected to fall back to that venv's site-packages. If that fallback
fails on this machine HAS_HCL is False and the round-trip tests are skipped,
but detection and the graceful-error path are always exercised.
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from core.configforge import (
    convert, detect_format, parse_text, serialize, SUPPORTED_FORMATS,
)
import core.configforge as cf


# ── Format registration (works regardless of HAS_HCL) ──
def test_hcl_in_supported_formats():
    assert "hcl" in SUPPORTED_FORMATS


def test_detect_hcl_resource_block():
    text = 'resource "aws_instance" "web" {\n  ami = "ami-123"\n}\n'
    assert detect_format(text) == "hcl"


def test_detect_hcl_variable_block():
    text = 'variable "region" {\n  default = "us-east-1"\n}\n'
    assert detect_format(text) == "hcl"


def test_detect_hcl_bare_block_with_top_level_kv():
    text = 'name = "app"\nsettings {\n  debug = true\n}\n'
    assert detect_format(text) == "hcl"


def test_hcl_detection_does_not_steal_toml():
    assert detect_format("[server]\nhost = 'localhost'\nport = 8080") == "toml"


def test_hcl_detection_does_not_steal_ini():
    assert detect_format("[database]\nhost=localhost\nport=5432") == "ini"


def test_hcl_detection_does_not_steal_toml_inline_table():
    assert detect_format('point = { x = 1, y = 2 }') == "toml"


# ── Parse / serialize (require the library) ──
requires_hcl = pytest.mark.skipif(not cf.HAS_HCL, reason="python-hcl2 not importable")


@requires_hcl
def test_parse_hcl_strips_value_quotes():
    text = 'name = "my-app"\nport = 8080\nenabled = true\n'
    parsed = parse_text(text, "hcl")
    assert parsed["format"] == "hcl"
    # Quotes that hcl2.loads leaves embedded must be stripped.
    assert parsed["data"]["name"] == "my-app"
    assert parsed["data"]["port"] == 8080
    assert parsed["data"]["enabled"] is True


@requires_hcl
def test_parse_hcl_list_values_unquoted():
    parsed = parse_text('tags = ["a", "b"]', "hcl")
    assert parsed["data"]["tags"] == ["a", "b"]


@requires_hcl
def test_parse_hcl_block_labels_unquoted_and_no_marker():
    text = 'resource "aws_instance" "web" {\n  ami = "ami-123"\n}\n'
    data = parse_text(text, "hcl")["data"]
    # Block labels come back quoted from hcl2; they must be normalized, and the
    # internal __is_block__ marker hcl2 injects must not leak into output.
    block = data["resource"][0]
    assert "aws_instance" in block
    inner = block["aws_instance"]["web"]
    assert inner["ami"] == "ami-123"
    assert "__is_block__" not in json.dumps(data)


@requires_hcl
def test_serialize_hcl_quotes_strings():
    out = serialize({"name": "my-app", "port": 8080, "enabled": True}, "hcl")
    assert 'name = "my-app"' in out
    # Non-strings stay unquoted.
    assert "port = 8080" in out
    assert "enabled = true" in out


@requires_hcl
def test_serialize_hcl_is_reparseable():
    # The whole point: dumps must not emit bare unquoted strings.
    data = {"name": "my-app", "tags": ["x", "y"], "nested": {"host": "localhost"}}
    out = serialize(data, "hcl")
    reparsed = parse_text(out, "hcl")["data"]
    assert reparsed == data


@requires_hcl
def test_serialize_hcl_top_level_list_errors():
    with pytest.raises(ValueError):
        serialize([{"a": 1}], "hcl")


@requires_hcl
def test_convert_json_to_hcl_roundtrip():
    src = '{"service": "api", "replicas": 3, "ports": [80, 443]}'
    fwd = convert(src, "hcl", "json")
    assert fwd["success"], fwd.get("error")
    back = convert(fwd["output"], "json", "hcl")
    assert back["success"], back.get("error")
    assert json.loads(back["output"]) == json.loads(src)


@requires_hcl
def test_convert_hcl_to_json_strips_quotes():
    src = 'name = "web"\nport = 8080\n'
    r = convert(src, "json", "hcl")
    assert r["success"], r.get("error")
    assert json.loads(r["output"]) == {"name": "web", "port": 8080}


# ── Graceful error when the library is unavailable ──
def test_hcl_unavailable_returns_error(monkeypatch):
    monkeypatch.setattr(cf, "HAS_HCL", False)
    r = convert('name = "x"\nblk {\n a = 1\n}\n', "json", "hcl")
    assert r["success"] is False
    assert "hcl" in r["error"].lower()
