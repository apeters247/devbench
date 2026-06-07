"""ConfigForge — tests for the top-10 user-complaint pain points.

Each test maps to a row in forge/user_complaints.md's MUST-Handle table.
"""
import io
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.configforge import (
    convert,
    round_trip,
    validate_indentation,
    main,
    detect_format,
)


# ── PP1: Comment loss on round-trip (YAML -> JSON -> YAML) ──
def test_round_trip_preserves_comments_via_json():
    src = "# header note\nname: test  # the name\nport: 8080\n"
    out = round_trip(src, via="json")
    assert out["success"]
    assert "# header note" in out["output"]
    assert "# the name" in out["output"]
    # data must survive intact too
    assert "name: test" in out["output"]
    assert "8080" in out["output"]


def test_round_trip_ini_via_json():
    src = "; top comment\n[server]\nhost = localhost  ; inline\n"
    out = round_trip(src, via="json")
    assert out["success"]
    assert "top comment" in out["output"]


# ── PP3: Unified CLI tool ──
def test_cli_file_to_stdout(tmp_path, capsys):
    f = tmp_path / "c.json"
    f.write_text('{"a": 1, "b": {"c": 2}}')
    rc = main([str(f), "--to", "yaml"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "a: 1" in out


def test_cli_stdin_to_stdout(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"x": 5}'))
    rc = main(["--to", "yaml", "--from", "json"])
    assert rc == 0
    assert "x: 5" in capsys.readouterr().out


def test_cli_writes_output_file(tmp_path):
    src = tmp_path / "in.json"
    src.write_text('{"k": "v"}')
    dst = tmp_path / "out.yaml"
    rc = main([str(src), "-o", str(dst)])
    assert rc == 0
    assert "k: v" in dst.read_text()


def test_cli_bad_input_returns_nonzero(tmp_path, capsys):
    f = tmp_path / "bad.json"
    f.write_text("{not valid json")
    rc = main([str(f), "--to", "yaml", "--from", "json"])
    assert rc != 0


# ── PP4: YAML indentation validation ──
def test_validate_indentation_consistent():
    good = "a:\n  b: 1\n  c:\n    d: 2\n"
    res = validate_indentation(good)
    assert res["valid"] is True
    assert res["issues"] == []


def test_validate_indentation_detects_mixed():
    bad = "a:\n  b: 1\n   c: 2\n"  # 3-space indent breaks the 2-space step
    res = validate_indentation(bad)
    assert res["valid"] is False
    assert res["issues"]


def test_convert_yaml_output_is_valid_indentation():
    r = convert('{"a": {"b": {"c": [1, 2, 3]}}}', "yaml")
    assert r["success"]
    assert validate_indentation(r["output"])["valid"]


# ── PP6: XML verbosity / flatten ──
def test_xml_flatten_reduces_nesting():
    xml = "<root><project><name>app</name><version>1.0</version></project></root>"
    deep = convert(xml, "json")
    flat = convert(xml, "json", flatten_xml=True)
    assert flat["success"]
    data = json.loads(flat["output"])
    # Flattened output uses dotted keys instead of nested dicts.
    assert "project.name" in data
    assert data["project.name"] == "app"
    # And it is genuinely less nested than the default.
    deep_data = json.loads(deep["output"])
    assert isinstance(deep_data.get("project"), dict)


# ── PP9: Timestamp type loss (JSON -> TOML) ──
def test_json_to_toml_emits_native_datetime():
    j = '{"created_at": "2024-01-15T10:30:00Z", "day": "2024-01-15"}'
    r = convert(j, "toml")
    assert r["success"]
    # Native TOML datetime/date is UNQUOTED.
    assert 'created_at = 2024-01-15T10:30:00' in r["output"]
    assert 'created_at = "2024-01-15' not in r["output"]
    assert "day = 2024-01-15" in r["output"]


def test_json_to_toml_infer_dates_can_be_disabled():
    j = '{"created_at": "2024-01-15T10:30:00Z"}'
    r = convert(j, "toml", infer_dates=False)
    assert r["success"]
    assert 'created_at = "2024-01-15T10:30:00Z"' in r["output"]


# ── PP10: Null value handling ──
def test_toml_null_handling_skip_default():
    r = convert('{"a": 1, "b": null}', "toml")
    assert r["success"]
    assert "a = 1" in r["output"]
    assert "b =" not in r["output"]  # skipped by default


def test_toml_null_handling_comment():
    r = convert('{"a": 1, "b": null}', "toml", null_handling="comment")
    assert r["success"]
    assert "# b = null" in r["output"]  # explicitly noted, not silently dropped


def test_toml_null_handling_empty():
    r = convert('{"b": null}', "toml", null_handling="empty")
    assert r["success"]
    assert 'b = ""' in r["output"]


def test_yaml_tilde_null_to_json_is_real_null():
    # YAML ~ must become JSON null, never the string "None".
    r = convert("timeout: ~\nname: x\n", "json")
    assert r["success"]
    data = json.loads(r["output"])
    assert data["timeout"] is None
