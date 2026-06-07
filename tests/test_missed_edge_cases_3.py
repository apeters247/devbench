"""ConfigForge — edge cases MISSED by the existing suite (Round 4).

Each test here corresponds to a concrete defect that was reproducible against
the pre-fix code:

 1. JSON mixed top-level scalars + section dicts -> INI crashed with
    "'str' object has no attribute 'items'".
 2. XML root element carrying only text (no children) lost the text entirely.
 3. INI numeric type-inference corrupted values: underscores ("1_000"),
    leading zeros ("007"), and overflow ("1e500" -> inf, unserializable).
 4. ENV serialization of a value containing a newline broke the file structure
    and swallowed subsequent keys.
 5. A dict key containing a space (or other XML-illegal char) produced
    malformed XML that could not be re-parsed.
 6. A top-level list-of-dicts with a nested dict value serialized to TOML as a
    stringified Python dict instead of a TOML inline table.
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from core.configforge import convert, parse_text, serialize, _infer_type


def _j(text):
    return json.loads(text)


# ═══ 1. Mixed top-level scalars + section dicts -> INI ═══

def test_ini_mixed_toplevel_scalar_and_section_no_crash():
    """JSON with a scalar alongside a section dict must not crash INI output."""
    src = json.dumps({"name": "top", "server": {"host": "x", "port": 8080}})
    r = convert(src, "ini")
    assert r["success"], r.get("error")
    # The scalar value must survive somewhere in the output.
    assert "name" in r["output"]
    assert "top" in r["output"]
    # The section and its keys must still be present.
    assert "[server]" in r["output"]
    assert "host" in r["output"]


def test_ini_mixed_scalar_roundtrips_to_json():
    """The top-level scalar must be retrievable after INI -> JSON."""
    src = json.dumps({"title": "app", "db": {"host": "local", "port": 5432}})
    r = convert(src, "ini")
    assert r["success"], r.get("error")
    back = convert(r["output"], "json")
    assert back["success"], back.get("error")
    blob = back["output"]
    assert "title" in blob and "app" in blob


def test_ini_toplevel_list_still_fails_gracefully():
    """A top-level list value (not representable) should fail, not crash."""
    src = json.dumps({"tags": [1, 2, 3], "server": {"host": "x"}})
    r = convert(src, "ini")
    assert not r["success"]
    assert r["error"]


# ═══ 2. XML root with only text ═══

def test_xml_text_only_root_preserved():
    """<root>hello world</root> must not lose its text."""
    r = convert("<root>hello world</root>", "json", "xml")
    assert r["success"], r.get("error")
    assert "hello world" in r["output"]


def test_xml_empty_root_still_ok():
    """<root></root> remains an empty mapping (no regression)."""
    r = convert("<root></root>", "json", "xml")
    assert r["success"], r.get("error")
    data = _j(r["output"])
    assert data == {} or data is None


def test_xml_text_only_root_roundtrip():
    """A text-only root survives XML -> JSON without raising."""
    r = convert("<note>remember the milk</note>", "json", "xml")
    assert r["success"], r.get("error")
    assert "milk" in r["output"]


# ═══ 3. INI strict numeric inference ═══

def test_ini_underscore_number_stays_string():
    """'1_000' must NOT be silently turned into the integer 1000."""
    src = "[s]\nserial = 1_000\n"
    r = convert(src, "json")
    assert r["success"], r.get("error")
    assert _j(r["output"])["s"]["serial"] == "1_000"


def test_ini_leading_zero_stays_string():
    """A leading-zero value (zip code, id) must stay a string, not become int."""
    # Pin source to INI: a bare 0-leading number is auto-detected as TOML
    # (where it is invalid), so force the INI path this test targets.
    src = "[addr]\nzip = 02134\n"
    r = convert(src, "json", "ini")
    assert r["success"], r.get("error")
    assert _j(r["output"])["addr"]["zip"] == "02134"


def test_ini_overflow_float_stays_string():
    """'1e500' overflows to inf; it must stay a string (inf is not valid JSON)."""
    src = "[s]\nbig = 1e500\n"
    r = convert(src, "json")
    assert r["success"], r.get("error")
    out = r["output"]
    # Must be valid JSON (no bare Infinity token) and preserve the literal.
    assert "Infinity" not in out
    assert _j(out)["s"]["big"] == "1e500"


def test_ini_normal_numbers_still_inferred():
    """Regression: ordinary ints/floats are still inferred."""
    src = "[s]\ncount = 42\nratio = 3.14\nsci = 1e3\nneg = -7\n"
    data = _j(convert(src, "json")["output"])["s"]
    assert data["count"] == 42 and isinstance(data["count"], int)
    assert abs(data["ratio"] - 3.14) < 1e-9
    assert data["sci"] == 1000.0
    assert data["neg"] == -7


def test_infer_type_unit():
    """Direct unit coverage of the strict inference helper."""
    assert _infer_type("1_000") == "1_000"
    assert _infer_type("007") == "007"
    assert _infer_type("1e500") == "1e500"
    assert _infer_type("42") == 42
    assert _infer_type("-3.5") == -3.5
    assert _infer_type("0") == 0


# ═══ 4. ENV serialize value with newline ═══

def test_env_serialize_newline_does_not_break_structure():
    """A newline inside a value must not split into a bogus extra line."""
    src = json.dumps({"A": "line1\nline2", "B": "ok"})
    r = convert(src, "env")
    assert r["success"], r.get("error")
    out = r["output"]
    # B must remain its own intact assignment.
    assert any(line.strip() == "B=ok" for line in out.split("\n")), out
    # There must be no raw line that is just the swallowed "line2".
    assert "line2\n" not in out or '"' in out


def test_env_serialize_newline_roundtrip_keeps_keys():
    """After ENV -> JSON, every original key must still be present."""
    src = json.dumps({"MULTI": "a\nb\nc", "PLAIN": "value", "LAST": "z"})
    r = convert(src, "env")
    assert r["success"], r.get("error")
    back = convert(r["output"], "json")
    assert back["success"], back.get("error")
    data = _j(back["output"])
    assert data.get("PLAIN") == "value"
    assert data.get("LAST") == "z"
    assert "MULTI" in data


# ═══ 5. Dict key with XML-illegal characters ═══

def test_xml_key_with_space_is_wellformed():
    """A key containing a space must produce well-formed, re-parseable XML."""
    src = json.dumps({"my key": "v", "ok": 1})
    r = convert(src, "xml")
    assert r["success"], r.get("error")
    # Output must round-trip back through the XML parser without error.
    back = convert(r["output"], "json", "xml")
    assert back["success"], back.get("error")


def test_xml_key_starting_with_digit_is_wellformed():
    """A key starting with a digit is illegal as an XML name; must be sanitized."""
    src = json.dumps({"123field": "v"})
    r = convert(src, "xml")
    assert r["success"], r.get("error")
    back = convert(r["output"], "json", "xml")
    assert back["success"], back.get("error")


# ═══ 6. TOML top-level list-of-dicts with a nested dict value ═══

def test_toml_inline_nested_dict_value():
    """A nested dict in a list-of-dicts must become a TOML inline table."""
    src = json.dumps([{"name": "a", "meta": {"k": 1}}])
    r = convert(src, "toml")
    assert r["success"], r.get("error")
    out = r["output"]
    # Must be a real inline table, not a stringified Python dict.
    assert "{'k'" not in out
    assert "meta = { k = 1 }" in out or "meta = {k = 1}" in out


def test_toml_inline_nested_list_value():
    """A nested list in a list-of-dicts must become a TOML array, not a string."""
    src = json.dumps([{"name": "a", "vals": [1, 2, 3]}])
    r = convert(src, "toml")
    assert r["success"], r.get("error")
    out = r["output"]
    assert "vals = [1, 2, 3]" in out
    assert "'[1, 2, 3]'" not in out and '"[1, 2, 3]"' not in out
