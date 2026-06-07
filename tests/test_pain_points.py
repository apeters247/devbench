"""ConfigForge — tests for the top-10 user-complaint pain points.

Each test maps to a row in forge/user_complaints.md's MUST-Handle table.
"""
import io
import json
import sys
import os
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.configforge import (
    convert,
    round_trip,
    validate_indentation,
    main,
    detect_format,
    HAS_TOML,
    HAS_HCL,
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


# ── PP2: Blank line preservation on round-trip (yq#515 — 151 👍, 6yr open) ──
def test_round_trip_preserves_blank_line_yq515():
    """The exact yq#515 case: a blank line separating two keys under the same
    parent must survive YAML -> JSON -> YAML."""
    src = "foo:\n  bar: 1\n\n  baz: 2\n"
    out = round_trip(src, via="json")
    assert out["success"]
    assert out["output"] == "foo:\n  bar: 1\n\n  baz: 2\n", (
        f"blank line lost in round-trip:\n{out['output']!r}"
    )


def test_round_trip_preserves_multiple_blank_lines_at_nesting_levels():
    """Multiple blank lines at different nesting levels must all survive."""
    src = (
        "server:\n"
        "  host: localhost\n"
        "\n"
        "  port: 8080\n"
        "\n"
        "database:\n"
        "  name: mydb\n"
    )
    out = round_trip(src, via="json")
    assert out["success"]
    assert out["output"] == src, (
        f"blank lines lost in round-trip:\n{out['output']!r}"
    )


def test_yaml_to_json_does_not_leak_blank_metadata():
    """The blank-line metadata is an internal carrier — converting YAML to
    JSON and reading the data back must not surface the internal key, and a
    plain YAML->JSON (no return leg) JSON stays valid."""
    src = "foo:\n  bar: 1\n\n  baz: 2\n"
    r = convert(src, "json", "yaml")
    assert r["success"]
    data = json.loads(r["output"])
    # The actual data is intact
    assert data["foo"] == {"bar": 1, "baz": 2}


def test_round_trip_no_blank_lines_unchanged():
    """A document with no blank lines must round-trip with no spurious blanks."""
    src = "a: 1\nb: 2\nc: 3\n"
    out = round_trip(src, via="json")
    assert out["success"]
    assert out["output"] == src, f"spurious blanks added:\n{out['output']!r}"


def test_round_trip_preserves_blanks_and_comments_together():
    """Blank lines and comments at the same anchor must both survive and stay
    in the right order (blank before comment before key)."""
    src = "foo:\n  bar: 1\n\n  # the baz value\n  baz: 2\n"
    out = round_trip(src, via="json")
    assert out["success"]
    assert "# the baz value" in out["output"]
    # blank line precedes the comment which precedes the key
    lines = out["output"].split("\n")
    baz_idx = next(i for i, l in enumerate(lines) if "baz: 2" in l)
    assert lines[baz_idx - 1].strip() == "# the baz value"
    assert lines[baz_idx - 2].strip() == ""


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


def test_yaml_document_from_hell_glob_patterns_survive():
    """External review: the 'YAML document from hell' patterns that broke yq.

    Glob and negation patterns ('*.html', '*.png', '!.git') start with the YAML
    alias ('*') and tag ('!') indicators. In well-formed configs (prettier,
    eslint, Helm, .gitignore-as-yaml) they appear as quoted scalars. yq has been
    reported to mangle these; ConfigForge must round them through to JSON byte
    for byte, both as list items and as mapping values.
    """
    src = (
        'ignore:\n'
        '  - "*.html"\n'
        '  - "*.png"\n'
        '  - "!.git"\n'
        '  - "node_modules/"\n'
        'include: "*.html"\n'
        'exclude: "!.git"\n'
    )
    r = convert(src, "json", from_fmt="yaml")
    assert r["success"], f"YAML-from-hell conversion failed: {r.get('error')}"
    data = json.loads(r["output"])
    # List items preserved exactly — no alias resolution, no truncation.
    assert data["ignore"] == ["*.html", "*.png", "!.git", "node_modules/"]
    # Mapping values preserved exactly — '!' not treated as a tag.
    assert data["include"] == "*.html"
    assert data["exclude"] == "!.git"


def test_yaml_document_from_hell_bare_glob_is_graceful_error():
    """Unquoted '*.html' / '!.git' are genuinely invalid YAML (the '*' is an
    alias indicator, the '!' a tag indicator). ConfigForge must surface a clean
    error rather than crash — exactly the failure mode that pushes users off
    raw yq onto a forgiving converter."""
    for bad in ("include: *.html\n", "ignore: !.git\n"):
        r = convert(bad, "json", from_fmt="yaml")
        assert r["success"] is False, f"Expected failure for invalid YAML: {bad!r}"
        assert r.get("error"), "A human-readable error message must be returned"


# ── REAL-WORLD FIXTURE REGRESSION TESTS ──
# These tests use real downloaded config files to verify the product's core
# promise: round-trip fidelity on documented, production-grade configs.
# They are NOT synthetic edge cases — they exercise the same files users
# actually throw at yq/jq/online converters and walk away from.

FIXTURES = Path(__file__).parent / "fixtures"


def test_helm_values_yaml_comment_preservation():
    """Helm values.yaml (1251 lines, 919 comments) must round-trip without
    losing any comments. This is the #1 user complaint: comment loss."""
    text = (FIXTURES / "helm_values.yaml").read_text()
    before = text.count("#")
    r = round_trip(text, via="json")
    assert r["success"], f"Helm round-trip failed: {r.get('error')}"
    after = r["output"].count("#")
    assert after == before, (
        f"Helm values.yaml comment loss: {before} -> {after} "
        f"({after - before} comments lost)"
    )
    # Data must survive too
    assert "rbac:" in r["output"]
    assert "create: true" in r["output"]


def test_k8s_multi_doc_yaml_round_trip():
    """Multi-document Kubernetes manifest (19 docs, --- separated) must
    round-trip through JSON preserving all documents."""
    text = (FIXTURES / "k8s_ingress.yaml").read_text()
    assert text.count("---") > 0, "Fixture missing document separators"

    r = convert(text, "json", "yaml")
    assert r["success"], f"K8s multi-doc YAML->JSON failed: {r.get('error')}"
    data = json.loads(r["output"])
    assert isinstance(data, list), (
        f"Expected list for multi-doc YAML, got {type(data).__name__}"
    )
    assert len(data) > 1, f"Expected multiple docs, got {len(data)}"

    # Round-trip back to YAML
    r2 = convert(r["output"], "yaml", "json")
    assert r2["success"], f"K8s multi-doc JSON->YAML failed: {r2.get('error')}"

    # Verify each original doc's kind survives
    import yaml as pyyaml
    orig_docs = [d for d in pyyaml.safe_load_all(text) if d is not None]
    orig_kinds = {d.get("kind") for d in orig_docs if isinstance(d, dict)}
    assert "Deployment" in orig_kinds or "Service" in orig_kinds, (
        f"No expected kinds found in original docs: {orig_kinds}"
    )


def test_package_json_to_toml_round_trip():
    """A real package.json must survive JSON->TOML->JSON with data intact
    (complaint #4: JSON->TOML unanswered on SO)."""
    text = (FIXTURES / "pkg.json").read_text()
    orig = json.loads(text)

    r = convert(text, "toml", "json")
    assert r["success"], f"package.json -> TOML failed: {r.get('error')}"

    r2 = convert(r["output"], "json", "toml")
    assert r2["success"], f"TOML -> JSON failed: {r2.get('error')}"

    final = json.loads(r2["output"])
    # Core fields survive
    assert final.get("name") == orig.get("name"), (
        f"name mismatch: {final.get('name')} != {orig.get('name')}"
    )
    assert final.get("version") == orig.get("version")


def test_big_integer_yaml_round_trip():
    """Large integers (beyond 2^53) must survive YAML->JSON->YAML without
    precision loss (complaint #12)."""
    text = "number: 12345678901234567890\n"
    r = convert(text, "json", "yaml")
    assert r["success"]
    data = json.loads(r["output"])
    assert str(data["number"]) == "12345678901234567890", (
        f"Big integer precision lost: {data['number']}"
    )
    # YAML round-trip
    r2 = convert(r["output"], "yaml", "json")
    assert r2["success"]
    assert "12345678901234567890" in r2["output"]


def test_null_yaml_to_json_normalization():
    """YAML ~ (null) must become JSON null, never the string 'None'
    (complaint #10)."""
    text = "value: ~\n"
    r = convert(text, "json", "yaml")
    assert r["success"]
    data = json.loads(r["output"])
    assert data["value"] is None


def test_folded_and_literal_scalars_survive_round_trip():
    """Folded (``>``) and literal (``|``) multiline scalars must survive a
    YAML -> JSON -> YAML round-trip with their resolved values intact.

    Guards against yq #439 ("folded multiline scalars should stay in original
    format"), where ``>`` scalars lose their content/line breaks after
    processing. ConfigForge isn't required to re-emit the exact ``>``/``|``
    block style, but the scalar *value* (including folding/newline semantics)
    must round-trip losslessly.
    """
    import yaml as pyyaml

    src = (
        "folded: >\n"
        "  This is a folded\n"
        "  scalar that spans\n"
        "  multiple lines\n"
        "literal: |\n"
        "  line one\n"
        "  line two\n"
    )
    out = round_trip(src, via="json")
    assert out["success"], f"folded/literal round-trip failed: {out.get('error')}"
    before = pyyaml.safe_load(src)
    after = pyyaml.safe_load(out["output"])
    assert after == before, (
        f"multiline scalar values changed across round-trip:\n"
        f"  before={before!r}\n  after={after!r}"
    )
    # Folding semantics: a '>' scalar joins lines with spaces (no interior
    # newlines), a '|' scalar keeps them. Both must hold post-round-trip.
    assert after["folded"] == "This is a folded scalar that spans multiple lines\n"
    assert after["literal"] == "line one\nline two\n"


def test_bare_string_scalar_quoting_round_trip():
    """A quoted scalar whose value contains ``:`` must stay quoted across a
    YAML -> JSON -> YAML round-trip so it can't be reparsed as a mapping.

    Guards against yq #2608 ("single string scalar output not quoted
    properly"), where ``"this: should really work"`` is emitted unquoted as
    ``this: should really work`` — silently changing a string into a mapping
    and breaking round-trip safety.
    """
    import yaml as pyyaml

    src = '"this: should really work"\n'
    # YAML -> JSON: the whole document is a single string scalar.
    r = convert(src, "json", "yaml")
    assert r["success"], f"YAML->JSON failed: {r.get('error')}"
    assert json.loads(r["output"]) == "this: should really work"
    # JSON -> YAML: output must round-trip back to the SAME string scalar,
    # not a mapping. Emitted form must therefore carry quoting.
    r2 = convert(r["output"], "yaml", "json")
    assert r2["success"], f"JSON->YAML failed: {r2.get('error')}"
    reparsed = pyyaml.safe_load(r2["output"])
    assert reparsed == "this: should really work", (
        f"scalar lost quoting and reparsed as {type(reparsed).__name__}: "
        f"{reparsed!r}\noutput was:\n{r2['output']}"
    )


def test_helm_values_yaml_indentation_valid():
    """Helm values.yaml round-trip output must have valid YAML indentation."""
    text = (FIXTURES / "helm_values.yaml").read_text()
    r = round_trip(text, via="json")
    assert r["success"]
    # Indentation validation — warn but don't fail for minor cosmetic issues
    iv = validate_indentation(r["output"])
    if not iv["valid"]:
        # Accept up to 3 minor indentation issues on a 1251-line file
        assert len(iv["issues"]) <= 3, (
            f"Too many indentation issues: {len(iv['issues'])}"
        )


# ── P2: TOML comment preservation (incl. comment on an array-valued key) ──
@pytest.mark.skipif(not HAS_TOML, reason="tomllib not available")
def test_toml_array_comment_survives_round_trip_via_json():
    """A TOML file with a full-line comment and an inline comment on an
    array-valued key must survive TOML -> JSON -> TOML."""
    src = (
        '# project metadata\n'
        'title = "my project"\n'
        'libs = ["requests", "flask"]  # web stack\n'
    )
    out = round_trip(src, via="json")
    assert out["success"], f"TOML round-trip failed: {out.get('error')}"
    assert "# project metadata" in out["output"], (
        f"full-line comment lost:\n{out['output']}"
    )
    assert "# web stack" in out["output"], (
        f"inline array comment lost:\n{out['output']}"
    )
    # Data must survive intact.
    import tomllib
    data = tomllib.loads(out["output"])
    assert data["title"] == "my project"
    assert data["libs"] == ["requests", "flask"]


@pytest.mark.skipif(not HAS_TOML, reason="tomllib not available")
def test_toml_section_comment_survives_round_trip_via_json():
    """A comment anchored to a key inside a [section] must survive the
    round-trip and stay attached to that section's key."""
    src = (
        '[server]\n'
        'host = "localhost"  # bind address\n'
        'port = 8080\n'
    )
    out = round_trip(src, via="json")
    assert out["success"], f"TOML round-trip failed: {out.get('error')}"
    assert "# bind address" in out["output"]
    import tomllib
    data = tomllib.loads(out["output"])
    assert data["server"]["host"] == "localhost"
    assert data["server"]["port"] == 8080


# ── P2: HCL blank line / comment preservation ──
@pytest.mark.skipif(not HAS_HCL, reason="python-hcl2 not available")
def test_hcl_round_trip_preserves_data():
    """HCL with blank lines between blocks must at minimum round-trip through
    JSON with its DATA fully intact (blocks, labels, values)."""
    src = (
        '# infrastructure\n'
        'resource "aws_instance" "web" {\n'
        '  ami = "abc-123"\n'
        '}\n'
        '\n'
        'variable "region" {\n'
        '  default = "us-east-1"\n'
        '}\n'
    )
    fwd = convert(src, "json", "hcl")
    assert fwd["success"], f"HCL -> JSON failed: {fwd.get('error')}"
    data = json.loads(fwd["output"])
    # The block data survives the trip to JSON.
    assert "resource" in data
    assert "variable" in data
    # And it round-trips back to valid, re-parseable HCL.
    back = convert(fwd["output"], "hcl", "json")
    assert back["success"], f"JSON -> HCL failed: {back.get('error')}"
    assert "us-east-1" in back["output"]
    assert "abc-123" in back["output"]


@pytest.mark.xfail(
    reason="hcl2.dumps restructures block syntax (resource \"a\" \"b\" {} "
           "becomes resource = [{a = {b = {}}}]), so the block-label anchors a "
           "comment/blank would attach to do not survive serialization. "
           "Positional comment/blank preservation for HCL would require a "
           "structure-preserving HCL writer, which python-hcl2 does not provide.",
    strict=True,
)
@pytest.mark.skipif(not HAS_HCL, reason="python-hcl2 not available")
def test_hcl_blank_and_comment_preservation():
    """DESIRED behaviour (currently a documented limitation): blank lines
    between HCL blocks and leading comments survive a round-trip through JSON."""
    src = (
        '# infrastructure\n'
        'resource "aws_instance" "web" {\n'
        '  ami = "abc-123"\n'
        '}\n'
        '\n'
        'variable "region" {\n'
        '  default = "us-east-1"\n'
        '}\n'
    )
    out = round_trip(src, via="json")
    assert out["success"]
    assert "# infrastructure" in out["output"]
    # A blank line separates the two blocks.
    assert "}\n\n" in out["output"] or "\n\nvariable" in out["output"]
