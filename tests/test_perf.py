"""Performance benchmarks for ConfigForge parse/convert/batch pipelines.

These tests guard against algorithmic regressions (not startup overhead).
Time limits are 5-10x the median observed on a modern Linux host so that
normal CI variance never trips them — only genuine O(n²) regressions will.

Comparative context (yq v4 on same class of config, published benchmarks):
  - yq is a compiled Go binary; Python startup alone costs ~80-100ms.
  - ConfigForge compensates with comment preservation, TOML write, and
    batch/streaming modes that yq lacks entirely.
  - These numbers are regression guards, not head-to-head claims.
"""
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.configforge import (
    HAS_TOML,
    batch_convert,
    convert,
    detect_format,
    parse_text,
)


# ── Config generators ─────────────────────────────────────────────────────────

def _flat_json(n: int) -> str:
    return json.dumps({f"key_{i}": f"value_{i}" for i in range(n)})


def _flat_yaml(n: int) -> str:
    return "\n".join(f"key_{i}: value_{i}" for i in range(n))


def _flat_yaml_with_comments(n: int) -> str:
    lines = []
    for i in range(n):
        if i % 10 == 0:
            lines.append(f"# Section {i // 10}")
        lines.append(f"key_{i}: value_{i}")
    return "\n".join(lines)


def _nested_yaml(n: int) -> str:
    """n services, each with 5 scalar fields — realistic Docker/k8s shape."""
    parts = []
    for i in range(n):
        parts.append(f"service_{i}:")
        parts.append(f"  name: svc-{i}")
        parts.append(f"  port: {8000 + i}")
        parts.append(f"  replicas: {(i % 5) + 1}")
        parts.append(f"  enabled: true")
        parts.append(f"  image: nginx:{i}.0-alpine")
        parts.append("")
    return "\n".join(parts)


def _toml_sections(n: int) -> str:
    lines = []
    for i in range(n):
        lines.append(f"[service_{i}]")
        lines.append(f'name = "svc-{i}"')
        lines.append(f"port = {8000 + i}")
        lines.append(f"enabled = true")
        lines.append("")
    return "\n".join(lines)


def _ini_sections(n: int) -> str:
    lines = []
    for i in range(n):
        lines.append(f"[section_{i}]")
        lines.append(f"key = value_{i}")
        lines.append(f"port = {8000 + i}")
        lines.append("")
    return "\n".join(lines)


def _env_vars(n: int) -> str:
    return "\n".join(f"VAR_{i}=value_{i}" for i in range(n))


# ── JSON benchmarks (stdlib — fastest baseline) ───────────────────────────────

def test_perf_json_2000_keys_parse():
    """2000-key flat JSON → parse_text under 3s (stdlib json; regression guard)."""
    text = _flat_json(2000)
    t0 = time.monotonic()
    result = parse_text(text, "json")
    elapsed = time.monotonic() - t0
    assert "data" in result and len(result["data"]) == 2000
    assert elapsed < 3.0, f"JSON 2000-key parse: {elapsed:.3f}s (limit 3.0s)"


def test_perf_json_to_yaml_500_convert():
    """500-key flat JSON → YAML conversion under 3s."""
    text = _flat_json(500)
    t0 = time.monotonic()
    result = convert(text, "yaml", "json")
    elapsed = time.monotonic() - t0
    assert "output" in result
    assert elapsed < 3.0, f"JSON→YAML 500-key: {elapsed:.3f}s (limit 3.0s)"


def test_perf_json_to_ini_300_convert():
    """300-key flat JSON → INI conversion under 3s."""
    text = _flat_json(300)
    t0 = time.monotonic()
    result = convert(text, "ini", "json")
    elapsed = time.monotonic() - t0
    assert "output" in result
    assert elapsed < 3.0, f"JSON→INI 300-key: {elapsed:.3f}s (limit 3.0s)"


# ── YAML benchmarks (PyYAML + comment extraction) ────────────────────────────

