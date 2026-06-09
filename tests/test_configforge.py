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
    expected_formats = ["json", "jsonc", "yaml", "toml", "xml", "csv", "ini", "env", "hcl", "properties", "plist"]
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
    results = batch_convert(str(tmp_path / "*.json"), "yaml", str(tmp_path / "yaml_out"))
    captured = capsys.readouterr()
    assert "[batch]" in captured.out
    assert "[1/2]" in captured.out
    assert "[2/2]" in captured.out
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


# ── .env type inference (yq issue #643 complaint) ──
# yq v4 broke environment variable type handling — quoted vars forced to string,
# losing int/float/bool types. ConfigForge infers types for unquoted .env values.

def test_env_infer_int():
    from core.configforge import parse_text
    r = parse_text("PORT=8080\nCOUNT=0", fmt="env")
    assert r["data"]["PORT"] == 8080
    assert isinstance(r["data"]["PORT"], int)
    assert r["data"]["COUNT"] == 0
    assert isinstance(r["data"]["COUNT"], int)


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
    assert isinstance(r["data"]["TIMEOUT"], float)
    assert r["data"]["RATIO"] == 0.75


def test_env_quoted_stays_string():
    """Double-quoted and single-quoted values must remain strings regardless of content."""
    from core.configforge import parse_text
    r = parse_text('PORT="8080"\nDEBUG=\'true\'\nNUM=\'42\'', fmt="env")
    assert r["data"]["PORT"] == "8080"
    assert isinstance(r["data"]["PORT"], str)
    assert r["data"]["DEBUG"] == "true"
    assert isinstance(r["data"]["DEBUG"], str)
    assert r["data"]["NUM"] == "42"
    assert isinstance(r["data"]["NUM"], str)


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
    assert isinstance(r["data"]["NAME"], str)
    assert r["data"]["EMPTY"] == ""


# ── MEDIUM-NEW4: parse_text() ValueError → clean error message, not traceback ──

def test_get_malformed_input_clean_error(tmp_path, capsys):
    """--get on malformed YAML prints a clean error, not a raw traceback."""
    from core.configforge import main
    f = tmp_path / "bad.yaml"
    f.write_text("key: : invalid: :\n")
    rc = main([str(f), "--get", "key", "-f", "yaml"])
    captured = capsys.readouterr()
    assert rc == 1
    assert captured.err.startswith("error:")
    assert "Traceback" not in captured.err


def test_set_malformed_input_returns_1(tmp_path, capsys):
    """--set on malformed YAML input returns exit code 1 with a clean message."""
    from core.configforge import main
    f = tmp_path / "bad.yaml"
    f.write_text("key: : invalid: :\n")
    rc = main([str(f), "--set", "key", "val", "-f", "yaml"])
    captured = capsys.readouterr()
    assert rc == 1
    assert captured.err.startswith("error:")
    assert "Traceback" not in captured.err


def test_delete_malformed_input_returns_1(tmp_path, capsys):
    """--delete on malformed YAML input returns exit code 1 with a clean message."""
    from core.configforge import main
    f = tmp_path / "bad.yaml"
    f.write_text("key: : invalid: :\n")
    rc = main([str(f), "--delete", "key", "-f", "yaml"])
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
    rc = main([str(base), "--merge", str(overlay), "-f", "yaml"])
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
    rc = main([str(base), "--merge", str(overlay), "-f", "yaml"])
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
