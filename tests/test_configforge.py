"""ConfigForge — conversion engine tests."""
import sys, os, json
import yaml
import tomllib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.configforge import convert, convert_file, batch_convert, batch_convert_stream, detect_format, SUPPORTED_FORMATS

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
    assert r["error"] is not None

def test_empty_input():
    r = convert("", "json")
    assert not r["success"]
    assert r["error"]

def test_supported_formats():
    expected_formats = ["json", "yaml", "toml", "xml", "csv", "ini", "env", "hcl", "properties"]
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
    assert isinstance(parsed["section"]["count"], int)

def test_ini_type_inference_float():
    """INI value '3.14' should parse as float, not string."""
    r = convert("[section]\npi=3.14\n", "json")
    assert r["success"]
    parsed = json.loads(r["output"])
    assert parsed["section"]["pi"] == 3.14
    assert isinstance(parsed["section"]["pi"], float)

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
    assert isinstance(parsed["section"]["name"], str)

def test_ini_type_inference_mixed_types():
    """INI section with mixed types should infer each correctly."""
    r = convert("[config]\nname=app\nport=8080\ndebug=false\nrate=0.75\n", "json")
    assert r["success"]
    parsed = json.loads(r["output"])
    assert parsed["config"]["name"] == "app"
    assert parsed["config"]["port"] == 8080 and isinstance(parsed["config"]["port"], int)
    assert parsed["config"]["debug"] is False
    assert parsed["config"]["rate"] == 0.75 and isinstance(parsed["config"]["rate"], float)

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
    assert isinstance(result["data"]["section"]["val"], int)

# -- Feature: Batch glob mode --
def test_batch_convert_empty_glob(tmp_path):
    """Empty glob returns empty list with no errors."""
    results = batch_convert(str(tmp_path / "nonexistent_*.json"), "yaml")
    assert results == []

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