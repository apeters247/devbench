"""Devbench core tools — 9 pure-function developer utilities.

Each tool exposes a ``run(input_text: str) -> str`` interface and returns
clean JSON-ish output suitable for a SwiftUI shell.
"""

from __future__ import annotations

import base64
import datetime
import difflib
import hashlib
import json
import re
import uuid
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, quote, unquote, urlparse, urlunparse

from . import configforge as _configforge

# ---------------------------------------------------------------------------
# 1. JSON Formatter
# ---------------------------------------------------------------------------


def _sort_json_keys(obj):
    """Recursively sort all dictionary keys in a JSON-like structure."""
    if isinstance(obj, dict):
        return {k: _sort_json_keys(v) for k, v in sorted(obj.items(), key=lambda x: x[0])}
    elif isinstance(obj, list):
        return [_sort_json_keys(item) for item in obj]
    return obj


FORMAT_TOGGLE = object()  # sentinel


def json_formatter(input_text: str) -> str:
    """Pretty-print or minify JSON. Validates, sorts keys, detects intent.

    Auto-detects:
      - If input is already compact (single line) → pretty-print
      - If input is already pretty (multi-line) → minify
      - Sort keys by default.
    """
    input_text = input_text.strip()
    if not input_text:
        return _err("json_formatter", "Empty input — nothing to format.")

    try:
        parsed = json.loads(input_text)
    except json.JSONDecodeError as e:
        return _err("json_formatter", f"Invalid JSON: {e}")

    parsed = _sort_json_keys(parsed)

    # Detect current style: single-line → pretty, multi-line → minify
    is_compact = _is_json_compact(input_text)

    if is_compact:
        output = json.dumps(parsed, indent=2, ensure_ascii=False, sort_keys=True)
        style = "pretty-printed"
    else:
        output = json.dumps(parsed, separators=(",", ":"), ensure_ascii=False, sort_keys=True)
        style = "minified"

    return _ok("json_formatter", output, style=style, char_count=len(output))


def _is_json_compact(text: str) -> bool:
    """Heuristic: if JSON has no newlines after stripping, treat as compact."""
    stripped = text.strip()
    # Remove strings (which could contain newlines) before checking
    # Simplistic: just check if there's any newline outside of quotes
    in_str = False
    for ch in stripped:
        if ch == '"':
            in_str = not in_str
        if not in_str and ch == "\n":
            return False
    return True


# ---------------------------------------------------------------------------
# 2. Base64 Codec
# ---------------------------------------------------------------------------


def base64_codec(input_text: str) -> str:
    """Encode or decode text to/from Base64.

    Auto-detects intent:
      - If input looks like valid Base64 (matches pattern, has correct padding) → decode
      - Otherwise → encode
    """
    input_text = input_text.strip()
    if not input_text:
        return _err("base64_codec", "Empty input.")

    if _looks_like_base64(input_text):
        # Try to decode
        try:
            # Add padding if needed
            padded = _pad_base64(input_text)
            decoded_bytes = base64.b64decode(padded, validate=True)
            decoded = decoded_bytes.decode("utf-8")
            return _ok("base64_codec", decoded, operation="decode", original=input_text)
        except (base64.binascii.Error, ValueError, UnicodeDecodeError) as e:
            # If decode fails but it looks like base64, maybe it's meant to be encoded?
            pass

    # Validate: if input doesn't look like base64 AND contains too many
    # unusual characters (not alphanumeric or common punctuation),
    # it's likely garbled input — reject instead of silently encoding
    text_chars = len(re.findall(r"[\w\s.,;:\'\"\-]", input_text))
    if input_text and text_chars < len(input_text) * 0.8:
        return _err("base64_codec", f"Input contains characters not valid in Base64.")

    # Encode
    try:
        encoded = base64.b64encode(input_text.encode("utf-8")).decode("ascii")
        return _ok("base64_codec", encoded, operation="encode", original=input_text)
    except Exception as e:
        return _err("base64_codec", f"Encoding failed: {e}")


def _looks_like_base64(text: str) -> bool:
    """Heuristic: string matches base64 charset and has plausible length."""
    text = text.strip()
    if not text:
        return False
    # Must be at least 4 chars
    if len(text) < 4:
        return False
    # Allow trailing '=' padding
    cleaned = text.rstrip("=")
    if not cleaned:
        return False
    # Must contain only base64 chars
    pattern = r"^[A-Za-z0-9+/]*$"
    if not re.match(pattern, cleaned):
        return False
    return True