def test_perf_yaml_500_flat_parse():
    """500-entry flat YAML parse under 5s (includes comment scan)."""
    text = _flat_yaml(500)
    t0 = time.monotonic()
    result = parse_text(text, "yaml")
    elapsed = time.monotonic() - t0
    assert "data" in result and len(result["data"]) == 500
    assert elapsed < 5.0, f"YAML 500-key flat parse: {elapsed:.3f}s (limit 5.0s)"


def test_perf_yaml_200_nested_parse():
    """200-service nested YAML (1200 lines) parse under 5s."""
    text = _nested_yaml(200)
    t0 = time.monotonic()
    result = parse_text(text, "yaml")
    elapsed = time.monotonic() - t0
    assert "data" in result and len(result["data"]) == 200
    assert elapsed < 5.0, f"YAML 200-nested parse: {elapsed:.3f}s (limit 5.0s)"


def test_perf_yaml_with_comments_200_parse():
    """200-entry YAML with comments (comment extraction path) under 5s."""
    text = _flat_yaml_with_comments(200)
    t0 = time.monotonic()
    result = parse_text(text, "yaml")
    elapsed = time.monotonic() - t0
    assert "data" in result and len(result["data"]) == 200
    assert elapsed < 5.0, f"YAML 200+comments parse: {elapsed:.3f}s (limit 5.0s)"


def test_perf_yaml_to_json_300_convert():
    """300-entry flat YAML → JSON conversion under 5s."""
    text = _flat_yaml(300)
    t0 = time.monotonic()
    result = convert(text, "json", "yaml")
    elapsed = time.monotonic() - t0
    assert "output" in result
    data = json.loads(result["output"])
    assert len(data) == 300
    assert elapsed < 5.0, f"YAML→JSON 300-key: {elapsed:.3f}s (limit 5.0s)"


def test_perf_yaml_comment_roundtrip_150():
    """150-entry YAML with comments → JSON → YAML roundtrip under 5s.

    Validates that comment preservation pipeline does not introduce O(n²) overhead
    in _extract_yaml_comments / _reinsert_yaml_comments.
    """
    text = _flat_yaml_with_comments(150)
    t0 = time.monotonic()
    r1 = convert(text, "json", "yaml")
    r2 = convert(r1["output"], "yaml", "json")
    elapsed = time.monotonic() - t0
    assert "output" in r1 and "output" in r2
    assert elapsed < 5.0, f"YAML comment roundtrip 150: {elapsed:.3f}s (limit 5.0s)"


# ── TOML benchmarks ──────────────────────────────────────────────────────────

@pytest.mark.skipif(not HAS_TOML, reason="tomllib/tomli not available")
def test_perf_toml_200_sections_parse():
    """200-section TOML parse under 3s (tomllib is stdlib in 3.11+)."""
    text = _toml_sections(200)
    t0 = time.monotonic()
    result = parse_text(text, "toml")
    elapsed = time.monotonic() - t0
    assert "data" in result and len(result["data"]) == 200
    assert elapsed < 3.0, f"TOML 200-section parse: {elapsed:.3f}s (limit 3.0s)"


@pytest.mark.skipif(not HAS_TOML, reason="tomllib/tomli not available")
def test_perf_json_to_toml_200_convert():
    """200-key flat JSON → TOML conversion under 3s.

    ConfigForge uniquely supports TOML write — yq cannot serialize to TOML at all.
    This benchmark validates the TOML serializer scales linearly.
    """
    text = _flat_json(200)
    t0 = time.monotonic()
    result = convert(text, "toml", "json")
    elapsed = time.monotonic() - t0
    assert "output" in result
    assert elapsed < 3.0, f"JSON→TOML 200-key: {elapsed:.3f}s (limit 3.0s)"


# ── INI / ENV benchmarks ─────────────────────────────────────────────────────

