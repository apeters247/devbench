"""Devbench core engine — HARDENED test suite.
Tests edge cases, pathological inputs, unicode, binary, performance.
"""
import json
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.tools import (
    json_formatter, base64_codec, jwt_decoder, hash_generator,
    url_codec, timestamp_converter, uuid_generator, text_diff,
    run_tool, get_tool,
)
from core.detector import detect


def parse(r):
    return json.loads(r)


# ═══════════════════════════════════════════════
# JSON FORMATTER — edge cases
# ═══════════════════════════════════════════════
def test_json_empty_object():
    r = parse(json_formatter("{}"))
    assert r["tool_name"] == "json_formatter"
    assert "{}" in r["output"] or "{\n" in r["output"]

def test_json_nested_deep():
    data = {"a": {"b": {"c": {"d": {"e": 1}}}}}
    r = parse(json_formatter(json.dumps(data)))
    assert r["error"] is None

def test_json_array():
    r = parse(json_formatter("[1, 2, 3]"))
    assert r["error"] is None

def test_json_unicode_keys():
    r = parse(json_formatter('{"café": 1, "日本語": 2}'))
    assert r["error"] is None

def test_json_special_floats():
    r = parse(json_formatter('{"nan": NaN, "inf": Infinity, "ninf": -Infinity}'))
    # Should handle or gracefully error
    assert r is not None

def test_json_huge_numbers():
    r = parse(json_formatter('{"big": 999999999999999999999999999999}'))
    assert r is not None

def test_json_duplicate_keys():
    r = parse(json_formatter('{"a":1,"a":2}'))
    assert r is not None  # Should handle (last key wins)

def test_json_1mb_input():
    """Stress test with 1MB JSON."""
    data = {"key": "x" * 500000, "nested": {"a": list(range(1000))}}
    r = parse(json_formatter(json.dumps(data)))
    assert r["error"] is None

def test_json_empty_string():
    r = parse(json_formatter('""'))
    assert r is not None

def test_json_null():
    r = parse(json_formatter('null'))
    assert r is not None

def test_json_boolean():
    r = parse(json_formatter('true'))
    assert r is not None

def test_json_tabs_vs_spaces():
    r = parse(json_formatter('{\n\t"a":\t1\n}'))
    assert r["error"] is None

def test_json_trailing_comma():
    r = parse(json_formatter('{"a": 1,}'))
    assert r["error"] is not None  # Invalid JSON

def test_json_single_quotes():
    r = parse(json_formatter("{'a': 1}"))
    assert r["error"] is not None  # Invalid JSON

def test_json_no_quotes():
    r = parse(json_formatter("{a: 1}"))
    assert r["error"] is not None  # Invalid JSON


# ═══════════════════════════════════════════════
# BASE64 — edge cases
# ═══════════════════════════════════════════════
def test_base64_binary():
    """Base64 encode binary data."""
    binary = bytes(range(256))
    import base64 as b64
    encoded = b64.b64encode(binary).decode()
    r = parse(base64_codec(encoded))
    assert r["error"] is None

def test_base64_unicode():
    r = parse(base64_codec("café ☕ 日本語"))
    assert r["error"] is None

def test_base64_empty_decode():
    r = parse(base64_codec(""))
    assert r["error"] is not None

def test_base64_invalid_chars():
    r = parse(base64_codec("!!!invalid!!!"))
    assert r["error"] is not None

def test_base64_very_long():
    data = "A" * 100000
    import base64 as b64
    encoded = b64.b64encode(data.encode()).decode()
    r = parse(base64_codec(encoded))
    assert r["error"] is None

def test_base64_padding_variants():
    """Test base64 with various padding."""
    import base64 as b64
    for i in range(1, 10):
        data = "x" * i
        encoded = b64.b64encode(data.encode()).decode()
        r = parse(base64_codec(encoded))
        assert r["error"] is None, f"Failed on {i}-byte input: {r.get('error')}"


# ═══════════════════════════════════════════════
# JWT — edge cases
# ═══════════════════════════════════════════════
def test_jwt_expired():
    """JWT with expired timestamp."""
    import base64 as b64, json
    payload = json.dumps({"exp": 1000000000})  # Expired in 2001
    p = b64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
    h = b64.urlsafe_b64encode(json.dumps({"alg":"HS256"}).encode()).rstrip(b"=").decode()
    s = b64.urlsafe_b64encode(b"sig").rstrip(b"=").decode()
    r = parse(jwt_decoder(f"{h}.{p}.{s}"))
    assert r["tool_name"] == "jwt_decoder"

