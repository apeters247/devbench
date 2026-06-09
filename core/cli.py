#!/usr/bin/env python3
"""Devbench CLI — command-line interface for the Devbench core library.

Usage:
    devbench detect "<text>"         Auto-detect and apply the right tool.
    devbench json "{...}"            Run a specific tool.
    devbench --list                  List all available tools.
    devbench batch --json --files *.txt   Batch process files.

Input can come from a command-line argument or stdin (pipe).

Examples:
    echo '{"name": "test"}' | devbench json
    devbench detect 'eyJhbGciOiJIUzI1NiJ9.eyJ0ZXN0IjoxfQ.'
    devbench --list
    devbench batch --json --files *.log
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, NoReturn
import importlib.util

from . import detector
from . import tools
from ._version import __version__ as _VERSION

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXIT_SUCCESS = 0
EXIT_ERROR = 1


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point. Returns exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    # --list / -l  → show available tools (at global level or as subcommand)
    if getattr(args, "global_list", False) or args.command == "list":
        print(_render_tool_list())
        return EXIT_SUCCESS

    # If no subcommand was given, show help
    if args.command is None:
        parser.print_help()
        return EXIT_SUCCESS

    # batch command
    if args.command == "batch":
        return _run_batch(args)

    # cf --serve  → launch the local web UI (handle before reading stdin)
    if args.command == "cf" and getattr(args, "serve", False):
        return _run_cf_serve(getattr(args, "port", 8080), getattr(args, "host", "127.0.0.1"))

    # cf --api  → launch the JSON HTTP API (handle before reading stdin)
    if args.command == "cf" and getattr(args, "api", False):
        return _run_cf_api(getattr(args, "api_port", 8081), getattr(args, "host", "127.0.0.1"))

    # cf --batch  → batch convert files matching a glob (handle before reading stdin)
    if args.command == "cf" and getattr(args, "batch", False):
        return _run_cf_batch(args)

    # cf CRUD / merge ops — read input themselves (file path or stdin)
    if args.command == "cf" and getattr(args, "get", None):
        return _run_cf_get(args)
    if args.command == "cf" and getattr(args, "set_kv", None):
        return _run_cf_set(args)
    if args.command == "cf" and getattr(args, "delete", None):
        return _run_cf_delete(args)
    if args.command == "cf" and getattr(args, "merge", None):
        return _run_cf_merge(args)

    # license commands (server starts before reading stdin)
    if args.command == "license":
        lc = getattr(args, "license_command", None)
        if lc == "server":
            return _run_license_server(getattr(args, "host", "127.0.0.1"), getattr(args, "port", 9001))
        elif lc == "activate":
            return _run_license_activate(args.key, args.server, args.machine_id)
        elif lc == "verify":
            return _run_license_verify(args.key, args.server)
        elif lc == "trial":
            return _run_license_trial(args.server, getattr(args, "email", ""))
        else:
            print("usage: devbench license {activate|verify|server|trial}", file=sys.stderr)
            return EXIT_ERROR

    # detect or specific tool command
    input_text = _get_input(args)

    if args.command == "detect":
        result_str = detector.detect_and_run(input_text)
        if getattr(args, "swift", False):
            result_str = _swiftify_detect(result_str)
    elif args.command == "cf" and (getattr(args, "list_formats", False)):
        result_str = _list_cf_formats()
    elif args.command == "cf":
        result_str = _run_cf(input_text, args)
    elif args.command in tools.TOOL_NAMES:
        # Route to a specific tool
        # The tool function will handle its specific arguments if any
        # All arguments are passed through `args` and accessed in the tool function.
        if args.command == "token":
            result_str = tools.token_counter(input_text, model_name=args.model)
        elif args.command == "chunk":
            result_str = tools.text_chunker(input_text, chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap)
        else:
            result_str = tools.run_tool(args.command, input_text)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return EXIT_ERROR

    _emit_output(result_str, args)
    
    try:
        parsed_result = json.loads(result_str)
        if parsed_result.get("error"):
            return EXIT_ERROR
    except json.JSONDecodeError:
        pass # Not a JSON result, assume success if no other errors.

    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devbench",
        description="Developer tools — 11 utilities in one CLI: json, base64, jwt, hash, url, timestamp, uuid, diff, token, chunk, cf (config converter).",
        epilog="Try: devbench detect 'some content' or pipe input: echo 'text' | devbench json",
    )

    parser.add_argument(
        "--list", "-l",
        action="store_true",
        dest="global_list",
        help="List all available tools",
    )
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"devbench {_VERSION}",
        help="Show version and exit",
    )
    parser.add_argument(
        "--pretty", "-p",
        action="store_true",
        help="Pretty-print the output (JSON only, otherwise no effect)",
    )
    parser.add_argument(
        "--raw", "-r",
        action="store_true",
        help="Output raw text instead of JSON envelope",
    )

    sub = parser.add_subparsers(dest="command")

    # detect
    detect_p = sub.add_parser("detect", help="Auto-detect content type and apply tool")
    detect_p.add_argument(
        "--swift",
        action="store_true",
        help="Emit a Swift-friendly JSON envelope (for the macOS app bridge)",
    )
    detect_p.add_argument("text", nargs="?", default=None, help="Text to detect")
    _add_common_args(detect_p)

    # specific tool subcommands
    for tool_name in tools.TOOL_NAMES:
        tool_help = tools.TOOL_HELP.get(tool_name, f"Run {tool_name} tool")
        tool_p = sub.add_parser(tool_name, help=tool_help)
        # ConfigForge needs extra flags
        if tool_name == "cf":
            tool_p.add_argument("--to", default=None, help="Output format: json/yaml/toml/xml/csv/ini/env")
            tool_p.add_argument("--from", dest="from_fmt", default="auto", help="Input format (auto-detect by default)")
            tool_p.add_argument("--list-formats", action="store_true", help="List supported formats")
            tool_p.add_argument("--serve", action="store_true", help="Launch the local web UI (browser config converter)")
            tool_p.add_argument("--port", type=int, default=8080, help="Port for --serve (default: 8080)")
            tool_p.add_argument("--host", default="127.0.0.1",
                                help="Host to bind (default: 127.0.0.1; use 0.0.0.0 inside Docker)")
            tool_p.add_argument("--api", action="store_true", help="Launch the JSON HTTP API (POST /convert)")
            tool_p.add_argument("--api-port", type=int, default=8081, help="Port for --api (default: 8081)")
            tool_p.add_argument("--batch", action="store_true", help="Treat input as a glob and convert every match")
            tool_p.add_argument("--stream", action="store_true", help="Use streaming mode for memory-efficient batch conversion (10K+ files)")
            tool_p.add_argument("--output-dir", help="Output directory for --batch mode")
            tool_p.add_argument("--indent", type=int, default=2, help="Indentation width for YAML/JSON output (default: 2)")
            tool_p.add_argument("--flatten-xml", action="store_true", help="Flatten nested XML into dotted keys")
            tool_p.add_argument("--no-comments", action="store_true", help="Do not preserve comments")
            tool_p.add_argument("--sort-keys", action="store_true", help="Sort keys in output")
            tool_p.add_argument("--no-infer-dates", action="store_true", help="Keep ISO-8601 date strings as strings (TOML)")
            tool_p.add_argument("--null-handling", default="skip", choices=["skip", "comment", "empty", "error"],
                                help="How to represent null/None in TOML (default: skip)")
            tool_p.add_argument("--get", metavar="PATH", default=None,
                                help="Extract a value by dot-notation path (e.g. server.port). Prints scalar or JSON for dicts/lists.")
            tool_p.add_argument("--set", metavar=("PATH", "VALUE"), nargs=2, dest="set_kv",
                                help="Set a value by dot-notation path. Value parsed as JSON (booleans, numbers, null); strings need no quoting.")
            tool_p.add_argument("--in-place", "-i", action="store_true", dest="in_place",
                                help="Write --set/--delete/--merge result back to the source file (requires a file path argument, not stdin).")
            tool_p.add_argument("--delete", metavar="PATH", default=None,
                                help="Delete a key by dot-notation path. Output defaults to input format.")
            tool_p.add_argument("--merge", metavar="OVERLAY", default=None,
                                help="Deep-merge OVERLAY file onto the base input. Output defaults to base format.")
            tool_p.add_argument("--list-merge", metavar="MODE", dest="list_merge", default="replace",
                                choices=["replace", "append"],
                                help="How to merge lists when using --merge: replace (default) overwrites; append extends.")
        elif tool_name == "token":
            tool_p.add_argument("--model", default="cl100k_base", help="tiktoken model to use (default: cl100k_base)")
        elif tool_name == "chunk":
            tool_p.add_argument("--chunk-size", type=int, default=500, help="Max tokens per chunk (default: 500)")
            tool_p.add_argument("--chunk-overlap", type=int, default=100, help="Overlap between chunks (default: 100)")
        tool_p.add_argument("text", nargs="?", default=None, help="Input text")
        _add_common_args(tool_p)

    # list subcommand (optional, --list is also available at top level)
    list_p = sub.add_parser("list", help="List all available tools")
    _add_common_args(list_p)

    # batch
    batch_p = sub.add_parser("batch", help="Batch process files")
    batch_p.add_argument("--json", action="store_true", help="Output JSON results per file")
    batch_p.add_argument("--tool", default="json", help=f"Tool to apply (default: json). Tools: {', '.join(tools.TOOL_NAMES)}")
    batch_p.add_argument("--files", nargs="+", required=True, help="Files to process")
    _add_common_args(batch_p)

    # license
    license_p = sub.add_parser("license", help="License key management (activate, verify, server)")
    license_sub = license_p.add_subparsers(dest="license_command")

    license_activate_p = license_sub.add_parser("activate", help="Activate a license on this machine")
    license_activate_p.add_argument("key", help="License key to activate")
    license_activate_p.add_argument("--server", default="http://127.0.0.1:9001", help="License server URL (default: http://127.0.0.1:9001)")
    license_activate_p.add_argument("--machine-id", default=None, help="Machine identifier (default: auto-detect)")

    license_verify_p = license_sub.add_parser("verify", help="Verify a license key against the server")
    license_verify_p.add_argument("key", help="License key to verify")
    license_verify_p.add_argument("--server", default="http://127.0.0.1:9001", help="License server URL (default: http://127.0.0.1:9001)")

    license_trial_p = license_sub.add_parser("trial", help="Start a time-limited trial")
    license_trial_p.add_argument("--server", default="http://127.0.0.1:9001", help="License server URL (default: http://127.0.0.1:9001)")
    license_trial_p.add_argument("--email", default="", help="Email address for the trial (optional)")
    license_server_p = license_sub.add_parser("server", help="Start the license server")
    license_server_p.add_argument("--port", type=int, default=9001, help="Port (default: 9001)")
    license_server_p.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")

    return parser


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--pretty", "-p",
        action="store_true",
        help="Pretty-print the output (JSON only, otherwise no effect)",
    )
    parser.add_argument(
        "--raw", "-r",
        action="store_true",
        help="Output raw text instead of JSON envelope",
    )


# ---------------------------------------------------------------------------
# Input handling
# ---------------------------------------------------------------------------


def _get_input(args: argparse.Namespace) -> str:
    """Get input text from argument or stdin."""
    if hasattr(args, "text") and args.text is not None:
        return args.text

    # Try stdin (pipe)
    if not sys.stdin.isatty():
        try:
            return sys.stdin.read().strip()
        except OSError:
            pass

    return ""


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _emit_output(result_str: str, args: argparse.Namespace) -> None:
    """Emit tool output to stdout."""
    raw = getattr(args, "raw", False)
    pretty = getattr(args, "pretty", False)

    if raw:
        # Try to extract just the output field from JSON wrapper
        try:
            parsed = json.loads(result_str)
            print(parsed.get("output", result_str))
        except (json.JSONDecodeError, TypeError):
            print(result_str)
        return

    if pretty:
        try:
            parsed = json.loads(result_str)
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
            return
        except (json.JSONDecodeError, TypeError):
            pass

    # Default: print as-is (already JSON-ish)
    print(result_str)


# ---------------------------------------------------------------------------
# Swift bridge envelope
# ---------------------------------------------------------------------------


def _stringify(value: Any) -> str:
    """Coerce a metadata value to a string for Swift's [String: String] decode."""
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _swiftify_detect(result_str: str) -> str:
    """Reshape a ``detect`` result into the fixed-shape envelope the macOS app decodes.

    The default ``detect`` output is intentionally left untouched (874 tests
    depend on it). This only runs for ``devbench detect --swift`` and guarantees
    every key Swift's ``DetectionResult`` needs is present:
    ``{tool_name, output, error, detection_type, metadata}`` — with ``metadata``
    always an object of string values (Swift decodes it as ``[String: String]?``).
    """
    try:
        parsed = json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        parsed = {}

    metadata = parsed.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    string_meta = {str(k): _stringify(v) for k, v in metadata.items()}

    envelope = {
        "tool_name": parsed.get("tool_name", "detect"),
        "output": parsed.get("output", ""),
        "error": parsed.get("error"),
        "detection_type": parsed.get("detection_type"),
        "metadata": string_meta,
    }
    return json.dumps(envelope, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tool list renderer
# ---------------------------------------------------------------------------


def _render_tool_list() -> str:
    """Render the list of available tools."""
    lines = [
        "═" * 60,
        "  DEV BENCH  —  Available Tools",
        "═" * 60,
        "",
    ]
    for name in tools.TOOL_NAMES:
        help_text = tools.TOOL_HELP.get(name, "")
        lines.append(f"  {name:<12}  {help_text}")
    lines.append("")
    lines.append("Usage:")
    lines.append("  devbench detect \"<text>\"     Auto-detect and apply tool")
    lines.append("  devbench <tool> \"<text>\"     Run a specific tool")
    lines.append("  echo \"text\" | devbench <tool>  Pipe input")
    lines.append("  devbench batch --tool json --files *.txt")
    lines.append("")

    result = {
        "tool_name": "list",
        "output": "\n".join(lines),
        "error": None,
        "detection_type": None,
        "metadata": {"available_tools": tools.TOOL_NAMES},
    }
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# ConfigForge helpers
# ---------------------------------------------------------------------------


def _enrich_error_message(error: str, raw_input: str = "", from_fmt: str = "auto") -> str:
    """Add actionable suggestions to cryptic error messages."""
    if not error:
        return "Conversion failed — unknown error."

    # Already a good message?  (starts with a suggestion or is about format detection)
    if "Try --from" in error or "Try --to" in error or "Specify" in error:
        return error

    # Common failure patterns we can detect
    lower = error.lower()
    suggestions = []

    if "column" in lower or "line" in lower or "parse" in lower or "syntax" in lower:
        # Parse errors: likely invalid input syntax
        suggestions.append("Check your input for syntax errors (missing quotes, brackets, colons)")
        if from_fmt == "auto":
            suggestions.append("Try specifying --from explicitly to skip auto-detection")

    if "yaml" in lower and ("scanner" in lower or "parser" in lower or "mapping" in lower):
        suggestions.append("YAML syntax error — check indentation (2 spaces) and colons")

    if "toml" in lower:
        suggestions.append("TOML syntax error — check brackets, quotes, and date formats")

    if "json" in lower and ("decode" in lower or "expect" in lower):
        suggestions.append("JSON syntax error — check trailing commas, quotes, and brackets")

    if "xml" in lower and ("etree" in lower or "parse" in lower):
        suggestions.append("XML syntax error — check well-formedness (matching tags, encoding)")

    if "unsupported" in lower or "format" in lower:
        suggestions.append(f"Run 'devbench cf --list-formats' to see all supported formats")

    if "file not found" in lower:
        suggestions.append("Check the file path and try again")

    if not suggestions:
        suggestions.append("Check your input is valid config content in the expected format")
        suggestions.append("Run 'devbench cf --list-formats' for available formats")

    return f"{error}. Suggestions: {'; '.join(suggestions)}."


def _run_cf(input_text: str, args: argparse.Namespace) -> str:
    """Run configforge with CLI arguments, passing through advanced options."""
    from . import configforge as _cf

    to_fmt = getattr(args, "to", None)
    from_fmt = getattr(args, "from_fmt", "auto")

    if not input_text:
        return tools._err("cf", "Empty input — pipe or provide config content.")

    # Collect advanced options that configforge.convert() accepts
    options = {}
    if hasattr(args, "indent"):
        options["indent"] = args.indent
    if hasattr(args, "flatten_xml") and args.flatten_xml:
        options["flatten_xml"] = True
    if hasattr(args, "no_comments") and args.no_comments:
        options["preserve_comments"] = False
    if hasattr(args, "sort_keys") and args.sort_keys:
        options["sort_keys"] = True
    if hasattr(args, "no_infer_dates") and args.no_infer_dates:
        options["infer_dates"] = False
    if hasattr(args, "null_handling"):
        options["null_handling"] = args.null_handling

    if to_fmt:
        # Format specified; run conversion with options
        raw = _cf.convert(input_text, to_fmt, from_fmt, **options)
        success = raw.get("success", False)
        error = raw.get("error")
        if not success and error:
            error = _enrich_error_message(error, input_text, from_fmt)
        # Surface comment-loss warning to stderr so users see it immediately
        cw = raw.get("comment_loss_warning")
        if cw:
            print(cw, file=sys.stderr)
        return tools._ok(
            "cf",
            raw.get("output", ""),
            input_format=raw.get("input_format"),
            output_format=raw.get("output_format"),
            input_size=raw.get("input_size"),
            output_size=raw.get("output_size"),
            success=success,
            comment_loss_warning=cw,
        )
    else:
        # No --to flag: auto-detect and convert to JSON for display
        detected = _cf.detect_format(input_text)
        if detected == "unknown":
            return tools._err(
                "cf",
                f"Could not detect format. Supported formats: {', '.join(_cf.SUPPORTED_FORMATS)}. "
                f"Try --from to specify manually, or paste valid "
                f"{'/'.join(f.upper() for f in _cf.SUPPORTED_FORMATS)}.",
            )
        raw = _cf.convert(input_text, "json", detected, **options)
        success = raw.get("success", False)
        error = raw.get("error")
        if not success and error:
            error = _enrich_error_message(error, input_text, from_fmt)
        return tools._ok(
            "cf",
            raw.get("output", ""),
            input_format=raw.get("input_format"),
            output_format="json",
            input_size=raw.get("input_size"),
            output_size=raw.get("output_size"),
            success=success,
            detection=f"Detected format: {detected}",
        )


def _run_cf_batch(args: argparse.Namespace) -> int:
    """Batch convert files matching a glob pattern.

    Handles `devbench cf --batch --output-dir ... --to yaml '*.json'`
    When ``--stream`` is passed, uses the lazy streaming generator for
    memory-efficient processing of 10K+ files.
    """
    from . import configforge as _cf

    input_glob = getattr(args, "text", None) or getattr(args, "input", None)
    to_fmt = getattr(args, "to", None)
    use_stream = getattr(args, "stream", False)

    if not input_glob:
        print("error: --batch requires a glob pattern as the text argument", file=sys.stderr)
        print("  Usage: devbench cf --batch --to yaml '*.json'", file=sys.stderr)
        return EXIT_ERROR
    if not to_fmt:
        print("error: --batch requires --to (target format)", file=sys.stderr)
        print("  Example: devbench cf --batch --to toml '*.ini'", file=sys.stderr)
        return EXIT_ERROR

    options = {}
    if hasattr(args, "indent") and args.indent != 2:
        options["indent"] = args.indent
    if hasattr(args, "flatten_xml") and args.flatten_xml:
        options["flatten_xml"] = True
    if hasattr(args, "no_comments") and args.no_comments:
        options["preserve_comments"] = False
    if hasattr(args, "sort_keys") and args.sort_keys:
        options["sort_keys"] = True
    if hasattr(args, "no_infer_dates") and args.no_infer_dates:
        options["infer_dates"] = False
    if hasattr(args, "null_handling"):
        options["null_handling"] = args.null_handling

    if use_stream:
        # Streaming mode: process one file at a time, never build full result list
        success = True
        file_count = 0
        for result in _cf.batch_convert_stream(
            input_glob, to_fmt, getattr(args, "output_dir", None), **options
        ):
            if "_summary" in result:
                # Final summary — report result
                s = result["_summary"]
                total_files = s["total"]
                print(f"\r[batch] Progress: {total_files}/{total_files} files  ", flush=True)
                if total_files == 0:
                    success = False
                if s["errors"] > 0:
                    print(f"[batch] Errors: {s['errors']}/{s['total']} files failed", file=sys.stderr)
                    success = False
                break
            file_count += 1
            fname = result.get("file", "?")
            ok = result.get("success", False)
            marker = "✓" if ok else "✗"
            print(f"\r[batch] [{file_count}] {marker} {fname}" + " " * 10, end="", flush=True)
            if not result.get("success"):
                success = False
        print()  # newline after streaming progress
        return 0 if success else 1
    else:
        results = _cf.batch_convert(input_glob, to_fmt, getattr(args, "output_dir", None), **options)
        if not results:
            print(f"[batch] No files matched glob: {input_glob}")
            return 1
        success = all(r.get("success") for r in results)
        return 0 if success else 1


def _run_cf_serve(port: int, host: str = "127.0.0.1") -> int:
    """Launch the ConfigForge web UI (web/serve.py) on the given port."""

    serve_path = Path(__file__).resolve().parent.parent / "web" / "serve.py"
    if not serve_path.exists():
        print(f"Web server not found: {serve_path}", file=sys.stderr)
        return EXIT_ERROR

    spec = importlib.util.spec_from_file_location("configforge_serve", serve_path)
    if spec is None or spec.loader is None:
        print(f"Could not load web server from {serve_path}", file=sys.stderr)
        return EXIT_ERROR

    serve = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(serve)
    return serve.run_server(port, host)


def _run_cf_api(port: int, host: str = "127.0.0.1") -> int:
    """Launch the ConfigForge REST API (web/api.py) on the given port.

    The API is a zero-dependency stdlib server (separate from --serve: a
    different module, different default port, different handler). It exposes
    POST /api/v1/convert, GET /api/v1/formats, GET /health and GET /, all
    delegating to ``core.configforge``.
    """
    api_path = Path(__file__).resolve().parent.parent / "web" / "api.py"
    if not api_path.exists():
        print(f"API server not found: {api_path}", file=sys.stderr)
        return EXIT_ERROR

    spec = importlib.util.spec_from_file_location("configforge_api", api_path)
    if spec is None or spec.loader is None:
        print(f"Could not load API server from {api_path}", file=sys.stderr)
        return EXIT_ERROR

    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    return api.run_server(port, host)


# ---------------------------------------------------------------------------
# License helpers
# ---------------------------------------------------------------------------


def _run_license_server(host: str = "127.0.0.1", port: int = 9001) -> int:
    """Launch the ConfigForge License Server (web/license_server.py)."""
    server_path = Path(__file__).resolve().parent.parent / "web" / "license_server.py"
    if not server_path.exists():
        print(f"License server not found: {server_path}", file=sys.stderr)
        return EXIT_ERROR

    spec = importlib.util.spec_from_file_location("license_server", server_path)
    if spec is None or spec.loader is None:
        print(f"Could not load license server from {server_path}", file=sys.stderr)
        return EXIT_ERROR

    server_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server_mod)
    return server_mod.run_server(host=host, port=port)