def _pad_base64(text: str) -> str:
    """Add missing padding to a Base64 string."""
    remainder = len(text) % 4
    if remainder:
        text += "=" * (4 - remainder)
    return text


# ---------------------------------------------------------------------------
# 3. JWT Decoder
# ---------------------------------------------------------------------------


def jwt_decoder(input_text: str) -> str:
    """Decode a JWT token, showing header, payload, signature, and expiry info."""
    input_text = input_text.strip()
    if not input_text:
        return _err("jwt_decoder", "Empty input.")

    parts = input_text.split(".")
    if len(parts) != 3:
        return _err(
            "jwt_decoder",
            "Not a valid JWT. Expected 3 dot-separated sections "
            "(header.payload.signature), got {0}.".format(len(parts)),
        )

    header_b64, payload_b64, signature_b64 = parts

    # Each JWT part should be at least a few chars long to be meaningful
    if len(header_b64) < 4 or len(payload_b64) < 4 or len(signature_b64) < 4:
        return _err(
            "jwt_decoder",
            "Not a valid JWT. Each of the 3 dot-separated sections must be "
            f"at least 4 characters long. Got header={len(header_b64)}, "
            f"payload={len(payload_b64)}, signature={len(signature_b64)}.",
        )

    # Decode header
    try:
        header_json = _decode_jwt_part(header_b64)
        header = json.loads(header_json)
    except Exception as e:
        header = {"_error": f"Could not decode header: {e}"}

    # Decode payload
    try:
        payload_json = _decode_jwt_part(payload_b64)
        payload = json.loads(payload_json)
    except Exception as e:
        payload = {"_error": f"Could not decode payload: {e}"}

    # Decode signature (just show truncated hex)
    try:
        sig_bytes = _decode_jwt_part_bytes(signature_b64)
        sig_hex = sig_bytes.hex()[:32] + "..." if len(sig_bytes) > 16 else sig_bytes.hex()
    except Exception:
        sig_hex = "<unable to decode>"

    # Check expiry
    exp_info = _check_jwt_expiry(payload)

    lines = [
        "═" * 60,
        "  JWT DECODED",
        "═" * 60,
        "",
        "── Header ──",
        json.dumps(header, indent=2, ensure_ascii=False),
        "",
        "── Payload ──",
        json.dumps(payload, indent=2, ensure_ascii=False),
        "",
        "── Signature (truncated) ──",
        f"  {sig_hex}",
        "",
    ]
    if exp_info:
        lines.extend(
            [
                "── Expiry Info ──",
                f"  {exp_info}",
                "",
            ]
        )
    lines.extend(
        [
            "── Raw Token ──",
            f"  {input_text}",
            "",
        ]
    )

    return _ok(
        "jwt_decoder",
        "\n".join(lines),
        header=header,
        payload=payload,
        expiry_info=exp_info,
    )


def _decode_jwt_part(b64_str: str) -> str:
    """Decode a URL-safe Base64 JWT segment to string."""
    # Restore padding
    b64 = b64_str.replace("-", "+").replace("_", "/")
    b64 = _pad_base64(b64)
    decoded = base64.b64decode(b64, validate=True)
    return decoded.decode("utf-8")


def _decode_jwt_part_bytes(b64_str: str) -> bytes:
    """Decode a URL-safe Base64 JWT segment to raw bytes."""
    b64 = b64_str.replace("-", "+").replace("_", "/")
    b64 = _pad_base64(b64)
    return base64.b64decode(b64, validate=True)


