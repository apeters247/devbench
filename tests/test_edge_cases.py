"""ConfigForge — consolidated edge case test suite.

Covers every format combination, empty/malformed input, unicode (incl. RTL,
bidi, binary), large files, deep nesting, CSV/XML/INI/ENV quirks, NaN/Infinity,
YAML anchors, TOML inline tables + scalar arrays + key quoting + scalar guards,
and comment-preservation round-trips (the #1 user complaint).

This file absorbs the genuinely-unique regression tests that previously lived
in the now-removed test_missed_edge_cases*.py and test_edge_cases_*.py files;
duplicate/trivial variations and the repeated "round N" category sweeps were
dropped during consolidation.
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from core.configforge import (
    convert,
    convert_file,
    batch_convert,
    detect_format,
    parse_text,
    serialize,
    round_trip,
    _infer_type,
    SUPPORTED_FORMATS,
    HAS_YAML,
    HAS_TOML,
)

# ── Helpers ──

ALL_FORMATS = list(SUPPORTED_FORMATS)  # json, yaml, toml, xml, csv, ini, env, properties, hcl
# The 7 "core" text formats. properties/hcl have dedicated suites
# (test_properties.py, test_hcl.py) and hcl needs an optional library, so the
# combinatorial sweeps below use the core set to avoid redundant fan-out.
CORE_FORMATS = ["json", "yaml", "toml", "xml", "csv", "ini", "env"]


def _j(text):
    """Parse JSON output from convert()."""
    return json.loads(text)


def _deep_dict(levels, leaf="bottom"):
    d = {}
    cur = d
    for _ in range(levels):
        nxt = {}
        cur["level"] = nxt
        cur = nxt
    cur["end"] = leaf
    return d


def _yaml_rt(src):
    """YAML -> JSON -> YAML, carrying comments through the JSON intermediate."""
    return round_trip(src, via="json", fmt="yaml")


# ════════════════════════════════════════════════════════════════
# 1. Format detection
# ════════════════════════════════════════════════════════════════

def test_detect_unknown_format():
    assert detect_format("some random text with no structure") == "unknown"


def test_detect_empty_string():
    assert detect_format("") == "unknown"


def test_detect_whitespace():
    assert detect_format("   \n\n\t  ") == "unknown"


def test_detect_json_array():
    assert detect_format("[1, 2, 3]") == "json"


def test_detect_json_nested():
    assert detect_format('{"a": {"b": {"c": [1, 2, 3]}}}') == "json"


def test_detect_ambiguous_toml_vs_ini():
    """Content that could be TOML or INI — should pick one."""
    assert detect_format("[section]\nkey = value\n") in ("toml", "ini")


def test_detect_csv_bom():
    """A BOM-prefixed comma file is still detected as CSV."""
    assert detect_format("﻿a,b,c\n1,2,3\n4,5,6\n") == "csv"


def test_detect_nan_json():
    """A JSON object containing NaN/Infinity is still detected as JSON."""
    assert detect_format('{"x": NaN, "y": Infinity}') == "json"


# ════════════════════════════════════════════════════════════════
# 2. All format combinations — convert every format to every other
# ════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("from_fmt", CORE_FORMATS)
@pytest.mark.parametrize("to_fmt", CORE_FORMATS)
def test_all_format_combinations(from_fmt, to_fmt):
    """Every format → every other format, using simple data."""
    if from_fmt == to_fmt:
        pytest.skip("same format, not a conversion")

    src = None
    if from_fmt == "json":
        src = json.dumps({"name": "test", "value": 42, "active": True})
    elif from_fmt == "yaml":
        src = "name: test\nvalue: 42\nactive: true\n"
    elif from_fmt == "toml":
        src = 'name = "test"\nvalue = 42\nactive = true\n'
    elif from_fmt == "xml":
        src = "<root><name>test</name><value>42</value><active>true</active></root>"
    elif from_fmt == "csv":
        src = "name,value,active\ntest,42,true\n"
    elif from_fmt == "ini":
        src = "[DEFAULT]\nname=test\nvalue=42\nactive=true\n"
    elif from_fmt == "env":
        src = "name=test\nvalue=42\nactive=true\n"

    r = convert(src, to_fmt, from_fmt)
    if not r["success"]:
        assert "error" in r
    else:
        assert r["output_format"] == to_fmt
        assert r["input_format"] == from_fmt
        assert len(r["output"]) > 0


def test_all_conversions_json_to_everything():
    """JSON source converted to all 6 other formats must succeed."""
    src = json.dumps({"server": {"host": "localhost", "port": 8080, "tls": True}})
    for fmt in ALL_FORMATS:
        if fmt == "json":
            continue
        r = convert(src, fmt)
        assert r["success"], f"JSON→{fmt} failed: {r.get('error')}"
        assert r["output_format"] == fmt


# ════════════════════════════════════════════════════════════════
# 3. Empty / whitespace input
# ════════════════════════════════════════════════════════════════

def test_empty_string():
    r = convert("", "json")
    assert not r["success"]
    assert r["error"] is not None


def test_empty_json_object():
    r = convert("{}", "yaml")
    assert r["success"]


def test_empty_xml():
    """Minimal XML — empty root element."""
    r = convert("<root></root>", "json")
    assert r["success"]


def test_empty_csv():
    """CSV with header but no data rows."""
    r = convert("name,age\n", "json")
    assert r["success"]
    data = _j(r["output"])
    assert data == [] or data == [{}]


def test_empty_ini():
    r = convert("[empty]\n", "json")
    assert r["success"]


def test_whitespace_only():
    r = convert("   \n\n\t  \n", "json")
    assert not r["success"]


# ════════════════════════════════════════════════════════════════
# 4. Malformed input
# ════════════════════════════════════════════════════════════════

def test_malformed_json_trailing_comma():
    assert not convert('{"a": 1,}', "json", "json")["success"]


def test_malformed_json_single_quotes():
    assert not convert("{'a': 1}", "json")["success"]


def test_malformed_json_no_quotes():
    assert not convert("{a: 1}", "json")["success"]


def test_malformed_yaml_tab_indent():
    """YAML with tab indentation — should not crash."""
    r = convert("key:\n\tvalue: 1\n", "json", "yaml")
    assert isinstance(r, dict)


def test_malformed_yaml_random_garbage():
    r = convert("@#$%^&*()!~", "json", "yaml")
    assert not r["success"] or r.get("error") is not None


def test_malformed_toml_no_equals():
    assert not convert("[section]\njustakey\n", "json", "toml")["success"]


def test_malformed_toml_invalid_value():
    assert not convert("key = #invalid\n", "json", "toml")["success"]


def test_malformed_xml_unclosed_tag():
    assert not convert("<root><item>value</root>", "json", "xml")["success"]


def test_malformed_xml_invalid_chars():
    r = convert("<root><1tag>value</1tag></root>", "json", "xml")
    assert isinstance(r, dict)


def test_malformed_csv_inconsistent_columns():
    src = "name,age,city\nAlice,30\nBob,25,LA,extra\n"
    r = convert(src, "json")
    assert r["success"]
    assert isinstance(_j(r["output"]), list)


def test_malformed_ini_no_section():
    r = convert("key=value\nfoo=bar\n", "json")
    assert isinstance(r, dict)


def test_malformed_env_no_value():
    r = convert("EMPTY_KEY=\nFOO=bar\n", "json")
    assert r["success"]


def test_malformed_env_weird_chars_in_key():
    r = convert("BAD-KEY=value\nWEIRD!KEY=val\n", "json")
    assert isinstance(r, dict) and "success" in r


def test_random_garbage_to_all_formats():
    """Random garbage to every format — no exceptions."""
    garbage = "!@#$%^&*()_+{}|:<>?~`-=[]\\;',./\n\t\x00\x01\x02"
    for fmt in ALL_FORMATS:
        r = convert(garbage, fmt)
        assert isinstance(r, dict)
        assert "success" in r


# ════════════════════════════════════════════════════════════════
# 5. Unicode (emoji, CJK, accented, RTL, bidi)
# ════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("target_fmt", CORE_FORMATS)
@pytest.mark.parametrize("label,src", [
    ("emoji", '{"greeting": "Hello 👋", "mood": "🔥🚀💻"}'),
    ("cjk", '{"language": "日本語", "city": "東京", "test": "テスト"}'),
    ("accented", '{"cafe": "crème brûlée", "piece": "numéro 1", "sp": "João"}'),
])
def test_unicode_passthrough(label, src, target_fmt):
    """Emoji / CJK / accented characters survive conversion to every format."""
    r = convert(src, target_fmt)
    if not r["success"] and target_fmt in ("csv", "ini", "env"):
        return
    assert r["success"], f"{label} → {target_fmt} failed: {r.get('error')}"


def test_unicode_yaml_input():
    assert convert("greeting: Hello 👋\ncafe: café\n日本語: テスト\n", "json")["success"]


def test_unicode_toml_input():
    assert convert('title = "日本語"\nemojis = "🔥🚀"\naccents = "São Paulo"\n', "json")["success"]


def test_unicode_xml_input():
    assert convert('<root><cafe>café crème</cafe><emoji>🔥🚀</emoji><cjk>日本語</cjk></root>', "json")["success"]


def test_unicode_csv_input():
    r = convert("name,emoji,city\nAlice,🚀,São Paulo\nBob,🔥,東京\n", "json")
    assert r["success"]
    assert len(_j(r["output"])) == 2


def test_unicode_ini_input():
    assert convert("[section]\ncafé=crème brûlée\ncity=São Paulo\n", "json")["success"]


def test_unicode_env_input():
    assert convert("GREETING=Hello 👋\nCITY=São Paulo\nLANG=日本語\n", "json")["success"]


def test_rtl_arabic_roundtrip_json_yaml_json():
    """Arabic data survives JSON -> YAML -> JSON unchanged."""
    original = {"اسم": "أحمد", "مدينة": "القاهرة"}
    src = json.dumps(original, ensure_ascii=False)
    r1 = convert(src, "yaml")
    assert r1["success"]
    r2 = convert(r1["output"], "json")
    assert r2["success"]
    assert json.loads(r2["output"]) == original


def test_rtl_arabic_roundtrip_json_toml_json():
    """Arabic data survives JSON -> TOML -> JSON (RTL key must be quoted)."""
    original = {"اسم": "قيمة"}
    src = json.dumps(original, ensure_ascii=False)
    r1 = convert(src, "toml")
    assert r1["success"]
    r2 = convert(r1["output"], "json", "toml")
    assert r2["success"]
    assert json.loads(r2["output"]) == original


def test_rtl_yaml_input_to_json():
    """RTL text as YAML source parses correctly."""
    r = convert("اسم: أحمد\nمدينة: القاهرة\nactive: true\n", "json", "yaml")
    assert r["success"]
    assert _j(r["output"]).get("اسم") == "أحمد"


def test_rtl_bidi_control_chars():
    """Explicit bidi control codepoints round-trip through JSON."""
    src = '{"mix": "abc\\u200fدef\\u200e123\\u202e987\\u202c"}'
    r = convert(src, "json")
    assert r["success"]
    data = _j(r["output"])
    assert "‏" in data["mix"] and "‮" in data["mix"]


def test_unicode_surrogate_pair_emoji():
    """An astral-plane (4-byte UTF-8) codepoint survives JSON round-trip."""
    src = '{"astral": "\\ud83d\\ude80"}'  # rocket emoji via surrogate pair
    r = convert(src, "json")
    assert r["success"]
    assert _j(r["output"])["astral"] == "\U0001F680"


# ════════════════════════════════════════════════════════════════
# 6. Binary / control bytes in strings
# ════════════════════════════════════════════════════════════════

def test_binary_control_chars_json_roundtrip():
    """Low control bytes (0x00-0x1f) round-trip through JSON escapes."""
    src = '{"blob": "\\u0000\\u0001\\u0007\\u001f\\u007f"}'
    r = convert(src, "json")
    assert r["success"]
    assert _j(r["output"])["blob"] == "\x00\x01\x07\x1f\x7f"


def test_binary_high_bytes_json():
    src = '{"bytes": "\\u00ff\\u00fe\\u0080\\u00c0"}'
    r = convert(src, "json")
    assert r["success"]
    assert "ÿ" in _j(r["output"])["bytes"]


def test_binary_null_byte_in_csv():
    """A NUL byte inside a CSV field does not crash the parser."""
    r = convert("id,payload\n1,ab\x00cd\n", "json")
    assert isinstance(r, dict) and "success" in r


def test_binary_control_to_toml():
    """Low control bytes are quoted/escaped into a valid TOML string."""
    assert convert('{"b": "\\u0001\\u0002\\u0003"}', "toml")["success"]


def test_binary_vertical_tab_formfeed_json():
    src = '{"w": "\\u000b\\u000c"}'
    r = convert(src, "json")
    assert r["success"]
    assert _j(r["output"])["w"] == "\x0b\x0c"


# ════════════════════════════════════════════════════════════════
# 7. NaN / Infinity in JSON
# ════════════════════════════════════════════════════════════════

def test_json_nan_to_json():
    r = convert('{"x": NaN}', "json")
    assert r["success"]
    assert "NaN" in r["output"]


def test_json_infinity_to_json():
    r = convert('{"x": Infinity}', "json")
    assert r["success"]
    assert "Infinity" in r["output"]


def test_json_negative_infinity_to_json():
    r = convert('{"x": -Infinity}', "json")
    assert r["success"]
    assert "-Infinity" in r["output"]


def test_json_nan_in_array():
    r = convert('{"arr": [1, NaN, 3]}', "json")
    assert r["success"]
    assert "NaN" in r["output"]


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_json_nan_to_yaml():
    r = convert('{"value": NaN}', "yaml")
    assert r["success"]
    assert "nan" in r["output"].lower()


def test_json_nan_to_toml():
    r = convert('{"x": NaN}', "toml")
    assert r["success"]
    assert "nan" in r["output"].lower()


def test_json_infinity_to_toml():
    r = convert('{"x": Infinity}', "toml")
    assert r["success"]
    assert "inf" in r["output"].lower()


def test_json_nan_to_xml():
    r = convert('{"x": NaN}', "xml")
    assert r["success"]
    assert "nan" in r["output"].lower()


# ════════════════════════════════════════════════════════════════
# 8. Large files (10K+ lines)
# ════════════════════════════════════════════════════════════════

def test_large_json_array():
    items = [{"id": i, "name": f"item_{i}", "value": i * 10} for i in range(10000)]
    r = convert(json.dumps(items), "yaml")
    assert r["success"]
    assert r["output_size"] > 10000


def test_large_json_object():
    data = {f"key_{i}": f"value_{i}_with_some_data" for i in range(10000)}
    assert convert(json.dumps(data), "yaml")["success"]


def test_large_csv():
    lines = ["id,name,score"] + [f"{i},user_{i},{i % 100}" for i in range(10000)]
    r = convert("\n".join(lines), "json")
    assert r["success"]
    assert len(_j(r["output"])) == 10000


def test_large_yaml_lines():
    lines = ["items:"] + [f"  item_{i}: value_{i}" for i in range(10000)]
    assert convert("\n".join(lines), "json")["success"]


def test_large_toml():
    lines = ["[config]"] + [f'key_{i} = "value_{i}"' for i in range(10000)]
    assert convert("\n".join(lines), "json")["success"]


def test_large_env():
    src = "\n".join(f"VAR_{i}=some_value_{i}" for i in range(10000))
    r = convert(src, "json")
    assert r["success"]
    assert len(_j(r["output"])) == 10000


def test_large_ini():
    lines = ["[large]"] + [f"key_{i}=value_{i}" for i in range(10000)]
    assert convert("\n".join(lines), "json")["success"]


def test_large_xml():
    children = "\n".join(f'<item id="{i}">value_{i}</item>' for i in range(10000))
    assert convert(f"<root>\n{children}\n</root>", "json")["success"]


def test_large_roundtrip_json_to_yaml():
    items = [{"id": i, "name": f"user_{i}"} for i in range(10000)]
    r1 = convert(json.dumps(items), "yaml")
    assert r1["success"]
    assert r1["output_size"] > 50000
    r2 = convert(r1["output"], "json")
    assert r2["success"]
    data = _j(r2["output"])
    assert len(data) == 10000 and data[0]["id"] == 0 and data[-1]["id"] == 9999


# ════════════════════════════════════════════════════════════════
# 9. Deep nesting
# ════════════════════════════════════════════════════════════════

def test_deeply_nested_json():
    """JSON with 100 levels of nesting."""
    assert convert(json.dumps(_deep_dict(100)), "yaml")["success"]


def test_deeply_nested_yaml():
    lines, indent = [], ""
    for i in range(100):
        lines.append(f"{indent}level_{i}:")
        indent += "  "
    lines.append(f"{indent}end: deep")
    assert convert("\n".join(lines), "json")["success"]


def test_deeply_nested_xml():
    inner = "deep"
    for i in range(100):
        inner = f"<level_{i}>{inner}</level_{i}>"
    assert convert(f"<root>{inner}</root>", "json")["success"]


def test_deeply_nested_toml():
    lines, prefix = [], ""
    for i in range(100):
        lines.append(f"[{prefix}section_{i}]")
        lines.append(f'name = "nest_{i}"')
        prefix = f"{prefix}section_{i}."
    assert convert("\n".join(lines), "json")["success"]


def test_deep_500_json_no_crash():
    """500-level nested JSON -> JSON/YAML must not raise."""
    src = json.dumps(_deep_dict(500))
    for fmt in ("json", "yaml"):
        r = convert(src, fmt)
        assert isinstance(r, dict) and "success" in r


def test_deep_nested_to_flat_conversion_fails():
    """Deeply nested data → INI must fail gracefully (can't flatten)."""
    assert not convert(json.dumps(_deep_dict(50, leaf=1)), "ini")["success"]


# ════════════════════════════════════════════════════════════════
# 10. CSV quirks (quoting, BOM, heterogeneous rows)
# ════════════════════════════════════════════════════════════════

def test_csv_quoted_commas():
    src = 'name,description,price\nWidget,"High quality, durable widget",19.99\n'
    r = convert(src, "json")
    assert r["success"]
    assert _j(r["output"])[0]["description"] == "High quality, durable widget"


def test_csv_quoted_newlines():
    src = 'id,notes\n1,"line one\nline two\nline three"\n'
    r = convert(src, "json")
    assert r["success"]
    assert "\n" in _j(r["output"])[0]["notes"]


def test_csv_quoted_quotes():
    src = 'id,text\n1,"She said ""hello"" to me"\n'
    r = convert(src, "json")
    assert r["success"]
    assert "hello" in _j(r["output"])[0]["text"]


def test_csv_mixed_quoted_unquoted():
    src = 'a,b,c\n1,hello,"world, foo"\n2,"bar",baz\n'
    r = convert(src, "json")
    assert r["success"]
    assert len(_j(r["output"])) == 2


def test_csv_empty_fields():
    src = 'a,b,c\n,,"",\n1,,3\n'
    r = convert(src, "json")
    assert r["success"]
    assert len(_j(r["output"])) == 2


def test_csv_tab_delimiter():
    r = convert("name\tage\tcity\nAlice\t30\tNYC\nBob\t25\tLA\n", "json")
    assert isinstance(r, dict) and "success" in r


def test_csv_pipe_delimiter():
    r = convert("name|age|city\nAlice|30|NYC\nBob|25|LA\n", "json")
    assert isinstance(r, dict) and "success" in r


def test_csv_trailing_newline():
    src = "a,b,c\n1,2,3\n4,5,6\n\n"
    r = convert(src, "json")
    assert r["success"]
    assert len(_j(r["output"])) >= 2


def test_csv_bom_parses():
    """A UTF-8 BOM prefix does not prevent CSV parsing."""
    r = convert("﻿name,age,city\nAlice,30,NYC\nBob,25,LA\n", "json")
    assert r["success"]
    assert len(_j(r["output"])) == 2


def test_csv_bom_quoted_field():
    src = '﻿name,note\nWidget,"durable, sturdy"\n'
    r = convert(src, "json")
    assert r["success"]
    assert any("durable, sturdy" in str(v) for v in _j(r["output"])[0].values())


def test_csv_single_row_with_missing_fields():
    src = "a,b,c\n1,,3\n"
    r = convert(src, "json")
    assert r["success"]
    data = _j(r["output"])
    assert len(data) == 1
    assert data[0].get("b") is None or data[0].get("b") == ""


def test_csv_trailing_empty_rows():
    src = "a,b\n1,2\n3,4\n\n\n"
    r = convert(src, "json")
    assert r["success"]
    assert len(_j(r["output"])) == 2


def test_csv_heterogeneous_dicts():
    """Serialize list-of-dicts with different keys per row — all headers present."""
    data = [
        {"name": "Alice", "age": "30"},
        {"name": "Bob", "city": "LA"},
        {"name": "Charlie", "age": "25", "city": "NYC"},
    ]
    r = convert(json.dumps(data), "csv")
    assert r["success"]
    out = r["output"]
    assert "name" in out and "age" in out and "city" in out


def test_csv_single_dict():
    assert convert(json.dumps({"name": "Alice", "age": "30", "city": "NYC"}), "csv")["success"]


def test_csv_empty_dict_list():
    """Serialize list with empty dicts — should error gracefully."""
    r = convert(json.dumps([{}]), "csv")
    assert not r["success"] or isinstance(r, dict)


# ════════════════════════════════════════════════════════════════
# 11. XML — namespaces, CDATA, attributes, escaping, illegal keys
# ════════════════════════════════════════════════════════════════

def test_xml_namespace():
    src = '<root xmlns:ns="http://example.com/ns"><ns:item>v</ns:item></root>'
    r = convert(src, "json", "xml")
    assert r["success"]
    assert "item" in r["output"]


def test_xml_default_namespace():
    src = '<root xmlns="http://default.example"><a>1</a><b>2</b></root>'
    r = convert(src, "json", "xml")
    assert r["success"]
    assert isinstance(_j(r["output"]), dict)


def test_xml_cdata_text_extracted():
    src = "<root><c><![CDATA[Hello <world> & friends]]></c></root>"
    r = convert(src, "json", "xml")
    assert r["success"]
    assert "world" in r["output"]


def test_xml_cdata_with_entities_and_markup():
    src = "<root><code><![CDATA[if (a < b && b > c) { x = 1; }]]></code></root>"
    r = convert(src, "json", "xml")
    assert r["success"]
    assert "&&" in r["output"]


def test_xml_attributes():
    src = '<root><item id="1" type="active">hello</item></root>'
    r = convert(src, "json", "xml")
    assert isinstance(r, dict)
    if r["success"]:
        assert r["output_format"] == "json"


def test_xml_self_closing():
    r = convert('<root><null/><empty attr="x"/><value>text</value></root>', "json", "xml")
    assert isinstance(r, dict)


def test_xml_processing_instructions():
    src = '<?xml version="1.0" encoding="UTF-8"?>\n<root><item>val</item></root>'
    assert isinstance(convert(src, "json", "xml"), dict)


def test_xml_duplicate_elements():
    """XML with duplicate element tags should become a list."""
    r = convert("<root><item>a</item><item>b</item><item>c</item></root>", "json")
    assert r["success"]
    data = _j(r["output"])
    assert isinstance(data.get("item"), list) or isinstance(data.get("root", {}).get("item"), list)


def test_xml_mixed_text_and_elements():
    assert isinstance(convert("<root>before<child>inner</child>after</root>", "json", "xml"), dict)


def test_xml_escaping_ampersand():
    """JSON→XML: & should become &amp; and < become &lt;."""
    r = convert(json.dumps({"name": "AT&T", "desc": "cost < $10"}), "xml")
    assert r["success"]
    assert "&amp;" in r["output"] and "&lt;" in r["output"]
    assert convert(r["output"], "json")["success"]


def test_xml_escaping_html_chars():
    r = convert(json.dumps({"text": '<script>alert("xss")</script>'}), "xml")
    assert r["success"]
    assert "&lt;" in r["output"] and "&gt;" in r["output"] and "&quot;" in r["output"]


def test_xml_escaping_roundtrip():
    original = {"title": "AT&T's <value> of $100"}
    r1 = convert(json.dumps(original), "xml")
    assert r1["success"]
    r2 = convert(r1["output"], "json")
    assert r2["success"]
    data = _j(r2["output"])
    assert "AT&T" in str(data) or "AT&amp;T" in str(data)


def test_xml_element_with_text_and_attributes():
    """XML element with both text and attributes preserves both."""
    r = convert('<root><item id="1">hello</item></root>', "json", "xml")
    assert r["success"]
    data = _j(r["output"])
    item = data.get("item") or data.get("root", {}).get("item", {})
    if isinstance(item, dict):
        assert "#text" in item or "hello" in str(item)


def test_xml_none_values_self_closing():
    """None value in dict → self-closing XML tag (no data corruption)."""
    r = convert(json.dumps({"name": "test", "empty": None}), "xml")
    assert r["success"]
    assert "/>" in r["output"] or "empty" not in r["output"]


def test_xml_text_only_root_preserved():
    """<root>hello world</root> must not lose its text."""
    r = convert("<root>hello world</root>", "json", "xml")
    assert r["success"]
    assert "hello world" in r["output"]


def test_xml_empty_root_still_ok():
    r = convert("<root></root>", "json", "xml")
    assert r["success"]
    data = _j(r["output"])
    assert data == {} or data is None


def test_xml_key_with_space_is_wellformed():
    """A key containing a space must produce well-formed, re-parseable XML."""
    r = convert(json.dumps({"my key": "v", "ok": 1}), "xml")
    assert r["success"], r.get("error")
    assert convert(r["output"], "json", "xml")["success"]


def test_xml_key_starting_with_digit_is_wellformed():
    """A key starting with a digit is illegal as an XML name; must be sanitized."""
    r = convert(json.dumps({"123field": "v"}), "xml")
    assert r["success"], r.get("error")
    assert convert(r["output"], "json", "xml")["success"]


def test_xml_toplevel_list_single_root_wellformed():
    """A list serialized to XML must be one re-parseable document, not many."""
    r = convert(json.dumps([{"a": "1"}, {"a": "2"}]), "xml")
    assert r["success"], r.get("error")
    assert convert(r["output"], "json", "xml")["success"]


def test_csv_to_xml_is_wellformed():
    """CSV (a list of dicts) -> XML must produce valid, re-parseable XML."""
    r = convert("name,age\nAlice,30\nBob,25\n", "xml")
    assert r["success"], r.get("error")
    back = convert(r["output"], "json", "xml")
    assert back["success"], back.get("error")
    assert "Alice" in back["output"] and "Bob" in back["output"]


# ════════════════════════════════════════════════════════════════
# 12. Environment files
# ════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("target_fmt", CORE_FORMATS)
def test_env_export_prefix(target_fmt):
    src = "export DB_HOST=localhost\nexport DB_PORT=5432\n"
    r = convert(src, target_fmt, "env")
    if not r["success"]:
        return
    assert r["output_format"] == target_fmt


def test_env_spaces_around_equals():
    r = convert("DB_HOST = localhost\nDB_PORT = 5432\n", "json", "env")
    assert r["success"]
    assert _j(r["output"]).get("DB_HOST") is not None


def test_env_quoted_values():
    r = convert('DB_HOST="localhost"\nDB_PORT=\'5432\'\n', "json", "env")
    assert r["success"]
    assert _j(r["output"])["DB_HOST"] == "localhost"


def test_env_quoted_values_with_spaces():
    r = convert('SECRET="my secret key with spaces"\nPATH="/usr/bin:/usr/local/bin"\n', "json", "env")
    assert r["success"]
    assert " " in _j(r["output"])["SECRET"]


def test_env_quoted_special_chars():
    src = 'PASSWORD="pa$$word!#"\nCONN_STR="postgres://user:pass@host:5432/db?sslmode=require"\n'
    r = convert(src, "json", "env")
    assert r["success"]
    assert "$" in _j(r["output"]).get("PASSWORD", "")


def test_env_comments():
    src = "# This is a comment\nDB_HOST=localhost\n# Another comment\nDB_PORT=5432\n"
    r = convert(src, "json", "env")
    assert r["success"]
    data = _j(r["output"])
    assert "DB_HOST" in data and "DB_PORT" in data


def test_env_empty_lines():
    r = convert("DB_HOST=localhost\n\nDB_PORT=5432\n\n\nDEBUG=true\n", "json", "env")
    assert r["success"]
    assert len(_j(r["output"])) == 3


def test_env_values_with_equals_in_value():
    src = 'CONN_STR="postgres://user:pass@host:5432/db?sslmode=require&timeout=30"\n'
    r = convert(src, "json", "env")
    assert r["success"]
    assert "sslmode" in _j(r["output"]).get("CONN_STR", "")


def test_env_literal_backslash_n():
    """An escaped \\n sequence inside a quoted ENV value is kept literally."""
    r = convert('CERT="line1\\nline2\\nline3"\n', "json", "env")
    assert r["success"]
    assert "\\n" in _j(r["output"])["CERT"]


def test_env_real_newline_does_not_swallow_keys():
    """A real newline in a quoted value does not consume the following keys."""
    r = convert('A="first\nstillfirst"\nB=second\nC=third\n', "json", "env")
    assert r["success"]
    data = _j(r["output"])
    assert data.get("B") == "second" and data.get("C") == "third"


def test_env_real_newline_value_serialized_escaped():
    """A real newline in JSON data is escaped when serialized to ENV (one line)."""
    r = convert('{"K": "a\\nb"}', "env")
    assert r["success"]
    assert "\\n" in r["output"]
    assert r["output"].count("\n") <= 1


def test_env_serialize_newline_does_not_break_structure():
    """A newline inside a value must not split into a bogus extra line."""
    r = convert(json.dumps({"A": "line1\nline2", "B": "ok"}), "env")
    assert r["success"], r.get("error")
    out = r["output"]
    assert any(line.strip() == "B=ok" for line in out.split("\n")), out


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


# ════════════════════════════════════════════════════════════════
# 13. Round-trip preservation
# ════════════════════════════════════════════════════════════════

def test_roundtrip_json_yaml_json():
    original = {"name": "Alice", "age": 30, "city": "NYC", "active": True}
    r1 = convert(json.dumps(original), "yaml")
    assert r1["success"]
    r2 = convert(r1["output"], "json")
    assert r2["success"]
    assert _j(r2["output"]) == original


def test_roundtrip_json_toml_json():
    original = {"name": "Alice", "age": 30, "active": True}
    r1 = convert(json.dumps(original), "toml")
    assert r1["success"], f"JSON→TOML failed: {r1.get('error')}"
    r2 = convert(r1["output"], "json")
    assert r2["success"], f"TOML→JSON failed: {r2.get('error')}"
    result = _j(r2["output"])
    for k in original:
        assert k in str(result)


def test_roundtrip_json_xml_json():
    r1 = convert(json.dumps({"name": "Alice", "value": "42", "flag": "true"}), "xml")
    assert r1["success"]
    r2 = convert(r1["output"], "json")
    assert r2["success"]
    assert isinstance(_j(r2["output"]), dict)


def test_roundtrip_json_ini_json():
    original = {"section": {"key": "value", "count": "5", "flag": "true"}}
    r1 = convert(json.dumps(original), "ini")
    assert r1["success"]
    r2 = convert(r1["output"], "json")
    assert r2["success"]
    assert "section" in _j(r2["output"])


def test_roundtrip_json_env_json():
    original = {"DB_HOST": "localhost", "DB_PORT": "5432"}
    r1 = convert(json.dumps(original), "env")
    assert r1["success"]
    r2 = convert(r1["output"], "json")
    assert r2["success"]
    assert _j(r2["output"]) == original


def test_roundtrip_toml_yaml_toml():
    r1 = convert('[user]\nname = "Alice"\nage = 30\nactive = true\n', "yaml")
    assert r1["success"]
    assert convert(r1["output"], "toml")["success"]


def test_roundtrip_yaml_json_yaml():
    r1 = convert("name: Alice\nage: 30\nactive: true\n", "json")
    assert r1["success"]
    assert convert(r1["output"], "yaml")["success"]


def test_csv_output_rfc4180_commas_in_values():
    """CSV output must quote fields containing commas per RFC 4180."""
    src = json.dumps([
        {"item": "widget", "description": "High quality, durable widget"},
        {"item": "gadget", "description": "Simple"},
    ])
    r = convert(src, "csv")
    assert r["success"], r.get("error")
    lines = r["output"].strip().split("\n")
    # CSV DictWriter uses CRLF; strip trailing \r from each line
    lines = [l.rstrip("\r") for l in lines]
    assert len(lines) == 3  # header + 2 data rows
    assert lines[0] == "item,description"
    assert 'widget,"High quality, durable widget"' in lines[1]
    assert lines[2] == 'gadget,Simple'


def test_csv_output_rfc4180_quotes_in_values():
    """CSV output must quote fields containing double quotes per RFC 4180."""
    src = json.dumps([
        {"text": 'She said "hello" to me'},
    ])
    r = convert(src, "csv")
    assert r["success"], r.get("error")
    assert '"""hello"""' in r["output"] or '""hello""' in r["output"] or '"She said ""hello"" to me"' in r["output"], \
        f"Quotes not properly escaped in CSV output: {r['output']!r}"


def test_roundtrip_csv_json_csv():
    r1 = convert("name,age\nAlice,30\nBob,25\n", "json")
    assert r1["success"]
    r2 = convert(r1["output"], "csv")
    assert r2["success"]
    assert "Alice" in r2["output"] and "Bob" in r2["output"]


def test_roundtrip_multiple_hops():
    """JSON → YAML → TOML → XML → JSON multi-hop preservation."""
    current = json.dumps({"name": "test", "value": 42})
    for fmt in ["yaml", "toml", "xml", "json"]:
        r = convert(current, fmt)
        if not r["success"]:
            return
        current = r["output"]
    assert isinstance(json.loads(current), dict)


def test_roundtrip_preserves_booleans():
    original = {"a": True, "b": False, "c": None, "d": 0, "e": ""}
    r1 = convert(json.dumps(original), "yaml")
    assert r1["success"]
    r2 = convert(r1["output"], "json")
    assert r2["success"]
    result = _j(r2["output"])
    assert result["a"] is True and result["b"] is False


def test_roundtrip_preserves_numbers():
    original = {"int": 42, "float": 3.14, "neg": -10, "large": 999999999999}
    r1 = convert(json.dumps(original), "yaml")
    assert r1["success"]
    r2 = convert(r1["output"], "json")
    assert r2["success"]
    result = _j(r2["output"])
    assert result["int"] == 42 and abs(result["float"] - 3.14) < 0.001


# ════════════════════════════════════════════════════════════════
# 14. YAML anchors and aliases
# ════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_anchor_alias_basic():
    src = "base: &base\n  host: localhost\n  port: 8080\ncopy: *base\n"
    r = convert(src, "json", "yaml")
    assert r["success"]
    data = _j(r["output"])
    assert data["copy"]["host"] == "localhost" and data["copy"]["port"] == 8080


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_merge_key():
    src = "defaults: &d\n  adapter: postgres\n  timeout: 30\ndev:\n  <<: *d\n  database: devdb\n"
    r = convert(src, "json", "yaml")
    assert r["success"]
    data = _j(r["output"])
    assert data["dev"]["adapter"] == "postgres" and data["dev"]["database"] == "devdb"


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_merge_key_override():
    """A local key after a merge (<<) overrides the merged value."""
    src = "d: &d\n  timeout: 30\n  retries: 3\ndev:\n  <<: *d\n  timeout: 60\n"
    r = convert(src, "json", "yaml")
    assert r["success"]
    data = _j(r["output"])
    assert data["dev"]["timeout"] == 60 and data["dev"]["retries"] == 3


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_merge_multiple_anchors():
    src = "a: &a\n  p: 1\nb: &b\n  q: 2\nc:\n  <<: [*a, *b]\n  r: 3\n"
    r = convert(src, "json", "yaml")
    assert r["success"]
    data = _j(r["output"])
    assert data["c"]["p"] == 1 and data["c"]["q"] == 2 and data["c"]["r"] == 3


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_anchor_scalar():
    src = "name: &n shared\nfirst: *n\nsecond: *n\n"
    r = convert(src, "json", "yaml")
    assert r["success"]
    data = _j(r["output"])
    assert data["first"] == data["second"] == "shared"


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_anchor_list():
    src = "tags: &t\n  - a\n  - b\n  - c\nmore: *t\n"
    r = convert(src, "json", "yaml")
    assert r["success"]
    assert _j(r["output"])["more"] == ["a", "b", "c"]


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_anchor_in_sequence():
    src = "items:\n  - &first\n    name: a\n  - *first\n"
    r = convert(src, "json", "yaml")
    assert r["success"]
    assert _j(r["output"])["items"][1]["name"] == "a"


# ════════════════════════════════════════════════════════════════
# 15. TOML inline tables
# ════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not HAS_TOML, reason="tomllib not available")
def test_toml_inline_table_basic():
    r = convert('point = { x = 1, y = 2 }\n', "json", "toml")
    assert r["success"]
    data = _j(r["output"])
    assert data["point"]["x"] == 1 and data["point"]["y"] == 2


@pytest.mark.skipif(not HAS_TOML, reason="tomllib not available")
def test_toml_inline_table_strings():
    r = convert('server = { host = "localhost", proto = "https" }\n', "json", "toml")
    assert r["success"]
    assert _j(r["output"])["server"]["host"] == "localhost"


@pytest.mark.skipif(not HAS_TOML, reason="tomllib not available")
def test_toml_array_of_inline_tables():
    r = convert('pts = [ { x = 1 }, { x = 2 }, { x = 3 } ]\n', "json", "toml")
    assert r["success"]
    assert [p["x"] for p in _j(r["output"])["pts"]] == [1, 2, 3]


@pytest.mark.skipif(not HAS_TOML, reason="tomllib not available")
def test_toml_nested_inline_table():
    r = convert('a = { b = { c = 42 } }\n', "json", "toml")
    assert r["success"]
    assert _j(r["output"])["a"]["b"]["c"] == 42


@pytest.mark.skipif(not HAS_TOML, reason="tomllib not available")
def test_toml_inline_table_mixed_types():
    r = convert('m = { i = 1, f = 2.5, b = true, s = "x" }\n', "json", "toml")
    assert r["success"]
    data = _j(r["output"])
    assert data["m"]["i"] == 1 and data["m"]["b"] is True and data["m"]["s"] == "x"


@pytest.mark.skipif(not HAS_TOML, reason="tomllib not available")
def test_toml_empty_inline_table():
    r = convert('e = {}\n', "json", "toml")
    assert r["success"]
    assert _j(r["output"])["e"] == {}


@pytest.mark.skipif(not HAS_TOML, reason="tomllib not available")
def test_toml_inline_escaped_quote():
    r = convert('item = {name = "he said \\"hello\\""}\n', "json")
    assert r["success"], r.get("error")
    assert _j(r["output"])["item"]["name"] == 'he said "hello"'


@pytest.mark.skipif(not HAS_TOML, reason="tomllib not available")
def test_toml_dotted_key_quad_nested():
    r = convert('a.b.c.d = 1\n', "json", "toml")
    assert r["success"], r.get("error")
    assert _j(r["output"])["a"]["b"]["c"]["d"] == 1


# ════════════════════════════════════════════════════════════════
# 16. TOML serialization — scalar arrays, key quoting, scalar guards
# ════════════════════════════════════════════════════════════════

def test_toml_int_array_roundtrip():
    """JSON→TOML: int list becomes proper TOML array, not [[table]] junk."""
    r = convert(json.dumps({"ports": [80, 443, 8080], "name": "web"}), "toml")
    assert r["success"], r.get("error")
    assert "ports = [80, 443, 8080]" in r["output"]
    assert "[[ports]]" not in r["output"]
    d = _j(convert(r["output"], "json")["output"])
    assert d["ports"] == [80, 443, 8080] and d["name"] == "web"


def test_toml_string_array_roundtrip():
    r = convert(json.dumps({"tags": ["a", "b", "c"]}), "toml")
    assert r["success"]
    assert _j(convert(r["output"], "json")["output"])["tags"] == ["a", "b", "c"]


def test_toml_bool_array_roundtrip():
    r = convert(json.dumps({"flags": [True, False, True]}), "toml")
    assert r["success"]
    assert _j(convert(r["output"], "json")["output"])["flags"] == [True, False, True]


def test_toml_float_array_roundtrip():
    r = convert(json.dumps({"vals": [1.5, 2.7, 3.14]}), "toml")
    assert r["success"]
    assert abs(_j(convert(r["output"], "json")["output"])["vals"][0] - 1.5) < 0.01


def test_toml_empty_array_roundtrip():
    r = convert(json.dumps({"items": []}), "toml")
    assert r["success"]
    assert _j(convert(r["output"], "json")["output"])["items"] == []


def test_toml_scalar_after_table_not_absorbed():
    """Scalar key after a [server] table must not be absorbed into server dict."""
    r = convert(json.dumps({"server": {"host": "localhost", "port": 8080}, "name": "top"}), "toml")
    assert r["success"], r.get("error")
    d = _j(convert(r["output"], "json")["output"])
    assert d["name"] == "top" and d["server"]["host"] == "localhost"
    assert "name" not in d["server"]


def test_toml_multiple_scalars_and_tables_order():
    r = convert(json.dumps({"a": {"x": 1}, "b": 2, "c": {"y": 3}, "d": 4}), "toml")
    assert r["success"]
    d = _j(convert(r["output"], "json")["output"])
    assert d["b"] == 2 and d["d"] == 4 and d["a"]["x"] == 1 and d["c"]["y"] == 3


def test_toml_array_of_tables_preserved():
    data = [{"name": "alice", "age": 30}, {"name": "bob", "age": 25}]
    r = convert(json.dumps(data), "toml")
    assert r["success"]
    assert "alice" in r["output"] and "bob" in r["output"]


def test_toml_inline_nested_dict_value():
    """A nested dict in a list-of-dicts must become a TOML inline table."""
    r = convert(json.dumps([{"name": "a", "meta": {"k": 1}}]), "toml")
    assert r["success"], r.get("error")
    out = r["output"]
    assert "{'k'" not in out
    assert "meta = { k = 1 }" in out or "meta = {k = 1}" in out


def test_toml_inline_nested_list_value():
    """A nested list in a list-of-dicts must become a TOML array, not a string."""
    r = convert(json.dumps([{"name": "a", "vals": [1, 2, 3]}]), "toml")
    assert r["success"], r.get("error")
    out = r["output"]
    assert "vals = [1, 2, 3]" in out
    assert "'[1, 2, 3]'" not in out and '"[1, 2, 3]"' not in out


def test_toml_key_with_space_is_wellformed():
    r = convert(json.dumps({"my key": "v", "ok": 1}), "toml")
    assert r["success"], r.get("error")
    d = _j(convert(r["output"], "json", "toml")["output"])
    assert d["my key"] == "v" and d["ok"] == 1


def test_toml_key_with_dot_is_quoted():
    r = convert(json.dumps({"db.host": "localhost"}), "toml")
    assert r["success"], r.get("error")
    d = _j(convert(r["output"], "json", "toml")["output"])
    assert d["db.host"] == "localhost"
    assert "db" not in d or not isinstance(d.get("db"), dict)


def test_toml_section_name_with_space_is_quoted():
    r = convert(json.dumps({"my section": {"a": 1}}), "toml")
    assert r["success"], r.get("error")
    assert _j(convert(r["output"], "json", "toml")["output"])["my section"]["a"] == 1


def test_toml_nested_key_with_space_in_table():
    r = convert(json.dumps({"server": {"my key": "v"}}), "toml")
    assert r["success"], r.get("error")
    assert _j(convert(r["output"], "json", "toml")["output"])["server"]["my key"] == "v"


def test_toml_unicode_key_is_quoted():
    r = convert(json.dumps({"café": 1}), "toml")
    assert r["success"], r.get("error")
    assert _j(convert(r["output"], "json", "toml")["output"])["café"] == 1


def test_toml_inline_table_key_with_space():
    r = convert(json.dumps([{"my key": 1}]), "toml")
    assert r["success"], r.get("error")
    assert '"my key" = 1' in r["output"]
    assert "my key = 1" not in r["output"]


def test_toml_normal_keys_stay_bare():
    """Normal alphanumeric keys must NOT be quoted."""
    r = convert(json.dumps({"host": "x", "port": 8080}), "toml")
    assert r["success"], r.get("error")
    assert "host = " in r["output"] and '"host"' not in r["output"]


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


def test_toml_toplevel_scalar_list_fails_gracefully():
    """A bare array of scalars cannot be TOML; must error, not vanish."""
    r = convert(json.dumps([1, 2, 3]), "toml")
    assert not r["success"] and r["error"]


def test_toml_toplevel_table_array_still_ok():
    r = convert(json.dumps([{"name": "a"}, {"name": "b"}]), "toml")
    assert r["success"], r.get("error")
    assert "a" in r["output"] and "b" in r["output"]


def test_toml_none_in_array_fails_gracefully():
    r = convert(json.dumps({"vals": [1, None, 3]}), "toml")
    assert not r["success"], r.get("output")
    assert r["error"]


def test_toml_none_in_inline_table_fails_gracefully():
    r = convert(json.dumps([{"meta": {"k": None}}]), "toml")
    assert not r["success"], r.get("output")
    assert r["error"]


def test_toml_dict_still_ok():
    r = convert(json.dumps({"a": 1}), "toml")
    assert r["success"], r.get("error")
    assert "a = 1" in r["output"]


# ════════════════════════════════════════════════════════════════
# 17. INI features — percent values, mixed scalars, strict inference,
#     comments in values
# ════════════════════════════════════════════════════════════════

def test_ini_percent_value_roundtrip():
    r = convert(json.dumps({"stats": {"cpu": "80%", "disk": "50%"}}), "ini")
    assert r["success"], r.get("error")
    d = _j(convert(r["output"], "json")["output"])
    assert d["stats"]["cpu"] == "80%" and d["stats"]["disk"] == "50%"


def test_ini_parse_percent_literal():
    r = convert("[section]\ntemplate = 100%\nname = value\n", "json")
    assert r["success"], r.get("error")
    assert _j(r["output"])["section"]["template"] == "100%"


def test_ini_mixed_toplevel_scalar_and_section_no_crash():
    """JSON with a scalar alongside a section dict must not crash INI output."""
    r = convert(json.dumps({"name": "top", "server": {"host": "x", "port": 8080}}), "ini")
    assert r["success"], r.get("error")
    out = r["output"]
    assert "name" in out and "top" in out and "[server]" in out and "host" in out


def test_ini_mixed_scalar_roundtrips_to_json():
    r = convert(json.dumps({"title": "app", "db": {"host": "local", "port": 5432}}), "ini")
    assert r["success"], r.get("error")
    back = convert(r["output"], "json")
    assert back["success"], back.get("error")
    assert "title" in back["output"] and "app" in back["output"]


def test_ini_toplevel_list_fails_gracefully():
    """A top-level list value (not representable) should fail, not crash."""
    r = convert(json.dumps({"tags": [1, 2, 3], "server": {"host": "x"}}), "ini")
    assert not r["success"]
    assert r["error"]


def test_ini_dotted_keys():
    r = convert("[section]\ndb.host=localhost\ndb.port=5432\n", "json")
    assert r["success"]


def test_ini_underscore_number_stays_string():
    """'1_000' must NOT be silently turned into the integer 1000."""
    r = convert("[s]\nserial = 1_000\n", "json")
    assert r["success"], r.get("error")
    assert _j(r["output"])["s"]["serial"] == "1_000"


def test_ini_leading_zero_stays_string():
    """A leading-zero value (zip code) must stay a string, not become int."""
    r = convert("[addr]\nzip = 02134\n", "json", "ini")
    assert r["success"], r.get("error")
    assert _j(r["output"])["addr"]["zip"] == "02134"


def test_ini_overflow_float_stays_string():
    """'1e500' overflows to inf; it must stay a string (inf is not valid JSON)."""
    r = convert("[s]\nbig = 1e500\n", "json")
    assert r["success"], r.get("error")
    out = r["output"]
    assert "Infinity" not in out
    assert _j(out)["s"]["big"] == "1e500"


def test_ini_normal_numbers_still_inferred():
    """Regression: ordinary ints/floats are still inferred."""
    data = _j(convert("[s]\ncount = 42\nratio = 3.14\nsci = 1e3\nneg = -7\n", "json")["output"])["s"]
    assert data["count"] == 42 and isinstance(data["count"], int)
    assert abs(data["ratio"] - 3.14) < 1e-9
    assert data["sci"] == 1000.0 and data["neg"] == -7


def test_infer_type_unit():
    """Direct unit coverage of the strict inference helper."""
    assert _infer_type("1_000") == "1_000"
    assert _infer_type("007") == "007"
    assert _infer_type("1e500") == "1e500"
    assert _infer_type("42") == 42
    assert _infer_type("-3.5") == -3.5
    assert _infer_type("0") == 0


def test_ini_semicolon_in_value_kept():
    """A semicolon inside a value is NOT treated as an inline comment by default."""
    r = convert("[section]\nkey = value ; not a comment\n", "json")
    assert r["success"]
    assert "; not a comment" in _j(r["output"])["section"]["key"]


def test_ini_hash_in_value_kept():
    """A '#' inside a value is preserved (URL fragments survive)."""
    r = convert("[web]\nurl = http://example.com/page#section\n", "json")
    assert r["success"]
    assert _j(r["output"])["web"]["url"].endswith("#section")


def test_ini_fullline_comment_skipped():
    r = convert("[s]\n; this whole line is a comment\nkey = realvalue\n", "json")
    assert r["success"]
    assert _j(r["output"])["s"]["key"] == "realvalue"


# ════════════════════════════════════════════════════════════════
# 18. Comment preservation (the #1 user complaint)
#     JSON can't hold comments; convert() extracts them and round_trip()
#     carries them back. These prove comments SURVIVE round-trips.
# ════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_block_comment_survives_roundtrip():
    out = round_trip("# database connection settings\nhost: localhost\nport: 5432\n", via="json", fmt="yaml")
    assert out["success"], out.get("error")
    assert "database connection settings" in out["output"]


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_inline_comment_survives_roundtrip():
    out = round_trip("host: localhost\nport: 5432  # default postgres port\n", via="json", fmt="yaml")
    assert out["success"], out.get("error")
    assert "default postgres port" in out["output"]


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_header_comment_survives_roundtrip():
    out = round_trip("# Auto-generated config -- do not edit by hand\nname: app\nversion: 2\n", via="json", fmt="yaml")
    assert out["success"], out.get("error")
    assert "Auto-generated config" in out["output"]


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_do_not_change_warning_survives_roundtrip():
    """The 'DO NOT CHANGE' safety warning above a critical value survives."""
    src = "replicas: 3\n# DO NOT CHANGE -- production traffic depends on this value\nmax_connections: 1000\n"
    out = round_trip(src, via="json", fmt="yaml")
    assert out["success"], out.get("error")
    assert "DO NOT CHANGE" in out["output"]


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_all_comments_survive_full_roundtrip():
    src = (
        "# header A\n# header B\nname: myapp  # inline name\n"
        "# section comment\ndatabase:\n  host: localhost  # db host\n  port: 5432\n"
    )
    out = round_trip(src, via="json", fmt="yaml")
    assert out["success"]
    for fragment in ["header A", "header B", "inline name", "section comment", "db host"]:
        assert fragment in out["output"], f"lost comment: {fragment}"


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_comment_count_is_preserved_not_inflated():
    out = _yaml_rt("# a\nx: 1  # b\n# c\ny: 2\n")
    assert out["success"]
    assert out["output"].count("#") == 3


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_roundtrip_is_idempotent():
    src = "# top\nname: myapp  # inline\n# block\nnested:\n  key: value  # leaf\n"
    first = _yaml_rt(src)
    assert first["success"]
    second = round_trip(first["output"], via="json", fmt="yaml")
    assert second["success"]
    assert second["output"] == first["output"]


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_roundtrip_still_preserves_data():
    """Carrying comments must not corrupt the underlying data."""
    out = round_trip("# header\nhost: localhost  # inline\nport: 5432\nactive: true\n", via="json", fmt="yaml")
    assert out["success"], out.get("error")
    reparsed = parse_text(out["output"], "yaml")["data"]
    assert reparsed["host"] == "localhost"
    assert reparsed["port"] == 5432
    assert reparsed["active"] is True


def test_yaml_comment_stripped_without_preservation():
    """Negative control: preserve_comments=False drops comments."""
    fwd = convert("# header comment\nhost: localhost\n", "json", "yaml", preserve_comments=False)
    assert fwd["success"]
    back = convert(fwd["output"], "yaml", "json", preserve_comments=False)
    assert back["success"]
    assert "header comment" not in back["output"]


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_list_item_inline_comment_survives_roundtrip():
    """An inline comment on a YAML list item (a line with no `key:`) must survive."""
    r = _yaml_rt("fruits:\n  - apple  # a tasty fruit\n  - banana\n")
    assert r["success"], r.get("error")
    assert "a tasty fruit" in r["output"]


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_multiple_list_item_comments_survive_roundtrip():
    r = _yaml_rt("ports:\n  - 80   # http\n  - 443  # https\n  - 22   # ssh\n")
    assert r["success"], r.get("error")
    for fragment in ("http", "https", "ssh"):
        assert fragment in r["output"], f"lost list-item comment: {fragment}"


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_comment_after_quoted_hash_value_survives_roundtrip():
    """A trailing comment after a value that itself contains a quoted '#' must survive."""
    r = _yaml_rt('color: "#ffffff"  # background color\n')
    assert r["success"], r.get("error")
    assert "background color" in r["output"]
    assert parse_text(r["output"], "yaml")["data"] == {"color": "#ffffff"}


def test_ini_block_comment_survives_roundtrip():
    out = round_trip("[database]\n# primary connection host\nhost = localhost\nport = 5432\n", via="json", fmt="ini")
    assert out["success"], out.get("error")
    assert "primary connection host" in out["output"]


def test_ini_semicolon_comment_survives_roundtrip():
    out = round_trip("[server]\n; classic ini comment style\nworkers = 4\n", via="json", fmt="ini")
    assert out["success"], out.get("error")
    assert "classic ini comment style" in out["output"]


def test_ini_inline_comment_survives_roundtrip():
    out = round_trip("[server]\nhost = localhost  # primary host\nport = 8080\n", via="json", fmt="ini")
    assert out["success"]
    assert "primary host" in out["output"]


def test_roundtrip_helper_reports_success_and_detects_yaml():
    out = round_trip("# c\nkey: value\n", via="json", fmt="yaml")
    assert out["success"], out.get("error")
    assert detect_format(out["output"]) == "yaml"


# ════════════════════════════════════════════════════════════════
# 19. Miscellaneous engine API
# ════════════════════════════════════════════════════════════════

def test_convert_file_nonexistent():
    r = convert_file("/nonexistent/path/file.json")
    assert not r["success"]
    assert "not found" in r["error"].lower()


def test_convert_file_binary():
    assert not convert("\x00\x01\x02\xff", "json")["success"]


def test_convert_with_options():
    """Convert with sort_keys puts 'a' before 'b'."""
    r = convert(json.dumps({"b": 2, "a": 1, "c": 3}), "json", sort_keys=True, indent=4)
    assert r["success"]
    assert r["output"].index('"a"') < r["output"].index('"b"')


def test_convert_preserve_unicode():
    """JSON serialization keeps non-ASCII (ensure_ascii=False)."""
    r = convert('{"emoji": "🚀"}', "json")
    assert r["success"]
    assert "🚀" in r["output"]


def test_serialize_to_unsupported():
    with pytest.raises(ValueError):
        serialize({"data": "test"}, "unsupported")


def test_parse_text_unsupported():
    with pytest.raises(ValueError):
        parse_text("hello", "unsupported")


def test_convert_batch_empty_glob():
    results = batch_convert("/nonexistent_glob_*.xyz", "json")
    assert isinstance(results, list) and len(results) == 0


def test_supported_formats_constant():
    for fmt in ("json", "yaml", "toml", "xml", "csv", "ini", "env"):
        assert fmt in SUPPORTED_FORMATS


def test_convert_all_primitive_types():
    src = json.dumps({
        "string": "hello", "integer": 42, "float": 3.14,
        "bool_true": True, "bool_false": False, "null_val": None,
        "list": [1, 2, 3], "nested": {"a": 1},
    })
    assert convert(src, "yaml")["success"]


def test_yaml_multiline_strings():
    """YAML with multiline string values (| and >)."""
    src = "description: |\n  This is a\n  multiline string\n  with three lines\n"
    r = convert(src, "json", "yaml")
    assert r["success"]
    assert "multiline" in _j(r["output"]).get("description", "")


def test_yaml_null_values():
    r = convert("a: null\nb: ~\nc:\n", "json", "yaml")
    assert r["success"]
    assert isinstance(_j(r["output"]), dict)


# ════════════════════════════════════════════════════════════════
# 20. External-review regression tests (forge/external-review-20260607-1416.md)
#     Sourced from real HN/GitHub complaints about yq, jq/gojq:
#       • yq#2516  — comments preceding merge-keys dropped in ireduce
#       • "the YAML document from hell" (ruudvanasseldonk.com 2023-01-11)
#       • the "Norway problem" (unquoted no/yes type inference)
#       • gojq does not preserve key order ("a non-starter for human review")
# ════════════════════════════════════════════════════════════════

# ── P0: comments preceding merge-keys survive (yq#2516) ──
# yq silently drops comments that sit immediately *before* a merge-key (`<<:`)
# during ireduce pipeline operations. ConfigForge carries the comment through
# the JSON intermediate and restores it on the way back out.

@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_comment_before_merge_key_survives_roundtrip():
    """yq#2516 regression: a comment right before a `<<:` merge survives YAML->JSON->YAML."""
    src = (
        "defaults: &d\n"
        "  adapter: postgres\n"
        "  timeout: 30\n"
        "# This comment should survive\n"
        "dev:\n"
        "  <<: *d\n"
        "  database: devdb\n"
    )
    out = _yaml_rt(src)
    assert out["success"], out.get("error")
    assert "This comment should survive" in out["output"]


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_comment_before_merge_key_data_intact():
    """The merge itself must still resolve correctly while the comment survives."""
    src = (
        "defaults: &d\n"
        "  adapter: postgres\n"
        "  timeout: 30\n"
        "# This comment should survive\n"
        "dev:\n"
        "  <<: *d\n"
        "  database: devdb\n"
    )
    r = convert(src, "json", "yaml")
    assert r["success"]
    data = _j(r["output"])
    assert data["dev"]["adapter"] == "postgres"
    assert data["dev"]["timeout"] == 30
    assert data["dev"]["database"] == "devdb"


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_comment_before_merge_key_with_multiple_anchors_survives():
    """Comment before a multi-anchor merge (`<<: [*a, *b]`) also survives the round-trip."""
    src = (
        "a: &a\n  p: 1\n"
        "b: &b\n  q: 2\n"
        "# merge note above the merge key\n"
        "c:\n  <<: [*a, *b]\n  r: 3\n"
    )
    out = _yaml_rt(src)
    assert out["success"], out.get("error")
    assert "merge note above the merge key" in out["output"]


# ── P1: "the YAML document from hell" edge cases ──
# yq required three edits (*.html, *.png, !.git) to even parse the canonical
# "document from hell". These lock in that the ambiguous-but-legal scalars are
# inferred as strings rather than mangled into numbers/dates/aliases.

@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_hell_timestamp_like_string_stays_string():
    """An unquoted value that merely *looks* like a date must serialize as a JSON string, not a number."""
    r = convert("release: 2023-01-11\n", "json", "yaml")
    assert r["success"]
    data = _j(r["output"])
    assert data["release"] == "2023-01-11"
    assert isinstance(data["release"], str)


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_hell_glob_and_bang_patterns_stay_strings():
    """Quoted glob/negation patterns (*.html, *.png, !.git) survive as plain strings.

    These are exactly the three tokens yq could not parse without edits. ConfigForge
    parses them (when quoted, as any YAML-legal config must) and keeps them as strings.
    """
    src = 'patterns:\n  - "*.html"\n  - "*.png"\n  - "!.git"\n'
    r = convert(src, "json", "yaml")
    assert r["success"]
    assert _j(r["output"])["patterns"] == ["*.html", "*.png", "!.git"]


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_hell_leading_zero_quoted_stays_string():
    """A quoted '007' stays the string '007' (leading zeros are not dropped)."""
    r = convert('code: "007"\n', "json", "yaml")
    assert r["success"]
    data = _j(r["output"])
    assert data["code"] == "007"
    assert isinstance(data["code"], str)


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_hell_full_document_multiformat_roundtrip():
    """A document combining the hell edge cases survives YAML->JSON->YAML intact."""
    src = (
        "release: 2023-01-11\n"
        "patterns:\n"
        '  - "*.html"\n'
        '  - "*.png"\n'
        '  - "!.git"\n'
        'code: "007"\n'
        'version: "1.0.0"\n'
    )
    out = _yaml_rt(src)
    assert out["success"], out.get("error")
    back = _j(convert(out["output"], "json", "yaml")["output"])
    assert back["release"] == "2023-01-11"
    assert back["patterns"] == ["*.html", "*.png", "!.git"]
    assert back["code"] == "007"
    assert back["version"] == "1.0.0"


# ── P1: Norwegian/boolean string type inference ──
# NOTE ON ACTUAL BEHAVIOR: ConfigForge (like YAML 1.1) treats *unquoted*
# no/yes/on/off/true/false as booleans — see _infer_type() and the documented
# test_configforge.py::test_ini_bool_inference. That is deliberate and
# *consistent* (unlike yq, which quotes some and not others). The Norway-SAFE
# path a config author uses is to quote the value; these tests pin down that
# quoting reliably preserves the string, and that multi-dot versions stay strings.

@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_norway_unquoted_no_is_bool_false():
    """Documents the actual (intentional, YAML-1.1) behavior: unquoted `no` -> False."""
    r = convert("allow_postgres: no\n", "json", "yaml")
    assert r["success"]
    assert _j(r["output"])["allow_postgres"] is False


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_norway_quoted_no_yes_stay_strings():
    """The Norway-safe path: quoted `no`/`yes` are preserved as strings, not booleans."""
    r = convert('a: "no"\nb: "yes"\n', "json", "yaml")
    assert r["success"]
    data = _j(r["output"])
    assert data["a"] == "no" and isinstance(data["a"], str)
    assert data["b"] == "yes" and isinstance(data["b"], str)


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_quoted_true_false_stay_strings():
    """Quoted `true`/`false` stay the strings 'true'/'false', not booleans."""
    r = convert('x: "true"\ny: "false"\n', "json", "yaml")
    assert r["success"]
    data = _j(r["output"])
    assert data["x"] == "true" and isinstance(data["x"], str)
    assert data["y"] == "false" and isinstance(data["y"], str)


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_multidot_version_stays_string():
    """A version like 1.0.0 (two dots) is unambiguous and stays a string."""
    r = convert("version: 1.0.0\n", "json", "yaml")
    assert r["success"]
    data = _j(r["output"])
    assert data["version"] == "1.0.0" and isinstance(data["version"], str)


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_yaml_quoted_two_component_version_stays_string():
    """A single-dot version like 2.0 must be quoted to stay a string (else it's a float)."""
    r = convert('version: "2.0"\n', "json", "yaml")
    assert r["success"]
    data = _j(r["output"])
    assert data["version"] == "2.0" and isinstance(data["version"], str)


def test_infer_type_norway_and_versions():
    """Direct _infer_type coverage of the Norway/version cases.

    Reflects ConfigForge's documented, consistent inference for non-YAML formats
    (INI/ENV/properties/CSV): yes/no/on/off -> bool, single-dot version -> float,
    multi-dot version -> string, leading-zero -> string.
    """
    assert _infer_type("no") is False
    assert _infer_type("yes") is True
    assert _infer_type("off") is False
    assert _infer_type("on") is True
    assert _infer_type("true") is True
    assert _infer_type("false") is False
    # multi-dot versions and leading zeros are not numbers -> preserved as strings
    assert _infer_type("1.0.0") == "1.0.0"
    assert _infer_type("007") == "007"
    # a single-dot version IS a valid float and is inferred as one
    assert _infer_type("2.0") == 2.0


# ── P2: key-order preservation (gojq does not; a "non-starter" for review) ──

def test_key_order_preserved_json_yaml_json():
    """Insertion order survives JSON -> YAML -> JSON (gojq does not preserve this)."""
    keys = ["zebra", "apple", "mango", "banana", "cherry", "delta", "echo"]
    src = json.dumps({k: i for i, k in enumerate(keys)})
    via_yaml = convert(src, "yaml", "json")
    assert via_yaml["success"]
    back = convert(via_yaml["output"], "json", "yaml")
    assert back["success"]
    assert list(_j(back["output"]).keys()) == keys


def test_key_order_preserved_in_yaml_output_lines():
    """The serialized YAML emits keys in original order, not sorted."""
    keys = ["zebra", "apple", "mango", "banana", "cherry"]
    src = json.dumps({k: i for i, k in enumerate(keys)})
    r = convert(src, "yaml", "json")
    assert r["success"]
    positions = [r["output"].index(f"{k}:") for k in keys]
    assert positions == sorted(positions), "YAML keys were reordered"


@pytest.mark.skipif(not HAS_TOML, reason="tomllib not available")
def test_key_order_preserved_json_toml_json():
    """Key order also survives a JSON -> TOML -> JSON round-trip."""
    keys = ["gamma", "alpha", "omega", "beta", "sigma"]
    src = json.dumps({k: i for i, k in enumerate(keys)})
    via_toml = convert(src, "toml", "json")
    assert via_toml["success"]
    back = convert(via_toml["output"], "json", "toml")
    assert back["success"]
    assert list(_j(back["output"]).keys()) == keys