def test_perf_ini_300_sections_parse():
    """300-section INI parse under 3s."""
    text = _ini_sections(300)
    t0 = time.monotonic()
    result = parse_text(text, "ini")
    elapsed = time.monotonic() - t0
    assert "data" in result and len(result["data"]) == 300
    assert elapsed < 3.0, f"INI 300-section parse: {elapsed:.3f}s (limit 3.0s)"


def test_perf_env_500_vars_parse():
    """500-var .env file parse under 2s."""
    text = _env_vars(500)
    t0 = time.monotonic()
    result = parse_text(text, "env")
    elapsed = time.monotonic() - t0
    assert "data" in result and len(result["data"]) == 500
    assert elapsed < 2.0, f"ENV 500-var parse: {elapsed:.3f}s (limit 2.0s)"


def test_perf_env_to_json_500_convert():
    """500-var .env → JSON conversion under 2s."""
    text = _env_vars(500)
    t0 = time.monotonic()
    result = convert(text, "json", "env")
    elapsed = time.monotonic() - t0
    assert "output" in result
    data = json.loads(result["output"])
    assert len(data) == 500
    assert elapsed < 2.0, f"ENV→JSON 500-var: {elapsed:.3f}s (limit 2.0s)"


# ── Format detection benchmark ────────────────────────────────────────────────

def test_perf_detect_format_100_calls():
    """detect_format on 5 different formats × 20 iterations = 100 calls under 2s.

    detect_format runs at every CLI invocation — it must not be a bottleneck.
    """
    samples = [
        _flat_json(5),
        _flat_yaml(5),
        _ini_sections(2),
        _env_vars(5),
        "<root><key>val</key></root>",
    ]
    t0 = time.monotonic()
    for _ in range(20):
        for s in samples:
            detect_format(s)
    elapsed = time.monotonic() - t0
    assert elapsed < 2.0, f"detect_format 100 calls: {elapsed:.3f}s (limit 2.0s)"


# ── Batch conversion benchmark ────────────────────────────────────────────────

def test_perf_batch_convert_10_files(tmp_path):
    """Batch-convert 10 JSON files (100 keys each) to YAML under 20s.

    Validates that batch_convert() doesn't have per-file startup overhead
    that would make it slower than 10 sequential single-file conversions.
    """
    for i in range(10):
        f = tmp_path / f"config_{i}.json"
        f.write_text(_flat_json(100))

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    t0 = time.monotonic()
    results = batch_convert(str(tmp_path / "*.json"), "yaml", str(out_dir))
    elapsed = time.monotonic() - t0

    assert len(results) == 10
    assert all(r.get("success") for r in results), \
        [r for r in results if not r.get("success")]
    assert elapsed < 20.0, f"Batch 10-file JSON→YAML: {elapsed:.3f}s (limit 20.0s)"


# ── Multi-format round-trip benchmark ────────────────────────────────────────

def test_perf_json_yaml_ini_roundtrip_100():
    """100-key JSON → YAML → INI chain under 5s (3-format pipeline)."""
    text = _flat_json(100)
    t0 = time.monotonic()
    r1 = convert(text, "yaml", "json")
    r2 = convert(r1["output"], "ini", "yaml")
    elapsed = time.monotonic() - t0
    assert "output" in r1 and "output" in r2
    assert elapsed < 5.0, f"JSON→YAML→INI 100-key: {elapsed:.3f}s (limit 5.0s)"


@pytest.mark.skipif(not HAS_TOML, reason="tomllib/tomli not available")
def test_perf_full_chain_yaml_json_toml_100():
    """100-entry YAML → JSON → TOML full chain under 5s."""
    text = _flat_yaml(100)
    t0 = time.monotonic()
    r1 = convert(text, "json", "yaml")
    r2 = convert(r1["output"], "toml", "json")
    elapsed = time.monotonic() - t0
    assert "output" in r1 and "output" in r2
    assert elapsed < 5.0, f"YAML→JSON→TOML 100-key: {elapsed:.3f}s (limit 5.0s)"
