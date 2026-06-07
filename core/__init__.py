"""Devbench — Developer tools library.

A pure-Python library providing 8 developer utilities, clipboard
auto-detection, and a CLI entry point. Designed to be embedded in
a SwiftUI macOS menubar app.

Quick start:
    >>> from devbench.core import tools
    >>> tools.json_formatter('{"name": "hello"}')

    >>> from devbench.core import detector
    >>> detector.detect_and_run('eyJhbGciOiJIUzI1NiJ9.eyJ0ZXN0Ijp0cnVlfQ.abc123')
"""

from __future__ import annotations

from . import cli
from . import detector
from . import models
from . import tools

from .detector import detect, detect_and_run
from .models import ToolResult
from .tools import (
    TOOLS,
    TOOL_HELP,
    TOOL_NAMES,
    base64_codec,
    configforge_tool,
    get_tool,
    hash_generator,
    json_formatter,
    jwt_decoder,
    run_tool,
    text_diff,
    timestamp_converter,
    url_codec,
    uuid_generator,
)

__all__ = [
    # Submodules
    "cli",
    "detector",
    "models",
    "tools",
    # Tools
    "json_formatter",
    "base64_codec",
    "configforge_tool",
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
    # Detector
    "detect",
    "detect_and_run",
    # Models
    "ToolResult",
]

__version__ = "0.1.0"