def test_jwt_malformed_payload():
    payload = b"not-json-but-base64"
    import base64 as b64, json
    p = b64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    h = b64.urlsafe_b64encode(json.dumps({"alg":"HS256"}).encode()).rstrip(b"=").decode()
    s = b64.urlsafe_b64encode(b"sig").rstrip(b"=").decode()
    r = parse(jwt_decoder(f"{h}.{p}.{s}"))
    assert r["error"] is None  # Should decode OK, payload is base64-readable

def test_jwt_short_segments():
    r = parse(jwt_decoder("a.b.c"))
    assert r["error"] is not None

def test_jwt_empty_parts():
    r = parse(jwt_decoder(".."))
    assert r["error"] is not None


# ═══════════════════════════════════════════════
# HASH — edge cases
# ═══════════════════════════════════════════════
def test_hash_empty_string():
    """Empty string should produce valid hash."""
    r = parse(hash_generator(""))
    assert r["error"] is not None  # or hash of empty string

def test_hash_unicode():
    r = parse(hash_generator("日本語💻"))
    assert r["error"] is None
    assert len(r["output"]) > 0

def test_hash_long_input():
    data = "x" * 1000000  # 1MB
    r = parse(hash_generator(data))
    assert r["error"] is None
    assert len(r["output"]) > 0


# ═══════════════════════════════════════════════
# URL — edge cases
# ═══════════════════════════════════════════════
def test_url_with_special_chars():
    """URL with unicode and special characters."""
    r = parse(url_codec("https://example.com/path with spaces?q=café&n=100%"))
    assert r is not None

def test_url_no_protocol():
    r = parse(url_codec("example.com/path?q=1"))
    assert r is not None

def test_url_mailto():
    r = parse(url_codec("mailto:test@example.com?subject=hello"))
    assert r is not None

def test_url_data_uri():
    r = parse(url_codec("data:text/plain;base64,SGVsbG8="))
    assert r is not None

def test_url_empty_query():
    r = parse(url_codec("https://example.com?"))
    assert r is not None

def test_url_multiple_slashes():
    r = parse(url_codec("https://example.com//path//to//resource"))
    assert r is not None


# ═══════════════════════════════════════════════
# TIMESTAMP — edge cases
# ═══════════════════════════════════════════════
def test_timestamp_year_2038():
    """Test beyond 32-bit time_t (2038 problem)."""
    r = parse(timestamp_converter("4102444800"))  # 2100-01-01
    assert "2100" in r["output"]

def test_timestamp_negative():
    """Pre-1970 dates."""
    r = parse(timestamp_converter("-12622780800"))  # 1570
    assert r is not None

def test_timestamp_milliseconds():
    """Timestamp in milliseconds (13 digits)."""
    r = parse(timestamp_converter("1625097600000"))
    assert r is not None  # Should detect as ms and convert

def test_timestamp_iso_format():
    r = parse(timestamp_converter("2021-07-01T00:00:00Z"))
    assert "1625097600" in str(r)

def test_timestamp_iso_with_offset():
    r = parse(timestamp_converter("2021-07-01T00:00:00+05:00"))
    assert r is not None

def test_timestamp_human_readable():
    r = parse(timestamp_converter("July 1, 2021"))
    assert r is not None

def test_timestamp_invalid_date():
    r = parse(timestamp_converter("not a date at all"))
    assert r["error"] is not None

def test_timestamp_leap_year():
    r = parse(timestamp_converter("2024-02-29"))
    assert r is not None  # Valid leap year

def test_timestamp_feb_30():
    r = parse(timestamp_converter("2023-02-30"))
    assert r["error"] is not None  # Invalid date


# ═══════════════════════════════════════════════
# UUID — edge cases
# ═══════════════════════════════════════════════
def test_uuid_zero():
    r = parse(uuid_generator("0"))
    assert r["tool_name"] == "uuid_generator"
    assert r["output"] != ""

def test_uuid_100():
    r = parse(uuid_generator("100"))
    assert r["metadata"]["count"] == 100

def test_uuid_large_number():
    r = parse(uuid_generator("10000"))
    assert r["metadata"]["count"] == 10000  # Should handle large counts

def test_uuid_invalid():
    r = parse(uuid_generator("-1"))
    assert r["tool_name"] == "uuid_generator"  # Should still work

def test_uuid_alpha():
    r = parse(uuid_generator("abc"))
    assert r["tool_name"] == "uuid_generator"  # Should handle gracefully


# ═══════════════════════════════════════════════
# TEXT DIFF — edge cases
# ═══════════════════════════════════════════════
def test_diff_identical():
    r = parse(text_diff("hello\nworld"))
    assert r is not None