def _run_license_activate(key: str, server_url: str, machine_id: str | None = None) -> int:
    """Activate a license key by calling the license server."""
    import uuid

    if machine_id is None:
        try:
            machine_id = uuid.getnode()
            machine_id = f"mac-{machine_id:012x}"
        except Exception:
            import hashlib
            import socket
            machine_id = hashlib.md5(socket.gethostname().encode(), usedforsecurity=False).hexdigest()[:16]

    url = f"{server_url.rstrip('/')}/license/activate"
    payload = json.dumps({"key": key, "machine_id": machine_id}).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(f"Error contacting license server at {server_url}: {e}", file=sys.stderr)
        return EXIT_ERROR
    except json.JSONDecodeError:
        print("Error: invalid response from license server", file=sys.stderr)
        return EXIT_ERROR

    if data.get("error"):
        print(f"Activation failed: {data.get('message', 'unknown error')}", file=sys.stderr)
        return EXIT_ERROR

    print(f"✓ License activated on machine: {machine_id}")
    print(f"  Activations: {data.get('activations', 0)}/3 used")
    return EXIT_SUCCESS


def _run_license_trial(server_url: str, email: str = "") -> int:
    """Request a 14-day trial license key from the license server."""
    url = f"{server_url.rstrip('/')}/license/trial"
    payload = json.dumps({"email": email} if email else {}).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(f"Error contacting license server at {server_url}: {e}", file=sys.stderr)
        return EXIT_ERROR
    except json.JSONDecodeError:
        print("Error: invalid response from license server", file=sys.stderr)
        return EXIT_ERROR

    if data.get("error"):
        print(f"Trial request failed: {data.get('message', 'unknown error')}", file=sys.stderr)
        return EXIT_ERROR

    print(f"✓ Trial license key: {data.get('license_key', 'N/A')}")
    print(f"  Valid for 14 days. Activate with: devbench license activate --key <KEY>")
    return EXIT_SUCCESS


