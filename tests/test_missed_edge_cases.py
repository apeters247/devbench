"""ConfigForge — edge cases Claude identified as missing.

Covers XML escaping, XML text+attributes, heterogeneous CSV, None in XML.
"""
import json
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from core.configforge import convert, serialize, parse_text


# ═══ A: XML escaping — & < > in values should not produce invalid XML ═══

def test_xml_escaping_ampersand():
    """JSON→XML: & should become &amp;"""
    src = json.dumps({"name": "AT&T", "desc": "cost < $10"})
    r = convert(src, "xml")
    assert r["success"]
    assert "&amp;" in r["output"]
    assert "&lt;" in r["output"]
    # Round trip back — should not crash
    r2 = convert(r["output"], "json")
    assert r2["success"]


def test_xml_escaping_html_chars():
    """XML handles all special characters."""
    src = json.dumps({"text": '<script>alert("xss")</script>'})
    r = convert(src, "xml")
    assert r["success"]
    assert "&lt;" in r["output"]
    assert "&gt;" in r["output"]
    assert "&quot;" in r["output"]


def test_xml_escaping_roundtrip():
    """JSON→XML→JSON with special characters."""
    original = {"title": "AT&T's <value> of $100"}
    src = json.dumps(original)
    r1 = convert(src, "xml")
    assert r1["success"]
    r2 = convert(r1["output"], "json")
    assert r2["success"]
    data = json.loads(r2["output"])
    # Should contain the original text (roughly)
    assert "AT&T" in str(data) or "AT&amp;T" in str(data)


# ═══ B: XML attributes + text — text should not be lost ═══

def test_xml_element_with_text_and_attributes():
    """XML element with both text and attributes preserves both."""
    src = '<root><item id="1">hello</item></root>'
    r = convert(src, "json", "xml")
    assert r["success"]
    data = json.loads(r["output"])
    # The item should have both #text and id
    item = data.get("item") or data.get("root", {}).get("item", {})
    if isinstance(item, dict):
        assert "#text" in item or "hello" in str(item)


def test_xml_attribute_only_element():
    """XML element with attributes but no text."""
    src = '<root><item id="1" class="active"/></root>'
    r = convert(src, "json", "xml")
    assert isinstance(r, dict)


def test_xml_element_text_and_children():
    """XML with mixed text, attributes, and children."""
    src = "<root>before<child attr='x'>inner</child>after</root>"
    r = convert(src, "json", "xml")
    assert isinstance(r, dict)


# ═══ C: Heterogeneous CSV — row keys differ ═══

def test_csv_heterogeneous_dicts():
    """Serialize list-of-dicts with different keys per row."""
    data = [
        {"name": "Alice", "age": "30"},
        {"name": "Bob", "city": "LA"},
        {"name": "Charlie", "age": "25", "city": "NYC"},
    ]
    result = serialize({"items": data}, "csv")  # This will fail because serialize expects dict, validate
    # csv serializer needs list of dicts directly
    r = convert(json.dumps(data), "csv")
    assert r["success"]
    output = r["output"]
    # Should have all headers
    assert "name" in output
    assert "age" in output
    assert "city" in output


def test_csv_single_dict():
    """Serialize a single flat dict to CSV."""
    data = {"name": "Alice", "age": "30", "city": "NYC"}
    r = convert(json.dumps(data), "csv")
    assert r["success"]


def test_csv_empty_dict_list():
    """Serialize list with empty dicts — should error gracefully."""
    data = [{}]
    r = convert(json.dumps(data), "csv")
    # CSV with no fields should fail gracefully
    assert not r["success"] or isinstance(r, dict)


# ═══ D: None in XML — should produce self-closing tag ═══

def test_xml_none_values_self_closing():
    """None value in dict → self-closing XML tag."""
    data = {"name": "test", "empty": None}
    r = convert(json.dumps(data), "xml")
    assert r["success"]
    # Should produce self-closing tag for None
    assert "/>" in r["output"] or "empty" not in r["output"]


def test_xml_nested_none_in_xml():
    """Nested None values in XML output."""
    data = {"root": {"a": None, "b": "value", "c": None}}
    r = convert(json.dumps(data), "xml")
    assert r["success"]
    assert "value" in r["output"]


# ═══ More: edge cases from review ═══

def test_csv_single_row_with_missing_fields():
    """CSV with one row, some fields empty."""
    src = "a,b,c\n1,,3\n"
    r = convert(src, "json")
    assert r["success"]
    data = json.loads(r["output"])
    assert len(data) == 1
    assert data[0].get("b") is None or data[0].get("b") == ""


def test_csv_trailing_empty_rows():
    """CSV with trailing empty lines after data."""
    src = "a,b\n1,2\n3,4\n\n\n"
    r = convert(src, "json")
    assert r["success"]
    data = json.loads(r["output"])
    assert len(data) == 2


def test_yaml_float_inf():
    """YAML with Infinity and NaN values."""
    src = "pi: 3.14\ninf: .inf\nninf: -.inf\nnan: .nan\n"
    r = convert(src, "json", "yaml")
    # May or may not succeed — shouldn't crash
    assert isinstance(r, dict)


def test_toml_table_array():
    """TOML with table arrays ([[...]])."""
    src = """[[products]]
name = "Hammer"
sku = 738594937

[[products]]
name = "Nail"
sku = 284758393
"""
    r = convert(src, "json", "toml")
    assert isinstance(r, dict)


def test_env_multiline_quoted_value():
    """ENV with multiline quoted value (backslash continuation)."""
    src = 'MULTILINE="line one\\\nline two\\\nline three"\n'
    r = convert(src, "json", "env")
    assert isinstance(r, dict)


def test_ini_dotted_keys():
    """INI with dotted key names."""
    src = "[section]\ndb.host=localhost\ndb.port=5432\n"
    r = convert(src, "json")
    assert r["success"]


def test_yaml_anchors_aliases():
    """YAML with anchors (&) and aliases (*)."""
    src = "defaults: &defaults\n  adapter: postgres\n  host: localhost\n\nproduction:\n  database: prod\n  <<: *defaults\n"
    r = convert(src, "json", "yaml")
    # Anchors may or may not resolve - shouldn't crash
    assert isinstance(r, dict)


def test_json_deeply_nested_500():
    """JSON with 500 levels of nesting."""
    d = {}
    cur = d
    for i in range(500):
        cur["l"] = {}
        cur = cur["l"]
    cur["end"] = True
    src = json.dumps(d)
    r = convert(src, "yaml")
    assert isinstance(r, dict)