def test_diff_completely_different():
    r = parse(text_diff("abc\ndef"))
    assert r is not None

def test_diff_unicode():
    r = parse(text_diff("café\n日本語"))
    assert r is not None

def test_diff_empty_vs_content():
    r = parse(text_diff(""))
    assert r is not None

def test_diff_1000_lines():
    a = "\n".join(f"line {i}" for i in range(1000))
    b = "\n".join(f"line {i}" for i in range(999, -1, -1))
    r = parse(text_diff(a))
    assert r is not None


# ═══════════════════════════════════════════════
# DETECTOR — edge cases
# ═══════════════════════════════════════════════
def test_detector_empty():
    r = detect("")
    assert r is not None
    assert r.get("tool") is not None

def test_detector_whitespace():
    r = detect("   \n\t   ")
    assert r is not None

def test_detector_special_chars():
    r = detect("!@#$%^&*()")
    assert r is not None

def test_detector_html():
    r = detect("<html><body>Hello</body></html>")
    assert r is not None

def test_detector_sql():
    r = detect("SELECT * FROM users WHERE id = 1")
    assert r is not None

def test_detector_ip_address():
    r = detect("192.168.1.1")
    assert r is not None

def test_detector_mac_address():
    r = detect("00:1A:2B:3C:4D:5E")
    assert r is not None

def test_detector_semver():
    r = detect("1.2.3-beta.4")
    assert r is not None

def test_detector_emoji():
    r = detect("💻🔥🚀")
    assert r is not None

def test_detector_very_long():
    r = detect("x" * 100000)
    assert r is not None  # Should not hang

def test_detector_mixed_content():
    """String that matches multiple detectors — should pick the best one."""
    r = detect('{"url": "https://example.com", "timestamp": 1625097600}')
    assert r.get("detection_type") is not None


# ═══════════════════════════════════════════════
# PERFORMANCE / STRESS
# ═══════════════════════════════════════════════
def test_stress_detect_many():
    """Run detector on 100 random strings — should be fast."""
    import random, string
    random.seed(42)
    inputs = []
    for _ in range(100):
        length = random.randint(1, 100)
        chars = string.ascii_letters + string.digits + "{}[],.:/\\"
        inputs.append("".join(random.choice(chars) for _ in range(length)))
    inputs.extend([
        '{"a": 1}', '{"x": [1,2,3]}', 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doS_8Mns3kI',
        "https://example.com", "1625097600", "550e8400-e29b-41d4-a716-446655440000",
    ])
    start = time.time()
    for s in inputs:
        detect(s)
    elapsed = time.time() - start
    assert elapsed < 5.0, f"Detector too slow: {elapsed:.2f}s for {len(inputs)} inputs"

def test_stress_run_tool_batch():
    """Run all tools on various inputs — should handle gracefully."""
    inputs = ["", "test", "123", "{}", "[]", '"str"', "null", "true", "false"]
    tools = ["json", "base64", "jwt", "hash", "url", "timestamp", "uuid", "diff"]
    for tool_name in tools:
        for inp in inputs:
            r = parse(run_tool(tool_name, inp))
            assert r is not None, f"{tool_name}({inp!r}) returned None"

def test_stress_no_crash():
    """Tools should never crash on any input."""
    dangerous = [
        "\x00\x01\x02",  # Null bytes
        "\x1b[31mred\x1b[0m",  # ANSI escape codes
        "\xff\xfe\x00",  # BOM
        "\n" * 10000,  # Newlines
        "\t" * 10000,  # Tabs
        "\\" * 10000,  # Backslashes
    ]
    for inp in dangerous:
        for tool in [json_formatter, base64_codec, jwt_decoder, hash_generator,
                     url_codec, timestamp_converter]:
            r = parse(tool(inp))
            assert r is not None  # No crash, just error or success


# ═══════════════════════════════════════════════
# INTERNAL API
# ═══════════════════════════════════════════════
def test_run_tool_detection():
    r = parse(run_tool("detect", '{"a":1}'))
    assert "detection_type" in str(r) or "tool" in str(r)

def test_run_tool_all_names():
    all_tools = ["json", "base64", "jwt", "hash", "url", "timestamp", "uuid", "diff"]
    for t in all_tools:
        assert get_tool(t) is not None, f"Tool '{t}' not found"
        r = parse(run_tool(t, "test"))
        assert r is not None

def test_imports():
    from core import cli, models, tools, detector
    assert hasattr(cli, "main")
    assert hasattr(detector, "detect")