def _run_license_verify(key: str, server_url: str) -> int:
    """Verify a license key against the server."""
    url = f"{server_url.rstrip('/')}/license/verify?key={urllib.parse.quote(key)}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(f"Error contacting license server at {server_url}: {e}", file=sys.stderr)
        return EXIT_ERROR
    except json.JSONDecodeError:
        print("Error: invalid response from license server", file=sys.stderr)
        return EXIT_ERROR

    valid = data.get("valid", False)
    if valid:
        print("✓ License key is VALID")
        print(f"  Email:       {data.get('email', 'N/A')}")
        print(f"  Customer:    {data.get('customer_id', 'N/A')}")
        print(f"  Issued at:   {data.get('issued_at', 'N/A')}")
        print(f"  Activations: {data.get('activations', 0)}/3 used")
        return EXIT_SUCCESS
    else:
        print("✗ License key is INVALID or expired", file=sys.stderr)
        return EXIT_ERROR


# ---------------------------------------------------------------------------
# ConfigForge list
# ---------------------------------------------------------------------------


def _list_cf_formats() -> str:
    """List supported config formats."""
    from . import configforge as _cf
    lines = [
        "═" * 60,
        "  CONFIGFORGE  —  Supported Formats",
        "═" * 60,
        "",
    ]
    for fmt in _cf.SUPPORTED_FORMATS:
        lines.append(f"  • {fmt}")
    lines += [
        "",
        "Usage:",
        "  devbench cf --to yaml '{...}'        Convert JSON to YAML",
        "  devbench cf --to toml --from ini < file.ini   Specify input format",
        "  echo 'key: value' | devbench cf     Auto-detect & convert to JSON",
        "  devbench cf --to csv --from json data.json     File conversion",
        "  devbench cf --list-formats           Show this list",
        "",
        f"Supported formats: {', '.join(_cf.SUPPORTED_FORMATS)}",
        "Use '--from auto' to auto-detect input format.",
        "",
        "Why ConfigForge instead of yq/jq?",
        f"  • One tool for ALL formats ({len(_cf.SUPPORTED_FORMATS)} formats), not just YAML↔JSON",
        "  • TOML-aware type inference: booleans/numbers/dates stay typed",
        "  • Batch mode: devbench batch --tool cf --files *.yaml",
        "  • XML flattening: convert XML to clean YAML, not nested <tag> soup",
        "  • Comment preservation: YAML→JSON→YAML round-trips keep your docs",
        "  • Fully offline: no network calls, no SaaS, no data leaving your machine",
        "  • Multi-document YAML (--- separator) properly handled",
        "  • Interactive web UI: devbench cf --serve (runs in your browser)",
        "  • REST API: devbench cf --api --api-port 8081",
        "  • INI→TOML type inference: 'enabled=true' stays a boolean, not a string",
    ]
    result = {
        "tool_name": "cf",
        "output": "\n".join(lines),
        "error": None,
        "detection_type": None,
        "metadata": {"supported_formats": _cf.SUPPORTED_FORMATS},
    }
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------