def _check_jwt_expiry(payload: dict) -> Optional[str]:
    """Check if the JWT is expired or about to expire."""
    exp = payload.get("exp")
    if exp is None:
        return None

    # Some JS-based JWT libraries emit ``exp`` in milliseconds rather than the
    # spec-mandated seconds. A seconds epoch only crosses 2e10 around the year
    # 2603, so a value above that is almost certainly milliseconds — normalize.
    if isinstance(exp, (int, float)) and exp > 2 * 10**10:
        exp = exp / 1000

    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        exp_dt = datetime.datetime.fromtimestamp(exp, tz=datetime.timezone.utc)
    except (OSError, ValueError, OverflowError):
        return f"exp claim value {exp} is not a valid timestamp"

    diff = exp_dt - now
    total_seconds = diff.total_seconds()

    if total_seconds < 0:
        return f"⚠️  EXPIRED {abs(total_seconds):.0f} seconds ago (at {exp_dt.isoformat()})"
    elif total_seconds < 300:
        return f"⚠️  Expiring soon — in {total_seconds:.0f} seconds (at {exp_dt.isoformat()})"
    elif total_seconds < 3600:
        return f"⏰ Expires in {total_seconds / 60:.1f} minutes (at {exp_dt.isoformat()})"
    else:
        return f"✅ Valid until {exp_dt.isoformat()} ({total_seconds / 3600:.1f} hours from now)"


# ---------------------------------------------------------------------------
# 4. Hash Generator
# ---------------------------------------------------------------------------


def hash_generator(input_text: str) -> str:
    """Generate MD5, SHA-1, SHA-256, SHA-512 hashes of the input.

    An empty string is a valid input: it hashes to the well-defined digests of
    zero bytes (e.g. MD5 ``d41d8cd98f00b204e9800998ecf8427e``), which users
    legitimately need when verifying empty files.
    """
    input_text = input_text.strip()

    data = input_text.encode("utf-8")

    # Wrap MD5 in try/except for FIPS systems where MD5 is completely disabled
    try:
        md5_hash = hashlib.md5(data, usedforsecurity=False).hexdigest()
    except (ValueError, TypeError):
        # FIPS mode: MD5 is unavailable, use SHA-256 as fallback
        md5_hash = f"SHA256({hashlib.sha256(data).hexdigest()})"

    hashes = {
        "MD5": md5_hash,
        "SHA-1": hashlib.sha1(data, usedforsecurity=False).hexdigest(),
        "SHA-256": hashlib.sha256(data).hexdigest(),
        "SHA-512": hashlib.sha512(data).hexdigest(),
    }

    lines = [
        "═" * 60,
        "  HASH GENERATOR",
        "═" * 60,
        "",
        f"  Input: \"{_truncate(input_text, 80)}\"",
        f"  Input length: {len(input_text)} characters",
        "",
    ]
    for algo, digest in hashes.items():
        lines.append(f"  {algo:<8}  {digest}")

    return _ok("hash_generator", "\n".join(lines), hashes=hashes)


# ---------------------------------------------------------------------------
# 5. URL Codec
# ---------------------------------------------------------------------------


def url_codec(input_text: str) -> str:
    """URL encode/decode + parse query strings into key-value pairs.

    Auto-detects intent:
      - If input contains '%' → decode
      - If input looks like a full URL with query string → parse it
      - Otherwise → encode
    """
    input_text = input_text.strip()
    if not input_text:
        return _err("url_codec", "Empty input.")

    parsed = urlparse(input_text)

    # Check if this looks like a full URL with scheme
    has_scheme = parsed.scheme in ("http", "https", "ftp", "file", "data")
    has_query = bool(parsed.query)

    if has_scheme and has_query:
        # Parse as URL with query string
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        # Flatten single-value lists
        flat_params = {k: v[0] if len(v) == 1 else v for k, v in query_params.items()}

        lines = [
            "═" * 60,
            "  URL PARSER",
            "═" * 60,
            "",
            f"  Scheme:   {parsed.scheme}",
            f"  Netloc:   {parsed.netloc}",
            f"  Path:     {parsed.path}",
            f"  Params:   {parsed.params}",
            f"  Query:    {parsed.query}",
            f"  Fragment: {parsed.fragment}",
            "",
            "── Query Parameters ──",
        ]
        if flat_params:
            for k, v in flat_params.items():
                lines.append(f"  {k} = {v}")
        else:
            lines.append("  (none)")
        lines.append("")
        # Also show decoded URL
        decoded = unquote(input_text)
        if decoded != input_text:
            lines.extend(["\n── Decoded URL ──", f"  {decoded}"])

        return _ok(
            "url_codec",
            "\n".join(lines),
            operation="parse",
            scheme=parsed.scheme,
            netloc=parsed.netloc,
            path=parsed.path,
            query_params=flat_params,
        )

    # Detect encode vs decode
    if "%" in input_text:
        # Decode
        try:
            decoded = unquote(input_text)
            return _ok("url_codec", decoded, operation="decode", original=input_text)
        except Exception as e:
            return _err("url_codec", f"URL decode failed: {e}")
    else:
        # Encode
        try:
            encoded = quote(input_text, safe="")
            return _ok("url_codec", encoded, operation="encode", original=input_text)
        except Exception as e:
            return _err("url_codec", f"URL encode failed: {e}")


