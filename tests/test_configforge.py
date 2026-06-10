"""ConfigForge — conversion engine tests."""
import sys, os, json
import yaml
import tomllib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.configforge import convert, convert_file, batch_convert, batch_convert_stream, detect_format, parse_text, SUPPORTED_FORMATS

def test_detect_json():
    assert detect_format('{"a":1}') == "json"
    assert detect_format('[1,2,3]') == "json"

def test_detect_yaml():
    assert detect_format("key: value\nnested:\n  a: 1") == "yaml"

def test_detect_toml():
    assert detect_format("[server]\nhost = 'localhost'\nport = 8080") == "toml"

def test_detect_xml():
    assert detect_format("<root><item>value</item></root>") == "xml"

def test_detect_ini():
    assert detect_format("[database]\nhost=localhost\nport=5432") == "ini"

def test_detect_env():
    assert detect_format("DATABASE_URL=postgres://localhost\nSECRET_KEY=abc123") == "env"

def test_detect_csv():
    assert detect_format("name,age,city\nAlice,30,NYC\nBob,25,LA") == "csv"

def test_convert_json_to_yaml():
    r = convert('{"name": "test", "value": 42}', "yaml")
    assert r["success"]
    parsed = yaml.safe_load(r["output"])
    assert parsed == {"name": "test", "value": 42}

def test_convert_json_to_toml():
    r = convert('{"server": {"host": "localhost", "port": 8080}}', "toml")
    assert r["success"]
    parsed = tomllib.loads(r["output"])
    assert parsed == {"server": {"host": "localhost", "port": 8080}}

def test_convert_yaml_to_json():
    r = convert("key: value\nnested:\n  a: 1", "json")
    assert r["success"]
    parsed = json.loads(r["output"])
    assert parsed["key"] == "value"

def test_convert_toml_to_json():
    tom = '[server]\nhost = "localhost"\nport = 8080'
    r = convert(tom, "json")
    assert r["success"]
    parsed = json.loads(r["output"])
    assert parsed["server"]["host"] == "localhost"

def test_convert_ini_to_json():
    r = convert("[section]\nkey=value\n", "json")
    assert r["success"]
    parsed = json.loads(r["output"])
    assert parsed["section"]["key"] == "value"

def test_convert_env_to_json():
    r = convert("DATABASE_URL=postgres://localhost\nSECRET=abc123", "json")
    assert r["success"]
    parsed = json.loads(r["output"])
    assert parsed["DATABASE_URL"] == "postgres://localhost"

def test_convert_csv_to_json():
    r = convert("name,age\nAlice,30\nBob,25", "json")
    assert r["success"]
    parsed = json.loads(r["output"])
    assert parsed == [
        {"name": "Alice", "age": "30"},
        {"name": "Bob", "age": "25"},
    ]

def test_convert_xml_to_json():
    r = convert("<root><item>hello</item></root>", "json")
    assert r["success"]
    parsed = json.loads(r["output"])
    assert parsed["item"] == "hello"

def test_roundtrip_json():
    """Convert JSON -> YAML -> JSON should preserve data."""
    original = '{"name":"Alice","age":30,"city":"NYC"}'
    r1 = convert(original, "yaml")
    assert r1["success"]
    r2 = convert(r1["output"], "json")
    assert r2["success"]
    assert json.loads(r2["output"]) == json.loads(original)

def test_roundtrip_toml():
    original = '[user]\nname = "Alice"\nage = 30'
    r1 = convert(original, "json")
    assert r1["success"]
    r2 = convert(r1["output"], "toml")
    assert r2["success"]
    parsed_original = tomllib.loads(original)
    parsed_roundtrip = tomllib.loads(r2["output"])
    assert parsed_original == parsed_roundtrip

def test_invalid_input():
    r = convert("not valid content", "json")
    assert not r["success"]
    assert "detect" in r["error"].lower() or "format" in r["error"].lower()

def test_empty_input():
    r = convert("", "json")
    assert not r["success"]
    assert r["error"]

def test_supported_formats():
    expected_formats = ["json", "jsonc", "json5", "yaml", "toml", "xml", "csv", "ini", "env", "hcl", "properties", "plist"]
    assert set(SUPPORTED_FORMATS) == set(expected_formats)

def test_convert_file(tmp_path):
    import pathlib
    f = tmp_path / "test.json"
    f.write_text('{"hello": "world"}')
    out = tmp_path / "test.yaml"
    r = convert_file(str(f), str(out))
    assert r["success"]
    assert out.exists()
    assert yaml.safe_load(out.read_text()) == {"hello": "world"}

def test_batch_convert(tmp_path):
    for i in range(3):
        (tmp_path / f"cfg{i}.json").write_text(f'{{"id": {i}}}')
    out_dir = tmp_path / "yaml_out"
    results = batch_convert(str(tmp_path / "*.json"), "yaml", str(out_dir))
    assert len(results) == 3
    assert all(r["success"] for r in results)
    for i in range(3):
        out_file = out_dir / f"cfg{i}.yaml"
        assert out_file.exists()
        assert yaml.safe_load(out_file.read_text()) == {"id": i}

def test_detect_unknown():
    assert detect_format("some random text") == "unknown"

def test_unicode():
    r = convert('{"caf\u00e9": "\u2615", "\u65e5\u672c\u8a9e": "\u30c6\u30b9\u30c8"}', "yaml")
    assert r["success"]
    assert "caf\u00e9" in r["output"]
    assert "\u2615" in r["output"]
    assert "\u65e5\u672c\u8a9e" in r["output"]


def test_unicode_json_output_no_escape():
    """JSON output must preserve Unicode characters, not emit \\uXXXX escape sequences.

    Addresses yq GitHub issue: users converting YAML with CJK/Arabic/accented
    characters to JSON got unreadable \\uXXXX sequences instead of real chars.
    """
    r = convert('name: \u7530\u4e2d\u592a\u90ce\ncity: \u6771\u4eac', "json")
    assert r["success"]
    assert "\u7530\u4e2d\u592a\u90ce" in r["output"], "CJK characters must not be \\uXXXX-escaped in JSON output"
    assert "\u6771\u4eac" in r["output"]
    assert "\\u" not in r["output"]


