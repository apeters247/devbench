"""Clipboard content auto-detector for Devbench.

Given a string, determine what it most likely is and route to the
appropriate tool. Returns a ToolResult or JSON-ish result string.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from . import models
from . import tools

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
    except (json.JSONDecodeError, TypeError):
        return result_str


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
    text = text.strip()

    # Must have a scheme
    if "://" not in text:
        return {"tool": None, "detection_type": "", "confidence": 0.0}

    try:
        parsed = urlparse(text)
        if parsed.scheme and parsed.netloc:
            # Valid URL with both scheme and network location
            return {
                "tool": "url",
                "detection_type": "URL detected",
                "confidence": 0.95,
            }
        # Has scheme but no netloc — could be a mailto, etc.
        if parsed.scheme in ("http", "https", "ftp", "file"):
            return {
                "tool": "url",
                "detection_type": "URL detected (partial)",
                "confidence": 0.7,
            }
    except Exception:
        pass

    # Also check for plain domain pattern
    domain_pattern = re.compile(
        r"^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\."
        r"[a-zA-Z]{2,}(/[a-zA-Z0-9./?=%-_]*)?$"
    )
    if domain_pattern.match(text):
        return {
            "tool": "url",
            "detection_type": "Domain detected",
            "confidence": 0.6,
        }

    return {"tool": None, "detection_type": "", "confidence": 0.0}


def _try_timestamp(text: str) -> dict[str, Any]:
    """Check if text looks like a Unix timestamp."""
    text = text.strip().strip('"').strip("'")

    # Must be numeric (possibly with decimal)
    if not re.match(r"^-?\d+(\.\d+)?$", text):
        return {"tool": None, "detection_type": "", "confidence": 0.0}

    try:
        val = float(text)
    except ValueError:
        return {"tool": None, "detection_type": "", "confidence": 0.0}

    # Accept epoch timestamps between year 1970 and 2100
    # (0 to roughly 4.1 billion for 32-bit, but we accept up to 200 billion for ms)
    if 0 < val < 1_000_000_000_000:
        # Likely seconds
        return {
            "tool": "timestamp",
            "detection_type": "Unix timestamp detected",
            "confidence": 0.9,
        }
    if 1_000_000_000_000 <= val < 1_000_000_000_000_000:
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

    # Check charset
    cleaned = text.rstrip("=")
    if not re.match(r"^[A-Za-z0-9+/]+$", cleaned):
        # Also try URL-safe variant
        if not re.match(r"^[A-Za-z0-9_-]+$", cleaned):
            return {"tool": None, "detection_type": "", "confidence": 0.0}

    # Base64 strings usually have length divisible by 4 after padding
    if len(text) % 4 == 0:
        confidence = 0.7
    else:
        confidence = 0.4

    # Penalize very short strings
    if len(text) < 16:
        confidence *= 0.5

    # Penalize if it looks like plain English
    if re.search(r"[aeiou]{3,}", cleaned, re.IGNORECASE):
        confidence *= 0.3

    if confidence > 0.3:
        return {
            "tool": "base64",
            "detection_type": "Base64 encoded data",
            "confidence": round(confidence, 2),
        }

    return {"tool": None, "detection_type": "", "confidence": 0.0}


def _try_config_format(text: str) -> dict[str, Any]:
    """Check if text looks like a config file format (YAML, TOML, INI, ENV, CSV, XML).

    Uses the ConfigForge detection engine for accurate identification.
    """
    try:
        from . import configforge as _cf
        detected = _cf.detect_format(text)
    except Exception:
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