# ---------------------------------------------------------------------------
# 6. Timestamp Converter
# ---------------------------------------------------------------------------


def timestamp_converter(input_text: str) -> str:
    """Convert between Unix timestamps and human-readable dates.

    Accepts:
      - Numeric Unix timestamp (seconds since epoch)
      - ISO 8601 date string
      - Common date format strings
    """
    input_text = input_text.strip()
    if not input_text:
        return _err("timestamp_converter", "Empty input.")

    now = datetime.datetime.now(datetime.timezone.utc)

    # Try to parse as numeric timestamp
    ts = _parse_as_timestamp(input_text)
    if ts is not None:
        try:
            dt_utc = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            dt_local = datetime.datetime.fromtimestamp(ts)
            return _format_timestamp_output(input_text, dt_utc, dt_local, ts)
        except (OSError, ValueError, OverflowError) as e:
            return _err("timestamp_converter", f"Invalid timestamp value: {e}")

    # Try to parse as ISO 8601 or other date string
    dt = _parse_as_datetime(input_text)
    if dt is not None:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
        ts = (dt - epoch).total_seconds()
        return _format_timestamp_output(input_text, dt, dt.astimezone(), ts)

    return _err(
        "timestamp_converter",
        f"Cannot parse \"{input_text}\" as a timestamp or date string. "
        "Try a Unix epoch number (e.g. 1700000000) or ISO 8601 "
        "(e.g. 2024-01-15T12:00:00Z).",
    )


def _parse_as_timestamp(text: str) -> Optional[float]:
    """Try to parse text as a numeric Unix timestamp."""
    text = text.strip().strip('"').strip("'")
    try:
        val = float(text)
    except ValueError:
        return None
    # Reject clearly non-timestamp values
    if val < 0 or val > 1_000_000_000_000:
        return None
    # If value is > 1e11 (year 5138+), assume milliseconds
    if val > 1_000_000_000_00:  # > 100 billion → ms
        val = val / 1000.0
    return val


