"""Clipboard content auto-detector for Devbench.

Given a string, determine what it most likely is and route to the
appropriate tool. Returns a ToolResult or JSON-ish result string.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Optional
from urllib.parse import urlparse
import base64

from . import models
from . import tools
from . import configforge as _cf

# ---------------------------------------------------------------------------
# Detection strategies
# ---------------------------------------------------------------------------


def detect_and_run(input_text: str) -> str:
    """Auto-detect the content type of ``input_text`` and run the matching tool.

    Returns a JSON-ish result string (same format as tools).
    """
    input_text = input_text.strip()
    if not input_text:
        return tools._err("detect", "Empty input — nothing to detect.")

    detection = detect(input_text)
    tool_name = detection["tool"]
    detection_type = detection["detection_type"]

    if tool_name is None:
        # No specific tool matched; show available tools
        return _show_all_tools(input_text, detection_type)

    tool_fn = tools.get_tool(tool_name)
    if tool_fn is None:
        return tools._err("detect", f"Internal error: unknown tool {tool_name!r}")

    result_str = tool_fn(input_text)

    # Inject detection_type into the result by parsing and re-wrapping
    try:
        result = json.loads(result_str)
        result["detection_type"] = detection_type
        return json.dumps(result, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError) as e:
        # If the tool's result isn't valid JSON, wrap it in an error message
        # but still provide the detection_type
        return json.dumps(
            {
                "tool_name": tool_name,
                "output": f"Error processing tool result: {e}. Original result: {result_str}",
                "error": "Tool result not valid JSON",
                "detection_type": detection_type,
            },
            ensure_ascii=False,
        )


def detect(input_text: str) -> dict[str, Any]:
    """Determine what type of content ``input_text`` is.

    Returns a dict with:
      - ``tool``: the tool name (or ``None`` if no match)
      - ``detection_type``: human-readable description
      - ``confidence``: 0.0 to 1.0
    """
    input_text = input_text.strip()

    if not input_text:
        return {
            "tool": "unknown",
            "detection_type": "empty",
            "confidence": 1.0,
        }

    # 1. Check JWT (most specific pattern — 3 base64 parts)
    result = _try_jwt(input_text)
    if result["confidence"] > 0.5:
        return result

    # 2. Check URL
    result = _try_url(input_text)
    if result["confidence"] > 0.7:
        return result

    # 3. Check timestamp (before JSON — a bare number should route here, not JSON)
    result = _try_timestamp(input_text)
    if result["confidence"] > 0.7:
        return result

    # 4. Check JSON (after timestamp so numbers route correctly)
    result = _try_json(input_text)
    if result["confidence"] > 0.5:
        return result

    # 5. Check Base64
    result = _try_base64(input_text)
    if result["confidence"] > 0.3:
        return result

    # 6. Check config formats (YAML, TOML, INI, ENV, CSV, XML)
    result = _try_config_format(input_text)
    if result["confidence"] > 0.5:
        return result

    # Default: show all tools
    return {
        "tool": None,
        "detection_type": "unknown",
        "confidence": 0.0,
    }


def _try_json(text: str) -> dict[str, Any]:
    """Check if text is valid JSON."""
    try:
        parsed = json.loads(text)
        # Object or array — definitely JSON
        if isinstance(parsed, (dict, list)):
            return {
                "tool": "json",
                "detection_type": "JSON detected",
                "confidence": 1.0,
            }
        # Primitive JSON values — still valid but less certain
        return {
            "tool": "json",
            "detection_type": "JSON value detected",
            "confidence": 0.6,
        }
    except (json.JSONDecodeError, ValueError):
        pass

    return {"tool": None, "detection_type": "", "confidence": 0.0}


def _try_jwt(text: str) -> dict[str, Any]:
    """Check if text looks like a JWT (3 base64 parts separated by dots)."""
    parts = text.split(".")
    if len(parts) != 3:
        return {"tool": None, "detection_type": "", "confidence": 0.0}

    # Must have at least some content in each part (signature can be short)
    if len(parts[0]) < 4 or len(parts[1]) < 4 or len(parts[2]) < 4:
        return {"tool": None, "detection_type": "", "confidence": 0.0}

    # All parts must be URL-safe Base64
    b64_pattern = re.compile(r"^[A-Za-z0-9_-]+=*$")
    if not all(b64_pattern.match(p) for p in parts):
        return {"tool": None, "detection_type": "", "confidence": 0.0}

    return {
        "tool": "jwt",
        "detection_type": "JWT token detected",
        "confidence": 0.95,
    }


def _try_url(text: str) -> dict[str, Any]:
    """Check if text looks like a valid URL."""
    original_text = text.strip()

    # Must have a scheme or look like a domain
    if "://" not in original_text:
        # If no scheme, try prepending http:// to make urlparse work better
        text_to_parse = "http://" + original_text
    else:
        text_to_parse = original_text

    try:
        parsed = urlparse(text_to_parse)

        # A valid URL must have a scheme and a network location (netloc)
        # For the case where we prepended http://, we expect netloc.
        # For original_text with a scheme, we expect both.
        if parsed.scheme and parsed.netloc:
            # If we prepended, and it parsed well, it's a confident URL
            if "://" not in original_text:
                return {
                    "tool": "url",
                    "detection_type": "Domain or implicit URL detected",
                    "confidence": 0.8, # Slightly lower than explicit URL
                }
            else:
                return {
                    "tool": "url",
                    "detection_type": "URL detected",
                    "confidence": 0.95,
                }
        
        # This branch might catch things like "mailto:user@example.com"
        # or file paths if parsed.scheme is present but netloc is not meaningful for HTTP/HTTPS
        if parsed.scheme and original_text == text_to_parse: # only if original text had a scheme
            return {
                "tool": "url",
                "detection_type": f"URL detected ({parsed.scheme} scheme)",
                "confidence": 0.7,
            }

    except ValueError: # urlparse can raise ValueError for truly malformed URLs
        pass

    return {"tool": None, "detection_type": "", "confidence": 0.0}


def _try_timestamp(text: str) -> dict[str, Any]:
    """Check if text looks like a Unix timestamp."""
    cleaned_text = text.strip()

    # Must be numeric (possibly with decimal)
    if not re.match(r"^-?\d+(\.\d+)?$", cleaned_text):
        return {"tool": None, "detection_type": "", "confidence": 0.0}

    try:
        val = float(cleaned_text)
    except ValueError:
        return {"tool": None, "detection_type": "", "confidence": 0.0}

    # Accept epoch timestamps between year 1970 and ~year 2300 (roughly)
    # This is a heuristic to differentiate from arbitrary numbers.
    # (0 to roughly 4.1 billion for 32-bit, but we accept up to 200 billion for ms)
    # The upper bound is chosen to accommodate future timestamps but avoid very large arbitrary numbers.
    if 0 < val < 1_000_000_000_000: # Up to 1 trillion for seconds (around year 3365)
        # Likely seconds
        return {
            "tool": "timestamp",
            "detection_type": "Unix timestamp detected",
            "confidence": 0.9,
        }
    if 1_000_000_000_000 <= val < 1_000_000_000_000_000: # Up to 1 quadrillion for milliseconds (around year 33650)
        # Likely milliseconds
        return {
            "tool": "timestamp",
            "detection_type": "Unix timestamp (ms) detected",
            "confidence": 0.85,
        }

    return {"tool": None, "detection_type": "", "confidence": 0.0}


def _try_base64(text: str) -> dict[str, Any]:
    """Check if text looks like base64 content."""
    text = text.strip()

    # Need at least 8 chars
    if len(text) < 8:
        return {"tool": None, "detection_type": "", "confidence": 0.0}

    # Base64 strings must have length divisible by 4 after padding
    # or be URL-safe without padding (len % 4 = 1 is invalid for standard base64)
    if len(text) % 4 == 1:
        return {"tool": None, "detection_type": "", "confidence": 0.0}

    # Attempt URL-safe base64 decode, which handles both standard and URL-safe variants
    try:
        # Pad if necessary for standard b64decoding
        padded_text = text + "=" * ((4 - len(text) % 4) % 4)
        decoded_bytes = base64.urlsafe_b64decode(padded_text)
        decoded_str = decoded_bytes.decode("ascii")

        # Check if the decoded string is mostly printable ASCII. This helps
        # filter out random binary data that might accidentally decode.
        printable_chars = sum(1 for c in decoded_str if 32 <= ord(c) <= 126)
        if printable_chars / max(1, len(decoded_str)) < 0.7:  # At least 70% printable
            return {"tool": None, "detection_type": "", "confidence": 0.0}

        # If it decodes and is largely printable, it's a good candidate
        confidence = 0.8
        if text.endswith("==") or text.endswith("="):
            confidence += 0.1 # Higher confidence if it has padding
        
        return {
            "tool": "base64",
            "detection_type": "Base64 encoded data",
            "confidence": round(confidence, 2),
        }
    except (ValueError, TypeError, UnicodeDecodeError):
        pass # Not valid base64 or not ASCII

    return {"tool": None, "detection_type": "", "confidence": 0.0}


def _try_config_format(text: str) -> dict[str, Any]:
    """Check if text looks like a config file format (YAML, TOML, INI, ENV, CSV, XML).

    Uses the ConfigForge detection engine for accurate identification.
    """
    try:
        detected = _cf.detect_format(text)
    except Exception: # TODO: Replace with more specific exception from configforge if available
        return {"tool": None, "detection_type": "", "confidence": 0.0}

    if detected == "yaml":
        return {"tool": "cf", "detection_type": f"YAML config detected", "confidence": 0.85}
    elif detected == "toml":
        return {"tool": "cf", "detection_type": "TOML config detected", "confidence": 0.88}
    elif detected == "ini":
        return {"tool": "cf", "detection_type": "INI config detected", "confidence": 0.85}
    elif detected == "env":
        return {"tool": "cf", "detection_type": "Environment file detected", "confidence": 0.82}
    elif detected == "csv":
        return {"tool": "cf", "detection_type": "CSV data detected", "confidence": 0.80}
    elif detected == "xml":
        return {"tool": "cf", "detection_type": "XML data detected", "confidence": 0.85}
    return {"tool": None, "detection_type": "", "confidence": 0.0}


def _show_all_tools(input_text: str, detection_type: str) -> str:
    """Return a listing of all available tools as a result string."""
    lines = [
        "═" * 60,
        "  DEV BENCH  —  Developer Tools",
        "═" * 60,
        "",
        f"  Input: \"{_truncate(input_text, 80)}\"",
        f"  Detection: {detection_type} (no specific tool matched)",
        "",
        "  Available tools:",
        "",
    ]
    for name in tools.TOOL_NAMES:
        help_text = tools.TOOL_HELP.get(name, "")
        lines.append(f"    devbench {name:<12}  {help_text}")
    lines.append("")
    lines.append("  Quick detection:")
    lines.append("    devbench detect \"<your content>\"")
    lines.append("")

    return json.dumps(
        {
            "tool_name": "detect",
            "output": "\n".join(lines),
            "error": None,
            "detection_type": detection_type,
            "metadata": {"available_tools": tools.TOOL_NAMES, "input": input_text},
        },
        ensure_ascii=False,
    )


def _truncate(text: str, max_len: int = 80) -> str:
    """Truncate text for display."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


# ---------------------------------------------------------------------------
# Re-exports
# ---------------------------------------------------------------------------

__all__ = [
    "detect",
    "detect_and_run",
]