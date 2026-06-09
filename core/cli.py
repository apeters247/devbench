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

    # cf --validate  → check config is parseable (single or --batch glob)
    if args.command == "cf" and getattr(args, "validate", False):
        return _run_cf_validate(args)

    # cf --grep  → regex search over config keys/values (supports --batch)
    if args.command == "cf" and getattr(args, "grep", None):
        return _run_cf_grep(args)

    # cf --batch  → batch convert files matching a glob (handle before reading stdin)
    if args.command == "cf" and getattr(args, "batch", False):
        return _run_cf_batch(args)

    # cf --keys  → list config keys
    if args.command == "cf" and getattr(args, "keys", False):
        return _run_cf_keys(args)

    # cf CRUD / merge ops — read input themselves (file path or stdin)
    if args.command == "cf" and getattr(args, "get", None):
        return _run_cf_get(args)
    if args.command == "cf" and getattr(args, "set_kv", None):
        return _run_cf_set(args)
    if args.command == "cf" and getattr(args, "append_kv", None):
        return _run_cf_append(args)
    if args.command == "cf" and getattr(args, "delete", None):
        return _run_cf_delete(args)
    if args.command == "cf" and getattr(args, "merge", None):
        return _run_cf_merge(args)
    if args.command == "cf" and getattr(args, "diff", None):
        return _run_cf_diff(args)
    if args.command == "cf" and getattr(args, "count", None):
        return _run_cf_count(args)
    if args.command == "cf" and getattr(args, "pick", None):
        return _run_cf_pick(args)
    if args.command == "cf" and getattr(args, "flatten", False):
        return _run_cf_flatten(args)
    if args.command == "cf" and getattr(args, "unflatten", False):
        return _run_cf_unflatten(args)

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
            tool_p.add_argument("--recursive", "-R", action="store_true",
                                help="For --batch: recursively match files in subdirectories (supports ** glob patterns). "
                                     "For --keys: list all nested key paths in dot-notation.")
            tool_p.add_argument("--output-dir", help="Output directory for --batch mode")
            tool_p.add_argument("--keys", action="store_true",
                                help="List all top-level keys from the input config. "
                                     "Add --recursive (-R) to list every nested key in dot-notation.")
            tool_p.add_argument("--indent", type=int, default=2, help="Indentation width for YAML/JSON output (default: 2)")
            tool_p.add_argument("--flatten-xml", action="store_true", help="Flatten nested XML into dotted keys")
            tool_p.add_argument("--no-comments", action="store_true", help="Do not preserve comments")
            tool_p.add_argument("--yaml12", action="store_true",
                                help="YAML 1.2 booleans: only true/false (not yes/no/on/off)")
            tool_p.add_argument("--template-safe", action="store_true", dest="template_safe",
                                help="Pre-quote Jinja/Helm/Ansible {{ var }} values in YAML before parsing")
            tool_p.add_argument("--sort-keys", action="store_true", help="Sort keys in output")
            tool_p.add_argument("--no-infer-dates", action="store_true", help="Keep ISO-8601 date strings as strings (TOML)")
            tool_p.add_argument("--null-handling", default="skip", choices=["skip", "comment", "empty", "error"],
                                help="How to represent null/None in TOML (default: skip)")
            tool_p.add_argument("--get", metavar="PATH", default=None,
                                help="Extract a value by dot-notation path (e.g. server.port). "
                                     "Prints YAML-safe scalar or JSON for dicts/lists. "
                                     "Use top-level --raw / -r for bare string output.")
            tool_p.add_argument("--set", metavar=("PATH", "VALUE"), nargs=2, dest="set_kv",
                                help="Set a value by dot-notation path. Value parsed as JSON (booleans, numbers, null); strings need no quoting.")
            tool_p.add_argument("--append", metavar=("PATH", "VALUE"), nargs=2, dest="append_kv",
                                help="Append VALUE to the list at PATH. Creates the list if the key is absent. "
                                     "Value parsed as JSON (booleans, numbers, null); strings need no quoting. "
                                     "Addresses yq v4 verbosity: no need for '.key += [\"v\"]' sub-expressions.")
            tool_p.add_argument("--in-place", "-i", action="store_true", dest="in_place",
                                help="Write --set/--append/--delete/--merge result back to the source file (requires a file path argument, not stdin).")
            tool_p.add_argument("--backup", metavar="SUFFIX", nargs="?", const=".bak", default=None, dest="backup_suffix",
                                help="Before --in-place write, save the original to FILE<SUFFIX> (default suffix: .bak). "
                                     "Example: --backup → file.yaml.bak; --backup .orig → file.yaml.orig")
            tool_p.add_argument("--delete", metavar="PATH", default=None,
                                help="Delete a key by dot-notation path. Output defaults to input format.")
            tool_p.add_argument("--merge", metavar="OVERLAY", default=None,
                                help="Deep-merge OVERLAY file onto the base input. Output defaults to base format.")
            tool_p.add_argument("--list-merge", metavar="MODE", dest="list_merge", default="replace",
                                choices=["replace", "append"],
                                help="How to merge lists when using --merge: replace (default) overwrites; append extends.")
            tool_p.add_argument("--diff", metavar="FILE", default=None,
                                help="Structural diff: compare the base input against FILE across any format. "
                                     "Exit 0 = identical, exit 1 = differences. "
                                     "Works cross-format: YAML vs JSON, TOML vs INI, etc. "
                                     "Use --raw for machine-readable JSON output.")
            tool_p.add_argument("--validate", action="store_true",
                                help="Validate that config file(s) are parseable. "
                                     "Exit 0 = all valid, exit 1 = any invalid. "
                                     "Combine with --batch for bulk validation. "
                                     "Use --raw for JSON output.")
            tool_p.add_argument("--count", metavar="PATH", default=None,
                                help="Count items at PATH: list length, dict key count, or 1 for scalars. "
                                     "Use '.' for top-level key count. "
                                     "Outputs a plain integer — ideal for shell scripts. "
                                     "Use --raw for JSON output.")
            tool_p.add_argument("--pick", metavar="PATH", nargs="+", default=None,
                                help="Extract specific paths from the config and output a new config with just those fields. "
                                     "Single path: outputs the raw value (like --get). "
                                     "Multiple paths: outputs a new config dict of {path: value} pairs. "
                                     "Use --to to control output format. "
                                     "Example: devbench cf deploy.yaml --pick spec.replicas spec.template.spec.containers --to yaml")
            tool_p.add_argument("--env-expand", action="store_true", dest="env_expand",
                                help="Substitute ${VAR} and $VAR references in config values with live environment variables. "
                                     "Missing vars are left unchanged. Works across all 11 formats. "
                                     "Example: APP_PORT=8080 devbench cf config.yaml --env-expand --to json")
            tool_p.add_argument("--grep", metavar="PATTERN", default=None,
                                help="Search config keys and values matching a regex pattern (case-insensitive by default). "
                                     "Flattens the config to dot-notation paths and filters by PATTERN. "
                                     "Exit 0=matches found, 1=no matches (grep semantics). "
                                     "Use --raw for JSON output, --batch for multi-file search. "
                                     "Example: devbench cf deploy.yaml --grep 'image'  "
                                     "         devbench cf '*.yaml' --batch --grep 'password'")
            tool_p.add_argument("--grep-case-sensitive", action="store_true", dest="grep_case_sensitive",
                                help="Make --grep case-sensitive (default: case-insensitive)")
            tool_p.add_argument("--flatten", action="store_true",
                                help="Flatten nested config to dotted-key pairs. "
                                     "Example: {a: {b: 1}} → {'a.b': 1}. "
                                     "Composes with --to for output format. "
                                     "Use --sep to change separator (default: '.'). "
                                     "Example: devbench cf config.yaml --flatten --to json")
            tool_p.add_argument("--unflatten", action="store_true",
                                help="Expand flat dotted-key pairs to a nested config (inverse of --flatten). "
                                     "Example: {'a.b': 1} → {a: {b: 1}}. "
                                     "Use --sep to match the separator used during flatten (default: '.'). "
                                     "Example: devbench cf flat.json --unflatten --to yaml")
            tool_p.add_argument("--sep", default=".", metavar="SEP",
                                help="Key separator for --flatten / --unflatten (default: '.'). "
                                     "Example: --sep __ for shell-friendly var names like DATABASE__HOST")
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
    """Get input text from argument or stdin. If args.text is a file path, read it."""
    text_arg = getattr(args, "text", None)
    if text_arg is not None:
        p = Path(text_arg)
        if p.is_file():
            try:
                return p.read_text(encoding="utf-8")
            except OSError:
                return text_arg  # Fall back to treating as content if read fails

    if text_arg is not None:
        return text_arg

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
    if hasattr(args, "yaml12") and args.yaml12:
        options["yaml12"] = True
    if hasattr(args, "template_safe") and args.template_safe:
        options["template_safe"] = True
    if hasattr(args, "sort_keys") and args.sort_keys:
        options["sort_keys"] = True
    if hasattr(args, "no_infer_dates") and args.no_infer_dates:
        options["infer_dates"] = False
    if hasattr(args, "null_handling"):
        options["null_handling"] = args.null_handling
    if hasattr(args, "env_expand") and args.env_expand:
        options["env_expand"] = True

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
    if hasattr(args, "env_expand") and args.env_expand:
        options["env_expand"] = True

    if getattr(args, "recursive", False):
        options["recursive"] = True

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