def _parse_as_datetime(text: str) -> Optional[datetime.datetime]:
    """Try to parse text as a date/time string."""
    text = text.strip().strip('"').strip("'")

    # ISO 8601 variants
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m/%d/%Y %H:%M:%S",
        "%d/%m/%Y",
        "%B %d, %Y",
        "%d %B %Y",
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            return datetime.datetime.strptime(text, fmt)
        except ValueError:
            continue

    # Try dateutil-like parsing via strptime with common patterns
    # Also try removing timezone offset manually
    # e.g. "2024-01-15T12:00:00+00:00"
    m = re.match(
        r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?)"
        r"([+-]\d{2}:\d{2}|Z)?",
        text,
    )
    if m:
        base = m.group(1)
        tz_str = m.group(2)
        if tz_str and tz_str != "Z":
            # Convert +HH:MM offset to +HHMM for %z
            tz_clean = tz_str.replace(":", "")
            try:
                return datetime.datetime.strptime(base + tz_clean, "%Y-%m-%dT%H:%M:%S%z")
            except ValueError:
                try:
                    return datetime.datetime.strptime(
                        base + tz_clean, "%Y-%m-%d %H:%M:%S%z"
                    )
                except ValueError:
                    pass
        else:
            try:
                return datetime.datetime.strptime(base, "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                try:
                    return datetime.datetime.strptime(base, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass

    return None


def _format_timestamp_output(
    original: str,
    dt_utc: datetime.datetime,
    dt_local: datetime.datetime,
    ts: float,
) -> str:
    """Build formatted timestamp output."""
    lines = [
        "═" * 60,
        "  TIMESTAMP CONVERTER",
        "═" * 60,
        "",
        f"  Input: {original}",
        "",
        f"  Unix timestamp (seconds):  {int(ts)}",
        f"  Unix timestamp (ms):       {int(ts * 1000)}",
        "",
        f"  UTC:    {dt_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC",
        f"  Local:  {dt_local.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "",
        f"  ISO 8601 (UTC):   {dt_utc.isoformat()}",
        f"  ISO 8601 (local): {dt_local.isoformat()}",
        "",
    ]

    return _ok(
        "timestamp_converter",
        "\n".join(lines),
        unix_seconds=int(ts),
        unix_milliseconds=int(ts * 1000),
        utc=dt_utc.isoformat(),
        local=dt_local.isoformat(),
    )


# ---------------------------------------------------------------------------
# 7. UUID Generator
# ---------------------------------------------------------------------------


def uuid_generator(input_text: str) -> str:
    """Generate UUIDs (v4).

    Input specifies how many: "1", "5", "10", "50", or empty (defaults to 1).
    Also accepts "copy" to return the first UUID from previous run (not stored,
    so just generates 1 new one).
    """
    input_text = input_text.strip().lower()

    if not input_text:
        count = 1
    elif input_text in ("copy", "copy 1", "-c"):
        count = 1
    else:
        try:
            count = int(input_text.split()[0])
            count = max(1, min(count, 10000))  # cap at 10000
        except (ValueError, IndexError):
            count = 1

    uuids = [str(uuid.uuid4()) for _ in range(count)]

    lines = [
        "═" * 60,
        f"  UUID GENERATOR  ({count} UUID{'s' if count != 1 else ''})",
        "═" * 60,
        "",
    ]
    for i, uid in enumerate(uuids, 1):
        lines.append(f"  {i:>3}.  {uid}")
    lines.extend(
        [
            "",
            f"  ↪ Copy any UUID above. First one: {uuids[0]}",
            "",
        ]
    )

    return _ok(
        "uuid_generator",
        "\n".join(lines),
        count=count,
        uuids=uuids,
        first=uuids[0],
    )


# ---------------------------------------------------------------------------
# 8. Text Diff
# ---------------------------------------------------------------------------


def text_diff(input_text: str) -> str:
    """Line-level side-by-side diff with colored output using difflib.

    Expects input with two blocks separated by a delimiter:
      "---" on its own line separates left (old) from right (new).
    Also accepts "left | right" style with a pipe separator.
    """
    input_text = input_text.strip()
    if not input_text:
        return _err("text_diff", "Empty input. Provide two text blocks separated by '---' or '|'.")

    # Detect separator
    sep = None
    if "\n---\n" in input_text:
        sep = "\n---\n"
        left_text, right_text = input_text.split(sep, 1)
    elif "\n|\n" in input_text:
        sep = "\n|\n"
        left_text, right_text = input_text.split(sep, 1)
    else:
        return _err(
            "text_diff",
            "Cannot find a separator. Use '---' on its own line or '|' on its own line "
            "between the old (left) and new (right) text blocks.",
        )

    left_lines = left_text.strip().splitlines()
    right_lines = right_text.strip().splitlines()

    diff = difflib.unified_diff(
        left_lines,
        right_lines,
        fromfile="original",
        tofile="modified",
        lineterm="",
    )

    unified = list(diff)

    # Also produce side-by-side using HtmlDiff for a text approximation
    # We'll do a simple side-by-side using difflib.SequenceMatcher
    matcher = difflib.SequenceMatcher(None, left_lines, right_lines)
    opcodes = matcher.get_opcodes()

    side_lines = []
    for tag, i1, i2, j1, j2 in opcodes:
        left_block = left_lines[i1:i2] if i1 < i2 else ["(empty)"]
        right_block = right_lines[j1:j2] if j1 < j2 else ["(empty)"]
        max_len = max(len(left_block), len(right_block))

        if tag == "equal":
            for idx in range(max_len):
                l = left_block[idx] if idx < len(left_block) else ""
                r = right_block[idx] if idx < len(right_block) else ""
                side_lines.append(f"   {l:<60} | {r}")
        elif tag in ("replace", "delete", "insert"):
            color_start_red = "\033[31m"
            color_start_green = "\033[32m"
            color_end = "\033[0m"
            for idx in range(max_len):
                l = left_block[idx] if idx < len(left_block) else ""
                r = right_block[idx] if idx < len(right_block) else ""
                if tag == "replace":
                    side_lines.append(
                        f"  {color_start_red}-{l:<60}{color_end} | "
                        f"{color_start_green}+{r}{color_end}"
                    )
                elif tag == "delete":
                    side_lines.append(f"  {color_start_red}-{l:<60}{color_end} |")
                elif tag == "insert":
                    side_lines.append(
                        f"  {'':>62} | {color_start_green}+{r}{color_end}"
                    )

    lines = [
        "═" * 60,
        "  TEXT DIFF  (side-by-side)",
        "═" * 60,
        "",
        f"  Original: {len(left_lines)} line(s)",
        f"  Modified: {len(right_lines)} line(s)",
        "",
        "  Legend:  \033[31m-red = removed\033[0m  \033[32m+green = added\033[0m",
        "",
        "  ── Side-by-side ──",
    ]
    lines.extend(side_lines)

    if unified:
        lines.extend(
            [
                "",
                "  ── Unified Diff ──",
            ]
        )
        lines.extend(unified)

    return _ok(
        "text_diff",
        "\n".join(lines),
        original_lines=len(left_lines),
        modified_lines=len(right_lines),
        changes=len([o for o in opcodes if o[0] != "equal"]),
    )


# ---------------------------------------------------------------------------
# 9. ConfigForge — multi-format config converter
# ---------------------------------------------------------------------------


def configforge_tool(input_text: str) -> str:
    """Convert config files between JSON, YAML, TOML, XML, CSV, INI, ENV.

    Auto-detects input format. Converts to JSON by default.
    Pipe in:  echo 'key: value' | devbench cf
    Specify:  devbench cf --to yaml '{...}'
    """
    input_text = input_text.strip()
    if not input_text:
        return _err("cf", "Empty input — provide config content to convert.")

    # Parse optional --to/--from embedded in the string (CLI handles real args)
    to_fmt = None
    from_fmt = "auto"
    lines = input_text.split("\n")
    for directive_prefix in ["#devbench:to=", "#devbench:from="]:
        for i, line in enumerate(lines):
            if line.startswith(directive_prefix):
                val = line.split("=", 1)[1].strip()
                if directive_prefix == "#devbench:to=":
                    to_fmt = val
                elif directive_prefix == "#devbench:from=":
                    from_fmt = val
                lines[i] = ""
                break
    cleaned = "\n".join(l for l in lines if l).strip()
    if not cleaned:
        cleaned = input_text

    if to_fmt is None:
        detected = _configforge.detect_format(cleaned)
        to_fmt = detected  # convert to own format = pretty-print
        if detected in ("unknown",):
            to_fmt = "json"

    raw = _configforge.convert(cleaned, to_fmt, from_fmt)
    if not raw.get("success", False):
        return _err("cf", raw.get("error", "Conversion failed."))
    return _ok(
        "cf",
        raw.get("output", ""),
        input_format=raw.get("input_format"),
        output_format=raw.get("output_format"),
        input_size=raw.get("input_size"),
        output_size=raw.get("output_size"),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TOOLS: dict[str, Callable[[str], str]] = {
    "json": json_formatter,
    "base64": base64_codec,
    "jwt": jwt_decoder,
    "hash": hash_generator,
    "url": url_codec,
    "timestamp": timestamp_converter,
    "uuid": uuid_generator,
    "diff": text_diff,
    "cf": configforge_tool,
}

_LLM_TOOLS_REGISTERED = False


def _ensure_llm_tools():
    """Lazily register token/chunk tools once the module is fully loaded."""
    global _LLM_TOOLS_REGISTERED
    if not _LLM_TOOLS_REGISTERED:
        TOOLS["token"] = token_counter
        TOOLS["chunk"] = text_chunker
        _LLM_TOOLS_REGISTERED = True

TOOL_ALIASES: dict[str, str] = {
    "json_formatter": "json",
    "base64_codec": "base64",
    "base64": "base64",
    "jwt_decoder": "jwt",
    "hash_generator": "hash",
    "url_codec": "url",
    "timestamp_converter": "timestamp",
    "uuid_generator": "uuid",
    "text_diff": "diff",
    "configforge": "cf",
    "convert": "cf",
    "cf_tool": "cf",
    "token_counter": "token",
    "text_chunker": "chunk",
}

TOOL_HELP: dict[str, str] = {
    "json": "Pretty-print or minify JSON → json_formatter(input)",
    "base64": "Encode/decode Base64 → base64_codec(input)",
    "jwt": "Decode JWT token → jwt_decoder(input)",
    "hash": "Generate MD5/SHA hashes → hash_generator(input)",
    "url": "Encode/decode URLs + parse query → url_codec(input)",
    "timestamp": "Convert timestamps ↔ dates → timestamp_converter(input)",
    "uuid": "Generate UUIDs (v4) → uuid_generator(input)",
    "diff": "Show text diff → text_diff(input)",
    "cf": "Convert config files: JSON/YAML/TOML/XML/CSV/INI/ENV",
    "token": "Count tokens for LLMs (tiktoken) → token_counter(input)",
    "chunk": "Chunk text for RAG (retrieval-augmented generation) → text_chunker(input)",
}

TOOL_NAMES: list[str] = ["json", "base64", "jwt", "hash", "url", "timestamp", "uuid", "diff", "cf", "token", "chunk"]


def get_tool(name: str) -> Optional[Callable[[str], str]]:
    """Resolve a tool name / alias to its callable."""
    _ensure_llm_tools()
    canonical = TOOL_ALIASES.get(name, name)
    return TOOLS.get(canonical)


def run_tool(name: str, input_text: str) -> str:
    """Run a named tool with the given input. Returns error string if not found."""
    _ensure_llm_tools()
    tool = get_tool(name)
    if tool is None:
        return _err("unknown", f"Unknown tool: {name!r}. Available: {', '.join(TOOLS)}")
    return tool(input_text)


# ---------------------------------------------------------------------------
# JSON-ish result helpers
# ---------------------------------------------------------------------------


def _ok(tool: str, output: str, **metadata) -> str:
    """Build a JSON-ish success string that the SwiftUI shell can parse."""
    result = {
        "tool_name": tool,
        "output": output,
        "error": None,
        "metadata": metadata,
    }
    return json.dumps(result, ensure_ascii=False)


def _err(tool: str, msg: str) -> str:
    """Build a JSON-ish error string."""
    result = {
        "tool_name": tool,
        "output": "",
        "error": msg,
        "metadata": {},
    }
    return json.dumps(result, ensure_ascii=False)


def _truncate(text: str, max_len: int = 80) -> str:
    """Truncate text for display."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."

# ---------------------------------------------------------------------------
# 10. Token Counter (for LLMs)
# ---------------------------------------------------------------------------


def _try_get_tiktoken_encoding(model_name: str = "cl100k_base"):
    """Try to get a tiktoken encoding. Returns None if tiktoken not installed."""
    try:
        import tiktoken
    except ImportError:
        return None
    try:
        return tiktoken.get_encoding(model_name)
    except Exception:
        try:
            return tiktoken.encoding_for_model(model_name)
        except Exception:
            return None


_TOKEN_ESTIMATE_RATIO = 4  # ~1 token per 4 chars for English text


def token_counter(input_text: str, model_name: str = "cl100k_base") -> str:
    """Count tokens in text. Uses tiktoken if available, falls back to
    character-based estimation (≈1 token / 4 chars)."""
    input_text = input_text.strip()
    if not input_text:
        return _err("token", "Empty input — provide text to count tokens.")

    encoding = _try_get_tiktoken_encoding(model_name)
    if encoding is not None:
        tokens = encoding.encode(input_text)
        token_count = len(tokens)
        method = "tiktoken"
    else:
        # Fallback: estimate by char count
        token_count = max(1, len(input_text) // _TOKEN_ESTIMATE_RATIO)
        method = "estimate"

    return _ok(
        "token", str(token_count),
        token_count=token_count,
        model=model_name,
        method=method,
        char_count=len(input_text),
    )


# ---------------------------------------------------------------------------
# 11. Text Chunker (for RAG)
# ---------------------------------------------------------------------------


def text_chunker(input_text: str, chunk_size: int = 500, chunk_overlap: int = 100) -> str:
    """Chunk text into smaller pieces for RAG applications.

    Splits text by paragraphs → sentences → fitting within chunk_size.
    Uses tiktoken if available, falls back to character estimation.
    Applies overlap between adjacent chunks.
    """
    input_text = input_text.strip()
    if not input_text:
        return _err("chunk", "Empty input — provide text to chunk.")
    if chunk_size <= 0:
        return _err("chunk", "Chunk size must be greater than 0.")
    if chunk_overlap < 0:
        return _err("chunk", "Chunk overlap cannot be negative.")
    if chunk_overlap >= chunk_size:
        return _err("chunk", "Chunk overlap must be less than chunk size.")

    encoding = _try_get_tiktoken_encoding("cl100k_base")
    use_tiktoken = encoding is not None

    def _count_units(text: str) -> int:
        if use_tiktoken:
            return len(encoding.encode(text))
        return max(1, len(text) // _TOKEN_ESTIMATE_RATIO)

    def _encode_unit(text: str):
        if use_tiktoken:
            return encoding.encode(text)
        return text  # pass-through for char-based

    def _unit_len(item) -> int:
        if use_tiktoken and isinstance(item, list):
            return len(item)
        return _count_units(str(item))

    # Normalize the text for chunking
    # Token-level chunker
    chunks = []
    current_chunk = []  # list of piece texts
    current_unit_count = 0
    current_unit_items = []  # list of token lists or strings

    # Split into paragraphs, then sentences
    paragraphs = [p for p in input_text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [input_text]

    for para in paragraphs:
        sentences = re.split(r"(?<=[.!?])\s+", para)
        sentences = [s.strip() for s in sentences if s.strip()]

        for sentence in sentences:
            sentence_item = _encode_unit(sentence + " ")
            sentence_units = _unit_len(sentence_item)

            # If a single sentence exceeds chunk_size, force-chunk it word-by-word
            if sentence_units > chunk_size:
                # Flush current chunk first
                if current_chunk:
                    chunk_str = " ".join(str(p) for p in current_chunk)
                    chunks.append(chunk_str)
                    current_chunk = []
                    current_unit_count = 0
                    current_unit_items = []

                # Split oversized sentence by words
                words = sentence.split()
                word_chunk = []
                word_units = 0
                for w in words:
                    w_item = _encode_unit(w + " ")
                    w_units = _unit_len(w_item)
                    if word_units + w_units > chunk_size and word_chunk:
                        chunks.append(" ".join(word_chunk))
                        # Apply overlap: keep last words
                        overlap_words = []
                        overlap_units = 0
                        for ow in reversed(word_chunk):
                            ow_units = _count_units(ow + " ")
                            if overlap_units + ow_units > chunk_overlap:
                                break
                            overlap_words.insert(0, ow)
                            overlap_units += ow_units
                        word_chunk = list(overlap_words)
                        word_units = overlap_units
                    word_units += w_units
                    word_chunk.append(w)
                if word_chunk:
                    chunks.append(" ".join(word_chunk))
                continue

            # Normal case: try to add sentence to current chunk
            if current_unit_count + sentence_units > chunk_size and current_chunk:
                # Finalize current chunk
                chunk_str = " ".join(str(p) for p in current_chunk)
                chunks.append(chunk_str)

                # Apply overlap: keep last N units from current chunk
                overlap_items = []
                overlap_units = 0
                for piece in reversed(current_chunk):
                    piece_units = _count_units(str(piece) + " ")
                    if overlap_units + piece_units > chunk_overlap:
                        break
                    overlap_items.insert(0, piece)
                    overlap_units += piece_units
                current_chunk = list(overlap_items)
                current_unit_count = overlap_units
                current_unit_items = []

            current_chunk.append(sentence)
            current_unit_count += sentence_units
            current_unit_items.append(sentence_item)

    # Flush last chunk
    if current_chunk:
        chunk_str = " ".join(str(p) for p in current_chunk)
        chunks.append(chunk_str)

    chunks = [c.strip() for c in chunks if c.strip()]

    return _ok(
        "chunk",
        json.dumps(chunks, indent=2, ensure_ascii=False),
        chunk_count=len(chunks),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        total_chars=len(input_text),
        method="tiktoken" if use_tiktoken else "estimate",
    )


# ---------------------------------------------------------------------------
# Re-export for convenience
# ---------------------------------------------------------------------------

__all__ = [
    "json_formatter",
    "base64_codec",
    "jwt_decoder",
    "hash_generator",
    "url_codec",
    "timestamp_converter",
    "uuid_generator",
    "text_diff",
    "run_tool",
    "get_tool",
    "TOOLS",
    "TOOL_NAMES",
    "TOOL_HELP",
]