def _run_batch(args: argparse.Namespace) -> int:
    """Process multiple files in batch mode."""
    tool_name = args.tool
    tool_fn = tools.get_tool(tool_name)

    if tool_fn is None:
        print(f"Unknown tool: {tool_name!r}", file=sys.stderr)
        return EXIT_ERROR

    results: list[dict[str, Any]] = []
    errors = 0

    for filepath_str in args.files:
        filepath = Path(filepath_str)
        if not filepath.exists():
            results.append({
                "file": str(filepath),
                "tool": tool_name,
                "error": f"File not found: {filepath}",
                "output": None,
            })
            errors += 1
            continue

        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError) as e:
            results.append({
                "file": str(filepath),
                "tool": tool_name,
                "error": f"Cannot read file: {e}",
                "output": None,
            })
            errors += 1
            continue

        try:
            result_str = tool_fn(content)
            parsed = json.loads(result_str)
            results.append({
                "file": str(filepath),
                "tool": tool_name,
                "error": parsed.get("error"),
                "output": parsed.get("output"),
                "metadata": parsed.get("metadata", {}),
            })
        except Exception as e:
            results.append({
                "file": str(filepath),
                "tool": tool_name,
                "error": str(e),
                "output": None,
            })
            errors += 1

    output = {
        "tool_name": "batch",
        "output": json.dumps(results, indent=2, ensure_ascii=False) if args.json else "",
        "error": None,
        "detection_type": None,
        "metadata": {
            "tool": tool_name,
            "files_processed": len(results),
            "errors": errors,
        },
    }

    if not args.json:
        # Human-readable output
        lines = [
            "═" * 60,
            f"  BATCH  —  Tool: {tool_name}  |  Files: {len(results)}  |  Errors: {errors}",
            "═" * 60,
            "",
        ]
        for r in results:
            status = "✓" if r.get("error") is None else "✗"
            lines.append(f"  {status}  {r['file']}")
            if r.get("error"):
                lines.append(f"       Error: {r['error']}")
        lines.append("")
        output["output"] = "\n".join(lines)

    print(json.dumps(output, indent=2, ensure_ascii=False) if args.json else output["output"])
    return EXIT_ERROR if errors > 0 else EXIT_SUCCESS