def test_get_unicode_dict_no_escape(tmp_path, capsys):
    """--get on a dict/list value with Unicode must output real chars, not escape sequences."""
    import io
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("team:\n  lead: \u7530\u4e2d\u592a\u90ce\n  city: \u6771\u4eac\n", encoding="utf-8")
    rc = main([str(f), "--get", "team"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "\u7530\u4e2d\u592a\u90ce" in captured.out, "Unicode must be preserved in --get JSON output"
    assert "\\u" not in captured.out

def test_deeply_nested():
    d = {"a": {"b": {"c": {"d": {"e": [1, 2, 3]}}}}}
    r = convert(json.dumps(d), "yaml")
    assert r["success"]

def test_large_array():
    d = list(range(1000))
    r = convert(json.dumps(d), "yaml")
    assert r["success"]
    list_from_yaml = yaml.safe_load(r["output"])
    assert list_from_yaml == d

# -- Feature: Type inference for INI values --
def test_ini_type_inference_int():
    """INI value '42' should parse as int, not string."""
    r = convert("[section]\ncount=42\n", "json")
    assert r["success"]
    parsed = json.loads(r["output"])
    assert parsed["section"]["count"] == 42

def test_ini_type_inference_float():
    """INI value '3.14' should parse as float, not string."""
    r = convert("[section]\npi=3.14\n", "json")
    assert r["success"]
    parsed = json.loads(r["output"])
    assert parsed["section"]["pi"] == 3.14

def test_ini_type_inference_bool_true():
    """INI value 'true' should parse as bool True."""
    r = convert("[section]\nenabled=true\n", "json")
    assert r["success"]
    parsed = json.loads(r["output"])
    assert parsed["section"]["enabled"] is True

def test_ini_type_inference_bool_false():
    """INI value 'false' should parse as bool False."""
    r = convert("[section]\nenabled=false\n", "json")
    assert r["success"]
    parsed = json.loads(r["output"])
    assert parsed["section"]["enabled"] is False

def test_ini_type_inference_bool_variants():
    """INI values yes/no/on/off should parse as bool."""
    for val, expected in [("yes", True), ("no", False), ("on", True), ("off", False)]:
        r = convert(f"[section]\nflag={val}\n", "json")
        assert r["success"]
        parsed = json.loads(r["output"])
        assert parsed["section"]["flag"] is expected, f"{val} -> {expected}"

def test_ini_type_inference_string_preserved():
    """INI plain string value should remain string, not inferred."""
    r = convert("[section]\nname=hello_world\n", "json")
    assert r["success"]
    parsed = json.loads(r["output"])
    assert parsed["section"]["name"] == "hello_world"

def test_ini_type_inference_mixed_types():
    """INI section with mixed types should infer each correctly."""
    r = convert("[config]\nname=app\nport=8080\ndebug=false\nrate=0.75\n", "json")
    assert r["success"]
    parsed = json.loads(r["output"])
    assert parsed["config"]["name"] == "app"
    assert parsed["config"]["port"] == 8080
    assert parsed["config"]["debug"] is False
    assert parsed["config"]["rate"] == 0.75

def test_ini_type_inference_off():
    """With infer_types=False, all values stay as strings."""
    r = convert("[section]\ncount=42\nflag=true\n", "json", from_fmt="ini", infer_types=False)
    assert r["success"]
    parsed = json.loads(r["output"])
    assert parsed["section"]["count"] == "42"
    assert parsed["section"]["flag"] == "true"

def test_ini_type_inference_direct():
    """Direct parse_text call with infer_types option."""
    from core.configforge import parse_text
    result = parse_text("[section]\nval=42\n", fmt="ini", infer_types=True)
    assert result["data"]["section"]["val"] == 42

# -- Feature: Batch glob mode --
def test_batch_convert_empty_glob(tmp_path):
    """Empty glob returns empty list with no errors."""
    results = batch_convert(str(tmp_path / "nonexistent_*.json"), "yaml")
    assert results == []


def test_batch_empty_glob_cli_exits_1(tmp_path, capsys):
    """CLI cf --batch with an empty glob returns exit code 1."""
    from core.cli import main as cli_main
    rc = cli_main(["cf", "--batch", "--to", "yaml", str(tmp_path / "nonexistent_*.json")])
    assert rc == 1


def test_batch_stream_empty_glob_cli_exits_1(tmp_path, capsys):
    """CLI cf --batch --stream with an empty glob returns exit code 1."""
    from core.cli import main as cli_main
    rc = cli_main(["cf", "--batch", "--stream", "--to", "yaml", str(tmp_path / "nonexistent_*.json")])
    assert rc == 1


def test_batch_convert_progress(tmp_path, capsys):
    """Batch convert with show_progress prints progress lines."""
    for i in range(2):
        (tmp_path / f"cfg{i}.json").write_text(f'{{"id": {i}}}')
    results = batch_convert(str(tmp_path / "*.json"), "yaml", str(tmp_path / "yaml_out"), show_progress=True)
    captured = capsys.readouterr()
    assert "[batch]" in captured.err
    assert "[1/2]" in captured.err
    assert "[2/2]" in captured.err
    assert len(results) == 2
    assert all(r["success"] for r in results)

def test_batch_convert_glob_yaml(tmp_path):
    """Glob pattern for YAML files with progress output."""
    for i in range(3):
        (tmp_path / f"cfg{i}.yaml").write_text(f"id: {i}\nname: item{i}\n")
    out_dir = tmp_path / "yaml_out"
    results = batch_convert(str(tmp_path / "*.yaml"), "json", str(out_dir))
    assert len(results) == 3
    assert all(r["success"] for r in results)
    for i in range(3):
        out_file = out_dir / f"cfg{i}.json"
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert data["id"] == i
        assert data["name"] == f"item{i}"

def test_batch_convert_no_progress(tmp_path):
    """With show_progress=False, no output is printed."""
    for i in range(2):
        (tmp_path / f"cfg{i}.json").write_text(f'{{"id": {i}}}')
    results = batch_convert(str(tmp_path / "*.json"), "yaml", show_progress=False)
    assert len(results) == 2

def test_batch_convert_partial_failure(tmp_path):
    """Batch convert handles mixed success/failure gracefully."""
    (tmp_path / "good.json").write_text('{"ok": true}')
    (tmp_path / "bad.json").write_text("not valid json at all {{{")
    results = batch_convert(str(tmp_path / "*.json"), "yaml", show_progress=False)
    assert len(results) == 2
    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]
    assert len(successes) == 1
    assert len(failures) == 1


# -- batch_convert_stream tests --


def test_batch_convert_stream_basic(tmp_path):
    """Streaming batch converts matching files correctly."""
    for i in range(3):
        (tmp_path / f"s{i}.json").write_text(f'{{"id": {i}}}')
    results = list(batch_convert_stream(str(tmp_path / "*.json"), "yaml", show_progress=False))
    items = [r for r in results if "_summary" not in r]
    assert len(items) == 3
    assert all(r["success"] for r in items)
    last = results[-1]
    assert "_summary" in last
    assert last["_summary"]["total"] == 3
    assert last["_summary"]["success"] == 3


def test_batch_convert_stream_empty_glob(tmp_path):
    """Streaming batch with no matching files yields empty summary."""
    results = list(batch_convert_stream(str(tmp_path / "nofiles*.json"), "yaml", show_progress=False))
    assert len(results) == 1
    r = results[0]
    assert r.get("_empty") is True
    assert r["_summary"]["total"] == 0


def test_batch_convert_stream_output_dir(tmp_path):
    """Streaming batch creates output files."""
    (tmp_path / "a.json").write_text('{"x": 1}')
    (tmp_path / "b.json").write_text('{"y": 2}')
    out_dir = tmp_path / "stream_out"
    results = list(batch_convert_stream(str(tmp_path / "*.json"), "yaml", str(out_dir), show_progress=False))
    items = [r for r in results if "_summary" not in r]
    assert len(items) == 2
    assert (out_dir / "a.yaml").exists()
    assert (out_dir / "b.yaml").exists()
    assert yaml.safe_load((out_dir / "a.yaml").read_text()) == {"x": 1}


def test_batch_convert_stream_partial_failure(tmp_path):
    """Streaming batch handles mixed success/failure."""
    (tmp_path / "good.json").write_text('{"ok": true}')
    (tmp_path / "bad.json").write_text("{{{invalid json}}}")
    results = list(batch_convert_stream(str(tmp_path / "*.json"), "yaml", show_progress=False))
    items = [r for r in results if "_summary" not in r]
    assert len(items) == 2
    successes = [r for r in items if r["success"]]
    failures = [r for r in items if not r["success"]]
    assert len(successes) == 1
    assert len(failures) == 1
    last = results[-1]
    assert last["_summary"]["total"] == 2
    assert last["_summary"]["success"] == 1
    assert last["_summary"]["errors"] == 1

def test_yaml_comment_preservation_json_roundtrip():
    yaml_with_comments = """
# This is a block comment
key: value  # inline comment
another:
  # comment inside nested
  nested_key: nested_value  # another inline
"""
    # Convert YAML to JSON
    r1 = convert(yaml_with_comments, "json")
    assert r1["success"], "Conversion failed: " + str(r1.get("error"))
    json_output = r1["output"]
    # The JSON should contain the data and metadata keys
    assert "__cf_comments__" in json_output
    assert "__cf_blanks__" in json_output
    # The data should be present as top-level keys
    import json
    data = json.loads(json_output)
    assert "key" in data
    assert "another" in data
    assert data["key"] == "value"
    assert data["another"]["nested_key"] == "nested_value"
    # Convert JSON back to YAML
    r2 = convert(json_output, "yaml")
    assert r2["success"], "Conversion back failed: " + str(r2.get("error"))
    yaml_output = r2["output"]
    # Check that the comments appear in the YAML output
    assert "# This is a block comment" in yaml_output
    assert "key: value  # inline comment" in yaml_output
    assert "another:" in yaml_output
    assert "  # comment inside nested" in yaml_output
    assert "  nested_key: nested_value  # another inline" in yaml_output


def test_env_null_values_serialize_as_empty():
    """YAML null values must become empty strings in .env output, not 'None'."""
    yaml_in = "DB_HOST: localhost\nDB_PORT: null\nEMPTY:\n"
    r = convert(yaml_in, "env")
    assert r["success"]
    lines = dict(line.split("=", 1) for line in r["output"].splitlines())
    assert lines["DB_HOST"] == "localhost"
    assert lines["DB_PORT"] == ""
    assert lines["EMPTY"] == ""


def test_env_bool_values_serialize_lowercase():
    """YAML booleans must become lowercase true/false in .env output, not True/False."""
    yaml_in = "DEBUG: true\nVERBOSE: false\n"
    r = convert(yaml_in, "env")
    assert r["success"]
    lines = dict(line.split("=", 1) for line in r["output"].splitlines())
    assert lines["DEBUG"] == "true"
    assert lines["VERBOSE"] == "false"


def test_env_inline_comment_stripped():
    """Unquoted .env values must have inline comments stripped (# preceded by whitespace)."""
    env_in = "FOO=bar # this is a comment\nBAZ=qux#not_a_comment\n"
    r = convert(env_in, "json")
    assert r["success"]
    import json as _json
    data = _json.loads(r["output"])
    assert data["FOO"] == "bar", f"expected 'bar', got {data['FOO']!r}"
    assert data["BAZ"] == "qux#not_a_comment", f"expected 'qux#not_a_comment', got {data['BAZ']!r}"


def test_env_double_quoted_escape_sequences():
    """Double-quoted .env values must process \\n, \\t, \\\\ escape sequences."""
    env_in = 'MSG="hello\\nworld"\tTAB="a\\tb"\tESC="back\\\\slash"\n'
    # use newline separated
    env_in = 'MSG="hello\\nworld"\nTAB="a\\tb"\nESC="back\\\\slash"\n'
    r = convert(env_in, "json")
    assert r["success"]
    import json as _json
    data = _json.loads(r["output"])
    assert data["MSG"] == "hello\nworld", f"expected 'hello\\nworld', got {data['MSG']!r}"
    assert data["TAB"] == "a\tb", f"expected 'a\\tb', got {data['TAB']!r}"
    assert data["ESC"] == "back\\slash", f"expected 'back\\\\slash', got {data['ESC']!r}"


def test_env_single_quoted_literal():
    """Single-quoted .env values must be treated literally (no escape processing)."""
    env_in = "LITERAL='hello\\nworld'\n"
    r = convert(env_in, "json")
    assert r["success"]
    import json as _json
    data = _json.loads(r["output"])
    assert data["LITERAL"] == "hello\\nworld", f"expected literal backslash-n, got {data['LITERAL']!r}"


def test_env_newline_roundtrip():
    """Values with real newlines must survive an env->env roundtrip via escape sequences."""
    import json as _json
    original = {"KEY": "line1\nline2"}
    env_text = convert(_json.dumps(original), "env")["output"]
    assert "\\n" in env_text, "serializer must escape newlines in .env output"
    back = convert(env_text, "json")
    assert back["success"]
    assert _json.loads(back["output"])["KEY"] == "line1\nline2"


def test_env_multiline_double_quoted_value():
    """Double-quoted .env values spanning real newlines are parsed as one value (PEM cert style)."""
    import json as _json
    text = 'KEY1=val1\nCERT="-----BEGIN CERT-----\nline2\nline3\n-----END CERT-----"\nKEY2=val2\n'
    r = convert(text, "json", "env")
    assert r["success"]
    data = _json.loads(r["output"])
    assert data["KEY1"] == "val1"
    assert data["KEY2"] == "val2"
    assert data["CERT"] == "-----BEGIN CERT-----\nline2\nline3\n-----END CERT-----"


def test_env_multiline_keys_after_are_parsed():
    """Keys following a multiline double-quoted value are correctly parsed."""
    import json as _json
    text = 'A=before\nB="multi\nline"\nC=after\n'
    r = convert(text, "json", "env")
    assert r["success"]
    data = _json.loads(r["output"])
    assert data["A"] == "before"
    assert data["B"] == "multi\nline"
    assert data["C"] == "after"


def test_get_by_path_scalar(tmp_path, capsys):
    """--get with dot-notation extracts a scalar without needing --to.

    Addresses the HN complaint that jq/yq query syntax is too complex for
    simple value extraction — 'server.port' beats '.server | .port // empty'."""
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("server:\n  host: localhost\n  port: 9200\n")
    rc = main([str(f), "--get", "server.port"])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.strip() == "9200"


def test_get_by_path_nested_dict(tmp_path, capsys):
    """--get returns JSON for a nested dict value."""
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("database:\n  host: db.example.com\n  port: 5432\n")
    rc = main([str(f), "--get", "database"])
    captured = capsys.readouterr()
    assert rc == 0
    result = json.loads(captured.out)
    assert result["host"] == "db.example.com"
    assert result["port"] == 5432


def test_get_by_path_list_index(tmp_path, capsys):
    """--get supports integer list index like items.1.name."""
    from core.configforge import main
    f = tmp_path / "data.json"
    f.write_text('{"items": [{"name": "alpha"}, {"name": "beta"}]}')
    rc = main([str(f), "--get", "items.1.name"])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.strip() == "beta"


def test_get_by_path_missing_key(tmp_path, capsys):
    """--get returns exit code 1 for a missing key."""
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("server:\n  port: 80\n")
    rc = main([str(f), "--get", "server.host"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "host" in captured.err


def test_get_leading_dot_yq_style(tmp_path, capsys):
    """--get accepts yq-style leading dot: .server.port works like server.port.

    HN complaint: users coming from yq/jq use .key.subkey syntax and get
    confusing errors because devbench uses key.subkey (no leading dot)."""
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("server:\n  host: localhost\n  port: 9200\n")
    rc = main([str(f), "--get", ".server.port"])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.strip() == "9200"


def test_get_leading_dot_bracket_notation(tmp_path, capsys):
    """yq-style leading dot works with bracket list index: .items[0].name."""
    from core.configforge import main
    f = tmp_path / "data.json"
    f.write_text('{"items": [{"name": "alpha"}, {"name": "beta"}]}')
    rc = main([str(f), "--get", ".items[0].name"])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.strip() == "alpha"


def test_get_dot_only_returns_root(tmp_path, capsys):
    """--get . returns the full document (yq root-document syntax)."""
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("x: 1\ny: 2\n")
    rc = main([str(f), "--get", "."])
    captured = capsys.readouterr()
    assert rc == 0
    result = json.loads(captured.out)
    assert result["x"] == 1
    assert result["y"] == 2


def test_set_leading_dot_yq_style(tmp_path, capsys):
    """--set accepts yq-style leading dot: .server.port works like server.port."""
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("server:\n  port: 8080\n")
    rc = main([str(f), "--set", ".server.port", "9200"])
    captured = capsys.readouterr()
    assert rc == 0
    import yaml
    result = yaml.safe_load(captured.out)
    assert result["server"]["port"] == 9200


# -- --set tests --


def test_set_scalar_yaml(tmp_path, capsys):
    """--set updates a scalar and re-emits valid YAML."""
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("server:\n  host: localhost\n  port: 8080\n")
    rc = main([str(f), "--set", "server.port", "9200"])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    assert result["server"]["port"] == 9200


def test_set_scalar_json(tmp_path, capsys):
    """--set updates a scalar in JSON and outputs valid JSON."""
    from core.configforge import main
    f = tmp_path / "config.json"
    f.write_text('{"database": {"host": "localhost", "port": 5432}}')
    rc = main([str(f), "--set", "database.host", "db.prod.example.com"])
    captured = capsys.readouterr()
    assert rc == 0
    result = json.loads(captured.out)
    assert result["database"]["host"] == "db.prod.example.com"
    assert result["database"]["port"] == 5432


def test_set_boolean_coercion(tmp_path, capsys):
    """--set parses JSON booleans and numbers, not just strings."""
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("debug: false\n")
    rc = main([str(f), "--set", "debug", "true"])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    assert result["debug"] is True


def test_set_python_true_is_boolean(tmp_path, capsys):
    """--set 'True' (Python-style) yields a boolean, not the string 'True'."""
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("enabled: false\n")
    rc = main([str(f), "--set", "enabled", "True"])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    assert result["enabled"] is True


def test_set_multiline_value_uses_block_scalar(tmp_path, capsys):
    """--set with a multiline string auto-uses block scalar style (yq#2025).

    Regression: without the fix PyYAML emits ugly single-quoted multi-line
    literals like ``key: 'line1\\n  line2'`` instead of the clean block form.
    """
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("key: old\nother: foo\n")
    rc = main([str(f), "--set", "key", "line1\nline2"])
    captured = capsys.readouterr()
    assert rc == 0
    # Output must use block scalar, not quoted single-line
    assert "|-" in captured.out or "|" in captured.out
    # Value must round-trip correctly
    result = yaml.safe_load(captured.out)
    assert result["key"] == "line1\nline2"
    assert result["other"] == "foo"


def test_set_python_false_is_boolean(tmp_path, capsys):
    """--set 'False' (Python-style) yields a boolean, not the string 'False'."""
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("enabled: true\n")
    rc = main([str(f), "--set", "enabled", "False"])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    assert result["enabled"] is False


def test_set_python_none_is_null(tmp_path, capsys):
    """--set 'None' (Python-style) yields null, not the string 'None'."""
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("value: hello\n")
    rc = main([str(f), "--set", "value", "None"])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    assert result["value"] is None


def test_set_creates_intermediate_key(tmp_path, capsys):
    """--set creates intermediate dict keys when they don't exist."""
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("app: {}\n")
    rc = main([str(f), "--set", "app.server.port", "8080"])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    assert result["app"]["server"]["port"] == 8080


def test_set_list_element(tmp_path, capsys):
    """--set can update an element inside a list by index."""
    from core.configforge import main
    f = tmp_path / "data.json"
    f.write_text('{"hosts": ["alpha", "beta", "gamma"]}')
    rc = main([str(f), "--set", "hosts.1", "bravo"])
    captured = capsys.readouterr()
    assert rc == 0
    result = json.loads(captured.out)
    assert result["hosts"] == ["alpha", "bravo", "gamma"]


def test_set_in_place(tmp_path):
    """--in-place writes the updated config back to the source file."""
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("version: 1\n")
    rc = main([str(f), "--set", "version", "2", "--in-place"])
    assert rc == 0
    result = yaml.safe_load(f.read_text())
    assert result["version"] == 2


def test_set_invalid_list_index(tmp_path, capsys):
    """--set returns exit code 1 for an out-of-range list index."""
    from core.configforge import main
    f = tmp_path / "data.json"
    f.write_text('{"items": [1, 2, 3]}')
    rc = main([str(f), "--set", "items.99", "42"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "99" in captured.err or "index" in captured.err.lower()


def test_delete_key_yaml(tmp_path, capsys):
    """--delete removes a key from YAML output."""
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("host: localhost\nport: 8080\ndebug: true\n")
    rc = main([str(f), "--delete", "debug"])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    assert "debug" not in result
    assert result["host"] == "localhost"
    assert result["port"] == 8080


def test_delete_nested_key(tmp_path, capsys):
    """--delete removes a nested key by dot-notation path."""
    from core.configforge import main
    f = tmp_path / "config.json"
    f.write_text('{"server": {"host": "localhost", "port": 9200, "debug": false}}')
    rc = main([str(f), "--delete", "server.debug"])
    captured = capsys.readouterr()
    assert rc == 0
    result = json.loads(captured.out)
    assert "debug" not in result["server"]
    assert result["server"]["host"] == "localhost"


def test_delete_list_element(tmp_path, capsys):
    """--delete removes an element from a list by index."""
    from core.configforge import main
    f = tmp_path / "data.json"
    f.write_text('{"hosts": ["alpha", "beta", "gamma"]}')
    rc = main([str(f), "--delete", "hosts.1"])
    captured = capsys.readouterr()
    assert rc == 0
    result = json.loads(captured.out)
    assert result["hosts"] == ["alpha", "gamma"]


def test_delete_missing_key(tmp_path, capsys):
    """--delete returns exit code 1 for a missing key."""
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("host: localhost\n")
    rc = main([str(f), "--delete", "nonexistent"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "nonexistent" in captured.err


def test_delete_in_place(tmp_path):
    """--delete with --in-place writes back to source file."""
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("host: localhost\nport: 8080\n")
    rc = main([str(f), "--delete", "port", "--in-place"])
    assert rc == 0
    result = yaml.safe_load(f.read_text())
    assert "port" not in result
    assert result["host"] == "localhost"


def test_set_check_identical(tmp_path, capsys):
    """--check exits 0 when file already has the target value."""
    from core.configforge import main
    f = tmp_path / "cfg.yaml"
    f.write_text("version: 1\n")
    rc = main([str(f), "--set", "version", "1", "--in-place", "--check"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "identical" in captured.out
    assert f.read_text() == "version: 1\n"  # unchanged

def test_set_check_would_change(tmp_path, capsys):
    """--check exits 1 when the target value differs from current."""
    from core.configforge import main
    f = tmp_path / "cfg.yaml"
    f.write_text("version: 1\n")
    rc = main([str(f), "--set", "version", "2", "--in-place", "--check"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "would change" in captured.out
    assert f.read_text() == "version: 1\n"  # unchanged

def test_set_dry_run_shows_diff(tmp_path, capsys):
    """--dry-run prints a diff and exits 1 when content would change."""
    from core.configforge import main
    f = tmp_path / "cfg.yaml"
    f.write_text("version: 1\n")
    rc = main([str(f), "--set", "version", "2", "--in-place", "--dry-run"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "-version: 1" in captured.out
    assert "+version: 2" in captured.out
    assert f.read_text() == "version: 1\n"  # unchanged

def test_set_dry_run_identical(tmp_path, capsys):
    """--dry-run exits 0 when no changes needed."""
    from core.configforge import main
    f = tmp_path / "cfg.yaml"
    f.write_text("version: 1\n")
    rc = main([str(f), "--set", "version", "1", "--in-place", "--dry-run"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "identical" in captured.out
    assert f.read_text() == "version: 1\n"  # unchanged

def test_delete_check_identical(tmp_path, capsys):
    """--delete --check exits 0 when key already absent."""
    from core.configforge import main
    f = tmp_path / "cfg.yaml"
    f.write_text("host: localhost\n")
    rc = main([str(f), "--delete", "port", "--in-place", "--check"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "identical" in captured.out

def test_merge_check_would_change(tmp_path, capsys):
    """--merge --check exits 1 when overlay would change the base."""
    from core.configforge import main
    base = tmp_path / "base.yaml"
    base.write_text("host: localhost\nport: 8080\n")
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text("port: 9200\n")
    rc = main([str(base), "--merge", str(overlay), "--in-place", "--check"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "would change" in captured.out
    assert base.read_text() == "host: localhost\nport: 8080\n"  # unchanged

def test_check_without_in_place_errors(tmp_path, capsys):
    """--check without --in-place should fail with a clear error message."""
    from core.configforge import main
    f = tmp_path / "cfg.yaml"
    f.write_text("version: 1\n")
    rc = main([str(f), "--set", "version", "2", "--check"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "--check" in captured.err and "--in-place" in captured.err


def test_dry_run_without_in_place_errors(tmp_path, capsys):
    """--dry-run without --in-place should fail with a clear error message."""
    from core.configforge import main
    f = tmp_path / "cfg.yaml"
    f.write_text("version: 1\n")
    rc = main([str(f), "--set", "version", "2", "--dry-run"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "--dry-run" in captured.err and "--in-place" in captured.err


def test_ini_null_values_serialize_as_empty():
    """YAML null values must become empty strings in INI output, not 'None'."""
    yaml_in = "host: localhost\nport: null\n"
    r = convert(yaml_in, "ini")
    assert r["success"]
    output = r["output"]
    assert "None" not in output
    assert "port = \n" in output or "port =\n" in output


def test_ini_bool_values_serialize_lowercase():
    """YAML booleans must become lowercase true/false in INI output."""
    yaml_in = "debug: true\nverbose: false\n"
    r = convert(yaml_in, "ini")
    assert r["success"]
    output = r["output"]
    assert "True" not in output
    assert "False" not in output
    assert "debug = true" in output
    assert "verbose = false" in output


def test_yaml_alias_error_actionable_message():
    """YAML with an unquoted *.ext value gives an actionable error, not a raw scanner dump."""
    yaml_in = "patterns:\n  - *.html\n  - *.css\n"
    r = convert(yaml_in, "json")
    assert not r["success"]
    err = r["error"]
    # Must mention quoting as the fix — not just a raw YAML scanner traceback
    assert "Fix:" in err or "quote" in err.lower(), f"Expected actionable fix hint, got: {err}"
    assert "*.html" not in err or "quote" in err.lower()  # points user to the problem


def test_yaml_tab_error_actionable_message():
    """YAML with tab indentation gives a clear 'use spaces' message."""
    yaml_in = "parent:\n\tchild: value\n"
    r = convert(yaml_in, "json", from_fmt="yaml")
    assert not r["success"]
    err = r["error"]
    assert "tab" in err.lower() or "spaces" in err.lower(), f"Expected tab hint, got: {err}"


def test_yaml_parse_error_includes_location():
    """A YAML parse error message should include a line number."""
    yaml_in = "key: valid\nbad: [\nincomplete\n"
    r = convert(yaml_in, "json")
    assert not r["success"]
    # Should contain either 'line' or a colon-separated location
    assert "line" in r["error"].lower() or ":" in r["error"]


def test_yaml_indentation_error_multiline_context():
    """YAML indentation error shows a multi-line context block with line numbers."""
    # A key without ':' causes "could not find expected ':'" ScannerError
    yaml_in = "key: val\nbad_continuation\n  sub: x\n"
    r = convert(yaml_in, "json", from_fmt="yaml")
    assert not r["success"]
    err = r["error"]
    # Error message must show numbered lines (e.g. "   2:") from _yaml_context_lines
    import re
    assert re.search(r"\d+:", err), f"Expected numbered context lines, got:\n{err}"
    # Must give an actionable Fix hint
    assert "Fix:" in err, f"Expected Fix hint in:\n{err}"


def test_yaml_indentation_error_points_to_source():
    """For 'could not find expected' errors, message uses context_mark (actual key), not problem_mark."""
    # "bad_continuation" on line 2 is the problematic key; parser fails at line 3
    yaml_in = "key: val\nbad_continuation\n  sub: x\n"
    r = convert(yaml_in, "json", from_fmt="yaml")
    assert not r["success"]
    err = r["error"]
    # Must mention indentation as the cause (uses context_mark pointing to line 2)
    assert "indent" in err.lower(), f"Expected 'indent' in error, got:\n{err}"
    # context_mark is line 2 — the error should mention line 2
    assert "line 2" in err, f"Expected 'line 2' reference, got:\n{err}"


def test_yaml_mapping_values_not_allowed_indentation():
    """'mapping values are not allowed here' gives an indentation error, not an anchor hint."""
    # A key indented under a scalar value
    yaml_in = "key: value\n  bad_indent: wrong\nnext: ok\n"
    r = convert(yaml_in, "json", from_fmt="yaml")
    assert not r["success"]
    err = r["error"]
    assert "indent" in err.lower(), f"Expected indentation message, got:\n{err}"
    assert "Fix:" in err, f"Expected Fix hint in:\n{err}"
    # Must NOT blame * or & special characters — this is not an anchor error
    assert "special character" not in err, f"Wrong error type, got:\n{err}"


def test_yaml_context_lines_helper():
    """_yaml_context_lines returns numbered lines with an arrow on the error line."""
    from core.configforge import _yaml_context_lines
    lines = ["alpha", "beta", "gamma", "delta", "epsilon"]
    block = _yaml_context_lines(lines, lineno=3, col=None, radius=1)
    assert "   2: beta" in block
    assert "→    3: gamma" in block
    assert "   4: delta" in block
    # Line 1 and 5 should be outside radius=1 window
    assert "alpha" not in block
    assert "epsilon" not in block


def test_yaml_find_indent_source_detects_deeper_line():
    """_yaml_find_indent_source returns the first line more indented than the error line."""
    from core.configforge import _yaml_find_indent_source
    lines = [
        "server:",           # line 1, indent 0
        "  host: x",        # line 2, indent 2
        "    port: 80",     # line 3, indent 4  ← too deep
        "  timeout: 30",    # line 4, indent 2  ← parser fails here
    ]
    source = _yaml_find_indent_source(lines, error_lineno=4)
    assert source == 3, f"Expected line 3 as source, got {source}"


def test_toml_no_empty_intermediate_headers():
    """TOML output must not emit empty [section] headers for intermediate-only tables.

    Addresses the yq GitHub issue #2710 pattern: deeply nested TOML like
    pyproject.toml produces clean output without noise like '[tool]' or
    '[tool.poetry.group]' when those levels carry no direct scalar values.
    """
    from core.configforge import serialize
    data = {
        "tool": {
            "poetry": {
                "name": "mypackage",
                "version": "1.0.0",
                "dependencies": {"python": "^3.10"},
                "group": {
                    "dev": {
                        "dependencies": {"pytest": "^7.0"}
                    }
                }
            }
        }
    }
    out = serialize(data, "toml")
    # Intermediate-only tables must NOT appear as standalone headers
    assert "[tool]\n" not in out
    assert "[tool.poetry.group]\n" not in out
    assert "[tool.poetry.group.dev]\n" not in out
    # Leaf sections WITH scalars must still have headers
    assert "[tool.poetry]\n" in out
    assert "[tool.poetry.dependencies]\n" in out
    assert "[tool.poetry.group.dev.dependencies]\n" in out
    # Data integrity: output must round-trip cleanly
    assert tomllib.loads(out) == data


def test_toml_empty_tables_preserved():
    """Genuinely empty TOML tables must survive serialization (yq#2459).

    yq silently drops empty tables mid-document. We must preserve [cache]-style
    empty sections so TOML->JSON->TOML and YAML->TOML roundtrips are lossless.
    """
    from core.configforge import convert, serialize
    # Serializer must emit [cache] even though its dict value is {}
    data = {"server": {"host": "localhost"}, "cache": {}, "db": {"port": 5432}}
    out = serialize(data, "toml")
    assert "[cache]" in out, "empty [cache] table must appear in TOML output"
    assert "host = \"localhost\"" in out
    assert "port = 5432" in out
    # Intermediate-only tables (have sub-tables) must still be suppressed
    nested = {"tool": {"poetry": {"name": "pkg"}}}
    nested_out = serialize(nested, "toml")
    assert "[tool]\n" not in nested_out, "[tool] with only sub-tables must stay implicit"
    # Full TOML->JSON->TOML roundtrip
    toml_src = "[server]\nhost = \"localhost\"\n\n[cache]\n\n[db]\nport = 5432\n"
    json_r = convert(toml_src, "json", "toml")
    assert json_r["success"]
    assert '"cache": {}' in json_r["output"]
    toml_r = convert(json_r["output"], "toml", "json")
    assert toml_r["success"]
    assert "[cache]" in toml_r["output"]


# -- --merge tests --
# Addresses the r/devops complaint that yq has no ergonomic deep-merge for
# Kubernetes YAML files with nested lists (containers, env vars, volumes).


def test_merge_dict_overlay_yaml(tmp_path, capsys):
    """--merge replaces scalar values from the overlay file (dict deep merge)."""
    from core.configforge import main
    base = tmp_path / "base.yaml"
    base.write_text("server:\n  host: localhost\n  port: 8080\ndebug: false\n")
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text("server:\n  port: 9200\ndebug: true\n")
    rc = main([str(base), "--merge", str(overlay)])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    assert result["server"]["host"] == "localhost"
    assert result["server"]["port"] == 9200
    assert result["debug"] is True


def test_merge_adds_new_keys(tmp_path, capsys):
    """--merge adds keys present in overlay but absent from base."""
    from core.configforge import main
    base = tmp_path / "base.yaml"
    base.write_text("name: myapp\n")
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text("version: '2.0'\nreplicas: 3\n")
    rc = main([str(base), "--merge", str(overlay)])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    assert result["name"] == "myapp"
    assert result["version"] == "2.0"
    assert result["replicas"] == 3


def test_merge_list_replace_default(tmp_path, capsys):
    """--merge with default --list-merge=replace replaces lists entirely."""
    from core.configforge import main
    base = tmp_path / "base.yaml"
    base.write_text("containers:\n  - name: app\n    image: myapp:v1\n")
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text("containers:\n  - name: app\n    image: myapp:v2\n  - name: sidecar\n    image: nginx\n")
    rc = main([str(base), "--merge", str(overlay)])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    assert len(result["containers"]) == 2
    assert result["containers"][0]["image"] == "myapp:v2"
    assert result["containers"][1]["name"] == "sidecar"


def test_merge_list_append(tmp_path, capsys):
    """--merge --list-merge=append appends overlay list to base list.

    The primary r/devops use-case: adding env vars or volumes to a base
    Kubernetes deployment without repeating every existing entry."""
    from core.configforge import main
    base = tmp_path / "base.yaml"
    base.write_text("env:\n  - name: APP_ENV\n    value: production\n")
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text("env:\n  - name: DEBUG\n    value: 'false'\n")
    rc = main([str(base), "--merge", str(overlay), "--list-merge", "append"])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    assert len(result["env"]) == 2
    assert result["env"][0]["name"] == "APP_ENV"
    assert result["env"][1]["name"] == "DEBUG"


def test_merge_list_merge_positional(tmp_path, capsys):
    """--list-merge=merge deep-merges list items by position (partial override).

    The key use case: update only the image of the first container without
    replacing the whole containers list — yq#2390 pain point.
    """
    from core.configforge import main
    base = tmp_path / "base.yaml"
    base.write_text(
        "containers:\n"
        "  - name: app\n"
        "    image: myapp:v1\n"
        "    env:\n"
        "      - name: APP_ENV\n"
        "        value: production\n"
        "  - name: sidecar\n"
        "    image: nginx:1.25\n"
    )
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text(
        "containers:\n"
        "  - image: myapp:v2\n"
    )
    rc = main([str(base), "--merge", str(overlay), "--list-merge", "merge"])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    containers = result["containers"]
    # overlay only updated image of first container — name and env preserved
    assert len(containers) == 2
    assert containers[0]["name"] == "app"
    assert containers[0]["image"] == "myapp:v2"
    assert containers[0]["env"][0]["name"] == "APP_ENV"
    # second container unchanged
    assert containers[1]["name"] == "sidecar"
    assert containers[1]["image"] == "nginx:1.25"


def test_merge_list_merge_extra_items_appended(tmp_path, capsys):
    """--list-merge=merge appends overlay items beyond the base list length."""
    from core.configforge import main
    base = tmp_path / "base.yaml"
    base.write_text("ports:\n  - 80\n  - 443\n")
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text("ports:\n  - 8080\n  - 8443\n  - 9090\n")
    rc = main([str(base), "--merge", str(overlay), "--list-merge", "merge"])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    assert result["ports"] == [8080, 8443, 9090]


def test_merge_list_merge_nested_dicts(tmp_path, capsys):
    """--list-merge=merge recursively merges nested dicts inside list items."""
    from core.configforge import main
    base = tmp_path / "base.json"
    base.write_text(
        '{"services": [{"name": "api", "config": {"timeout": 30, "retries": 3}}, '
        '{"name": "worker", "config": {"timeout": 60}}]}'
    )
    overlay = tmp_path / "overlay.json"
    overlay.write_text(
        '{"services": [{"config": {"timeout": 45}}]}'
    )
    rc = main([str(base), "--merge", str(overlay), "--list-merge", "merge"])
    captured = capsys.readouterr()
    assert rc == 0
    result = json.loads(captured.out)
    services = result["services"]
    # config.timeout updated, retries preserved
    assert services[0]["name"] == "api"
    assert services[0]["config"]["timeout"] == 45
    assert services[0]["config"]["retries"] == 3
    # second service unchanged
    assert services[1]["name"] == "worker"
    assert services[1]["config"]["timeout"] == 60


def test_merge_json_files(tmp_path, capsys):
    """--merge works on JSON base and JSON overlay."""
    from core.configforge import main
    base = tmp_path / "base.json"
    base.write_text('{"database": {"host": "localhost", "port": 5432}, "debug": false}')
    overlay = tmp_path / "overlay.json"
    overlay.write_text('{"database": {"host": "db.prod.example.com"}, "log_level": "warn"}')
    rc = main([str(base), "--merge", str(overlay)])
    captured = capsys.readouterr()
    assert rc == 0
    result = json.loads(captured.out)
    assert result["database"]["host"] == "db.prod.example.com"
    assert result["database"]["port"] == 5432
    assert result["log_level"] == "warn"
    assert result["debug"] is False


def test_merge_cross_format_yaml_base_json_overlay(tmp_path, capsys):
    """--merge accepts overlay in a different format from the base."""
    from core.configforge import main
    base = tmp_path / "base.yaml"
    base.write_text("server:\n  host: localhost\n  port: 8080\n")
    overlay = tmp_path / "overlay.json"
    overlay.write_text('{"server": {"port": 443}, "tls": true}')
    rc = main([str(base), "--merge", str(overlay)])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    assert result["server"]["host"] == "localhost"
    assert result["server"]["port"] == 443
    assert result["tls"] is True


def test_merge_in_place(tmp_path):
    """--merge --in-place overwrites the base file with the merged result."""
    from core.configforge import main
    base = tmp_path / "config.yaml"
    base.write_text("version: 1\nfeatures:\n  - alpha\n")
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text("version: 2\n")
    rc = main([str(base), "--merge", str(overlay), "--in-place"])
    assert rc == 0
    result = yaml.safe_load(base.read_text())
    assert result["version"] == 2
    assert result["features"] == ["alpha"]


def test_merge_deep_nested_dict(tmp_path, capsys):
    """--merge does recursive deep merge on arbitrarily nested dicts."""
    from core.configforge import main
    base = tmp_path / "base.yaml"
    base.write_text("app:\n  db:\n    host: localhost\n    port: 5432\n    name: mydb\n")
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text("app:\n  db:\n    host: db.prod\n    pool_size: 10\n")
    rc = main([str(base), "--merge", str(overlay)])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    assert result["app"]["db"]["host"] == "db.prod"
    assert result["app"]["db"]["port"] == 5432
    assert result["app"]["db"]["name"] == "mydb"
    assert result["app"]["db"]["pool_size"] == 10


def test_merge_new_only_does_not_overwrite_existing(tmp_path, capsys):
    """--merge --merge-new-only only adds missing keys; existing values are preserved.

    Addresses yq issue #2201: users want to populate default config without
    clobbering already-set values. With plain --merge, overlay always wins for
    leaf scalars. With --merge-new-only the base always wins.
    """
    from core.configforge import main
    base = tmp_path / "base.yaml"
    base.write_text("host: localhost\nport: 5432\n")
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text("host: db.prod\nport: 9999\ntimeout: 30\n")
    rc = main([str(base), "--merge", str(overlay), "--merge-new-only"])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    # Existing values must NOT be overwritten
    assert result["host"] == "localhost"
    assert result["port"] == 5432
    # New key from overlay IS added
    assert result["timeout"] == 30


def test_merge_new_only_adds_nested_missing_keys(tmp_path, capsys):
    """--merge-new-only adds nested keys that are absent from base."""
    from core.configforge import main
    base = tmp_path / "base.yaml"
    base.write_text("app:\n  host: localhost\n  port: 8080\n")
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text("app:\n  host: prod.example.com\n  debug: false\nlogging:\n  level: info\n")
    rc = main([str(base), "--merge", str(overlay), "--merge-new-only"])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    # Existing nested value preserved
    assert result["app"]["host"] == "localhost"
    assert result["app"]["port"] == 8080
    # New nested key added
    assert result["app"]["debug"] is False
    # Entirely new top-level section added
    assert result["logging"]["level"] == "info"


def test_merge_new_only_json(tmp_path, capsys):
    """--merge-new-only works for JSON files too."""
    from core.configforge import main
    base = tmp_path / "base.json"
    base.write_text('{"name": "myapp", "version": "1.0"}')
    overlay = tmp_path / "overlay.json"
    overlay.write_text('{"name": "overridden", "description": "a tool"}')
    rc = main([str(base), "--merge", str(overlay), "--merge-new-only"])
    captured = capsys.readouterr()
    assert rc == 0
    result = json.loads(captured.out)
    assert result["name"] == "myapp"
    assert result["version"] == "1.0"
    assert result["description"] == "a tool"


def test_merge_at_nested_path(tmp_path, capsys):
    """--merge-at merges overlay into a specific nested path, not the root.

    r/devops complaint: yq can only merge at the top-level — cannot inject
    a chunk of YAML under .spec.template.spec without a complex expression.
    """
    from core.configforge import main
    base = tmp_path / "base.yaml"
    base.write_text(
        "spec:\n"
        "  replicas: 3\n"
        "  template:\n"
        "    spec:\n"
        "      nodeSelector: {}\n"
    )
    overlay = tmp_path / "patch.yaml"
    overlay.write_text("tolerations:\n  - key: gpu\n    effect: NoSchedule\n")
    rc = main([str(base), "--merge", str(overlay), "--merge-at", "spec.template.spec"])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    # Top-level and sibling keys untouched
    assert result["spec"]["replicas"] == 3
    assert result["spec"]["template"]["spec"]["nodeSelector"] == {}
    # Overlay content injected at the target path
    assert result["spec"]["template"]["spec"]["tolerations"] == [
        {"key": "gpu", "effect": "NoSchedule"}
    ]


def test_merge_at_creates_missing_intermediate(tmp_path, capsys):
    """--merge-at creates the target path if it doesn't exist yet."""
    from core.configforge import main
    base = tmp_path / "base.yaml"
    base.write_text("name: myapp\n")
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text("debug: true\nlog_level: info\n")
    rc = main([str(base), "--merge", str(overlay), "--merge-at", "settings"])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    assert result["name"] == "myapp"
    assert result["settings"]["debug"] is True
    assert result["settings"]["log_level"] == "info"


def test_merge_at_with_merge_new_only(tmp_path, capsys):
    """--merge-at and --merge-new-only compose: inject defaults at path."""
    from core.configforge import main
    base = tmp_path / "base.yaml"
    base.write_text("db:\n  host: localhost\n  port: 5432\n")
    overlay = tmp_path / "defaults.yaml"
    overlay.write_text("host: db.prod\nport: 9999\ntimeout: 30\n")
    rc = main([str(base), "--merge", str(overlay), "--merge-at", "db", "--merge-new-only"])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    # Existing values protected
    assert result["db"]["host"] == "localhost"
    assert result["db"]["port"] == 5432
    # New key added
    assert result["db"]["timeout"] == 30


def test_merge_dedupe_lists_removes_duplicates(tmp_path, capsys):
    """--merge-dedupe-lists deduplicates after append, fixes yq issue #2564."""
    from core.configforge import main
    base = tmp_path / "base.yaml"
    base.write_text("tags:\n  - python\n  - yaml\n")
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text("tags:\n  - yaml\n  - toml\n")
    rc = main([str(base), "--merge", str(overlay), "--list-merge", "append", "--merge-dedupe-lists"])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    assert result["tags"] == ["python", "yaml", "toml"]


def test_merge_dedupe_lists_without_flag_allows_duplicates(tmp_path, capsys):
    """Without --merge-dedupe-lists, append produces duplicates (expected default)."""
    from core.configforge import main
    base = tmp_path / "base.yaml"
    base.write_text("tags:\n  - python\n  - yaml\n")
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text("tags:\n  - yaml\n  - toml\n")
    rc = main([str(base), "--merge", str(overlay), "--list-merge", "append"])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    assert result["tags"] == ["python", "yaml", "yaml", "toml"]


def test_merge_dedupe_lists_self_merge(tmp_path, capsys):
    """Merging a file with itself + dedupe produces the original list (yq #2564 scenario)."""
    from core.configforge import main
    f = tmp_path / "data.yaml"
    f.write_text("items:\n  - a\n  - b\n  - c\n")
    rc = main([str(f), "--merge", str(f), "--list-merge", "append", "--merge-dedupe-lists"])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    assert result["items"] == ["a", "b", "c"]


def test_toml_set_pyproject_version(tmp_path, capsys):
    """--set on a pyproject.toml-style file updates the version and preserves structure.

    The yq GitHub issue #2710 showed yq mangling [tool.poetry.dependencies] when
    updating version — ConfigForge must preserve all sections correctly.
    """
    from core.configforge import main
    toml_content = (
        '[tool.poetry]\n'
        'name = "mypackage"\n'
        'version = "1.0.0"\n'
        '\n'
        '[tool.poetry.dependencies]\n'
        'python = "^3.10"\n'
        'requests = "^2.28"\n'
    )
    f = tmp_path / "pyproject.toml"
    f.write_text(toml_content)
    rc = main([str(f), "--set", "tool.poetry.version", "2.0.0"])
    captured = capsys.readouterr()
    assert rc == 0
    parsed = tomllib.loads(captured.out)
    # Version updated
    assert parsed["tool"]["poetry"]["version"] == "2.0.0"
    # Dependencies section preserved — not mangled or dropped
    assert parsed["tool"]["poetry"]["dependencies"]["python"] == "^3.10"
    assert parsed["tool"]["poetry"]["dependencies"]["requests"] == "^2.28"
    # Name unchanged
    assert parsed["tool"]["poetry"]["name"] == "mypackage"


# ── Plist tests (macOS developer use case) ──

PLIST_INFO = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>com.example.MyApp</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>NSAppTransportSecurity</key>
    <dict>
        <key>NSAllowsArbitraryLoads</key>
        <false/>
    </dict>
    <key>UIRequiredDeviceCapabilities</key>
    <array>
        <string>armv7</string>
    </array>
</dict>
</plist>
"""


def test_plist_detect_format():
    """Plist XML is detected as 'plist', not 'xml'."""
    assert detect_format(PLIST_INFO) == "plist"


def test_plist_in_supported_formats():
    assert "plist" in SUPPORTED_FORMATS


def test_plist_parse_basic():
    """Plist parses to expected Python dict with correct types."""
    r = convert(PLIST_INFO, "json")
    assert r["success"]
    data = json.loads(r["output"])
    assert data["CFBundleIdentifier"] == "com.example.MyApp"
    assert data["CFBundleVersion"] == "1.0.0"
    assert data["NSAppTransportSecurity"]["NSAllowsArbitraryLoads"] is False
    assert data["UIRequiredDeviceCapabilities"] == ["armv7"]


def test_plist_to_yaml():
    """Plist converts cleanly to YAML."""
    r = convert(PLIST_INFO, "yaml")
    assert r["success"]
    parsed = yaml.safe_load(r["output"])
    assert parsed["CFBundleIdentifier"] == "com.example.MyApp"
    assert parsed["CFBundleVersion"] == "1.0.0"


def test_plist_round_trip():
    """JSON dict serializes to valid plist XML and back."""
    from core.configforge import serialize, parse_text
    data = {
        "CFBundleIdentifier": "com.example.App",
        "CFBundleVersion": "2.1.0",
        "DebugEnabled": False,
        "MaxConnections": 4,
    }
    plist_out = serialize(data, "plist")
    assert "<?xml" in plist_out
    assert "com.example.App" in plist_out
    assert "<integer>4</integer>" in plist_out
    parsed_back = parse_text(plist_out, "plist")
    assert parsed_back["data"]["CFBundleIdentifier"] == "com.example.App"
    assert parsed_back["data"]["CFBundleVersion"] == "2.1.0"
    assert parsed_back["data"]["DebugEnabled"] is False
    assert parsed_back["data"]["MaxConnections"] == 4


def test_plist_set_bundle_version_in_place(tmp_path, capsys):
    """macOS CI use case: --set CFBundleVersion 2.1.0 Info.plist -i updates version."""
    from core.configforge import main
    f = tmp_path / "Info.plist"
    f.write_text(PLIST_INFO)
    rc = main([str(f), "--set", "CFBundleVersion", "2.1.0", "-i"])
    assert rc == 0
    import plistlib
    updated = plistlib.loads(f.read_bytes())
    assert updated["CFBundleVersion"] == "2.1.0"
    # Other keys must be preserved
    assert updated["CFBundleIdentifier"] == "com.example.MyApp"
    assert updated["NSAppTransportSecurity"]["NSAllowsArbitraryLoads"] is False


def test_plist_convert_file_extension(tmp_path):
    """convert_file auto-detects .plist extension and converts to JSON."""
    from core.configforge import convert_file
    f = tmp_path / "Info.plist"
    f.write_text(PLIST_INFO)
    out = tmp_path / "Info.json"
    result = convert_file(str(f), str(out))
    assert result["success"]
    data = json.loads(out.read_text())
    assert data["CFBundleIdentifier"] == "com.example.MyApp"
    assert data["CFBundleVersion"] == "1.0.0"


# ── Binary plist support ───────────────────────────────────────────────────────

def test_binary_plist_detect_format():
    """Binary plist (bplist00 magic) is detected as 'plist'."""
    import plistlib
    raw = plistlib.dumps({"k": "v"}, fmt=plistlib.FMT_BINARY)
    # detect_format receives text; binary plist starts with printable 'bplist'
    text = raw.decode("latin-1")
    assert detect_format(text) == "plist"


def test_binary_plist_parse():
    """Binary plist bytes are parsed by parse_text when fmt='plist'."""
    import plistlib
    raw = plistlib.dumps({"version": "3.1", "count": 99}, fmt=plistlib.FMT_BINARY)
    result = parse_text(raw, "plist")
    assert result["format"] == "plist"
    assert result["data"]["version"] == "3.1"
    assert result["data"]["count"] == 99


def test_binary_plist_convert_file_to_json(tmp_path):
    """convert_file reads a binary .plist file and converts it to JSON."""
    import plistlib
    data = {"CFBundleVersion": "5.0", "Name": "MyMacApp", "Retina": True}
    raw = plistlib.dumps(data, fmt=plistlib.FMT_BINARY)
    f = tmp_path / "Info.plist"
    f.write_bytes(raw)
    out = tmp_path / "Info.json"
    result = convert_file(str(f), str(out))
    assert result["success"], result.get("error")
    parsed = json.loads(out.read_text())
    assert parsed["CFBundleVersion"] == "5.0"
    assert parsed["Name"] == "MyMacApp"
    assert parsed["Retina"] is True


def test_binary_plist_convert_file_to_yaml(tmp_path):
    """convert_file converts a binary plist to YAML."""
    import plistlib
    data = {"AppName": "DevBench", "BuildNumber": 42}
    raw = plistlib.dumps(data, fmt=plistlib.FMT_BINARY)
    f = tmp_path / "build.plist"
    f.write_bytes(raw)
    result = convert_file(str(f), to_fmt="yaml")
    assert result["success"], result.get("error")
    assert "AppName: DevBench" in result["output"]
    assert "BuildNumber: 42" in result["output"]


# ── jq-style passthrough (stdin, no --to) ──────────────────────────────────────

def test_passthrough_json_stdin(capsys, monkeypatch):
    """Piping JSON with no --to pretty-prints the same JSON (jq '.' equivalent).

    HN complaint: 'yq doesn't accept standard input in the way jq does
    (ie pipe in some json, and output some pretty json)' — configforge fixes
    this by auto-detecting the format and re-serialising with indent=2."""
    import io
    from core.configforge import main
    monkeypatch.setattr("sys.stdin", io.StringIO('{"name":"alice","age":30}'))
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 0
    data = json.loads(captured.out)
    assert data["name"] == "alice"
    assert data["age"] == 30
    assert "  " in captured.out  # pretty-printed


def test_passthrough_yaml_stdin(capsys, monkeypatch):
    """Piping YAML with no --to pretty-prints the same YAML."""
    import io
    from core.configforge import main
    monkeypatch.setattr("sys.stdin", io.StringIO("name: alice\nage: 30\n"))
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 0
    data = yaml.safe_load(captured.out)
    assert data["name"] == "alice"
    assert data["age"] == 30


def test_passthrough_json_file(tmp_path, capsys):
    """Passing a JSON file with no --to pretty-prints it in place."""
    from core.configforge import main
    f = tmp_path / "cfg.json"
    f.write_text('{"x":1,"y":2}')
    rc = main([str(f)])
    captured = capsys.readouterr()
    assert rc == 0
    data = json.loads(captured.out)
    assert data["x"] == 1
    assert data["y"] == 2


def test_passthrough_unknown_format_errors(capsys, monkeypatch):
    """Unrecognised stdin with no --to exits with code 2."""
    import io
    from core.configforge import main
    monkeypatch.setattr("sys.stdin", io.StringIO("@@@@not a config@@@@"))
    rc = main([])
    assert rc == 2
    assert "could not auto-detect" in capsys.readouterr().err


# ── Backslash-escaped dot paths (macOS plist bundle ID fix) ──
# Addresses the complaint that --get com.apple.finder splits on dots and
# traverses incorrectly instead of addressing the flat bundle-ID key.

def test_split_path_plain():
    from core.configforge import _split_path
    assert _split_path("a.b.c") == ["a", "b", "c"]


def test_split_path_escaped_dot():
    from core.configforge import _split_path
    assert _split_path("a\\.b.c") == ["a.b", "c"]


def test_split_path_all_escaped():
    from core.configforge import _split_path
    assert _split_path("com\\.apple\\.finder") == ["com.apple.finder"]


def test_split_path_no_dots():
    from core.configforge import _split_path
    assert _split_path("key") == ["key"]


def test_split_path_double_backslash_before_dot():
    r"""Two backslashes before a dot = literal backslash key + separator dot.

    The path string a\\.b (a, backslash, backslash, dot, b in memory) should
    yield segments ["a\", "b"]: the \\ escape resolves to one literal backslash
    inside the key name, and the following dot is an unescaped separator.
    """
    from core.configforge import _split_path
    path = "a" + "\\\\" + ".b"   # a, \, \, ., b  — two backslashes then a dot
    result = _split_path(path)
    assert result == ["a\\", "b"]
    assert result[0] == "a\\"    # first segment: the literal string  a\


def test_split_path_double_backslash_then_escaped_dot():
    r"""Four backslashes + escaped dot = literal backslash + literal dot in one key.

    The path a\\\\.b (four backslashes then dot) should yield one segment "a\."
    because \\ → one backslash and \. → one literal dot.
    """
    from core.configforge import _split_path
    path = "a" + "\\\\" + "\\."   # a, \, \, \, .  — \\ then \.
    result = _split_path(path)
    assert result == ["a\\."]
    assert len(result) == 1


def test_split_path_bracket_index():
    """Bracket notation items[0].name → ['items', '0', 'name']."""
    from core.configforge import _split_path
    assert _split_path("items[0].name") == ["items", "0", "name"]


def test_split_path_bracket_negative_index():
    """Negative bracket index items[-1] → ['items', '-1']."""
    from core.configforge import _split_path
    assert _split_path("items[-1]") == ["items", "-1"]


def test_split_path_chained_brackets():
    """Chained brackets a[0][1].b → ['a', '0', '1', 'b']."""
    from core.configforge import _split_path
    assert _split_path("a[0][1].b") == ["a", "0", "1", "b"]


def test_split_path_bracket_only():
    """Bracket-only path [0].name → ['0', 'name'] (list root)."""
    from core.configforge import _split_path
    assert _split_path("[0].name") == ["0", "name"]


def test_get_by_path_bracket_notation():
    """_get_by_path supports bracket notation for array access."""
    from core.configforge import _get_by_path
    data = {"items": [{"name": "foo"}, {"name": "bar"}]}
    assert _get_by_path(data, "items[0].name") == "foo"
    assert _get_by_path(data, "items[1].name") == "bar"
    assert _get_by_path(data, "items[-1].name") == "bar"


def test_get_by_path_bracket_cli(tmp_path, capsys):
    """CLI --get bracket notation works end-to-end (yq-style path)."""
    import json
    from core.configforge import main
    f = tmp_path / "data.json"
    f.write_text(json.dumps({"pods": [{"name": "alpha"}, {"name": "beta"}]}))
    rc = main([str(f), "--get", "pods[0].name"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "alpha"


def test_set_by_path_bracket_notation():
    """_set_by_path supports bracket notation for array mutation."""
    from core.configforge import _set_by_path
    data = {"items": [{"v": 1}, {"v": 2}]}
    _set_by_path(data, "items[0].v", 99)
    assert data["items"][0]["v"] == 99


def test_delete_by_path_bracket_notation():
    """_delete_by_path supports bracket notation to remove list elements."""
    from core.configforge import _delete_by_path
    data = {"items": [1, 2, 3]}
    _delete_by_path(data, "items[1]")
    assert data["items"] == [1, 3]


def test_get_by_path_dotted_key():
    """--get with escaped dot retrieves a flat key containing a literal dot.

    Fixes the macOS plist complaint: bundle IDs like com.apple.finder are
    flat keys, not nested paths.  Users escape dots with backslash to opt out
    of path traversal."""
    from core.configforge import _get_by_path
    data = {"com.apple.finder": {"ShowPathbar": True}, "other": 1}
    assert _get_by_path(data, "com\\.apple\\.finder") == {"ShowPathbar": True}


def test_get_by_path_mixed_escaped_and_plain():
    """Partial escape: one escaped dot keeps the prefix as a single segment."""
    from core.configforge import _get_by_path
    data = {"db.host": {"port": 5432}}
    assert _get_by_path(data, "db\\.host.port") == 5432


def test_set_by_path_dotted_key():
    """--set with escaped dot updates a flat bundle-ID key."""
    from core.configforge import _set_by_path
    data = {"com.example.App": "old"}
    _set_by_path(data, "com\\.example\\.App", "new")
    assert data["com.example.App"] == "new"


def test_delete_by_path_dotted_key():
    """--delete with escaped dot removes a flat bundle-ID key."""
    from core.configforge import _delete_by_path
    data = {"com.example.App": "present", "other": 1}
    _delete_by_path(data, "com\\.example\\.App")
    assert "com.example.App" not in data
    assert data["other"] == 1


def test_get_by_path_dotted_key_cli(tmp_path, capsys):
    """CLI --get with backslash-escaped dot works end-to-end on a JSON file.

    Simulates a macOS developer querying a preferences.json file that has
    flat bundle-ID keys instead of nested dicts."""
    from core.configforge import main
    f = tmp_path / "prefs.json"
    f.write_text('{"com.apple.finder": {"ShowPathbar": true}, "other": 42}')
    rc = main([str(f), "--get", "com\\.apple\\.finder"])
    captured = capsys.readouterr()
    assert rc == 0
    result = json.loads(captured.out)
    assert result["ShowPathbar"] is True


# ── --sort-keys across all formats (HN yq-alternatives complaint) ──
# Users noted that gojq doesn't preserve or sort key order — "a non-starter"
# for API cleanup workflows where diffs need to be deterministic.

def test_sort_keys_toml():
    from core.configforge import serialize
    result = serialize({"zebra": 1, "apple": 2, "mango": 3}, "toml", sort_keys=True)
    lines = [l for l in result.splitlines() if "=" in l]
    keys = [l.split("=")[0].strip() for l in lines]
    assert keys == ["apple", "mango", "zebra"]


def test_sort_keys_env():
    from core.configforge import serialize
    result = serialize({"zebra": 1, "apple": 2, "mango": 3}, "env", sort_keys=True)
    lines = [l for l in result.splitlines() if "=" in l]
    keys = [l.split("=")[0] for l in lines]
    assert keys == ["apple", "mango", "zebra"]


def test_sort_keys_properties():
    from core.configforge import serialize
    result = serialize({"zebra": 1, "apple": 2, "mango": 3}, "properties", sort_keys=True)
    lines = [l for l in result.splitlines() if "=" in l]
    keys = [l.split("=")[0] for l in lines]
    assert keys == ["apple", "mango", "zebra"]


def test_sort_keys_csv_list():
    from core.configforge import serialize
    result = serialize([{"zebra": 1, "apple": 2, "mango": 3}], "csv", sort_keys=True)
    header = result.splitlines()[0]
    assert header == "apple,mango,zebra"


def test_sort_keys_csv_dict():
    from core.configforge import serialize
    result = serialize({"zebra": 1, "apple": 2, "mango": 3}, "csv", sort_keys=True)
    header = result.splitlines()[0]
    assert header == "apple,mango,zebra"


def test_sort_keys_plist():
    from core.configforge import serialize
    result = serialize({"zebra": 1, "apple": 2, "mango": 3}, "plist", sort_keys=True)
    keys = [l.strip().replace("<key>", "").replace("</key>", "")
            for l in result.splitlines() if "<key>" in l]
    assert keys == ["apple", "mango", "zebra"]


def test_sort_keys_xml():
    from core.configforge import serialize
    result = serialize({"zebra": "<z>", "apple": "<a>", "mango": "<m>"}, "xml", sort_keys=True)
    tags = [w.strip("<>").split(">")[0] for w in result.split("<") if w and w[0].isalpha()
            and "root" not in w]
    # First child element should be 'apple'
    assert tags[0] == "apple"


def test_sort_keys_ini():
    from core.configforge import serialize
    data = {"section": {"zebra": "z", "apple": "a", "mango": "m"}}
    result = serialize(data, "ini", sort_keys=True)
    lines = [l for l in result.splitlines() if "=" in l and not l.startswith("[")]
    keys = [l.split("=")[0].strip() for l in lines]
    assert keys == ["apple", "mango", "zebra"]


def test_sort_keys_nested_toml():
    from core.configforge import serialize
    data = {"z_section": {"z_key": 1, "a_key": 2}, "a_section": {"b": 3}}
    result = serialize(data, "toml", sort_keys=True)
    # a_section header should appear before z_section header
    assert result.index("[a_section]") < result.index("[z_section]")


def test_sort_keys_unsorted_preserves_insertion_order():
    """Without sort_keys, insertion order is preserved (default behavior)."""
    from core.configforge import serialize
    result = serialize({"zebra": 1, "apple": 2, "mango": 3}, "toml", sort_keys=False)
    lines = [l for l in result.splitlines() if "=" in l]
    keys = [l.split("=")[0].strip() for l in lines]
    assert keys == ["zebra", "apple", "mango"]


def test_sort_keys_icu_plural_no_blank_lines():
    """sort_keys must not inject blank lines inside ICU Message Format plural strings.

    yq#2452: sort_keys(..) on YAML with ICU plurals ({count, plural, one {# year}
    other {# years}}) added a spurious blank line inside the string value, breaking
    CI pipelines that diff translations.  Verify our serialiser is clean.
    """
    from core.configforge import convert
    yaml_in = (
        "en:\n"
        "  timeago.year: '{count, plural, one {# year} other {# years}}'\n"
        "  timeago.month: '{count, plural, one {# month} other {# months}}'\n"
        "  timeago.day: '{count, plural, one {# day} other {# days}}'\n"
        "  simple: just now\n"
    )
    result = convert(yaml_in, "yaml", "yaml", sort_keys=True)
    assert result["success"], result.get("error")
    output = result["output"]
    # Keys must be sorted
    keys = [l.split(":")[0].strip() for l in output.splitlines() if "timeago." in l]
    assert keys == sorted(keys), f"Keys not sorted: {keys}"
    # ICU plural brace content must be intact — no blank lines added
    assert "\n\n" not in output, "sort_keys added spurious blank line in output"
    # Actual plural strings must survive round-trip unchanged
    assert "{count, plural, one {# year} other {# years}}" in output
    assert "{count, plural, one {# month} other {# months}}" in output
    assert "{count, plural, one {# day} other {# days}}" in output


# ── .env type inference (yq issue #643 complaint) ──
# yq v4 broke environment variable type handling — quoted vars forced to string,
# losing int/float/bool types. ConfigForge infers types for unquoted .env values.

def test_env_infer_int():
    from core.configforge import parse_text
    r = parse_text("PORT=8080\nCOUNT=0", fmt="env")
    assert r["data"]["PORT"] == 8080
    assert r["data"]["COUNT"] == 0


def test_env_infer_bool():
    from core.configforge import parse_text
    r = parse_text("DEBUG=true\nVERBOSE=false\nENABLED=yes\nDISABLED=no", fmt="env")
    assert r["data"]["DEBUG"] is True
    assert r["data"]["VERBOSE"] is False
    assert r["data"]["ENABLED"] is True
    assert r["data"]["DISABLED"] is False


def test_env_infer_float():
    from core.configforge import parse_text
    r = parse_text("TIMEOUT=30.5\nRATIO=0.75", fmt="env")
    assert r["data"]["TIMEOUT"] == 30.5
    assert r["data"]["RATIO"] == 0.75


def test_env_quoted_stays_string():
    """Double-quoted and single-quoted values must remain strings regardless of content."""
    from core.configforge import parse_text
    r = parse_text('PORT="8080"\nDEBUG=\'true\'\nNUM=\'42\'', fmt="env")
    assert r["data"]["PORT"] == "8080"
    assert r["data"]["DEBUG"] == "true"
    assert r["data"]["NUM"] == "42"


def test_env_infer_types_false_keeps_strings():
    from core.configforge import parse_text
    r = parse_text("PORT=8080\nDEBUG=true\nTIMEOUT=30.5", fmt="env", infer_types=False)
    assert r["data"]["PORT"] == "8080"
    assert r["data"]["DEBUG"] == "true"
    assert r["data"]["TIMEOUT"] == "30.5"


def test_env_to_yaml_preserves_types():
    """Round-trip: .env -> YAML should produce typed YAML output."""
    from core.configforge import parse_text, serialize
    r = parse_text("PORT=8080\nDEBUG=true\nTIMEOUT=30.5\nNAME=myapp", fmt="env")
    yaml_out = serialize(r["data"], "yaml")
    assert "PORT: 8080" in yaml_out
    assert "DEBUG: true" in yaml_out
    assert "TIMEOUT: 30.5" in yaml_out
    assert "NAME: myapp" in yaml_out


def test_env_to_json_preserves_types():
    """Round-trip: .env -> JSON should produce typed JSON output."""
    import json as _json
    from core.configforge import parse_text, serialize
    r = parse_text("PORT=8080\nDEBUG=true\nTIMEOUT=30.5", fmt="env")
    obj = _json.loads(serialize(r["data"], "json"))
    assert obj["PORT"] == 8080
    assert obj["DEBUG"] is True
    assert obj["TIMEOUT"] == 30.5


def test_env_plain_string_unchanged():
    """Plain strings that look like nothing special stay as strings."""
    from core.configforge import parse_text
    r = parse_text("NAME=myapp\nURL=http://example.com\nEMPTY=", fmt="env")
    assert r["data"]["NAME"] == "myapp"
    assert r["data"]["EMPTY"] == ""


# ── MEDIUM-NEW4: parse_text() ValueError → clean error message, not traceback ──

def test_get_malformed_input_clean_error(tmp_path, capsys):
    """--get on malformed YAML prints a clean error, not a raw traceback."""
    from core.configforge import main
    f = tmp_path / "bad.yaml"
    f.write_text("key: : invalid: :\n")
    rc = main([str(f), "--get", "key", "--from", "yaml"])
    captured = capsys.readouterr()
    assert rc == 1
    assert captured.err.startswith("error:")
    assert "Traceback" not in captured.err


def test_set_malformed_input_returns_1(tmp_path, capsys):
    """--set on malformed YAML input returns exit code 1 with a clean message."""
    from core.configforge import main
    f = tmp_path / "bad.yaml"
    f.write_text("key: : invalid: :\n")
    rc = main([str(f), "--set", "key", "val", "--from", "yaml"])
    captured = capsys.readouterr()
    assert rc == 1
    assert captured.err.startswith("error:")
    assert "Traceback" not in captured.err


def test_delete_malformed_input_returns_1(tmp_path, capsys):
    """--delete on malformed YAML input returns exit code 1 with a clean message."""
    from core.configforge import main
    f = tmp_path / "bad.yaml"
    f.write_text("key: : invalid: :\n")
    rc = main([str(f), "--delete", "key", "--from", "yaml"])
    captured = capsys.readouterr()
    assert rc == 1
    assert captured.err.startswith("error:")
    assert "Traceback" not in captured.err


def test_merge_malformed_base_returns_1(tmp_path, capsys):
    """--merge on malformed base YAML returns exit code 1 with a clean message."""
    from core.configforge import main
    base = tmp_path / "bad.yaml"
    base.write_text("key: : invalid: :\n")
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text("key: value\n")
    rc = main([str(base), "--merge", str(overlay), "--from", "yaml"])
    captured = capsys.readouterr()
    assert rc == 1
    assert captured.err.startswith("error:")
    assert "Traceback" not in captured.err


def test_merge_malformed_overlay_returns_1(tmp_path, capsys):
    """--merge with malformed overlay YAML returns exit code 1 with a clean message."""
    from core.configforge import main
    base = tmp_path / "base.yaml"
    base.write_text("host: localhost\n")
    overlay = tmp_path / "bad_overlay.yaml"
    overlay.write_text("key: : invalid: :\n")
    rc = main([str(base), "--merge", str(overlay), "--from", "yaml"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "error" in captured.err
    assert "Traceback" not in captured.err


# ── LOW-NEW3: .plist in ext_map lets configforge auto-detect output format ──

def test_plist_ext_map_auto_output(tmp_path, capsys):
    """configforge input.yaml -o output.plist auto-detects plist as target format."""
    from core.configforge import main
    src = tmp_path / "config.yaml"
    src.write_text("version: 1\napp: myapp\n")
    out = tmp_path / "config.plist"
    rc = main([str(src), "-o", str(out)])
    assert rc == 0
    assert out.exists()
    content = out.read_text()
    assert "<plist" in content
    assert "myapp" in content


# ── Jinja/Helm template-safe YAML parsing (yq#1126 / yq#2270) ──

def test_template_yaml_pure_var_to_json():
    """YAML with unquoted {{ var }} values auto-parses (template-quoted fallback)."""
    r = convert("name: {{ app_name }}\nimage: {{ registry }}/myapp:{{ tag }}\n", "json")
    assert r["success"]
    parsed = json.loads(r["output"])
    assert "{{ app_name }}" in parsed["name"]
    assert "{{ registry }}/myapp:{{ tag }}" in parsed["image"]


def test_template_yaml_mixed_suffix_to_json():
    """YAML with {{ var }}-suffix mixed values auto-parses (yq#1126 complaint)."""
    r = convert("host: {{ domain }}-api.example.com\nport: 8080\n", "json")
    assert r["success"]
    parsed = json.loads(r["output"])
    assert "{{ domain }}-api.example.com" in parsed["host"]
    assert parsed["port"] == 8080


def test_template_yaml_helm_values_to_json():
    """Realistic Helm values.yaml with multiple template vars converts cleanly."""
    helm_yaml = (
        "replicaCount: {{ .Values.replicas | default 1 }}\n"
        "image:\n"
        "  repository: {{ .Values.registry }}/{{ .Values.image }}\n"
        "  tag: {{ .Values.tag }}\n"
        "service:\n"
        "  port: 80\n"
    )
    r = convert(helm_yaml, "json")
    assert r["success"]
    parsed = json.loads(r["output"])
    assert "{{ .Values.replicas | default 1 }}" in parsed["replicaCount"]
    assert parsed["service"]["port"] == 80


def test_template_yaml_ansible_to_json():
    """Ansible playbook vars with {{ inventory_hostname }} parse correctly."""
    ansible_yaml = (
        "hostname: {{ inventory_hostname }}\n"
        "db_url: postgresql://{{ db_user }}:{{ db_pass }}@{{ db_host }}/{{ db_name }}\n"
    )
    r = convert(ansible_yaml, "json")
    assert r["success"]
    parsed = json.loads(r["output"])
    assert parsed["hostname"] == "{{ inventory_hostname }}"
    assert "{{ db_user }}" in parsed["db_url"]


def test_template_yaml_detect_format():
    """Templated YAML auto-detected as 'yaml' format."""
    fmt = detect_format("name: {{ app }}\nversion: 1.0\n")
    assert fmt == "yaml"


def test_template_yaml_to_toml():
    """Template YAML converts to TOML preserving template strings."""
    r = convert("name: {{ app_name }}\nenv: {{ environment }}\n", "toml")
    assert r["success"]
    assert "{{ app_name }}" in r["output"]
    assert "{{ environment }}" in r["output"]


# ── --template-safe explicit flag ──

def test_template_safe_parse_text_forces_quoting():
    """parse_text(template_safe=True) pre-quotes templates before normal parse."""
    yaml_text = "image: {{ .Values.image }}\nreplicas: 3\n"
    result = parse_text(yaml_text, fmt="yaml", template_safe=True)
    assert result["format"] == "yaml"
    assert result["data"]["replicas"] == 3
    assert "{{ .Values.image }}" in result["data"]["image"]
    assert result.get("template_quoted") is True


def test_template_safe_no_op_on_plain_yaml():
    """template_safe=True is harmless when no template syntax present."""
    yaml_text = "host: localhost\nport: 8080\n"
    result = parse_text(yaml_text, fmt="yaml", template_safe=True)
    assert result["format"] == "yaml"
    assert result["data"]["host"] == "localhost"
    assert result["data"]["port"] == 8080


def test_template_safe_via_convert():
    """convert() with template_safe=True converts Helm YAML to JSON."""
    helm = "image: {{ .Values.image }}\nreplicas: {{ .Values.replicas | default 1 }}\n"
    r = convert(helm, "json", template_safe=True)
    assert r["success"]
    data = json.loads(r["output"])
    assert "{{ .Values.image }}" in data["image"]


def test_template_safe_cli_flag():
    """configforge --template-safe flag parses Helm values.yaml correctly."""
    from core.configforge import main
    import io
    helm_yaml = "service:\n  port: {{ .Values.servicePort }}\n  type: ClusterIP\n"
    old_stdin = sys.stdin
    sys.stdin = io.StringIO(helm_yaml)
    try:
        rc = main(["-t", "json", "--template-safe"])
    finally:
        sys.stdin = old_stdin
    assert rc == 0


def test_yaml12_via_devbench_cf():
    """devbench cf --yaml12 treats yes/no/on/off as strings (not booleans)."""
    from core.cli import main as cli_main
    import io
    yaml_text = "enabled: yes\ndisabled: no\nflag: on\n"
    old_stdin = sys.stdin
    sys.stdin = io.StringIO(yaml_text)
    try:
        rc = cli_main(["cf", "--to", "json", "--yaml12"])
    finally:
        sys.stdin = old_stdin
    assert rc == 0


def test_template_safe_via_devbench_cf():
    """devbench cf --template-safe parses Jinja template YAML."""
    from core.cli import main as cli_main
    import io
    yaml_text = "name: {{ app }}\nversion: 1.0\n"
    old_stdin = sys.stdin
    sys.stdin = io.StringIO(yaml_text)
    try:
        rc = cli_main(["cf", "--to", "json", "--template-safe"])
    finally:
        sys.stdin = old_stdin
    assert rc == 0


# ── _format_get_output / --raw round-trip safety (yq #2608) ──────────────────

def test_format_get_output_plain_string():
    """Plain strings are output as-is without quoting."""
    from core.configforge import _format_get_output
    assert _format_get_output("hello world") == "hello world"
    assert _format_get_output("simple") == "simple"


def test_format_get_output_ambiguous_strings_quoted():
    """Strings that look like YAML scalars are quoted for round-trip safety."""
    from core.configforge import _format_get_output
    out_colon = _format_get_output("this: is a mapping")
    assert yaml.safe_load(out_colon) == "this: is a mapping"
    assert ":" in out_colon  # the colon survived
    out_yes = _format_get_output("yes")
    assert yaml.safe_load(out_yes) == "yes"


def test_format_get_output_null_like_string():
    """'null' string is quoted so it doesn't become NoneType when re-parsed."""
    from core.configforge import _format_get_output
    out = _format_get_output("null")
    assert yaml.safe_load(out) == "null"


def test_format_get_output_date_like_string():
    """ISO-8601 string is quoted so it doesn't become a date object."""
    from core.configforge import _format_get_output
    out = _format_get_output("2024-01-01")
    reparsed = yaml.safe_load(out)
    assert reparsed == "2024-01-01"


def test_format_get_output_scalar_types():
    """Actual booleans, ints, and None emit as unquoted YAML scalars."""
    from core.configforge import _format_get_output
    assert _format_get_output(True) == "true"
    assert _format_get_output(False) == "false"
    assert _format_get_output(None) == "null"
    assert _format_get_output(42) == "42"
    assert _format_get_output(3.14) == "3.14"


def test_format_get_output_raw_bypasses_quoting():
    """--raw flag returns the bare string, matching jq -r / yq -r behaviour."""
    from core.configforge import _format_get_output
    assert _format_get_output("this: is a mapping", raw=True) == "this: is a mapping"
    assert _format_get_output("yes", raw=True) == "yes"
    assert _format_get_output("null", raw=True) == "null"


def test_format_get_output_dict_and_list():
    """Dicts and lists are emitted as JSON regardless of --raw."""
    from core.configforge import _format_get_output
    d = {"a": 1, "b": [2, 3]}
    out = _format_get_output(d)
    assert json.loads(out) == d
    lst = [1, "two", None]
    out2 = _format_get_output(lst)
    assert json.loads(out2) == lst


def test_get_via_cli_round_trip_safe(tmp_path):
    """devbench cf --get emits YAML-safe output for ambiguous string scalars."""
    from core.cli import main as cli_main
    import io
    # YAML file where the value would be mis-parsed if unquoted
    p = tmp_path / "test.yaml"
    p.write_text("label: 'host: example.com'\n")
    buf = io.StringIO()
    old_stdout, sys.stdout = sys.stdout, buf
    try:
        rc = cli_main(["cf", "--get", "label", str(p)])
    finally:
        sys.stdout = old_stdout
    assert rc == 0
    out = buf.getvalue().strip()
    # Output must be a valid YAML scalar that re-parses to the original string
    reparsed = yaml.safe_load(out)
    assert reparsed == "host: example.com"


def test_get_raw_via_cli(tmp_path):
    """devbench cf --raw --get emits the bare string value (no YAML quoting)."""
    from core.cli import main as cli_main
    import io
    p = tmp_path / "test.yaml"
    p.write_text("label: 'host: example.com'\n")
    buf = io.StringIO()
    old_stdout, sys.stdout = sys.stdout, buf
    try:
        rc = cli_main(["cf", "--raw", "--get", "label", str(p)])
    finally:
        sys.stdout = old_stdout
    assert rc == 0
    assert buf.getvalue().strip() == "host: example.com"


# ── _list_keys / --keys tests ──────────────────────────────────────────────────

def test_list_keys_flat_dict():
    from core.configforge import _list_keys
    data = {"a": 1, "b": 2, "c": 3}
    assert _list_keys(data) == ["a", "b", "c"]


def test_list_keys_nested_non_recursive():
    from core.configforge import _list_keys
    data = {"server": {"host": "localhost", "port": 8080}, "debug": True}
    assert _list_keys(data) == ["server", "debug"]


def test_list_keys_recursive():
    from core.configforge import _list_keys
    data = {"server": {"host": "localhost", "port": 8080}, "debug": True}
    keys = _list_keys(data, recursive=True)
    assert "server" in keys
    assert "server.host" in keys
    assert "server.port" in keys
    assert "debug" in keys


def test_list_keys_list_top_level():
    from core.configforge import _list_keys
    data = ["a", "b", "c"]
    assert _list_keys(data) == ["0", "1", "2"]


def test_list_keys_nested_list_recursive():
    from core.configforge import _list_keys
    data = {"items": [{"name": "x"}, {"name": "y"}]}
    keys = _list_keys(data, recursive=True)
    assert "items" in keys
    assert "items.0" in keys
    assert "items.0.name" in keys
    assert "items.1.name" in keys


def test_list_keys_empty():
    from core.configforge import _list_keys
    assert _list_keys({}) == []
    assert _list_keys([]) == []


def test_keys_flag_configforge_main(capsys):
    from core.configforge import main as cf_main
    import io, sys
    yaml_text = "host: localhost\nport: 8080\ndebug: true\n"
    buf = io.StringIO()
    old_stdin, sys.stdin = sys.stdin, io.StringIO(yaml_text)
    old_stdout, sys.stdout = sys.stdout, buf
    try:
        rc = cf_main(["--keys", "--from", "yaml"])
    finally:
        sys.stdin = old_stdin
        sys.stdout = old_stdout
    assert rc == 0
    lines = buf.getvalue().strip().split("\n")
    assert "host" in lines
    assert "port" in lines
    assert "debug" in lines


def test_keys_recursive_configforge_main(capsys):
    from core.configforge import main as cf_main
    import io, sys
    yaml_text = "server:\n  host: localhost\n  port: 8080\ndebug: true\n"
    buf = io.StringIO()
    old_stdin, sys.stdin = sys.stdin, io.StringIO(yaml_text)
    old_stdout, sys.stdout = sys.stdout, buf
    try:
        rc = cf_main(["--keys", "--recursive", "--from", "yaml"])
    finally:
        sys.stdin = old_stdin
        sys.stdout = old_stdout
    assert rc == 0
    lines = buf.getvalue().strip().split("\n")
    assert "server" in lines
    assert "server.host" in lines
    assert "server.port" in lines
    assert "debug" in lines


def test_keys_flag_cli(tmp_path):
    from core.cli import main as cli_main
    import io, sys
    p = tmp_path / "cfg.yaml"
    p.write_text("host: localhost\nport: 8080\ndebug: true\n")
    buf = io.StringIO()
    old_stdout, sys.stdout = sys.stdout, buf
    try:
        rc = cli_main(["cf", "--keys", str(p)])
    finally:
        sys.stdout = old_stdout
    assert rc == 0
    lines = buf.getvalue().strip().split("\n")
    assert "host" in lines
    assert "port" in lines
    assert "debug" in lines


def test_keys_recursive_cli(tmp_path):
    from core.cli import main as cli_main
    import io, sys
    p = tmp_path / "cfg.yaml"
    p.write_text("server:\n  host: localhost\n  port: 8080\ndebug: true\n")
    buf = io.StringIO()
    old_stdout, sys.stdout = sys.stdout, buf
    try:
        rc = cli_main(["cf", "--keys", "--recursive", str(p)])
    finally:
        sys.stdout = old_stdout
    assert rc == 0
    lines = buf.getvalue().strip().split("\n")
    assert "server" in lines
    assert "server.host" in lines
    assert "server.port" in lines
    assert "debug" in lines


def test_keys_json_input_cli(tmp_path):
    from core.cli import main as cli_main
    import io, sys
    p = tmp_path / "cfg.json"
    p.write_text('{"a": 1, "b": {"c": 2}}')
    buf = io.StringIO()
    old_stdout, sys.stdout = sys.stdout, buf
    try:
        rc = cli_main(["cf", "--keys", str(p)])
    finally:
        sys.stdout = old_stdout
    assert rc == 0
    lines = buf.getvalue().strip().split("\n")
    assert "a" in lines
    assert "b" in lines
    assert "c" not in lines  # non-recursive: nested keys not exposed


def test_keys_malformed_input_error(tmp_path, capsys):
    from core.configforge import main as cf_main
    import io, sys
    buf = io.StringIO()
    old_stdin, sys.stdin = sys.stdin, io.StringIO("not: valid: yaml: : :")
    old_stderr, sys.stderr = sys.stderr, buf
    try:
        rc = cf_main(["--keys", "--from", "yaml"])
    finally:
        sys.stdin = old_stdin
        sys.stderr = old_stderr
    assert rc == 1
    assert "error" in buf.getvalue().lower()


# ── recursive batch glob tests ─────────────────────────────────────────────────

def test_batch_convert_recursive(tmp_path):
    """batch_convert with recursive=True finds files in subdirectories."""
    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / "a.json").write_text('{"key": "top"}')
    (sub / "b.json").write_text('{"key": "nested"}')
    results = batch_convert(
        str(tmp_path / "**" / "*.json"),
        "yaml",
        recursive=True,
        show_progress=False,
    )
    assert len(results) == 2
    assert all(r["success"] for r in results)


def test_batch_convert_stream_recursive(tmp_path):
    """batch_convert_stream with recursive=True finds files in subdirectories."""
    sub = tmp_path / "deep"
    sub.mkdir()
    (tmp_path / "x.json").write_text('{"v": 1}')
    (sub / "y.json").write_text('{"v": 2}')
    results = list(batch_convert_stream(
        str(tmp_path / "**" / "*.json"),
        "yaml",
        recursive=True,
        show_progress=False,
    ))
    file_results = [r for r in results if "file" in r]
    assert len(file_results) == 2
    assert all(r["success"] for r in file_results)


def test_batch_convert_recursive_false_skips_subdirs(tmp_path):
    """recursive=False (default) does not match files in subdirectories."""
    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / "top.json").write_text('{"k": 1}')
    (sub / "nested.json").write_text('{"k": 2}')
    results = batch_convert(
        str(tmp_path / "*.json"),
        "yaml",
        recursive=False,
        show_progress=False,
    )
    # Only the top-level file matches a non-recursive glob
    assert len(results) == 1
    assert results[0]["success"]


# ---------------------------------------------------------------------------
# --append: ergonomic array-append (yq v4 verbosity complaint)
# ---------------------------------------------------------------------------

def test_append_to_path_existing_list():
    """_append_to_path adds a value to an existing list."""
    from core.configforge import _append_to_path
    data = {"servers": ["alpha", "beta"]}
    _append_to_path(data, "servers", "gamma")
    assert data["servers"] == ["alpha", "beta", "gamma"]


def test_append_to_path_creates_list_when_key_missing():
    """_append_to_path creates a new single-element list when key absent."""
    from core.configforge import _append_to_path
    data = {}
    _append_to_path(data, "tags", "new-tag")
    assert data["tags"] == ["new-tag"]


def test_append_to_path_nested_key():
    """_append_to_path traverses nested dicts before appending."""
    from core.configforge import _append_to_path
    data = {"app": {"features": ["auth"]}}
    _append_to_path(data, "app.features", "logging")
    assert data["app"]["features"] == ["auth", "logging"]


def test_append_to_path_non_list_raises():
    """_append_to_path raises KeyError when target is not a list."""
    from core.configforge import _append_to_path
    import pytest
    data = {"host": "localhost"}
    with pytest.raises(KeyError, match="str"):
        _append_to_path(data, "host", "extra")


def test_append_to_path_json_value():
    """_append_to_path accepts numeric and boolean values."""
    from core.configforge import _append_to_path
    data = {"ports": [8080]}
    _append_to_path(data, "ports", 9090)
    assert data["ports"] == [8080, 9090]


def test_append_cli_yaml(tmp_path, capsys):
    """devbench cf --append adds to an existing YAML list."""
    from core.configforge import main
    src = tmp_path / "config.yaml"
    src.write_text("servers:\n  - alpha\n  - beta\n")
    rc = main([str(src), "--append", "servers", "gamma"])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    assert result["servers"] == ["alpha", "beta", "gamma"]


def test_append_cli_creates_new_list(tmp_path, capsys):
    """devbench cf --append creates the list when key is absent."""
    from core.configforge import main
    src = tmp_path / "config.yaml"
    src.write_text("name: myapp\n")
    rc = main([str(src), "--append", "tags", "release"])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    assert result["tags"] == ["release"]
    assert result["name"] == "myapp"


def test_append_cli_in_place(tmp_path):
    """devbench cf --append --in-place modifies the file on disk."""
    from core.configforge import main
    src = tmp_path / "config.yaml"
    src.write_text("envs:\n  - prod\n")
    rc = main([str(src), "--append", "envs", "staging", "--in-place"])
    assert rc == 0
    result = yaml.safe_load(src.read_text())
    assert result["envs"] == ["prod", "staging"]


def test_append_cli_json_value(tmp_path, capsys):
    """devbench cf --append parses numeric JSON value correctly."""
    from core.configforge import main
    src = tmp_path / "config.yaml"
    src.write_text("ports:\n  - 8080\n")
    rc = main([str(src), "--append", "ports", "9090"])
    captured = capsys.readouterr()
    assert rc == 0
    result = yaml.safe_load(captured.out)
    assert result["ports"] == [8080, 9090]


def test_append_cli_non_list_error(tmp_path, capsys):
    """devbench cf --append returns error when target is not a list."""
    from core.configforge import main
    src = tmp_path / "config.yaml"
    src.write_text("host: localhost\n")
    rc = main([str(src), "--append", "host", "extra"])
    assert rc != 0
    captured = capsys.readouterr()
    assert "error" in captured.err.lower()


def test_append_cli_json_format(tmp_path, capsys):
    """devbench cf --append works on JSON input."""
    from core.configforge import main
    src = tmp_path / "config.json"
    src.write_text('{"plugins": ["auth", "cache"]}')
    rc = main([str(src), "--append", "plugins", "logging"])
    captured = capsys.readouterr()
    assert rc == 0
    result = json.loads(captured.out)
    assert result["plugins"] == ["auth", "cache", "logging"]


# ---------------------------------------------------------------------------
# configforge.main() — 5 new flags (parity with cli.py)
# ---------------------------------------------------------------------------

def test_main_sort_keys_reverse(tmp_path, capsys):
    """configforge --sort-keys-reverse emits keys in reverse alphabetical order."""
    from core.configforge import main
    src = tmp_path / "cfg.yaml"
    src.write_text("alpha: 1\nbeta: 2\nzeta: 3\n")
    rc = main([str(src), "--to", "json", "--sort-keys-reverse"])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    keys = list(data.keys())
    assert keys == sorted(keys, reverse=True)


def test_main_compact(tmp_path, capsys):
    """configforge --compact produces minified single-line JSON."""
    from core.configforge import main
    src = tmp_path / "cfg.yaml"
    src.write_text("host: localhost\nport: 8080\n")
    rc = main([str(src), "--to", "json", "--compact"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert "\n" not in out
    data = json.loads(out)
    assert data["port"] == 8080


def test_main_get_default_missing_path(tmp_path, capsys):
    """configforge --get missing.path --default fallback returns fallback."""
    from core.configforge import main
    src = tmp_path / "cfg.yaml"
    src.write_text("host: localhost\n")
    rc = main([str(src), "--get", "timeout", "--default", "30"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "30"


def test_main_get_default_present_path(tmp_path, capsys):
    """configforge --get existing.path --default returns actual value, not default."""
    from core.configforge import main
    src = tmp_path / "cfg.yaml"
    src.write_text("timeout: 60\n")
    rc = main([str(src), "--get", "timeout", "--default", "30"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "60"


def test_main_select_basic(tmp_path, capsys):
    """configforge --select filters list items by field=value."""
    from core.configforge import main
    src = tmp_path / "pods.yaml"
    src.write_text(
        "- name: app\n  status: Running\n"
        "- name: db\n  status: Pending\n"
    )
    rc = main([str(src), "--select", "status=Running"])
    assert rc == 0
    import yaml
    result = yaml.safe_load(capsys.readouterr().out)
    assert len(result) == 1
    assert result[0]["name"] == "app"


def test_main_select_no_matches(tmp_path):
    """configforge --select with no matches returns exit code 1."""
    from core.configforge import main
    src = tmp_path / "pods.yaml"
    src.write_text("- name: app\n  status: Running\n")
    rc = main([str(src), "--select", "status=Pending"])
    assert rc == 1


def test_main_select_negate(tmp_path, capsys):
    """configforge --select FIELD!=VALUE keeps non-matching items."""
    from core.configforge import main
    src = tmp_path / "pods.yaml"
    src.write_text(
        "- name: app\n  status: Running\n"
        "- name: db\n  status: Pending\n"
    )
    rc = main([str(src), "--select", "status!=Running"])
    assert rc == 0
    import yaml
    result = yaml.safe_load(capsys.readouterr().out)
    assert len(result) == 1
    assert result[0]["name"] == "db"


def test_main_template_string_template(tmp_path, capsys):
    """configforge --template renders ${key} templates from config."""
    from core.configforge import main
    src = tmp_path / "cfg.yaml"
    src.write_text("host: db.internal\nport: 5432\n")
    tmpl = tmp_path / "conn.tmpl"
    tmpl.write_text("postgres://${host}:${port}/mydb\n")
    rc = main([str(src), "--template", str(tmpl)])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out == "postgres://db.internal:5432/mydb"


def test_main_template_missing_file(tmp_path, capsys):
    """configforge --template with non-existent template file returns error."""
    from core.configforge import main
    src = tmp_path / "cfg.yaml"
    src.write_text("host: localhost\n")
    rc = main([str(src), "--template", str(tmp_path / "nonexistent.tmpl")])
    assert rc != 0
    assert "error" in capsys.readouterr().err.lower()


def test_detect_json5_with_single_quotes():
    """JSON5 with single quotes should be detected as json5."""
    text = "{ 'name': 'test', 'value': 42 }"
    assert detect_format(text) == "json5"


def test_detect_json5_with_unquoted_keys():
    """JSON5 with unquoted keys should be detected as json5."""
    text = "{ name: 'test', value: 42 }"
    assert detect_format(text) == "json5"


def test_detect_json5_mixed_features():
    """JSON5 with unquoted keys and comments should be detected as json5."""
    text = """{
  // configuration
  name: 'test',
  value: 42
}"""
    assert detect_format(text) == "json5"


def test_parse_json5_with_comments():
    """JSON5 with comments should parse correctly."""
    text = """{
  // this is a comment
  "name": "test",
  "value": 42
}"""
    result = parse_text(text, "json5")
    assert result["format"] == "json5"
    assert result["data"]["name"] == "test"
    assert result["data"]["value"] == 42


def test_parse_json5_with_single_quotes():
    """JSON5 with single quotes should parse correctly."""
    text = "{ 'name': 'test', 'value': 42 }"
    result = parse_text(text, "json5")
    assert result["data"]["name"] == "test"
    assert result["data"]["value"] == 42


def test_parse_json5_with_trailing_commas():
    """JSON5 with trailing commas should parse correctly."""
    text = """{
  "name": "test",
  "items": [1, 2, 3,],
}"""
    result = parse_text(text, "json5")
    assert result["data"]["name"] == "test"
    assert result["data"]["items"] == [1, 2, 3]


def test_convert_json5_to_yaml():
    """JSON5 should convert to YAML correctly."""
    text = "{ name: 'test', value: 42 }"
    result = convert(text, "yaml")
    assert result["success"]
    parsed = yaml.safe_load(result["output"])
    assert parsed == {"name": "test", "value": 42}


def test_convert_json5_auto_detect():
    """JSON5 should auto-detect and convert correctly."""
    text = """{
  // config
  name: 'test',
  value: 42,
}"""
    result = convert(text, "json")
    assert result["success"]
    parsed = json.loads(result["output"])
    assert parsed["name"] == "test"
    assert parsed["value"] == 42


# ══════════════════════════════════════════════════════════════════════════════
# --each KEY — extract a field from every list element
# ══════════════════════════════════════════════════════════════════════════════

def test_each_simple_string_field(tmp_path, capsys):
    """Extract a string field from each list element."""
    from core.cli import main as cli_main
    src = tmp_path / "containers.yaml"
    src.write_text("- name: nginx\n  image: nginx:latest\n- name: redis\n  image: redis:7\n")
    rc = cli_main(["cf", str(src), "--each", "name", "--to", "json"])
    assert rc == 0
    import json
    result = json.loads(capsys.readouterr().out)
    assert result == ["nginx", "redis"]


def test_each_simple_int_field(tmp_path, capsys):
    """Extract an integer field from each list element."""
    from core.cli import main as cli_main
    src = tmp_path / "ports.yaml"
    src.write_text("- port: 80\n  protocol: TCP\n- port: 443\n  protocol: TCP\n")
    rc = cli_main(["cf", str(src), "--each", "port", "--to", "json", "--compact"])
    assert rc == 0
    import json
    assert json.loads(capsys.readouterr().out.strip()) == [80, 443]


def test_each_json_array_output(tmp_path, capsys):
    """--each with --to json produces a JSON array."""
    from core.cli import main as cli_main
    src = tmp_path / "items.yaml"
    src.write_text("- id: 1\n  name: foo\n- id: 2\n  name: bar\n")
    rc = cli_main(["cf", str(src), "--each", "name", "--to", "json"])
    assert rc == 0
    import json
    assert json.loads(capsys.readouterr().out) == ["foo", "bar"]


def test_each_nested_dot_path(tmp_path, capsys):
    """--each with a nested dot-path extracts deeply nested values."""
    from core.cli import main as cli_main
    src = tmp_path / "deploy.yaml"
    src.write_text(
        "containers:\n"
        "  - metadata:\n      name: web\n    spec:\n      image: nginx\n"
        "  - metadata:\n      name: cache\n    spec:\n      image: redis\n"
    )
    rc = cli_main(["cf", str(src), "--get", "containers", "--each", "metadata.name", "--to", "json"])
    assert rc == 0
    import json
    assert json.loads(capsys.readouterr().out) == ["web", "cache"]


def test_each_missing_key_skipped(tmp_path, capsys):
    """Items missing the target key are silently omitted."""
    from core.cli import main as cli_main
    src = tmp_path / "mixed.yaml"
    src.write_text("- name: a\n  port: 80\n- name: b\n- name: c\n  port: 443\n")
    rc = cli_main(["cf", str(src), "--each", "port", "--to", "json"])
    assert rc == 0
    import json
    assert json.loads(capsys.readouterr().out.strip()) == [80, 443]


def test_each_with_select_filter(tmp_path, capsys):
    """--each combined with --select filters before extracting."""
    from core.cli import main as cli_main
    src = tmp_path / "pods.yaml"
    src.write_text(
        "- name: nginx\n  status: Running\n"
        "- name: redis\n  status: Running\n"
        "- name: debug\n  status: Pending\n"
    )
    rc = cli_main(["cf", str(src), "--select", "status=Running", "--each", "name", "--to", "json"])
    assert rc == 0
    import json
    assert set(json.loads(capsys.readouterr().out)) == {"nginx", "redis"}


def test_each_raw_scalar_one_per_line(tmp_path, capsys):
    """--raw outputs scalar values one per line."""
    from core.cli import main as cli_main
    src = tmp_path / "names.yaml"
    src.write_text("- name: a\n- name: b\n- name: c\n")
    rc = cli_main(["cf", str(src), "--each", "name", "--raw"])
    assert rc == 0
    assert capsys.readouterr().out.strip().splitlines() == ["a", "b", "c"]


def test_each_non_list_exits_error(tmp_path):
    """--each on non-list input returns error exit."""
    from core.cli import main as cli_main
    src = tmp_path / "scalar.yaml"
    src.write_text("name: foo\nport: 8080\n")
    rc = cli_main(["cf", str(src), "--each", "name"])
    assert rc != 0


def test_each_empty_list(tmp_path, capsys):
    """--each on empty list outputs empty JSON array."""
    from core.cli import main as cli_main
    src = tmp_path / "empty.yaml"
    src.write_text("[]\n")
    rc = cli_main(["cf", str(src), "--each", "name", "--to", "json"])
    assert rc == 0
    import json
    assert json.loads(capsys.readouterr().out.strip()) == []


def test_each_json5_input(tmp_path, capsys):
    """--each works when input is JSON5."""
    from core.cli import main as cli_main
    src = tmp_path / "services.json5"
    src.write_text("[{name: 'alpha', port: 8080}, {name: 'beta', port: 9090}]")
    rc = cli_main(["cf", str(src), "--from", "json5", "--each", "name", "--to", "json"])
    assert rc == 0
    import json
    assert set(json.loads(capsys.readouterr().out)) == {"alpha", "beta"}


# ── configforge.main() --each parity tests ──────────────────────────────────

def test_main_each_simple(tmp_path, capsys):
    """configforge --each extracts a field from each list element."""
    from core.configforge import main
    src = tmp_path / "items.yaml"
    src.write_text("- name: alpha\n  port: 8080\n- name: beta\n  port: 9090\n")
    rc = main([str(src), "--each", "name", "--to", "json"])
    assert rc == 0
    import json
    assert json.loads(capsys.readouterr().out) == ["alpha", "beta"]


def test_main_each_with_get(tmp_path, capsys):
    """configforge --get PATH --each KEY extracts field from nested list."""
    from core.configforge import main
    import json
    src = tmp_path / "deploy.yaml"
    src.write_text("spec:\n  containers:\n  - name: app\n    image: nginx\n  - name: sidecar\n    image: envoy\n")
    rc = main([str(src), "--get", "spec.containers", "--each", "name", "--to", "json"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out) == ["app", "sidecar"]


def test_main_each_with_select(tmp_path, capsys):
    """configforge --select --each chains filtering with field extraction."""
    from core.configforge import main
    import json
    src = tmp_path / "pods.yaml"
    src.write_text(
        "- name: pod-a\n  status: Running\n"
        "- name: pod-b\n  status: Pending\n"
        "- name: pod-c\n  status: Running\n"
    )
    rc = main([str(src), "--select", "status=Running", "--each", "name", "--to", "json"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out) == ["pod-a", "pod-c"]


def test_main_each_missing_key_skipped(tmp_path, capsys):
    """configforge --each silently omits items missing the key."""
    from core.configforge import main
    import json
    src = tmp_path / "mixed.json"
    src.write_text('[{"name": "a"}, {"port": 80}, {"name": "b"}]')
    rc = main([str(src), "--each", "name", "--to", "json"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out) == ["a", "b"]


def test_main_each_not_a_list_error(tmp_path, capsys):
    """configforge --each exits 1 when input is not a list."""
    from core.configforge import main
    src = tmp_path / "scalar.yaml"
    src.write_text("name: single\n")
    rc = main([str(src), "--each", "name"])
    assert rc == 1
    assert "error" in capsys.readouterr().err.lower()


def test_main_select_count_composition(tmp_path, capsys):
    """--select --count . counts matching items after filtering."""
    from core.cli import main as cli_main
    src = tmp_path / "pods.yaml"
    src.write_text(
        "- name: pod-a\n  status: Running\n"
        "- name: pod-b\n  status: Pending\n"
        "- name: pod-c\n  status: Running\n"
    )
    rc = cli_main(["cf", str(src), "--select", "status=Running", "--count", "."])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "2"


# ── --select regex tests ─────────────────────────────────────────────────────

def test_select_regex_match(tmp_path, capsys):
    """--select FIELD=/pattern/ keeps items whose field matches the regex."""
    import json as _json
    from core.cli import main as cli_main
    src = tmp_path / "pods.yaml"
    src.write_text(
        "- name: web-frontend\n  status: Running\n"
        "- name: api-backend\n  status: CrashLoopBackOff\n"
        "- name: web-proxy\n  status: Running\n"
    )
    rc = cli_main(["cf", str(src), "--select", "name=/^web/", "--to", "json"])
    assert rc == 0
    result = _json.loads(capsys.readouterr().out)
    assert len(result) == 2
    assert all(item["name"].startswith("web") for item in result)


def test_select_regex_not_match(tmp_path, capsys):
    """--select FIELD!=/pattern/ excludes items whose field matches the regex."""
    import json as _json
    from core.cli import main as cli_main
    src = tmp_path / "pods.yaml"
    src.write_text(
        "- name: web-frontend\n  status: Running\n"
        "- name: api-backend\n  status: Running\n"
    )
    rc = cli_main(["cf", str(src), "--select", "name!=/^web/", "--to", "json"])
    assert rc == 0
    result = _json.loads(capsys.readouterr().out)
    assert len(result) == 1
    assert result[0]["name"] == "api-backend"


def test_select_regex_case_insensitive(tmp_path, capsys):
    """--select regex matching is case-insensitive."""
    import json as _json
    from core.cli import main as cli_main
    src = tmp_path / "items.yaml"
    src.write_text("- name: Alpha\n- name: BETA\n- name: gamma\n")
    rc = cli_main(["cf", str(src), "--select", "name=/alpha/", "--to", "json"])
    assert rc == 0
    result = _json.loads(capsys.readouterr().out)
    assert len(result) == 1
    assert result[0]["name"] == "Alpha"


# ── --wrap-in tests ──────────────────────────────────────────────────────────

def test_wrap_in_simple_key(tmp_path, capsys):
    """--wrap-in wraps the entire config under a single key."""
    from core.cli import main as cli_main
    src = tmp_path / "config.yaml"
    src.write_text("host: localhost\nport: 5432\n")
    rc = cli_main(["cf", str(src), "--wrap-in", "database", "--to", "json"])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {"database": {"host": "localhost", "port": 5432}}


def test_wrap_in_dotted_key(tmp_path, capsys):
    """--wrap-in creates nested dicts for dotted paths."""
    from core.cli import main as cli_main
    src = tmp_path / "vals.yaml"
    src.write_text("replicas: 3\nimage: nginx\n")
    rc = cli_main(["cf", str(src), "--wrap-in", "spec.template.spec", "--to", "json"])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {"spec": {"template": {"spec": {"replicas": 3, "image": "nginx"}}}}


def test_wrap_in_yaml_output(tmp_path, capsys):
    """--wrap-in outputs YAML by default when input is YAML."""
    from core.cli import main as cli_main
    src = tmp_path / "config.yaml"
    src.write_text("key: value\n")
    rc = cli_main(["cf", str(src), "--wrap-in", "data"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "data:" in out
    assert "key: value" in out


def test_wrap_in_json_input_yaml_output(tmp_path, capsys):
    """--wrap-in accepts JSON input and emits YAML output."""
    from core.cli import main as cli_main
    src = tmp_path / "config.json"
    src.write_text('{"name": "app", "version": "1.0"}')
    rc = cli_main(["cf", str(src), "--wrap-in", "metadata", "--to", "yaml"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "metadata:" in out
    assert "name: app" in out


def test_wrap_in_configforge_main(tmp_path, capsys):
    """configforge standalone --wrap-in produces same result as cli --wrap-in."""
    from core.configforge import main
    src = tmp_path / "config.yaml"
    src.write_text("host: db\nport: 5432\n")
    rc = main([str(src), "--wrap-in", "database", "--to", "json"])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {"database": {"host": "db", "port": 5432}}


def test_wrap_in_list_input(tmp_path, capsys):
    """--wrap-in handles list-typed configs."""
    from core.cli import main as cli_main
    src = tmp_path / "items.yaml"
    src.write_text("- a\n- b\n- c\n")
    rc = cli_main(["cf", str(src), "--wrap-in", "items", "--to", "json"])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {"items": ["a", "b", "c"]}


def test_wrap_in_stdin(capsys, monkeypatch):
    """--wrap-in reads from stdin when no file provided."""
    import io
    from core.cli import main as cli_main
    monkeypatch.setattr("sys.stdin", io.StringIO("key: value\n"))
    rc = cli_main(["cf", "--wrap-in", "data", "--to", "json"])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {"data": {"key": "value"}}


# -- Feature: INI --ini-quote-strings round-trip (yq issue #2456) --

def test_ini_quote_strings_bare_values():
    """Bare INI values get double-quoted when --ini-quote-strings is set."""
    ini_in = "[theme]\ncolor = Default\nbg = ffffff\n"
    r = convert(ini_in, "ini", from_fmt="ini", ini_quote_strings=True)
    assert r["success"]
    assert 'color = "Default"' in r["output"]
    assert 'bg = "ffffff"' in r["output"]


def test_ini_quote_strings_already_quoted_round_trip():
    """Pre-quoted INI values don't get double-wrapped when --ini-quote-strings is set.

    Addresses yq issue #2456: tools that write quoted INI values like
    color_theme = "Default" must survive a round-trip without gaining
    extra quotes (e.g. "\\\"Default\\\"").
    """
    ini_in = '[theme]\ncolor = "Default"\nbg = "#ffffff"\n'
    r = convert(ini_in, "ini", from_fmt="ini", ini_quote_strings=True)
    assert r["success"]
    out = r["output"]
    assert 'color = "Default"' in out, f"Expected single-quoted value, got: {out!r}"
    assert '"Default"' in out and '\\\"' not in out


def test_ini_quote_strings_numerics_not_quoted():
    """Numeric and boolean INI values are not quoted even with --ini-quote-strings."""
    ini_in = "[app]\nport = 8080\ndebug = true\nfactor = 3.14\n"
    r = convert(ini_in, "ini", from_fmt="ini", ini_quote_strings=True)
    assert r["success"]
    out = r["output"]
    assert "port = 8080" in out
    assert "debug = true" in out
    assert "factor = 3.14" in out


# -- Feature: INI --ini-strip-quotes (yq issue #2456 complement) --

def test_ini_strip_quotes_basic():
    """--ini-strip-quotes strips surrounding double-quotes from INI values on parse."""
    ini_in = '[theme]\ncolor_theme = "Default"\nbg = "#ffffff"\nport = 8080\n'
    r = convert(ini_in, "yaml", from_fmt="ini", ini_strip_quotes=True)
    assert r["success"]
    out = r["output"]
    assert "color_theme: Default" in out, f"Expected unquoted Default, got: {out!r}"
    assert "bg: '#ffffff'" in out or "bg: \"#ffffff\"" in out or "bg: '#ffffff'" in out or "bg: '#ffffff'" in out or "#ffffff" in out


def test_ini_strip_quotes_json_output():
    """--ini-strip-quotes produces clean JSON output without literal quote chars."""
    ini_in = '[app]\nname = "MyApp"\nversion = "1.0"\nport = 9000\n'
    r = convert(ini_in, "json", from_fmt="ini", ini_strip_quotes=True)
    assert r["success"]
    import json as _json
    data = _json.loads(r["output"])
    assert data["app"]["name"] == "MyApp"
    assert data["app"]["version"] == 1.0  # "1.0" stripped then inferred as float
    assert data["app"]["port"] == 9000


def test_ini_strip_quotes_only_full_quotes():
    """--ini-strip-quotes only strips values that are fully wrapped in double-quotes."""
    ini_in = '[section]\npartial = say "hello"\nfull = "Default"\nnone = bare\n'
    r = convert(ini_in, "json", from_fmt="ini", ini_strip_quotes=True)
    assert r["success"]
    import json as _json
    data = _json.loads(r["output"])
    assert data["section"]["partial"] == 'say "hello"'
    assert data["section"]["full"] == "Default"
    assert data["section"]["none"] == "bare"


def test_ini_strip_quotes_off_by_default():
    """Without --ini-strip-quotes, quote characters are preserved as literal values."""
    ini_in = '[theme]\ncolor_theme = "Default"\n'
    r = convert(ini_in, "json", from_fmt="ini")
    assert r["success"]
    import json as _json
    data = _json.loads(r["output"])
    assert data["theme"]["color_theme"] == '"Default"'


def test_ini_strip_and_requote_roundtrip(tmp_path, capsys):
    """Full round-trip pipeline from yq#2456: read INI with quotes → modify → write back with quotes preserved.

    This ties together --ini-strip-quotes (parse) and --ini-quote-strings (serialize)
    so that a value like ``color_theme = "Default"`` is read without literal quote
    chars, modified, and re-quoted on write — exactly the workflow yq#2456 requests.
    """
    from core.cli import main as cli_main
    f = tmp_path / "btop.ini"
    f.write_text("[theme]\ncolor_theme = \"Default\"\ntheme_background = \"False\"\n")
    rc = cli_main(["cf", str(f), "--set", "theme.color_theme", "catppuccin",
                    "--to", "ini", "--in-place",
                    "--ini-strip-quotes", "--ini-quote-strings"])
    assert rc == 0, f"Round-trip failed with exit code {rc}"
    result = f.read_text(encoding="utf-8")
    assert 'color_theme = "catppuccin"' in result, f"Expected quoted catppuccin, got: {result!r}"
    assert 'theme_background = "False"' in result, f"Expected preserved quoted False, got: {result!r}"
    assert '\"catppuccin\"' not in result or '\\\"' not in result, "No double-wrapping"


# ── --select /regex/ + --each / --join composition tests ────────────────────

def test_each_with_select_regex(tmp_path, capsys):
    """--select FIELD=/regex/ --each extracts field from regex-matching items only."""
    import json as _json
    from core.cli import main as cli_main
    src = tmp_path / "pods.yaml"
    src.write_text(
        "- name: web-frontend\n  status: Running\n"
        "- name: api-backend\n  status: CrashLoopBackOff\n"
        "- name: web-proxy\n  status: Running\n"
        "- name: db\n  status: Pending\n"
    )
    rc = cli_main(["cf", str(src), "--select", "name=/^web/", "--each", "name", "--to", "json"])
    assert rc == 0
    result = _json.loads(capsys.readouterr().out)
    assert sorted(result) == ["web-frontend", "web-proxy"]


def test_each_with_select_regex_not_match(tmp_path, capsys):
    """--select FIELD!=/regex/ --each excludes regex-matching items before extracting."""
    import json as _json
    from core.cli import main as cli_main
    src = tmp_path / "services.yaml"
    src.write_text(
        "- name: nginx\n  port: 80\n"
        "- name: internal-api\n  port: 8080\n"
        "- name: internal-db\n  port: 5432\n"
    )
    rc = cli_main(["cf", str(src), "--select", "name!=/^internal/", "--each", "name", "--to", "json"])
    assert rc == 0
    result = _json.loads(capsys.readouterr().out)
    assert result == ["nginx"]


def test_join_with_select_regex(tmp_path, capsys):
    """--select FIELD=/regex/ --join filters before joining."""
    from core.cli import main as cli_main
    src = tmp_path / "items.yaml"
    src.write_text(
        "- host: web-01.prod\n  ip: 10.0.0.1\n"
        "- host: db-01.prod\n  ip: 10.0.0.2\n"
        "- host: web-02.prod\n  ip: 10.0.0.3\n"
    )
    rc = cli_main(["cf", str(src), "--select", "host=/^web/", "--join", "host", "--to", "json"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "web-01.prod" in out
    assert "web-02.prod" in out
    assert "db-01.prod" not in out


def test_each_select_regex_case_insensitive(tmp_path, capsys):
    """--select regex matching is case-insensitive in --each composition."""
    import json as _json
    from core.cli import main as cli_main
    src = tmp_path / "pods.yaml"
    src.write_text(
        "- name: Alpha\n  env: PROD\n"
        "- name: Beta\n  env: dev\n"
        "- name: Gamma\n  env: Prod\n"
    )
    rc = cli_main(["cf", str(src), "--select", "env=/prod/", "--each", "name", "--to", "json"])
    assert rc == 0
    result = _json.loads(capsys.readouterr().out)
    assert sorted(result) == ["Alpha", "Gamma"]


# ── --select + --sort-by / --unique composition tests ───────────────────────

def test_select_then_sort_by(tmp_path, capsys):
    """--select filters before --sort-by; both flags compose correctly."""
    import json as _json
    from core.cli import main as cli_main
    src = tmp_path / "pods.yaml"
    src.write_text(
        "- name: zeta\n  env: prod\n  replicas: 3\n"
        "- name: alpha\n  env: prod\n  replicas: 1\n"
        "- name: beta\n  env: staging\n  replicas: 2\n"
    )
    rc = cli_main(["cf", str(src), "--select", "env=prod", "--sort-by", "name", "--to", "json"])
    assert rc == 0
    result = _json.loads(capsys.readouterr().out)
    assert [r["name"] for r in result] == ["alpha", "zeta"]


def test_select_then_sort_by_desc(tmp_path, capsys):
    """--select --sort-by --sort-desc: filters then sorts descending."""
    import json as _json
    from core.cli import main as cli_main
    src = tmp_path / "services.yaml"
    src.write_text(
        "- name: svc-a\n  tier: frontend\n  port: 80\n"
        "- name: svc-b\n  tier: frontend\n  port: 443\n"
        "- name: svc-c\n  tier: backend\n  port: 8080\n"
    )
    rc = cli_main(["cf", str(src), "--select", "tier=frontend", "--sort-by", "port", "--sort-desc", "--to", "json"])
    assert rc == 0
    result = _json.loads(capsys.readouterr().out)
    assert [r["port"] for r in result] == [443, 80]


def test_select_then_unique_by(tmp_path, capsys):
    """--select filters before --unique-by; both flags compose correctly."""
    import json as _json
    from core.cli import main as cli_main
    src = tmp_path / "pods.yaml"
    src.write_text(
        "- image: nginx\n  env: prod\n"
        "- image: nginx\n  env: prod\n"
        "- image: redis\n  env: prod\n"
        "- image: nginx\n  env: dev\n"
    )
    rc = cli_main(["cf", str(src), "--select", "env=prod", "--unique-by", "image", "--to", "json"])
    assert rc == 0
    result = _json.loads(capsys.readouterr().out)
    assert len(result) == 2
    assert sorted(r["image"] for r in result) == ["nginx", "redis"]


def test_select_then_unique(tmp_path, capsys):
    """--select filters before --unique; both flags compose correctly."""
    import json as _json
    from core.cli import main as cli_main
    src = tmp_path / "items.yaml"
    src.write_text(
        "- name: a\n  active: true\n"
        "- name: a\n  active: true\n"
        "- name: b\n  active: true\n"
        "- name: c\n  active: false\n"
    )
    rc = cli_main(["cf", str(src), "--select", "active=true", "--unique", "--to", "json"])
    assert rc == 0
    result = _json.loads(capsys.readouterr().out)
    assert len(result) == 2
    assert sorted(r["name"] for r in result) == ["a", "b"]


def test_select_regex_then_sort_by(tmp_path, capsys):
    """--select /regex/ --sort-by: regex filter then sort composes correctly."""
    import json as _json
    from core.cli import main as cli_main
    src = tmp_path / "pods.yaml"
    src.write_text(
        "- name: web-03\n  status: Running\n"
        "- name: web-01\n  status: Running\n"
        "- name: db-01\n  status: Running\n"
        "- name: web-02\n  status: Pending\n"
    )
    rc = cli_main(["cf", str(src), "--select", "name=/^web/", "--sort-by", "name", "--to", "json"])
    assert rc == 0
    result = _json.loads(capsys.readouterr().out)
    assert [r["name"] for r in result] == ["web-01", "web-02", "web-03"]


# --- yq GitHub issue #2592: TOML comments in arrays ---
def test_toml_comments_in_arrays():
    """Devbench parses TOML with inline comments inside arrays (yq#2592 fails this)."""
    toml_src = (
        "[section]\n"
        "the_array = [\n"
        "  # first item\n"
        "  \"value1\",\n"
        "  # second item\n"
        "  \"value2\",\n"
        "]\n"
    )
    r = convert(toml_src, "json", source_format="toml")
    assert r["success"], r.get("error")
    parsed = json.loads(r["output"])
    parsed.pop("__cf_comments__", None)
    assert parsed == {"section": {"the_array": ["value1", "value2"]}}


# --- --explicit-start / --explicit-end / --yaml-width ---
def test_yaml_explicit_start():
    """--explicit-start emits '---' document-start marker (fixes kislyuk/yq#93)."""
    r = convert('{"key": "value"}', "yaml", explicit_start=True)
    assert r["success"]
    assert r["output"].startswith("---")
    assert "key: value" in r["output"]


def test_yaml_explicit_end():
    """--explicit-end emits '...' document-end marker."""
    r = convert('{"key": "value"}', "yaml", explicit_end=True)
    assert r["success"]
    assert r["output"].rstrip().endswith("...")


def test_yaml_explicit_start_and_end():
    """--explicit-start --explicit-end emits both markers."""
    r = convert('{"key": "value"}', "yaml", explicit_start=True, explicit_end=True)
    assert r["success"]
    assert r["output"].startswith("---")
    assert r["output"].rstrip().endswith("...")


def test_yaml_width_unlimited():
    """--yaml-width 0 disables line wrapping; long strings stay on one line."""
    long_val = "x" * 200
    r = convert(json.dumps({"url": long_val}), "yaml", yaml_width=0)
    assert r["success"]
    lines = r["output"].splitlines()
    url_line = next(l for l in lines if "url:" in l)
    assert long_val in url_line


def test_yaml_width_custom():
    """--yaml-width N wraps scalar lines at N characters."""
    long_val = "word " * 30  # 150 chars
    r = convert(json.dumps({"text": long_val.strip()}), "yaml", yaml_width=40)
    assert r["success"]
    # At least one line should be short (wrapping occurred)
    lines = [l for l in r["output"].splitlines() if l.strip()]
    assert any(len(l) <= 45 for l in lines)


# ── Blank line + comment preservation during CRUD ops (r/devops complaint) ──

def test_set_preserves_yaml_blank_lines(tmp_path, capsys):
    """--set keeps blank lines between sections (yq#1248: blank lines stripped during edits)."""
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("app: myapp\n\nversion: 1\n\ndebug: false\n")
    rc = main([str(f), "--set", "debug", "true"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "\n\n" in captured.out, "blank lines must survive --set"
    assert "debug: true" in captured.out


def test_set_preserves_yaml_comments(tmp_path, capsys):
    """--set keeps inline and leading comments when reserializing YAML."""
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("# app name\napp: myapp\nversion: 1\n")
    rc = main([str(f), "--set", "version", "2"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "app name" in captured.out, "comments must survive --set"
    assert "version: 2" in captured.out


def test_delete_preserves_yaml_blank_lines(tmp_path, capsys):
    """--delete keeps blank lines between surviving keys."""
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("app: myapp\n\nversion: 1\n\ndebug: true\n")
    rc = main([str(f), "--delete", "debug"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "\n\n" in captured.out, "blank lines must survive --delete"
    assert "debug" not in captured.out


def test_append_preserves_yaml_blank_lines(tmp_path, capsys):
    """--append keeps blank lines in surrounding YAML structure."""
    from core.configforge import main
    f = tmp_path / "config.yaml"
    f.write_text("app: myapp\n\nitems:\n  - a\n\ndebug: false\n")
    rc = main([str(f), "--append", "items", "b"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "\n\n" in captured.out, "blank lines must survive --append"
    assert "- b" in captured.out


BOM = "﻿"


def test_bom_json_stripped():
    """UTF-8 BOM at start of JSON is silently stripped (common in Windows/Excel exports)."""
    result = parse_text(BOM + '{"host": "localhost", "port": 5432}', "json")
    assert result["data"] == {"host": "localhost", "port": 5432}


def test_bom_yaml_stripped():
    """UTF-8 BOM in YAML doesn't corrupt the first key."""
    result = parse_text(BOM + "host: localhost\nport: 5432", "yaml")
    assert result["data"]["host"] == "localhost"
    assert "port" in result["data"]


def test_bom_toml_stripped():
    """UTF-8 BOM in TOML is stripped before parsing."""
    result = parse_text(BOM + '[db]\nhost = "localhost"', "toml")
    assert result["data"]["db"]["host"] == "localhost"


def test_bom_json_auto_detect():
    """BOM-prefixed JSON is auto-detected and parsed correctly."""
    result = parse_text(BOM + '{"env": "prod"}')
    assert result["format"] == "json"
    assert result["data"]["env"] == "prod"


# ── Wildcard --get (yq#2448) ─────────────────────────────────────────────────

def test_get_by_glob_single_wildcard():
    """'parent.*' returns all children of parent as (path, value) pairs."""
    from core.configforge import _get_by_glob
    data = {"block1": {"root": {"rp1": "a", "rp2": "b"}}}
    matches = _get_by_glob(data, "block1.root.*")
    paths = {p for p, _ in matches}
    vals = {v for _, v in matches}
    assert paths == {"block1.root.rp1", "block1.root.rp2"}
    assert vals == {"a", "b"}


def test_get_by_glob_leading_wildcard():
    """'*.key' returns matching key from every top-level child."""
    from core.configforge import _get_by_glob
    data = {"svc1": {"port": 80}, "svc2": {"port": 443}, "meta": {"name": "x"}}
    matches = _get_by_glob(data, "*.port")
    assert len(matches) == 2
    assert all(v in (80, 443) for _, v in matches)


def test_get_by_glob_deep_double_wildcard():
    """'*.*.host' drills two levels and collects every host value."""
    from core.configforge import _get_by_glob
    data = {"prod": {"db": {"host": "db.prod"}}, "staging": {"db": {"host": "db.stg"}}}
    matches = _get_by_glob(data, "*.*.host")
    hosts = {v for _, v in matches}
    assert hosts == {"db.prod", "db.stg"}


def test_get_by_glob_no_match_returns_empty():
    """Wildcard path that matches nothing returns an empty list."""
    from core.configforge import _get_by_glob
    data = {"a": 1}
    assert _get_by_glob(data, "b.*") == []


def test_get_by_glob_list_wildcard():
    """'items.*' fans out over list indices."""
    from core.configforge import _get_by_glob
    data = {"items": [{"name": "foo"}, {"name": "bar"}]}
    matches = _get_by_glob(data, "items.*.name")
    names = [v for _, v in matches]
    assert names == ["foo", "bar"]


def test_get_wildcard_cli(tmp_path, capsys):
    """CLI --get with * wildcard prints one 'path: value' line per match."""
    import json as _json
    from core.cli import main
    cfg = tmp_path / "cfg.json"
    cfg.write_text(_json.dumps({"services": {"web": {"port": 80}, "api": {"port": 8080}}}))
    rc = main(["cf", str(cfg), "--get", "services.*"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "services.web" in out
    assert "services.api" in out
    assert "port" in out


def test_get_wildcard_no_match_cli_uses_default(tmp_path, capsys):
    """CLI --get wildcard with --default returns default when nothing matches."""
    import json as _json
    from core.cli import main
    cfg = tmp_path / "cfg.json"
    cfg.write_text(_json.dumps({"a": 1}))
    rc = main(["cf", str(cfg), "--get", "b.*", "--default", "none"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.strip() == "none"


# ── NO_COLOR env var support (no-color.org standard) ───────────────────────

def test_no_color_env_suppresses_auto_color(tmp_path, capsys, monkeypatch):
    """NO_COLOR env var disables ANSI color even when --colors flag is absent and stdout is a TTY."""
    import json as _json
    from core.cli import main

    monkeypatch.setenv("NO_COLOR", "1")
    cfg = tmp_path / "data.json"
    cfg.write_text(_json.dumps({"key": "value"}))
    rc = main(["cf", str(cfg), "--to", "json", "--raw"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "\x1b[" not in out


def test_no_color_empty_string_also_disables(tmp_path, capsys, monkeypatch):
    """NO_COLOR='' (empty string) still disables color per the standard."""
    import json as _json
    from core.cli import main

    monkeypatch.setenv("NO_COLOR", "")
    cfg = tmp_path / "data.json"
    cfg.write_text(_json.dumps({"x": 42}))
    rc = main(["cf", str(cfg), "--to", "json", "--raw", "--colors"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "\x1b[" not in out


def test_no_no_color_env_allows_explicit_flag(tmp_path, capsys, monkeypatch):
    """Without NO_COLOR set, --no-colors flag still disables color output."""
    import json as _json
    from core.cli import main

    monkeypatch.delenv("NO_COLOR", raising=False)
    cfg = tmp_path / "data.json"
    cfg.write_text(_json.dumps({"a": "b"}))
    rc = main(["cf", str(cfg), "--to", "json", "--raw", "--no-colors"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "\x1b[" not in out


# ── Short format flags -f / -o (HN: yq users expect short flags) ───────────────


def test_short_flag_o_for_output_format(tmp_path, capsys):
    """-o is a short alias for --to (output format)."""
    import json as _json
    from core.cli import main

    cfg = tmp_path / "input.yaml"
    cfg.write_text("host: localhost\nport: 5432\n")
    rc = main(["cf", str(cfg), "-o", "json", "-r"])
    out = capsys.readouterr().out
    assert rc == 0
    data = _json.loads(out)
    assert data["host"] == "localhost"
    assert data["port"] == 5432


def test_short_flag_f_for_input_format(tmp_path, capsys):
    """-f is a short alias for --from (input format); overrides auto-detection."""
    import json as _json
    from core.cli import main

    cfg = tmp_path / "data.txt"
    cfg.write_text('{"key": "value", "num": 7}')
    rc = main(["cf", str(cfg), "-f", "json", "-o", "yaml", "-r"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "key: value" in out
    assert "num: 7" in out


def test_short_flags_f_and_o_together(tmp_path, capsys):
    """-f json -o toml round-trips through both short flags."""
    import json as _json
    from core.cli import main

    cfg = tmp_path / "data.txt"
    cfg.write_text('{"name": "devbench", "version": "1.0"}')
    rc = main(["cf", str(cfg), "-f", "json", "-o", "toml", "-r"])
    out = capsys.readouterr().out
    assert rc == 0
    assert 'name = "devbench"' in out
    assert 'version = "1.0"' in out