def _run_cf_keys(args) -> int:
    from . import configforge as _cf
    content, _ = _cf_read_file_or_content(args)
    if content is None:
        return EXIT_ERROR
    from_fmt = getattr(args, "from_fmt", "auto")
    try:
        parsed = _cf.parse_text(content, fmt=None if from_fmt == "auto" else from_fmt,
                                **_cf_parse_opts(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    data = parsed.get("data", parsed)
    recursive = getattr(args, "recursive", False)
    for k in _cf._list_keys(data, recursive=recursive):
        print(k)
    return EXIT_SUCCESS


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


def _cf_write_in_place(file_path, output_text: str, backup_suffix) -> bool:
    """Write output_text to file_path, optionally backing up the original first.

    Returns True on success, False on error (error printed to stderr).
    """
    if backup_suffix:
        bak_path = Path(str(file_path) + backup_suffix)
        try:
            import shutil
            shutil.copy2(file_path, bak_path)
        except OSError as e:
            print(f"error: could not create backup {bak_path}: {e}", file=sys.stderr)
            return False
    try:
        file_path.write_text(output_text, encoding="utf-8")
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return False
    return True


def _cf_serialize_options(args) -> dict:
    opts: dict = {}
    if hasattr(args, "indent"):
        opts["indent"] = args.indent
    if getattr(args, "sort_keys", False):
        opts["sort_keys"] = True
    if getattr(args, "no_comments", False):
        opts["preserve_comments"] = False
    return opts


def _cf_parse_opts(args) -> dict:
    """Collect parse-only options for parse_text() from cf subcommand args."""
    opts: dict = {}
    if getattr(args, "yaml12", False):
        opts["yaml12"] = True
    if getattr(args, "template_safe", False):
        opts["template_safe"] = True
    if getattr(args, "env_expand", False):
        opts["env_expand"] = True
    return opts


def _run_cf_get(args) -> int:
    from . import configforge as _cf
    content, _ = _cf_read_file_or_content(args)
    if content is None:
        return EXIT_ERROR
    from_fmt = getattr(args, "from_fmt", "auto")
    try:
        parsed = _cf.parse_text(content, fmt=None if from_fmt == "auto" else from_fmt,
                                **_cf_parse_opts(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    data = parsed.get("data", parsed)
    try:
        val = _cf._get_by_path(data, args.get)
    except (KeyError, IndexError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    sys.stdout.write(_cf._format_get_output(val, raw=getattr(args, "raw", False)) + "\n")
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
        parsed = _cf.parse_text(content, fmt=None if from_fmt == "auto" else from_fmt,
                                **_cf_parse_opts(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
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
        if not _cf_write_in_place(file_path, output_text, getattr(args, "backup_suffix", None)):
            return EXIT_ERROR
    else:
        sys.stdout.write(output_text)
    return EXIT_SUCCESS


def _run_cf_append(args) -> int:
    from . import configforge as _cf
    content, file_path = _cf_read_file_or_content(args)
    if content is None:
        return EXIT_ERROR
    path, raw_value = args.append_kv
    value = _cf._coerce_set_value(raw_value)
    from_fmt = getattr(args, "from_fmt", "auto")
    try:
        parsed = _cf.parse_text(content, fmt=None if from_fmt == "auto" else from_fmt,
                                **_cf_parse_opts(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    detected_fmt = parsed.get("format")
    data = parsed.get("data", parsed)
    try:
        _cf._append_to_path(data, path, value)
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
        if not _cf_write_in_place(file_path, output_text, getattr(args, "backup_suffix", None)):
            return EXIT_ERROR
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
        parsed = _cf.parse_text(content, fmt=None if from_fmt == "auto" else from_fmt,
                                **_cf_parse_opts(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
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
        if not _cf_write_in_place(file_path, output_text, getattr(args, "backup_suffix", None)):
            return EXIT_ERROR
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
        base_parsed = _cf.parse_text(content, fmt=None if from_fmt == "auto" else from_fmt,
                                     **_cf_parse_opts(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    detected_fmt = base_parsed.get("format")
    base_data = base_parsed.get("data", base_parsed)
    try:
        overlay_text = Path(args.merge).read_text(encoding="utf-8")
    except OSError as e:
        print(f"error: cannot read overlay file: {e}", file=sys.stderr)
        return EXIT_ERROR
    try:
        overlay_parsed = _cf.parse_text(overlay_text, **_cf_parse_opts(args))
    except ValueError as exc:
        print(f"error reading overlay: {exc}", file=sys.stderr)
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
        if not _cf_write_in_place(file_path, output_text, getattr(args, "backup_suffix", None)):
            return EXIT_ERROR
    else:
        sys.stdout.write(output_text)
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# cf --diff: structural cross-format config comparison
# ---------------------------------------------------------------------------


def _flatten_for_diff(obj, prefix=""):
    """Flatten nested dict/list to {dot.path: value} for structural diffing."""
    result = {}
    if isinstance(obj, dict):
        for key, val in obj.items():
            safe_key = str(key).replace(".", "\\.")
            new_prefix = f"{prefix}.{safe_key}" if prefix else safe_key
            result.update(_flatten_for_diff(val, new_prefix))
    elif isinstance(obj, list):
        for idx, val in enumerate(obj):
            new_prefix = f"{prefix}[{idx}]"
            result.update(_flatten_for_diff(val, new_prefix))
    else:
        result[prefix] = obj
    return result


def _run_cf_diff(args) -> int:
    """Structural diff between two config files, across any supported format."""
    from . import configforge as _cf
    content_a, _ = _cf_read_file_or_content(args)
    if content_a is None:
        return EXIT_ERROR
    diff_file = args.diff
    try:
        content_b = Path(diff_file).read_text(encoding="utf-8")
    except OSError as e:
        print(f"error: cannot read diff file: {e}", file=sys.stderr)
        return EXIT_ERROR

    from_fmt = getattr(args, "from_fmt", "auto")
    parse_opts = _cf_parse_opts(args)

    try:
        parsed_a = _cf.parse_text(content_a, fmt=None if from_fmt == "auto" else from_fmt, **parse_opts)
    except ValueError as exc:
        print(f"error parsing base input: {exc}", file=sys.stderr)
        return EXIT_ERROR
    try:
        parsed_b = _cf.parse_text(content_b, **parse_opts)
    except ValueError as exc:
        print(f"error parsing diff target: {exc}", file=sys.stderr)
        return EXIT_ERROR

    data_a = parsed_a.get("data", parsed_a)
    data_b = parsed_b.get("data", parsed_b)
    fmt_a = parsed_a.get("format", "unknown")
    fmt_b = parsed_b.get("format", "unknown")

    flat_a = _flatten_for_diff(data_a)
    flat_b = _flatten_for_diff(data_b)

    keys_a = set(flat_a)
    keys_b = set(flat_b)
    removed = sorted(keys_a - keys_b)
    added = sorted(keys_b - keys_a)
    changed = sorted(
        (k, flat_a[k], flat_b[k]) for k in keys_a & keys_b if flat_a[k] != flat_b[k]
    )

    if not removed and not added and not changed:
        print("identical")
        return EXIT_SUCCESS

    label_a = getattr(args, "text", None) or "stdin"
    label_b = diff_file

    if getattr(args, "raw", False):
        result = {
            "identical": False,
            "formats": {"a": fmt_a, "b": fmt_b},
            "added": {k: flat_b[k] for k in added},
            "removed": {k: flat_a[k] for k in removed},
            "changed": [{"path": k, "from": ov, "to": nv} for k, ov, nv in changed],
        }
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"--- {label_a}  ({fmt_a})")
        print(f"+++ {label_b}  ({fmt_b})")
        for k in removed:
            print(f"- {k}: {flat_a[k]!r}")
        for k in added:
            print(f"+ {k}: {flat_b[k]!r}")
        for k, ov, nv in changed:
            print(f"~ {k}: {ov!r} → {nv!r}")

    return EXIT_ERROR  # exit 1 = differences found (standard diff semantics)


# ---------------------------------------------------------------------------
# cf --count: count items at a path
# ---------------------------------------------------------------------------


def _run_cf_count(args) -> int:
    """Count items at PATH: list length, dict key count, or 1 for scalars.

    Use '.' to count top-level keys. Outputs a plain integer for shell scripts.
    """
    from . import configforge as _cf
    content, _ = _cf_read_file_or_content(args)
    if content is None:
        return EXIT_ERROR
    from_fmt = getattr(args, "from_fmt", "auto")
    try:
        parsed = _cf.parse_text(content, fmt=None if from_fmt == "auto" else from_fmt,
                                **_cf_parse_opts(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    data = parsed.get("data", parsed)
    path = args.count
    if path == ".":
        val = data
    else:
        try:
            val = _cf._get_by_path(data, path)
        except (KeyError, IndexError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_ERROR
    if isinstance(val, (dict, list)):
        count = len(val)
        type_name = "dict" if isinstance(val, dict) else "list"
    else:
        count = 1
        type_name = "scalar"
    if getattr(args, "raw", False):
        print(json.dumps({"path": path, "count": count, "type": type_name}))
    else:
        print(count)
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# cf --validate: single-file or batch config validation
# ---------------------------------------------------------------------------


def _run_cf_validate(args) -> int:
    """Validate that one or more config files are parseable.

    Single-file mode: reads one file (or stdin) and reports valid/invalid.
    Batch mode (--batch also set): loops over glob matches, reports each.
    Exit 0 if all valid, exit 1 if any invalid — suitable for CI/CD hooks.
    """
    import glob as _glob
    from . import configforge as _cf

    raw = getattr(args, "raw", False)
    from_fmt = getattr(args, "from_fmt", "auto")
    parse_opts = _cf_parse_opts(args)
    is_batch = getattr(args, "batch", False)

    def _validate_content(content: str, label: str) -> dict:
        """Parse content and return a result dict."""
        try:
            parsed = _cf.parse_text(
                content,
                fmt=None if from_fmt == "auto" else from_fmt,
                **parse_opts,
            )
            data = parsed.get("data", parsed)
            fmt = parsed.get("format", "unknown")
            key_count = len(data) if isinstance(data, (dict, list)) else 1
            return {"valid": True, "file": label, "format": fmt, "key_count": key_count}
        except Exception as exc:
            return {"valid": False, "file": label, "error": str(exc)}

    def _print_result(r: dict) -> None:
        if r["valid"]:
            fmt = r.get("format", "?")
            kc = r.get("key_count", "?")
            ks = "key" if kc == 1 else "keys"
            print(f"{r['file']}: valid  ({fmt}, {kc} {ks})")
        else:
            print(f"{r['file']}: INVALID")
            print(f"  error: {r.get('error', 'unknown error')}", file=sys.stderr)

    if is_batch:
        input_glob = getattr(args, "text", None)
        if not input_glob:
            print("error: --validate --batch requires a glob pattern as the text argument", file=sys.stderr)
            print("  Usage: devbench cf --validate --batch '*.yaml'", file=sys.stderr)
            return EXIT_ERROR

        recursive = getattr(args, "recursive", False)
        files = sorted(_glob.glob(input_glob, recursive=recursive))
        if not files:
            print(f"error: no files matched: {input_glob}", file=sys.stderr)
            return EXIT_ERROR

        results = []
        for f in files:
            try:
                content = Path(f).read_text(encoding="utf-8")
                r = _validate_content(content, f)
            except OSError as e:
                r = {"valid": False, "file": f, "error": str(e)}
            results.append(r)

        if raw:
            print(json.dumps(results, indent=2, default=str))
        else:
            for r in results:
                _print_result(r)
            valid_count = sum(1 for r in results if r["valid"])
            invalid_count = len(results) - valid_count
            print(f"[validate] {len(results)} files: {valid_count} valid, {invalid_count} invalid")

        return EXIT_SUCCESS if all(r["valid"] for r in results) else EXIT_ERROR

    # Single-file / stdin mode
    content, file_path = _cf_read_file_or_content(args)
    if content is None:
        return EXIT_ERROR
    label = str(file_path) if file_path else "stdin"
    r = _validate_content(content, label)

    if raw:
        print(json.dumps(r, indent=2, default=str))
    else:
        _print_result(r)

    return EXIT_SUCCESS if r["valid"] else EXIT_ERROR


# ---------------------------------------------------------------------------
# cf --pick: extract / project specific paths from a config
# ---------------------------------------------------------------------------


def _run_cf_pick(args) -> int:
    """Extract (project) one or more paths from a config file.

    Single path: prints the raw value at that path (like --get, but routed
    through --pick so it composes with --to for format conversion of the value).

    Multiple paths: builds a new flat dict of {path: value} entries and
    serializes it to the requested output format (defaulting to the detected
    input format).  This lets you extract a subset of a Kubernetes manifest,
    Compose file, etc. without jq filter expressions.

    Exit 0 on success, exit 1 if any path is missing.
    """
    from . import configforge as _cf

    content, _ = _cf_read_file_or_content(args)
    if content is None:
        return EXIT_ERROR

    from_fmt = getattr(args, "from_fmt", "auto")
    try:
        parsed = _cf.parse_text(
            content,
            fmt=None if from_fmt == "auto" else from_fmt,
            **_cf_parse_opts(args),
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    data = parsed.get("data", parsed)
    detected_fmt = parsed.get("format", "yaml")
    paths = args.pick  # list[str]

    # Resolve each path; bail on the first missing key
    picked: dict = {}
    for path in paths:
        try:
            val = _cf._get_by_path(data, path)
            picked[path] = val
        except (KeyError, IndexError) as exc:
            print(f"error: path not found: {exc}", file=sys.stderr)
            return EXIT_ERROR

    # Single path → print value directly (matches --get behaviour)
    if len(paths) == 1:
        raw = getattr(args, "raw", False)
        sys.stdout.write(_cf._format_get_output(picked[paths[0]], raw=raw) + "\n")
        return EXIT_SUCCESS

    # Multiple paths → serialize the picked dict
    to_fmt = getattr(args, "to", None) or detected_fmt
    if not to_fmt:
        print("error: cannot determine output format; use --to", file=sys.stderr)
        return EXIT_ERROR
    try:
        output_text = _cf.serialize(picked, to_fmt, **_cf_serialize_options(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if not output_text.endswith("\n"):
        output_text += "\n"
    sys.stdout.write(output_text)
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# cf --grep: regex search across flattened config keys and values
# ---------------------------------------------------------------------------


def _run_cf_grep(args) -> int:
    """Search config keys/values matching a regex pattern.

    Parses the config, flattens all key→value pairs to dot-notation paths,
    and prints entries where the path or string-repr of the value matches
    the regex (case-insensitive by default).

    Single-file: reads one file (or stdin).
    Batch mode (--batch also set): loops over glob matches, searches each.

    Exit 0 if any matches found, exit 1 if no matches — grep semantics.
    """
    import re
    import glob as _glob
    from . import configforge as _cf

    pattern_str = args.grep
    flags = 0 if getattr(args, "grep_case_sensitive", False) else re.IGNORECASE
    try:
        pattern = re.compile(pattern_str, flags)
    except re.error as exc:
        print(f"error: invalid regex pattern: {exc}", file=sys.stderr)
        return EXIT_ERROR

    raw = getattr(args, "raw", False)
    from_fmt = getattr(args, "from_fmt", "auto")
    parse_opts = _cf_parse_opts(args)
    is_batch = getattr(args, "batch", False)

    def _grep_content(content: str, label: str) -> list:
        """Return list of {path, value} dicts for matching entries."""
        try:
            parsed = _cf.parse_text(
                content,
                fmt=None if from_fmt == "auto" else from_fmt,
                **parse_opts,
            )
        except Exception as exc:
            print(f"error parsing {label}: {exc}", file=sys.stderr)
            return []
        data = parsed.get("data", parsed)
        flat = _flatten_for_diff(data)
        matches = []
        for path, val in sorted(flat.items()):
            val_str = str(val) if val is not None else ""
            if pattern.search(path) or pattern.search(val_str):
                matches.append({"path": path, "value": val})
        return matches

    if is_batch:
        input_glob = getattr(args, "text", None)
        if not input_glob:
            print("error: --grep --batch requires a glob pattern as the text argument", file=sys.stderr)
            print("  Usage: devbench cf --grep PATTERN --batch '*.yaml'", file=sys.stderr)
            return EXIT_ERROR
        recursive = getattr(args, "recursive", False)
        files = sorted(_glob.glob(input_glob, recursive=recursive))
        if not files:
            print(f"error: no files matched: {input_glob}", file=sys.stderr)
            return EXIT_ERROR

        any_matches = False
        batch_results = []
        for f in files:
            try:
                content = Path(f).read_text(encoding="utf-8")
            except OSError as e:
                print(f"error reading {f}: {e}", file=sys.stderr)
                continue
            matches = _grep_content(content, f)
            if matches:
                any_matches = True
            batch_results.append({"file": f, "matches": matches, "count": len(matches)})

        if raw:
            print(json.dumps(batch_results, indent=2, default=str))
        else:
            for br in batch_results:
                if br["matches"]:
                    n = br["count"]
                    print(f"--- {br['file']} ({n} match{'es' if n != 1 else ''}) ---")
                    for m in br["matches"]:
                        print(f"  {m['path']}: {m['value']!r}")
            if not any_matches:
                print(f"no matches for {pattern_str!r}", file=sys.stderr)

        return EXIT_SUCCESS if any_matches else EXIT_ERROR

    # Single-file / stdin mode
    content, file_path = _cf_read_file_or_content(args)
    if content is None:
        return EXIT_ERROR
    label = str(file_path) if file_path else "stdin"
    matches = _grep_content(content, label)

    if raw:
        result = {
            "file": label,
            "pattern": pattern_str,
            "matches": matches,
            "count": len(matches),
        }
        print(json.dumps(result, indent=2, default=str))
    else:
        for m in matches:
            print(f"{m['path']}: {m['value']!r}")

    if not matches:
        print(f"no matches for {pattern_str!r}", file=sys.stderr)
        return EXIT_ERROR

    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# cf --flatten / --unflatten: dotted-key transform
# ---------------------------------------------------------------------------


def _run_cf_flatten(args) -> int:
    """Flatten nested config to dotted-key pairs.

    Converts {a: {b: 1, c: 2}} to {'a.b': 1, 'a.c': 2} using the separator
    specified via --sep (default '.'). Lists are kept as values at their
    dotted path. The result is serialized with --to (or the detected input
    format). Composes with --sort-keys, --in-place, --backup, etc.
    """
    from . import configforge as _cf

    content, file_path = _cf_read_file_or_content(args)
    if content is None:
        return EXIT_ERROR

    from_fmt = getattr(args, "from_fmt", "auto")
    try:
        parsed = _cf.parse_text(
            content,
            fmt=None if from_fmt == "auto" else from_fmt,
            **_cf_parse_opts(args),
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    data = parsed.get("data", parsed)
    detected_fmt = parsed.get("format", "yaml")
    sep = getattr(args, "sep", ".")

    flat = _cf._flatten_dict(data, sep=sep)
    if not isinstance(flat, dict):
        print("error: input must be a config object (dict) to flatten", file=sys.stderr)
        return EXIT_ERROR

    to_fmt = getattr(args, "to", None) or detected_fmt
    if not to_fmt:
        print("error: cannot determine output format; use --to", file=sys.stderr)
        return EXIT_ERROR
    try:
        output_text = _cf.serialize(flat, to_fmt, **_cf_serialize_options(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if not output_text.endswith("\n"):
        output_text += "\n"

    if getattr(args, "in_place", False):
        if file_path is None:
            print("error: --in-place requires a file argument, not stdin", file=sys.stderr)
            return EXIT_ERROR
        if not _cf_write_in_place(file_path, output_text, getattr(args, "backup_suffix", None)):
            return EXIT_ERROR
    else:
        sys.stdout.write(output_text)
    return EXIT_SUCCESS


def _run_cf_unflatten(args) -> int:
    """Expand flat dotted-key config back to a nested dict.

    Inverse of _run_cf_flatten: {'a.b': 1, 'a.c': 2} → {a: {b: 1, c: 2}}.
    Use --sep to specify the separator that was used when flattening.
    Raises an error if key collisions are detected (a key is both a scalar
    and a dict prefix — unresolvable ambiguity).
    """
    from . import configforge as _cf

    content, file_path = _cf_read_file_or_content(args)
    if content is None:
        return EXIT_ERROR

    from_fmt = getattr(args, "from_fmt", "auto")
    try:
        parsed = _cf.parse_text(
            content,
            fmt=None if from_fmt == "auto" else from_fmt,
            **_cf_parse_opts(args),
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    data = parsed.get("data", parsed)
    detected_fmt = parsed.get("format", "yaml")
    sep = getattr(args, "sep", ".")

    try:
        nested = _cf._unflatten_dict(data, sep=sep)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    to_fmt = getattr(args, "to", None) or detected_fmt
    if not to_fmt:
        print("error: cannot determine output format; use --to", file=sys.stderr)
        return EXIT_ERROR
    try:
        output_text = _cf.serialize(nested, to_fmt, **_cf_serialize_options(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if not output_text.endswith("\n"):
        output_text += "\n"

    if getattr(args, "in_place", False):
        if file_path is None:
            print("error: --in-place requires a file argument, not stdin", file=sys.stderr)
            return EXIT_ERROR
        if not _cf_write_in_place(file_path, output_text, getattr(args, "backup_suffix", None)):
            return EXIT_ERROR
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