# ---------------------------------------------------------------------------
# cf CRUD / merge helpers
# ---------------------------------------------------------------------------


def _cf_read_file_or_content(args):
    """Return (content: str, file_path: Path|None) for CRUD ops.

    If args.text looks like an existing file path, read it.
    Otherwise treat it as raw content (or read stdin if absent).
    Returns (None, None) on I/O error (error already printed).
    """
    text_arg = getattr(args, "text", None)
    if text_arg is not None:
        p = Path(text_arg)
        if p.is_file():
            try:
                return p.read_text(encoding="utf-8"), p
            except OSError as e:
                print(f"error: {e}", file=sys.stderr)
                return None, None
        return text_arg, None
    if not sys.stdin.isatty():
        try:
            return sys.stdin.read().strip(), None
        except OSError:
            pass
    return "", None


def _cf_serialize_options(args) -> dict:
    opts: dict = {}
    if hasattr(args, "indent"):
        opts["indent"] = args.indent
    if getattr(args, "sort_keys", False):
        opts["sort_keys"] = True
    if getattr(args, "no_comments", False):
        opts["preserve_comments"] = False
    return opts


def _run_cf_get(args) -> int:
    from . import configforge as _cf
    content, _ = _cf_read_file_or_content(args)
    if content is None:
        return EXIT_ERROR
    from_fmt = getattr(args, "from_fmt", "auto")
    try:
        parsed = _cf.parse_text(content, fmt=None if from_fmt == "auto" else from_fmt)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if "error" in parsed:
        print(f"error: {parsed['error']}", file=sys.stderr)
        return EXIT_ERROR
    data = parsed.get("data", parsed)
    try:
        val = _cf._get_by_path(data, args.get)
    except (KeyError, IndexError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if isinstance(val, (dict, list)):
        sys.stdout.write(json.dumps(val, indent=2, ensure_ascii=False) + "\n")
    elif val is None:
        sys.stdout.write("null\n")
    else:
        sys.stdout.write(str(val) + "\n")
    return EXIT_SUCCESS


def _run_cf_set(args) -> int:
    from . import configforge as _cf
    content, file_path = _cf_read_file_or_content(args)
    if content is None:
        return EXIT_ERROR
    path, raw_value = args.set_kv
    value = _cf._coerce_set_value(raw_value)
    from_fmt = getattr(args, "from_fmt", "auto")
    try:
        parsed = _cf.parse_text(content, fmt=None if from_fmt == "auto" else from_fmt)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if "error" in parsed:
        print(f"error: {parsed['error']}", file=sys.stderr)
        return EXIT_ERROR
    detected_fmt = parsed.get("format")
    data = parsed.get("data", parsed)
    try:
        _cf._set_by_path(data, path, value)
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    to_fmt = getattr(args, "to", None) or detected_fmt
    if not to_fmt:
        print("error: cannot determine output format; use --to", file=sys.stderr)
        return EXIT_ERROR
    try:
        output_text = _cf.serialize(data, to_fmt, **_cf_serialize_options(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if not output_text.endswith("\n"):
        output_text += "\n"
    if getattr(args, "in_place", False):
        if file_path is None:
            print("error: --in-place requires a file argument, not stdin", file=sys.stderr)
            return EXIT_ERROR
        file_path.write_text(output_text, encoding="utf-8")
    else:
        sys.stdout.write(output_text)
    return EXIT_SUCCESS


def _run_cf_delete(args) -> int:
    from . import configforge as _cf
    content, file_path = _cf_read_file_or_content(args)
    if content is None:
        return EXIT_ERROR
    from_fmt = getattr(args, "from_fmt", "auto")
    try:
        parsed = _cf.parse_text(content, fmt=None if from_fmt == "auto" else from_fmt)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if "error" in parsed:
        print(f"error: {parsed['error']}", file=sys.stderr)
        return EXIT_ERROR
    detected_fmt = parsed.get("format")
    data = parsed.get("data", parsed)
    try:
        _cf._delete_by_path(data, args.delete)
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    to_fmt = getattr(args, "to", None) or detected_fmt
    if not to_fmt:
        print("error: cannot determine output format; use --to", file=sys.stderr)
        return EXIT_ERROR
    try:
        output_text = _cf.serialize(data, to_fmt, **_cf_serialize_options(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if not output_text.endswith("\n"):
        output_text += "\n"
    if getattr(args, "in_place", False):
        if file_path is None:
            print("error: --in-place requires a file argument, not stdin", file=sys.stderr)
            return EXIT_ERROR
        file_path.write_text(output_text, encoding="utf-8")
    else:
        sys.stdout.write(output_text)
    return EXIT_SUCCESS


def _run_cf_merge(args) -> int:
    from . import configforge as _cf
    content, file_path = _cf_read_file_or_content(args)
    if content is None:
        return EXIT_ERROR
    from_fmt = getattr(args, "from_fmt", "auto")
    try:
        base_parsed = _cf.parse_text(content, fmt=None if from_fmt == "auto" else from_fmt)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if "error" in base_parsed:
        print(f"error: {base_parsed['error']}", file=sys.stderr)
        return EXIT_ERROR
    detected_fmt = base_parsed.get("format")
    base_data = base_parsed.get("data", base_parsed)
    try:
        overlay_text = Path(args.merge).read_text(encoding="utf-8")
    except OSError as e:
        print(f"error: cannot read overlay file: {e}", file=sys.stderr)
        return EXIT_ERROR
    try:
        overlay_parsed = _cf.parse_text(overlay_text)
    except ValueError as exc:
        print(f"error reading overlay: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if "error" in overlay_parsed:
        print(f"error reading overlay: {overlay_parsed['error']}", file=sys.stderr)
        return EXIT_ERROR
    overlay_data = overlay_parsed.get("data", overlay_parsed)
    list_mode = getattr(args, "list_merge", "replace")
    merged = _cf._deep_merge(base_data, overlay_data, list_mode=list_mode)
    to_fmt = getattr(args, "to", None) or detected_fmt
    if not to_fmt:
        print("error: cannot determine output format; use --to", file=sys.stderr)
        return EXIT_ERROR
    try:
        output_text = _cf.serialize(merged, to_fmt, **_cf_serialize_options(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if not output_text.endswith("\n"):
        output_text += "\n"
    if getattr(args, "in_place", False):
        if file_path is None:
            print("error: --in-place requires a file argument, not stdin", file=sys.stderr)
            return EXIT_ERROR
        file_path.write_text(output_text, encoding="utf-8")
    else:
        sys.stdout.write(output_text)
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def entry_point() -> NoReturn:
    """Console_scripts entry point."""
    sys.exit(main())


if __name__ == "__main__":
    sys.exit(main())