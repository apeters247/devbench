"""ConfigForge — JSONC (JSON with Comments) format tests.

Addresses yq GitHub issue #2536 — the most-requested format addition for
config tools used in devops (tsconfig.json, .vscode/settings.json, etc.).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.configforge import (
    convert, detect_format, parse_text, serialize, SUPPORTED_FORMATS,
    _strip_jsonc,
)


# ── _strip_jsonc internals ──

def test_strip_line_comment():
    assert _strip_jsonc('{"a": 1} // trailing') == '{"a": 1} '

def test_strip_line_comment_midline():
    result = _strip_jsonc('{"a": 1, // inline\n"b": 2}')
    import json
    assert json.loads(result) == {"a": 1, "b": 2}

def test_strip_block_comment():
    result = _strip_jsonc('{"a": /* comment */ 1}')
    import json
    assert json.loads(result) == {"a": 1}

def test_strip_multiline_block_comment():
    text = '{\n  /* multi\n     line */\n  "key": "val"\n}'
    import json
    assert json.loads(_strip_jsonc(text)) == {"key": "val"}

def test_strip_trailing_comma_object():
    import json
    result = _strip_jsonc('{"a": 1, "b": 2,}')
    assert json.loads(result) == {"a": 1, "b": 2}

def test_strip_trailing_comma_array():
    import json
    result = _strip_jsonc('[1, 2, 3,]')
    assert json.loads(result) == [1, 2, 3]

def test_strip_comment_inside_string_untouched():
    import json
    text = '{"url": "http://example.com/path"}'
    result = _strip_jsonc(text)
    assert json.loads(result) == {"url": "http://example.com/path"}

def test_strip_double_slash_inside_string_untouched():
    import json
    text = '{"msg": "a // not a comment"}'
    assert json.loads(_strip_jsonc(text)) == {"msg": "a // not a comment"}

def test_strip_block_comment_inside_string_untouched():
    import json
    text = '{"msg": "/* not a comment */"}'
    assert json.loads(_strip_jsonc(text)) == {"msg": "/* not a comment */"}

def test_strip_escaped_quote_in_string():
    import json
    text = '{"key": "say \\"hello\\" // not a comment"}'
    assert json.loads(_strip_jsonc(text)) == {"key": 'say "hello" // not a comment'}


# ── Detection ──

def test_detect_jsonc_line_comment():
    text = '{\n  // a comment\n  "name": "tsconfig"\n}'
    assert detect_format(text) == "jsonc"

def test_detect_jsonc_block_comment():
    text = '{\n  /* block */\n  "name": "value"\n}'
    assert detect_format(text) == "jsonc"

def test_detect_jsonc_trailing_comma():
    text = '{\n  "a": 1,\n}'
    assert detect_format(text) == "jsonc"

def test_detect_plain_json_not_stolen():
    text = '{"a": 1, "b": [1, 2]}'
    assert detect_format(text) == "json"

def test_jsonc_in_supported_formats():
    assert "jsonc" in SUPPORTED_FORMATS


# ── parse_text ──

def test_parse_jsonc_line_comment():
    text = '{\n  // version comment\n  "version": "1.0"\n}'
    r = parse_text(text, "jsonc")
    assert r["data"]["version"] == "1.0"
    assert r["format"] == "jsonc"

def test_parse_jsonc_block_comment():
    text = '{\n  /* describes the field */\n  "port": 8080\n}'
    r = parse_text(text, "jsonc")
    assert r["data"]["port"] == 8080

def test_parse_jsonc_trailing_comma():
    text = '{"include": ["src/",],}'
    r = parse_text(text, "jsonc")
    assert r["data"]["include"] == ["src/"]

def test_parse_jsonc_vscode_settings():
    text = '''{
  // VS Code settings
  "editor.tabSize": 2,
  "editor.formatOnSave": true, // trailing comma
}'''
    r = parse_text(text, "jsonc")
    assert r["data"]["editor.tabSize"] == 2
    assert r["data"]["editor.formatOnSave"] is True

def test_parse_jsonc_tsconfig():
    text = '''{
  /* TypeScript compiler options */
  "compilerOptions": {
    "target": "es2020", // modern target
    "strict": true,
  },
  "include": ["src/**/*",]
}'''
    r = parse_text(text, "jsonc")
    d = r["data"]
    assert d["compilerOptions"]["target"] == "es2020"
    assert d["compilerOptions"]["strict"] is True
    assert d["include"] == ["src/**/*"]


# ── serialize ──

def test_serialize_jsonc_produces_valid_json():
    import json
    data = {"name": "ConfigForge", "version": 1}
    out = serialize(data, "jsonc")
    assert json.loads(out) == data

def test_serialize_jsonc_indented():
    out = serialize({"a": 1}, "jsonc", indent=4)
    assert '    "a": 1' in out


# ── convert ──

def test_convert_jsonc_to_yaml():
    text = '{\n  // port\n  "port": 8080\n}'
    r = convert(text, "yaml", "jsonc")
    assert r["success"]
    assert "8080" in r["output"]

def test_convert_jsonc_to_toml():
    text = '{\n  "name": "myapp", // name\n  "version": "1.0"\n}'
    r = convert(text, "toml", "jsonc")
    assert r["success"]
    assert 'name = "myapp"' in r["output"]

def test_convert_jsonc_auto_detect():
    text = '{\n  // comment\n  "key": "value"\n}'
    r = convert(text, "yaml")
    assert r["success"]
    assert "value" in r["output"]

def test_convert_jsonc_to_json_strips_comments():
    text = '{\n  // a comment\n  "a": 1,\n}'
    r = convert(text, "json", "jsonc")
    import json
    assert r["success"]
    assert json.loads(r["output"]) == {"a": 1}

def test_convert_plain_json_to_jsonc():
    text = '{"a": 1}'
    r = convert(text, "jsonc")
    import json
    assert r["success"]
    assert json.loads(r["output"]) == {"a": 1}
