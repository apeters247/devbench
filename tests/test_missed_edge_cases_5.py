"""ConfigForge — edge cases MISSED by the existing suite (Round 6, Claude audit).

All three concern TOML serialization, reproducible against pre-fix code:
 1. Dict keys with TOML-illegal chars (space/dot/unicode) emitted bare -> invalid TOML.
 2. A top-level scalar serialized to TOML silently produced "" with success=True.
 3. A None nested in a TOML array/inline-table was corrupted into the string "None".
"""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from core.configforge import convert


def _j(t):
    return json.loads(t)


# ═══ 1. TOML keys with special characters must be quoted ═══

def test_toml_key_with_space_is_wellformed():
    r = convert(json.dumps({"my key": "v", "ok": 1}), "toml")
    assert r["success"], r.get("error")
    back = convert(r["output"], "json", "toml")
    assert back["success"], back.get("error")
    d = _j(back["output"])
    assert d["my key"] == "v" and d["ok"] == 1


def test_toml_key_with_dot_is_quoted():
    r = convert(json.dumps({"db.host": "localhost"}), "toml")
    assert r["success"], r.get("error")
    back = convert(r["output"], "json", "toml")
    assert back["success"], back.get("error")
    # The dotted key must round-trip as a single key, not become nested
    d = _j(back["output"])
    assert d["db.host"] == "localhost"
    assert "db" not in d or not isinstance(d.get("db"), dict)


def test_toml_section_name_with_space_is_quoted():
    r = convert(json.dumps({"my section": {"a": 1}}), "toml")
    assert r["success"], r.get("error")
    back = convert(r["output"], "json", "toml")
    assert back["success"], back.get("error")
    assert _j(back["output"])["my section"]["a"] == 1


def test_toml_nested_key_with_space_in_table():
    r = convert(json.dumps({"server": {"my key": "v"}}), "toml")
    assert r["success"], r.get("error")
    back = convert(r["output"], "json", "toml")
    assert back["success"], back.get("error")
    assert _j(back["output"])["server"]["my key"] == "v"


def test_toml_unicode_key_is_quoted():
    r = convert(json.dumps({"café": 1}), "toml")
    assert r["success"], r.get("error")
    back = convert(r["output"], "json", "toml")
    assert back["success"], back.get("error")
    assert _j(back["output"])["café"] == 1


def test_toml_inline_table_key_with_space():
    r = convert(json.dumps([{"my key": 1}]), "toml")
    assert r["success"], r.get("error")
    assert '"my key" = 1' in r["output"]
    assert "my key = 1" not in r["output"]


def test_toml_normal_keys_stay_bare():
    """Normal alphanumeric underscore/hyphen keys must NOT be quoted."""
    r = convert(json.dumps({"host": "x", "port": 8080}), "toml")
    assert r["success"], r.get("error")
    assert "host = " in r["output"]
    assert '"host"' not in r["output"]


# ═══ 2. Top-level scalar → TOML must fail gracefully ═══

def test_toml_toplevel_string_fails_gracefully():
    r = convert('"hello"', "toml", "json")
    assert not r["success"] and r["error"]


def test_toml_toplevel_number_fails_gracefully():
    r = convert("42", "toml", "json")
    assert not r["success"] and r["error"]


def test_toml_toplevel_bool_fails_gracefully():
    r = convert("true", "toml", "json")
    assert not r["success"] and r["error"]


def test_toml_toplevel_null_fails_gracefully():
    r = convert("null", "toml", "json")
    assert not r["success"] and r["error"]


def test_toml_dict_still_ok():
    """Verify that dict input still works after scalar-guard patch."""
    r = convert(json.dumps({"a": 1}), "toml")
    assert r["success"], r.get("error")
    assert "a = 1" in r["output"]


# ═══ 3. None nested in a TOML array / inline-table must not corrupt ═══

def test_toml_none_in_array_fails_gracefully():
    r = convert(json.dumps({"vals": [1, None, 3]}), "toml")
    assert not r["success"], r.get("output")
    assert r["error"]


def test_toml_none_in_inline_table_fails_gracefully():
    r = convert(json.dumps([{"meta": {"k": None}}]), "toml")
    assert not r["success"], r.get("output")
    assert r["error"]


def test_toml_array_without_none_still_ok():
    r = convert(json.dumps({"vals": [1, 2, 3]}), "toml")
    assert r["success"], r.get("error")
    assert "vals = [1, 2, 3]" in r["output"]
