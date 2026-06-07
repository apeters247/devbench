"""Contract tests for the Python <-> Swift bridge.

These tests call the ``devbench`` CLI *exactly* the way the macOS SwiftUI app
does in ``ui/Sources/Bridge/PythonBridge.swift``: spawn a subprocess, capture
stdout, and JSON-decode it. They pin down the contract the Swift side relies
on so that the Python CLI and the Swift bridge can never silently drift apart.

The contract (after the Swift Bridge Fix):

1. ``detect`` keeps its default envelope UNCHANGED (874 existing tests depend on
   it). A new ``--swift`` flag emits a friendlier, fixed-shape envelope with
   keys ``{tool_name, output, error, detection_type, metadata}`` that Swift's
   ``DetectionResult`` decodes directly.
2. The UI tool picker (``ui/Sources/Views/ContentView.swift``) offers only REAL
   CLI subcommands: ``detect, cf, json, base64, jwt, hash, url, timestamp,
   uuid, diff``.
3. ``runTool`` returns the inner ``output`` field, not the whole JSON envelope
   (no double wrapping).
4. Every UI-relevant subcommand emits valid JSON Swift's JSONDecoder can parse.

Reference (kept in sync with the Swift source):
- ui/Sources/Views/ContentView.swift  -> tools list, DetectionResult
- ui/Sources/Bridge/PythonBridge.swift -> subprocess invocation + JSON decode
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_VIEW = REPO_ROOT / "ui" / "Sources" / "Views" / "ContentView.swift"


# ---------------------------------------------------------------------------
# Swift-side contract, transcribed from the Swift source.
# ---------------------------------------------------------------------------

# Keys Swift's DetectionResult decodes from `devbench detect --swift`.
SWIFT_DETECT_KEYS = {
    "tool_name",
    "output",
    "error",
    "detection_type",
    "metadata",
}

# The tool picker after the fix. Each UI label maps to a real CLI subcommand:
# "Auto-Detect" runs `detect`, "Convert" runs `cf`, the rest lowercase to their
# subcommand name. These are the ONLY tools the UI may offer.
UI_TOOL_TO_SUBCOMMAND = {
    "Auto-Detect": "detect",
    "Convert": "cf",
    "JSON": "json",
    "Base64": "base64",
    "JWT": "jwt",
    "Hash": "hash",
    "URL": "url",
    "Timestamp": "timestamp",
    "UUID": "uuid",
    "Diff": "diff",
}


# ---------------------------------------------------------------------------
# Subprocess helper — mirrors PythonBridge.runDevbench(arguments:)
# ---------------------------------------------------------------------------


def _devbench_command() -> list[str]:
    """Resolve the invocation PythonBridge would use.

    Swift tries the ``devbench`` executable on PATH first, then falls back to
    ``python3 -m core.cli``. We mirror that.
    """
    found = shutil.which("devbench")
    if found:
        return [found]
    return [sys.executable, "-m", "core.cli"]


def run_devbench(args: list[str], stdin: str | None = None) -> subprocess.CompletedProcess:
    """Run devbench as a subprocess, exactly as the Swift bridge does."""
    return subprocess.run(
        _devbench_command() + args,
        input=stdin,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def detect_json(text: str, swift: bool = False) -> dict:
    """Call ``devbench detect [--swift] <text>`` and JSON-decode stdout."""
    args = ["detect"]
    if swift:
        args.append("--swift")
    args.append(text)
    proc = run_devbench(args)
    assert proc.returncode == 0, (
        f"`devbench {' '.join(args[:-1])}` exited {proc.returncode}; Swift expects 0.\n"
        f"stderr: {proc.stderr.strip()}"
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:  # pragma: no cover - failure detail
        raise AssertionError(
            f"Swift JSONDecoder would fail: {e}\nRaw stdout: {proc.stdout[:500]!r}"
        )


def _content_view_tools() -> list[str]:
    """Extract the `tools` array literal from ContentView.swift."""
    src = CONTENT_VIEW.read_text(encoding="utf-8")
    m = re.search(r"private let tools\s*=\s*\[([^\]]*)\]", src)
    assert m, "Could not find the `tools` array in ContentView.swift"
    return re.findall(r'"([^"]+)"', m.group(1))


# A representative sample of inputs the clipboard monitor would feed `detect`.
DETECT_SAMPLES = [
    '{"name": "test", "count": 1}',
    "eyJhbGciOiJIUzI1NiJ9.eyJ0ZXN0IjoxfQ.",
    "https://example.com/path?q=1",
    "1700000000",
]


# ---------------------------------------------------------------------------
# Baseline: the CLI emits decodable JSON and the default envelope is untouched.
# ---------------------------------------------------------------------------


def test_detect_default_output_is_unchanged():
    """The default `devbench detect` envelope must NOT gain Swift-only keys.

    The 874 existing tests depend on the default shape, so the fix must live
    behind `--swift` and leave the default emitting its own keys.
    """
    obj = detect_json('{"name": "test"}')
    # The default envelope keeps its original keys; it must NOT be silently
    # reshaped into the Swift-only envelope.
    for key in ("tool_name", "output", "error", "detection_type"):
        assert key in obj, f"default detect envelope lost key {key!r}"


# ---------------------------------------------------------------------------
# Task 1.1 — detect --swift envelope keys.
# ---------------------------------------------------------------------------


def test_detect_envelope_keys():
    """`devbench detect --swift` must emit every key Swift's DetectionResult needs.

    We do NOT rename detect's default keys (that breaks 874 tests). Instead the
    friendlier envelope is gated behind the --swift flag.
    """
    for sample in DETECT_SAMPLES:
        obj = detect_json(sample, swift=True)
        missing = SWIFT_DETECT_KEYS - set(obj.keys())
        assert not missing, (
            f"Swift's DetectionResult cannot decode {sample!r}: missing keys "
            f"{sorted(missing)}.\nCLI emitted keys: {sorted(obj.keys())}"
        )
        # metadata must always be present as an object so [String: String]?
        # decoding never trips over a surprise type.
        assert isinstance(obj["metadata"], dict), (
            f"--swift metadata must be an object, got {type(obj['metadata']).__name__}"
        )
        # Swift decodes metadata as [String: String]; every value is a string.
        non_string = {k: v for k, v in obj["metadata"].items() if not isinstance(v, str)}
        assert not non_string, (
            f"--swift metadata values must all be strings for {sample!r}: {non_string}"
        )


# ---------------------------------------------------------------------------
# Task 1.2 — UI tool names must be real CLI subcommands.
# ---------------------------------------------------------------------------


def test_ui_tool_names_are_valid():
    """Every tool in ContentView.swift must map to a runnable CLI subcommand.

    The picker no longer offers fictional tools (Format/Lint/Explain/Refactor/
    Document). It offers exactly the real ones, each of which exits 0.
    """
    ui_tools = _content_view_tools()
    assert set(ui_tools) == set(UI_TOOL_TO_SUBCOMMAND), (
        f"ContentView tools {ui_tools} != expected {list(UI_TOOL_TO_SUBCOMMAND)}"
    )
    for ui_name in ui_tools:
        subcommand = UI_TOOL_TO_SUBCOMMAND[ui_name]
        proc = run_devbench([subcommand, "hello"])
        assert proc.returncode == 0, (
            f"UI tool {ui_name!r} -> `devbench {subcommand}` exited "
            f"{proc.returncode}; the app would show this as an error.\n"
            f"stderr: {proc.stderr.strip()}"
        )


# ---------------------------------------------------------------------------
# Task 1.3 — runTool returns the `output` field (no double wrapping).
# ---------------------------------------------------------------------------


def test_output_not_double_wrapped():
    """The user-facing `output` is the tool's result, not a nested envelope.

    Swift's runTool extracts `output` from the envelope. That field must be the
    plain tool result (e.g. formatted JSON), never another full JSON envelope.
    """
    # detect --swift on a JSON array: output is the formatted JSON, not a wrapper.
    obj = detect_json('[1, 2, 3]', swift=True)
    out = obj["output"]
    assert isinstance(out, str), "`output` must be a string"
    assert json.loads(out) == [1, 2, 3]
    assert "tool_name" not in out, "`output` is double-wrapped (contains an envelope)"

    # Direct tool subcommand: same guarantee.
    proc = run_devbench(["json", '{"a": 1}'])
    envelope = json.loads(proc.stdout)
    assert json.loads(envelope["output"]) == {"a": 1}
    assert "tool_name" not in envelope["output"]


# ---------------------------------------------------------------------------
# Task 1.4 — every UI-relevant subcommand produces valid JSON.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("subcommand", sorted(set(UI_TOOL_TO_SUBCOMMAND.values())))
def test_all_subcommands_produce_json(subcommand):
    """Each UI subcommand must emit valid JSON with a string `output` field."""
    proc = run_devbench([subcommand, "hello"])
    assert proc.returncode == 0, (
        f"`devbench {subcommand}` exited {proc.returncode}\nstderr: {proc.stderr.strip()}"
    )
    try:
        obj = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"`devbench {subcommand}` stdout is not JSON: {e}\nRaw: {proc.stdout[:300]!r}"
        )
    assert isinstance(obj, dict), f"`devbench {subcommand}` must emit a JSON object"
    assert "output" in obj, f"`devbench {subcommand}` envelope missing `output`"
    assert isinstance(obj["output"], str), (
        f"`devbench {subcommand}` `output` must be a string"
    )
