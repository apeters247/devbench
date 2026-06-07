"""ConfigForge — edge cases MISSED by the existing suite (Round 5).

 1. ENV serialization dropped leading/trailing whitespace and value-internal
    quote characters on round-trip (only newline-bearing values were quoted).
 2. A top-level list serialized to XML produced multiple sibling root elements,
    i.e. invalid, non-reparseable XML. This also broke every CSV -> XML
    conversion, since CSV parses to a list of dicts.
 3. A top-level array of scalars serialized to TOML silently produced an empty
    string with success=True — total, silent data loss instead of a clear error.
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from core.configforge import convert


def _j(text):
    return json.loads(text)


# ═══ 1. ENV round-trip preserves whitespace and embedded quotes ═══

def test_env_leading_trailing_whitespace_roundtrip():
    """A value padded with spaces must survive JSON -> ENV -> JSON intact."""
    src = json.dumps({"PADDED": "  spaced value  ", "PLAIN": "ok"})
    r = convert(src, "env")
    assert r["success"], r.get("error")
    back = convert(r["output"], "json")
    assert back["success"], back.get("error")
    data = _j(back["output"])
    assert data["PADDED"] == "  spaced value  "
    assert data["PLAIN"] == "ok"


def test_env_value_wrapped_in_quotes_roundtrip():
    """A value that itself begins/ends with a quote char must not be stripped."""
    src = json.dumps({"Q": '"literal quotes"', "S": "'single'"})
    r = convert(src, "env")
    assert r["success"], r.get("error")
    back = convert(r["output"], "json")
    assert back["success"], back.get("error")
    data = _j(back["output"])
    assert data["Q"] == '"literal quotes"'
    assert data["S"] == "'single'"


def test_env_plain_value_still_unquoted():
    """Regression: ordinary values stay unquoted (one assignment per line)."""
    src = json.dumps({"A": "localhost", "B": "5432"})
    r = convert(src, "env")
    assert r["success"], r.get("error")
    lines = [l for l in r["output"].split("\n") if l.strip()]
    assert "A=localhost" in lines
    assert "B=5432" in lines


# ═══ 2. Top-level list -> XML is a single well-formed document ═══

def test_xml_toplevel_list_single_root_wellformed():
    """A list serialized to XML must be one re-parseable document, not many."""
    src = json.dumps([{"a": "1"}, {"a": "2"}])
    r = convert(src, "xml")
    assert r["success"], r.get("error")
    back = convert(r["output"], "json", "xml")
    assert back["success"], back.get("error")


def test_csv_to_xml_is_wellformed():
    """CSV (a list of dicts) -> XML must produce valid, re-parseable XML."""
    src = "name,age\nAlice,30\nBob,25\n"
    r = convert(src, "xml")
    assert r["success"], r.get("error")
    back = convert(r["output"], "json", "xml")
    assert back["success"], back.get("error")
    assert "Alice" in back["output"] and "Bob" in back["output"]


# ═══ 3. Top-level scalar array -> TOML fails gracefully (no silent loss) ═══

def test_toml_toplevel_scalar_list_fails_gracefully():
    """A bare array of scalars cannot be TOML; must error, not vanish."""
    src = json.dumps([1, 2, 3])
    r = convert(src, "toml")
    assert not r["success"]
    assert r["error"]


def test_toml_toplevel_table_array_still_ok():
    """Regression: a list of dicts is still representable as TOML."""
    src = json.dumps([{"name": "a"}, {"name": "b"}])
    r = convert(src, "toml")
    assert r["success"], r.get("error")
    assert "a" in r["output"] and "b" in r["output"]