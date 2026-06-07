"""ConfigForge — Java .properties format tests."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.configforge import (
    convert, detect_format, parse_text, serialize, SUPPORTED_FORMATS,
)


# ── Detection ──
def test_detect_properties_basic():
    text = "name=ConfigForge\nversion=1.0\nlevel=debug"
    assert detect_format(text) == "properties"


def test_detect_properties_colon_separator():
    text = "name:ConfigForge\nversion:1.0\nlevel:debug"
    assert detect_format(text) == "properties"


def test_detect_properties_with_bang_comment():
    text = "! a comment line\nname=ConfigForge\nversion=1.0"
    assert detect_format(text) == "properties"


def test_detect_properties_with_hash_comment():
    text = "# a comment line\napp.name=ConfigForge\napp.version=1.0"
    assert detect_format(text) == "properties"


def test_env_still_detected_not_stolen():
    # Uppercase-only ENV-style keys must NOT be classified as properties.
    text = "DATABASE_URL=postgres://localhost\nSECRET_KEY=abc123"
    assert detect_format(text) == "env"


# ── Parsing ──
def test_parse_equals():
    r = parse_text("name=ConfigForge\nversion=1.0", "properties")
    assert r["data"]["name"] == "ConfigForge"
    assert r["data"]["version"] == "1.0"


def test_parse_colon():
    r = parse_text("name:ConfigForge\nversion : 1.0", "properties")
    assert r["data"]["name"] == "ConfigForge"
    assert r["data"]["version"] == "1.0"


def test_parse_whitespace_separator():
    r = parse_text("name ConfigForge\nversion\t1.0", "properties")
    assert r["data"]["name"] == "ConfigForge"
    assert r["data"]["version"] == "1.0"


def test_parse_trims_whitespace():
    r = parse_text("  name  =   ConfigForge   ", "properties")
    assert r["data"]["name"] == "ConfigForge"


def test_parse_comments_ignored():
    text = "# comment\n! another comment\n   # indented comment\nname=value"
    r = parse_text(text, "properties")
    assert r["data"] == {"name": "value"}


def test_parse_blank_lines_ignored():
    r = parse_text("\n\nname=value\n\n", "properties")
    assert r["data"] == {"name": "value"}


def test_parse_continuation_lines():
    text = "message=hello \\\nworld \\\nagain"
    r = parse_text(text, "properties")
    assert r["data"]["message"] == "hello world again"


def test_parse_unicode_escape():
    r = parse_text("greeting=caf\\u00e9", "properties")
    assert r["data"]["greeting"] == "café"


def test_parse_escape_sequences():
    r = parse_text("path=line1\\nline2\\ttabbed", "properties")
    assert r["data"]["path"] == "line1\nline2\ttabbed"


def test_parse_escaped_backslash():
    r = parse_text("winpath=C:\\\\temp", "properties")
    assert r["data"]["winpath"] == "C:\\temp"


def test_parse_empty_value():
    r = parse_text("emptykey=", "properties")
    assert r["data"]["emptykey"] == ""


# ── Serialization ──
def test_serialize_basic():
    out = serialize({"name": "ConfigForge", "version": "1.0"}, "properties")
    assert "name=ConfigForge" in out
    assert "version=1.0" in out


def test_serialize_unicode_encoded():
    out = serialize({"greeting": "café"}, "properties")
    assert "\\u00e9" in out
    assert "café" not in out


def test_serialize_escapes_special_chars():
    out = serialize({"path": "line1\nline2"}, "properties")
    assert "\\n" in out
    assert "\n" == out[-1] or "line1\\nline2" in out


def test_serialize_comments_option():
    out = serialize({"name": "x"}, "properties", comments=["Generated file"])
    assert "# Generated file" in out


def test_serialize_multiline_continuation():
    # With multiline=True, embedded newlines are wrapped with backslash
    # continuation (escape + physical line break) and still round-trip.
    out = serialize({"text": "a\nb\nc"}, "properties", multiline=True)
    assert "\\\n" in out  # a physical continuation backslash appears
    back = parse_text(out, "properties")
    assert back["data"]["text"] == "a\nb\nc"


# ── Round-trip ──
def test_round_trip_properties():
    original = {"app.name": "ConfigForge", "app.version": "1.0", "greeting": "café"}
    out = serialize(original, "properties")
    back = parse_text(out, "properties")
    assert back["data"] == original


def test_convert_properties_to_json():
    r = convert("name=ConfigForge\nversion=1.0", "json", "properties")
    assert r["success"]
    assert json.loads(r["output"])["name"] == "ConfigForge"


def test_convert_json_to_properties():
    r = convert('{"name": "ConfigForge", "port": 8080}', "properties", "json")
    assert r["success"]
    assert "name=ConfigForge" in r["output"]
    assert "port=8080" in r["output"]


# ── Format registration ──
def test_properties_in_supported_formats():
    assert "properties" in SUPPORTED_FORMATS
