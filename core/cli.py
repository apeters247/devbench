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

    # cf --each  → extract a field from every list element (check before --select and --get)
    if args.command == "cf" and getattr(args, "each_key", None):
        return _run_cf_each(args)

    # cf --join DELIM → join list items with delimiter (check before --get so --get + --join composes)
    if args.command == "cf" and getattr(args, "join_delim", None) is not None:
        return _run_cf_join(args)

    # cf --select  → filter list items by field condition (check before --get)
    if args.command == "cf" and getattr(args, "select_expr", None):
        return _run_cf_select(args)

    # cf --sort-by FIELD → sort list by field value (must precede --get so --get + --sort-by composes)
    if args.command == "cf" and getattr(args, "sort_by", None):
        return _run_cf_sort_by(args)

    # cf --unique / --unique-by FIELD → deduplicate list items (must precede --get so --get + --unique composes)
    if args.command == "cf" and (getattr(args, "unique", False) or getattr(args, "unique_by", None)):
        return _run_cf_unique(args)

    # cf CRUD / merge ops — read input themselves (file path or stdin)
    if args.command == "cf" and getattr(args, "get", None):
        return _run_cf_get(args)
    if args.command == "cf" and getattr(args, "set_kv", None):
        return _run_cf_set(args)
    if args.command == "cf" and getattr(args, "append_kv", None):
        return _run_cf_append(args)
    if args.command == "cf" and getattr(args, "delete", None):
        return _run_cf_delete(args)
    if args.command == "cf" and getattr(args, "rename_paths", None):
        return _run_cf_rename(args)
    if args.command == "cf" and getattr(args, "merge", None):
        return _run_cf_merge(args)
    if args.command == "cf" and getattr(args, "diff", None):
        return _run_cf_diff(args)
    if args.command == "cf" and getattr(args, "count", None):
        return _run_cf_count(args)
    if args.command == "cf" and getattr(args, "length_path", None):
        return _run_cf_length(args)
    if args.command == "cf" and getattr(args, "type_path", None):
        return _run_cf_type(args)
    if args.command == "cf" and getattr(args, "has_path", None):
        return _run_cf_has(args)
    if args.command == "cf" and getattr(args, "pick", None):
        return _run_cf_pick(args)
    # cf --shell-export  → emit shell-safe export statements (must precede --flatten)
    if args.command == "cf" and getattr(args, "shell_export", False):
        return _run_cf_shell_export(args)

    if args.command == "cf" and getattr(args, "flatten", False):
        return _run_cf_flatten(args)
    if args.command == "cf" and getattr(args, "unflatten", False):
        return _run_cf_unflatten(args)

    # cf --mask  → redact sensitive values
    if args.command == "cf" and getattr(args, "mask_pattern", None):
        return _run_cf_mask(args)

    # cf --hash-field  → replace field values with their hash
    if args.command == "cf" and getattr(args, "hash_pattern", None):
        return _run_cf_hash_field(args)

    # cf --schema  → validate config against a JSON Schema file
    if args.command == "cf" and getattr(args, "schema_file", None):
        return _run_cf_schema(args)

    # cf --assert  → assert config key(s) equal expected values
    if args.command == "cf" and getattr(args, "asserts", None):
        return _run_cf_assert(args)

    # cf --path-exists  → check whether a path exists in the config
    if args.command == "cf" and getattr(args, "path_exists", None):
        return _run_cf_path_exists(args)

    # cf --template  → render a template file using config as context
    if args.command == "cf" and getattr(args, "template_file", None):
        return _run_cf_template(args)

    # cf --wrap-in KEY  → wrap entire config under a dotted key path
    if args.command == "cf" and getattr(args, "wrap_in", None):
        return _run_cf_wrap_in(args)

    # cf --schema-gen  → generate JSON Schema from config structure
    if args.command == "cf" and getattr(args, "schema_gen", False):
        return _run_cf_schema_gen(args)

    # cf --replace-value OLD NEW  → find-and-replace values recursively
    if args.command == "cf" and getattr(args, "replace_value", None):
        return _run_cf_replace_value(args)

    # cf --check-env  → show environment info (no stdin needed)
    if args.command == "cf" and getattr(args, "check_env", False):
        return _run_cf_check_env(args)

    # completion — emit shell completion script
    if args.command == "completion":
        return _run_completion(args.shell)

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
            tool_p.add_argument("--block-scalars", action="store_true", dest="block_scalars",
                                help="Force multiline strings to use YAML block scalar style (|) in output. "
                                     "Prevents yq-style corruption of strings with trailing spaces. "
                                     "Example: devbench cf config.yaml -t yaml --block-scalars")
            tool_p.add_argument("--sort-keys", action="store_true", help="Sort keys in output")
            tool_p.add_argument("--sort-keys-reverse", action="store_true", dest="sort_keys_reverse",
                                help="Sort keys in reverse order (yq#2390 alternative to sort_keys(.) | reverse)")
            tool_p.add_argument("--no-infer-dates", action="store_true", help="Keep ISO-8601 date strings as strings (TOML)")
            tool_p.add_argument("--ini-quote-strings", action="store_true", dest="ini_quote_strings",
                                help="Wrap string values in double quotes when writing INI output. "
                                     "Addresses yq issue #2456: quoted values lose their quotes on round-trip "
                                     "because configparser strips them when parsing. "
                                     "Numerics and booleans are never quoted. "
                                     "Example: devbench cf config.ini -t ini --ini-quote-strings")
            tool_p.add_argument("--null-handling", default="skip", choices=["skip", "comment", "empty", "error"],
                                help="How to represent null/None in TOML (default: skip)")
            tool_p.add_argument("--get", metavar="PATH", default=None,
                                help="Extract a value by dot-notation path (e.g. server.port). "
                                     "Prints YAML-safe scalar or JSON for dicts/lists. "
                                     "Use top-level --raw / -r for bare string output.")
            tool_p.add_argument("--default", metavar="VALUE", default=None, dest="get_default",
                                help="Return VALUE when --get path does not exist instead of erroring. "
                                     "Exit 0 when the default is used. "
                                     "Example: devbench cf config.yaml --get timeout --default 30")
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
            tool_p.add_argument("--rename", metavar=("OLD_PATH", "NEW_PATH"), nargs=2, dest="rename_paths",
                                default=None,
                                help="Rename/move a key: copies value at OLD_PATH to NEW_PATH then deletes OLD_PATH. "
                                     "Use dot-notation paths. Combine with --in-place to edit the file. "
                                     "Exit 0=success, 1=key not found. Use --raw for JSON output.")
            tool_p.add_argument("--merge", metavar="OVERLAY", default=None,
                                help="Deep-merge OVERLAY file onto the base input. Output defaults to base format.")
            tool_p.add_argument("--list-merge", metavar="MODE", dest="list_merge", default="replace",
                                choices=["replace", "append", "merge"],
                                help="How to merge lists when using --merge: replace (default) overwrites; append extends; merge deep-merges corresponding items by position.")
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
            tool_p.add_argument("--length", metavar="PATH", default=None, dest="length_path",
                                help="Output the length of the value at PATH. "
                                     "list/dict: item count; string: character count; null: 0; scalar: 1. "
                                     "Equivalent to jq '.PATH | length'. Exit 0=found, 1=not found. "
                                     "Use --raw for JSON output: {path, length, type}. "
                                     "Example: devbench cf config.yaml --length users  # array length\n"
                                     "         devbench cf config.yaml --length name   # string char count")
            tool_p.add_argument("--type", metavar="PATH", default=None, dest="type_path",
                                help="Output the JSON Schema type of the value at PATH: string, integer, number, "
                                     "boolean, array, object, or null. Use '.' for the root value. "
                                     "Exit 0=found, 1=path not found. Use --raw for JSON output "
                                     "{path, type, length} where length is set for array/object.")
            tool_p.add_argument("--has", metavar="PATH", default=None, dest="has_path",
                                help="Check whether PATH exists in the config. "
                                     "Prints 'true' and exits 0 if the path exists (even if null). "
                                     "Prints 'false' and exits 1 if the path is not found. "
                                     "Use '.' for the root (always true for any parseable config). "
                                     "Use --raw for JSON output: {path, exists, type}. "
                                     "Ideal for shell conditionals: if devbench cf config.yaml --has db.host; then ... "
                                     "Example: devbench cf k8s.yaml --has spec.replicas "
                                     "         devbench cf config.yaml --has database.password --raw")
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
            tool_p.add_argument("--select", metavar="FIELD=VALUE", default=None, dest="select_expr",
                                help="Filter list items by field condition. "
                                     "FIELD=VALUE keeps items where item[FIELD] == VALUE. "
                                     "FIELD!=VALUE keeps items where item[FIELD] != VALUE. "
                                     "FIELD=/pat/ keeps items where item[FIELD] matches regex (case-insensitive). "
                                     "FIELD!=/pat/ keeps items where item[FIELD] does NOT match regex. "
                                     "FIELD~VALUE keeps items where item[FIELD] is an array containing VALUE. "
                                     "FIELD!~VALUE keeps items where item[FIELD] is an array NOT containing VALUE. "
                                     "Values coerced to int/bool/null for comparison. "
                                     "Exit 0=matches found, 1=no matches (grep semantics). "
                                     "Combine with --get to navigate to the list first. "
                                     "Addresses yq issue #517 and dasel issue #183 (regex filter). "
                                     "Example: devbench cf pods.yaml --select status=Running  "
                                     "         devbench cf deploy.yaml --get spec.containers --select name=/^prod-/  "
                                     "         devbench cf config.yaml --select image=/alpine/ --each name  "
                                     "         devbench cf countries.yaml --select tags~commonwealth  "
                                     "         devbench cf deploy.yaml --get spec.containers --select name=nginx")
            tool_p.add_argument("--each", metavar="KEY", default=None, dest="each_key",
                                help="Extract KEY from each element of a list and output the resulting list. "
                                     "Equivalent to jq '[.[] | .key]' or yq '.[].key'. "
                                     "KEY uses dot-notation (e.g. metadata.name, spec.ports.0.port). "
                                     "Items missing the key are omitted. "
                                     "Combine with --get to navigate to the list first, "
                                     "or with --select to filter before extracting. "
                                     "Exit 0=ok, 1=input is not a list. "
                                     "Example: devbench cf deploy.yaml --get spec.containers --each name  "
                                     "         devbench cf pods.yaml --select status=Running --each metadata.name")
            tool_p.add_argument("--join", metavar="DELIM", default=None, dest="join_delim",
                                help="Join list items into a single string using DELIM as the separator. "
                                     "Use \\\\n for newline, \\\\t for tab. "
                                     "Compose with --get to navigate to a nested list first. "
                                     "Compose with --select/--each to filter/transform before joining. "
                                     "Equivalent to jq '.list | join(\",\")'. "
                                     "Exit 0=ok, 1=input is not a list. "
                                     "Example: devbench cf config.yaml --get services --join ,  # api,worker,db\n"
                                     "         devbench cf deps.yaml --get packages --join ' '  # space-separated\n"
                                     "         devbench cf hosts.yaml --select env=prod --each name --join ,")
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
            tool_p.add_argument("--check-env", action="store_true", dest="check_env",
                                help="Show environment info: Python version, platform, available formats, "
                                     "and optional dependency status. Useful for CI/CD debugging. "
                                     "Use --raw for JSON output.")
            tool_p.add_argument("--schema", metavar="SCHEMA_FILE", default=None, dest="schema_file",
                                help="Validate the parsed config against a JSON Schema file (.json or .yaml). "
                                     "Requires: pip install jsonschema. "
                                     "Exit 0 = valid, exit 1 = invalid. "
                                     "Use --raw for JSON output {valid, errors}. "
                                     "Example: devbench cf config.yaml --schema schema.json")
            tool_p.add_argument("--mask", metavar="PATTERN", default=None, dest="mask_pattern",
                                help="Redact values whose key names match the regex PATTERN. "
                                     "Case-insensitive. Matching values replaced with ***REDACTED*** "
                                     "(override with --mask-value). "
                                     "Combine with --to to convert format while masking. "
                                     "Example: devbench cf prod.yaml --mask 'password|secret|token'")
            tool_p.add_argument("--mask-value", metavar="TEXT", default="***REDACTED***", dest="mask_value",
                                help="Replacement text for masked values (default: ***REDACTED***). "
                                     "Example: --mask-value '[REDACTED]'")
            tool_p.add_argument("--hash-field", metavar="PATTERN", default=None, dest="hash_pattern",
                                help="Replace values whose key names match PATTERN with their hash. "
                                     "Case-insensitive regex. Use with --hash-algorithm to choose algorithm. "
                                     "Addresses yq issue #2283: hash field values for audit logs or safe sharing. "
                                     "Example: devbench cf prod.yaml --hash-field 'password|secret|token'")
            tool_p.add_argument("--hash-algorithm", metavar="ALGO", default="sha256", dest="hash_algorithm",
                                help="Hash algorithm for --hash-field (default: sha256). "
                                     "Choices: md5, sha1, sha256, sha512, blake2b. "
                                     "Example: devbench cf prod.yaml --hash-field password --hash-algorithm sha512")
            tool_p.add_argument("--assert", metavar="PATH=VALUE", dest="asserts",
                                action="append", default=None,
                                help="Assert that a config key equals the expected value. "
                                     "Format: PATH=VALUE using dot-notation (e.g. spec.replicas=3). "
                                     "Exit 0 = all assertions pass, exit 1 = any assertion fails. "
                                     "Use --raw for JSON output {assertions, all_passed}. "
                                     "Repeat to test multiple keys: --assert a=1 --assert b=prod. "
                                     "Example: devbench cf deploy.yaml --assert spec.replicas=3")
            tool_p.add_argument("--path-exists", metavar="PATH", default=None, dest="path_exists",
                                help="Check whether PATH exists in the config (dot-notation). "
                                     "Exit 0 = path exists, exit 1 = path missing. "
                                     "Use --raw for JSON output {path, exists}. "
                                     "Useful in shell conditionals: "
                                     "if devbench cf config.yaml --path-exists database.password; then echo ok; fi")
            tool_p.add_argument("--shell-export", action="store_true", dest="shell_export",
                                help="Output shell-safe 'export KEY=\"value\"' statements. "
                                     "Keys are uppercased and dots/dashes replaced with underscores. "
                                     "Values are shell-quoted. Lists become indexed vars: SERVERS_0=nginx SERVERS_1=apache SERVERS_COUNT=2. "
                                     "Use --bash-arrays for bash declare -a syntax. "
                                     "Combine with --flatten for nested configs. "
                                     "Example: source <(devbench cf config.yaml --flatten --shell-export)")
            tool_p.add_argument("--bash-arrays", action="store_true", dest="bash_arrays",
                                help="With --shell-export: output lists as bash arrays using 'declare -a KEY=(item1 item2)' "
                                     "instead of indexed variables. Requires bash 3.1+. Not compatible with sh/dash. "
                                     "Example: source <(devbench cf config.yaml --shell-export --bash-arrays)")
            tool_p.add_argument("--compact", "-c", action="store_true", dest="compact",
                                help="Output compact/minified JSON (no whitespace). "
                                     "Works with --to json or when output is JSON. "
                                     "Combine with --raw/-r to get just the compact JSON string. "
                                     "Example: devbench cf config.yaml --to json --compact --raw | jq .")
            tool_p.add_argument("--wrap-in", metavar="KEY", default=None, dest="wrap_in",
                                help="Wrap the entire parsed config under a dotted key path. "
                                     "Example: devbench cf config.yaml --wrap-in data → {data: {original...}}. "
                                     "Nested paths create intermediate dicts: --wrap-in spec.template.spec. "
                                     "Compose with --to to convert format while wrapping. "
                                     "Example: devbench cf values.yaml --wrap-in spec.values --to json")
            tool_p.add_argument("--csv-delimiter", metavar="CHAR", default=None, dest="csv_delimiter",
                                help="Override CSV field delimiter (default: auto-detect). "
                                     "Use \\t for TSV, | for pipe-separated, ; for semicolon-separated. "
                                     "Example: devbench cf data.tsv --csv-delimiter $'\\t' --to json. "
                                     "See also: --tsv shorthand.")
            tool_p.add_argument("--tsv", action="store_true", default=False, dest="tsv",
                                help="Treat input as tab-separated (TSV). Shorthand for --csv-delimiter $'\\t'. "
                                     "Example: devbench cf data.tsv --tsv --to json. "
                                     "Combine with --to csv to convert TSV → CSV.")
            tool_p.add_argument("--template", metavar="FILE", default=None, dest="template_file",
                                help="Render a template file using config values as context. "
                                     "Use ${KEY} syntax (Python string.Template, always available) or "
                                     "{{ key }} syntax (Jinja2, if installed). "
                                     "Dot-paths become underscores: database.host → ${database_host}. "
                                     "Uppercase variants also available: ${DATABASE_HOST}. "
                                     "Example: devbench cf app.yaml --template deploy.tmpl > deploy.sh")
            tool_p.add_argument("--schema-gen", action="store_true", dest="schema_gen",
                                help="Generate a JSON Schema (Draft 7) from the config structure. "
                                     "Infers types, required fields, and array item shapes automatically. "
                                     "Use --to yaml for YAML schema output. "
                                     "No competitor (yq/dasel/jq) has this as a built-in flag. "
                                     "Example: devbench cf config.yaml --schema-gen > config-schema.json "
                                     "         devbench cf deploy.yaml --schema-gen --to yaml")
            tool_p.add_argument("--replace-value", metavar=("OLD", "NEW"), nargs=2, dest="replace_value",
                                help="Find and replace all matching leaf values across the entire config. "
                                     "OLD is compared as a string (so 'nginx:1.19' matches string values). "
                                     "NEW is JSON-coerced (so '3' → integer 3, 'true' → bool True). "
                                     "Exit 0 = at least one replacement made, exit 1 = no matches. "
                                     "Combine with --in-place / --backup to edit files directly. "
                                     "Example: devbench cf deploy.yaml --replace-value nginx:1.19 nginx:1.21 "
                                     "         devbench cf config.yaml --replace-value prod staging --in-place")
            tool_p.add_argument("--sort-by", metavar="FIELD", default=None, dest="sort_by",
                                help="Sort a list of objects by a field value. FIELD is a dot-notation path. "
                                     "Strings sort alphabetically, numbers numerically. Items missing FIELD sort last. "
                                     "Use --sort-desc to reverse. Combine with --get PATH to navigate to a nested list. "
                                     "Exit 0 = sorted output written, exit 1 = input is not a list. "
                                     "Example: devbench cf pods.yaml --sort-by metadata.name "
                                     "         devbench cf deploy.yaml --sort-by spec.replicas --sort-desc")
            tool_p.add_argument("--sort-desc", action="store_true", default=False, dest="sort_desc",
                                help="Reverse the sort order for --sort-by (descending instead of ascending).")
            tool_p.add_argument("--unique", action="store_true", default=False, dest="unique",
                                help="Remove duplicate items from a list. Scalars and objects compared by value. "
                                     "Use --unique-by FIELD to deduplicate object lists by a specific field. "
                                     "Example: devbench cf tags.yaml --unique "
                                     "         devbench cf log.json --get items --unique")
            tool_p.add_argument("--unique-by", metavar="FIELD", default=None, dest="unique_by",
                                help="Deduplicate a list of objects by a field value (keep first occurrence). "
                                     "FIELD is a dot-notation path. Items without FIELD are always kept. "
                                     "Example: devbench cf pods.yaml --unique-by metadata.name "
                                     "         devbench cf services.yaml --get spec.ports --unique-by port")
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

    # completion
    completion_p = sub.add_parser(
        "completion",
        help="Generate shell completion script (bash/zsh/fish). Source with: eval \"$(devbench completion bash)\"",
    )
    completion_p.add_argument(
        "shell",
        choices=["bash", "zsh", "fish"],
        help="Shell type to generate completions for",
    )

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
    compact = getattr(args, "compact", False)

    if raw:
        # Try to extract just the output field from JSON wrapper
        try:
            parsed = json.loads(result_str)
            output_str = parsed.get("output", result_str)
        except (json.JSONDecodeError, TypeError):
            output_str = result_str
        if compact:
            try:
                output_str = json.dumps(json.loads(output_str), separators=(",", ":"), ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                pass
        print(output_str)
        return

    if compact:
        try:
            parsed = json.loads(result_str)
            output_field = parsed.get("output", "")
            try:
                parsed["output"] = json.dumps(json.loads(output_field), separators=(",", ":"), ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                pass
            print(json.dumps(parsed, ensure_ascii=False))
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
    if hasattr(args, "block_scalars") and args.block_scalars:
        options["block_scalars"] = True
    if hasattr(args, "sort_keys") and args.sort_keys:
        options["sort_keys"] = True
    if hasattr(args, "sort_keys_reverse") and args.sort_keys_reverse:
        options["sort_keys_reverse"] = True
    if hasattr(args, "no_infer_dates") and args.no_infer_dates:
        options["infer_dates"] = False
    if getattr(args, "ini_quote_strings", False):
        options["ini_quote_strings"] = True
    if hasattr(args, "null_handling"):
        options["null_handling"] = args.null_handling
    if hasattr(args, "env_expand") and args.env_expand:
        options["env_expand"] = True
    if getattr(args, "tsv", False):
        options["csv_delimiter"] = "\t"
    elif getattr(args, "csv_delimiter", None):
        d = args.csv_delimiter
        if d in ("\\t", "TAB", "tab"):
            d = "\t"
        options["csv_delimiter"] = d

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
    if hasattr(args, "sort_keys_reverse") and args.sort_keys_reverse:
        options["sort_keys_reverse"] = True
    if hasattr(args, "no_infer_dates") and args.no_infer_dates:
        options["infer_dates"] = False
    if getattr(args, "ini_quote_strings", False):
        options["ini_quote_strings"] = True
    if hasattr(args, "null_handling"):
        options["null_handling"] = args.null_handling
    if hasattr(args, "env_expand") and args.env_expand:
        options["env_expand"] = True
    if getattr(args, "tsv", False):
        options["csv_delimiter"] = "\t"
    elif getattr(args, "csv_delimiter", None):
        d = args.csv_delimiter
        if d in ("\\t", "TAB", "tab"):
            d = "\t"
        options["csv_delimiter"] = d

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


def _get_env_info() -> dict:
    """Collect environment info for --check-env output."""
    import platform
    import sys as _sys

    from . import configforge as _cf
    from ._version import __version__ as _ver

    # Optional dependency probes
    optional_deps: dict[str, str | None] = {}
    for modname, label in [
        ("yaml", "pyyaml"),
        ("hcl2", "python-hcl2"),
        ("lxml", "lxml"),
        ("ruamel.yaml", "ruamel.yaml"),
    ]:
        try:
            mod = importlib.util.find_spec(modname.split(".")[0])
            if mod is not None:
                imported = __import__(modname.split(".")[0])
                optional_deps[label] = getattr(imported, "__version__", "installed")
            else:
                optional_deps[label] = None
        except Exception:
            optional_deps[label] = None

    # Format availability — map format → dep that enables it
    _format_deps: dict[str, str | None] = {
        "json": None, "jsonc": None, "env": None, "properties": None,
        "yaml": "pyyaml", "toml": None, "xml": None, "csv": None,
        "ini": None, "hcl": "python-hcl2", "plist": None,
    }
    formats_status: dict[str, bool] = {}
    for fmt in _cf.SUPPORTED_FORMATS:
        dep = _format_deps.get(fmt)
        formats_status[fmt] = (dep is None) or (optional_deps.get(dep) is not None)

    return {
        "version": _ver,
        "python_version": _sys.version.split()[0],
        "python_impl": platform.python_implementation(),
        "platform": _sys.platform,
        "arch": platform.machine(),
        "formats": formats_status,
        "optional_deps": optional_deps,
    }


def _run_cf_check_env(args: argparse.Namespace) -> int:
    """Implement devbench cf --check-env."""
    info = _get_env_info()

    if getattr(args, "raw", False):
        print(json.dumps(info, ensure_ascii=False))
        return EXIT_SUCCESS

    lines = [
        "═" * 60,
        f"  DevBench {info['version']} — Environment",
        "═" * 60,
        "",
        f"Python:   {info['python_version']} ({info['python_impl']}) — {info['platform']}",
        f"Platform: {info['arch']}",
        "",
        f"Config Formats ({sum(info['formats'].values())}/{len(info['formats'])} available):",
    ]
    _dep_labels: dict[str, str] = {
        "json": "stdlib", "jsonc": "stdlib", "env": "stdlib",
        "properties": "stdlib", "toml": "stdlib tomllib", "xml": "stdlib xml.etree",
        "csv": "stdlib csv", "ini": "stdlib configparser", "plist": "stdlib plistlib",
        "yaml": "PyYAML", "hcl": "python-hcl2",
    }
    for fmt, available in info["formats"].items():
        mark = "✓" if available else "✗"
        label = _dep_labels.get(fmt, "")
        status = ""
        if not available:
            dep_name = {"yaml": "pyyaml", "hcl": "python-hcl2"}.get(fmt, "")
            status = f"  [pip install {dep_name}]" if dep_name else ""
        lines.append(f"  {mark} {fmt:<12} {label}{status}")

    lines += [
        "",
        "Optional dependencies:",
    ]
    for dep, ver in info["optional_deps"].items():
        mark = "✓" if ver else "✗"
        lines.append(f"  {mark} {dep:<20} {ver or 'not installed'}")

    lines += [
        "",
        "CI/CD quick start:",
        "  pip install devbench",
        "  devbench cf config.yaml --to json",
        "  devbench cf '*.yaml' --batch --validate",
        "  devbench cf deploy.yaml --get spec.replicas",
        "",
        "Verify install:",
        f"  devbench --version   →  devbench {info['version']}",
        "  devbench cf --check-env --raw  →  JSON output for scripts",
    ]

    print("\n".join(lines))
    return EXIT_SUCCESS


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
    """Write output_text to file_path atomically, optionally backing up the original.

    Uses write-to-temp + rename so the file is never left in a truncated state
    if the write fails mid-way — the same data-loss bug reported against yq's
    -i flag (yq issue / codegenes.net post: yq truncates before writing, so a
    failed write destroys the original).

    Returns True on success, False on error (error printed to stderr).
    """
    import tempfile, os, shutil

    if backup_suffix:
        bak_path = Path(str(file_path) + backup_suffix)
        try:
            shutil.copy2(file_path, bak_path)
        except OSError as e:
            print(f"error: could not create backup {bak_path}: {e}", file=sys.stderr)
            return False

    tmp_path = None
    try:
        # Write to a sibling temp file so rename() is always on the same filesystem.
        fd, tmp_name = tempfile.mkstemp(dir=file_path.parent, suffix=".devbench.tmp")
        tmp_path = Path(tmp_name)
        try:
            os.write(fd, output_text.encode("utf-8"))
        finally:
            os.close(fd)
        # Preserve original file permissions on the new file.
        try:
            os.chmod(tmp_path, file_path.stat().st_mode)
        except OSError:
            pass
        # Atomic replace — original is never truncated before the new content is ready.
        tmp_path.replace(file_path)
        tmp_path = None  # rename succeeded; nothing to clean up
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        if tmp_path is not None:
            try:
                tmp_path.unlink()
            except OSError:
                pass
        return False
    return True


def _cf_serialize_options(args) -> dict:
    opts: dict = {}
    if hasattr(args, "indent"):
        opts["indent"] = args.indent
    if getattr(args, "sort_keys", False):
        opts["sort_keys"] = True
    if getattr(args, "sort_keys_reverse", False):
        opts["sort_keys_reverse"] = True
    if getattr(args, "no_comments", False):
        opts["preserve_comments"] = False
    if getattr(args, "block_scalars", False):
        opts["block_scalars"] = True
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
        default = getattr(args, "get_default", None)
        if default is not None:
            sys.stdout.write(default + "\n")
            return EXIT_SUCCESS
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


def _run_cf_rename(args) -> int:
    """Rename/move a config key from OLD_PATH to NEW_PATH.

    Reads the config, fetches the value at OLD_PATH, writes it to NEW_PATH
    (creating intermediate dicts as needed), then deletes OLD_PATH.
    Supports all 11 formats; outputs in input format by default.
    Combine with --in-place to edit the file in-place with optional --backup.
    --raw outputs JSON: {success, renamed_from, renamed_to}.
    Exit 0 = success, exit 1 = key not found or path error.
    Preserves comments by updating comment metadata paths during rename.
    """
    from . import configforge as _cf
    raw = getattr(args, "raw", False)
    content, file_path = _cf_read_file_or_content(args)
    if content is None:
        return EXIT_ERROR
    from_fmt = getattr(args, "from_fmt", "auto")
    try:
        parsed = _cf.parse_text(content, fmt=None if from_fmt == "auto" else from_fmt,
                                **_cf_parse_opts(args))
    except ValueError as exc:
        msg = f"error: {exc}"
        if raw:
            print(json.dumps({"success": False, "error": msg}))
        else:
            print(msg, file=sys.stderr)
        return EXIT_ERROR
    detected_fmt = parsed.get("format")
    data = parsed.get("data", parsed)

    comments, blanks = [], []
    if detected_fmt == "yaml" and _cf.HAS_YAML:
        comments = _cf._extract_yaml_comments(content)
        blanks = _cf._extract_yaml_blank_lines(content)

    old_path, new_path = args.rename_paths
    try:
        _cf._rename_by_path(data, old_path, new_path)
    except KeyError as exc:
        msg = f"error: {exc}"
        if raw:
            print(json.dumps({"success": False, "error": msg}))
        else:
            print(msg, file=sys.stderr)
        return EXIT_ERROR

    for comment in comments:
        if "key" in comment:
            key = comment["key"]
            if key == old_path:
                comment["key"] = new_path
            elif key.startswith(old_path + "."):
                suffix = key[len(old_path):]
                comment["key"] = new_path + suffix

    to_fmt = getattr(args, "to", None) or detected_fmt
    if not to_fmt:
        print("error: cannot determine output format; use --to", file=sys.stderr)
        return EXIT_ERROR
    try:
        output_text = _cf.serialize(data, to_fmt, **_cf_serialize_options(args))
    except ValueError as exc:
        msg = f"error: {exc}"
        if raw:
            print(json.dumps({"success": False, "error": msg}))
        else:
            print(msg, file=sys.stderr)
        return EXIT_ERROR

    if not output_text.endswith("\n"):
        output_text += "\n"

    if to_fmt == "yaml":
        if blanks:
            output_text = _cf._reinsert_yaml_blank_lines(output_text, blanks)
        if comments:
            output_text = _cf._reinsert_yaml_comments(output_text, comments)
    elif comments and to_fmt == "ini":
        output_text = _cf._reinsert_ini_comments(output_text, comments)
    elif comments and to_fmt == "toml":
        output_text = _cf._reinsert_toml_comments(output_text, comments)

    if raw:
        print(json.dumps({"success": True, "renamed_from": old_path, "renamed_to": new_path}))
        return EXIT_SUCCESS
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
# cf --length PATH: length of value at path (jq `.path | length` equivalent)
# ---------------------------------------------------------------------------


def _run_cf_length(args) -> int:
    """Output the length of the value at PATH.

    - list/dict: item count (same as --count)
    - string: character count
    - null: 0
    - scalar (int/float/bool): 1

    Exit 0 = path found, exit 1 = path not found.
    --raw outputs JSON: {path, length, type}.
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
    path = args.length_path
    if path == ".":
        val = data
    else:
        try:
            val = _cf._get_by_path(data, path)
        except (KeyError, IndexError, TypeError) as exc:
            msg = f"path not found: {path!r}"
            if getattr(args, "raw", False):
                print(json.dumps({"path": path, "error": msg}))
            else:
                print(f"error: {msg}", file=sys.stderr)
            return EXIT_ERROR

    if val is None:
        length = 0
        type_name = "null"
    elif isinstance(val, str):
        length = len(val)
        type_name = "string"
    elif isinstance(val, (list, dict)):
        length = len(val)
        type_name = "array" if isinstance(val, list) else "object"
    else:
        length = 1
        type_name = "boolean" if isinstance(val, bool) else "number" if isinstance(val, float) else "integer"

    if getattr(args, "raw", False):
        print(json.dumps({"path": path, "length": length, "type": type_name}))
    else:
        print(length)
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# cf --type PATH: report JSON Schema type of a value
# ---------------------------------------------------------------------------

_PYTHON_TO_JSON_TYPE = {
    bool: "boolean",   # must come before int (bool is subclass of int)
    int: "integer",
    float: "number",
    str: "string",
    list: "array",
    dict: "object",
    type(None): "null",
}


def _json_type_name(val) -> str:
    for py_type, name in _PYTHON_TO_JSON_TYPE.items():
        if type(val) is py_type:
            return name
    return "unknown"


def _run_cf_type(args) -> int:
    """Output the JSON Schema type of the value at TYPE_PATH.

    Prints one of: string, integer, number, boolean, array, object, null.
    --raw outputs JSON: {path, type, length} where length is the item count
    for array/object values (omitted for scalars).
    Exit 0 = path found, exit 1 = path not found.
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
    path = args.type_path
    if path == ".":
        val = data
    else:
        try:
            val = _cf._get_by_path(data, path)
        except (KeyError, IndexError) as exc:
            raw = getattr(args, "raw", False)
            msg = f"error: {exc}"
            if raw:
                print(json.dumps({"path": path, "error": str(exc)}))
            else:
                print(msg, file=sys.stderr)
            return EXIT_ERROR
    type_name = _json_type_name(val)
    raw = getattr(args, "raw", False)
    if raw:
        result: dict = {"path": path, "type": type_name}
        if isinstance(val, (list, dict)):
            result["length"] = len(val)
        print(json.dumps(result))
    else:
        print(type_name)
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# cf --has PATH: check whether a path exists in the config
# ---------------------------------------------------------------------------


def _run_cf_has(args) -> int:
    """Check whether PATH exists in the config.

    Prints 'true' and exits 0 if found (even if the value is null).
    Prints 'false' and exits 1 if the path is not found.
    --raw outputs JSON: {path, exists, type}.

    Examples:
        devbench cf config.yaml --has database.host
        devbench cf k8s.yaml --has spec.template.spec.containers
        if devbench cf config.yaml --has feature.flags.dark_mode; then echo enabled; fi
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
    path = args.has_path
    raw = getattr(args, "raw", False)

    if path == ".":
        exists = True
        type_name = _json_type_name(data)
    else:
        try:
            val = _cf._get_by_path(data, path)
            exists = True
            type_name = _json_type_name(val)
        except (KeyError, IndexError, TypeError):
            exists = False
            type_name = None

    if raw:
        result: dict = {"path": path, "exists": exists}
        if type_name is not None:
            result["type"] = type_name
        print(json.dumps(result))
    else:
        print("true" if exists else "false")

    return EXIT_SUCCESS if exists else EXIT_ERROR


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
# cf --mask: redact sensitive values matching a key-name regex
# ---------------------------------------------------------------------------


def _run_cf_mask(args) -> int:
    """Redact config values whose key names match a regex pattern.

    Parses the input config (any of 11 formats), walks the data tree,
    replaces values for matching key names with the redaction string, then
    serializes to the target format (--to, default: same as input).

    Useful for:
      - CI/CD pipeline logging without credential leaks
      - Creating sanitized configs for documentation or bug reports
      - Sharing configs with teammates without exposing prod secrets
      - Audit log generation (mask before storing)

    Exit 0 always (masking cannot fail if parsing succeeds).
    """
    from . import configforge as _cf

    raw = getattr(args, "raw", False)
    pattern = args.mask_pattern
    replacement = getattr(args, "mask_value", "***REDACTED***")
    to_fmt = getattr(args, "to", None)
    from_fmt = getattr(args, "from_fmt", "auto")
    parse_opts = _cf_parse_opts(args)

    # Read input
    content, file_path = _cf_read_file_or_content(args)
    if content is None:
        return EXIT_ERROR
    label = str(file_path) if file_path else "stdin"

    # Parse (auto-detects format via parse_text)
    try:
        parsed = _cf.parse_text(content, fmt=None if from_fmt == "auto" else from_fmt, **parse_opts)
        data = parsed.get("data", parsed)
        detected_fmt = parsed.get("format") or "yaml"
    except Exception as exc:
        msg = f"error: could not parse config: {exc}"
        if raw:
            print(json.dumps({"error": msg}))
        else:
            print(msg, file=sys.stderr)
        return EXIT_ERROR

    # Validate pattern is a valid regex
    import re as _re
    try:
        _re.compile(pattern)
    except _re.error as exc:
        msg = f"error: invalid regex pattern '{pattern}': {exc}"
        if raw:
            print(json.dumps({"error": msg}))
        else:
            print(msg, file=sys.stderr)
        return EXIT_ERROR

    # Mask
    masked = _cf.mask_sensitive(data, pattern, replacement)

    # Count how many values were redacted (for --raw metadata)
    redacted_count = [0]

    def _count_redacted(original, result):
        if isinstance(result, dict):
            for k in result:
                if result[k] == replacement and original.get(k) != replacement:
                    redacted_count[0] += 1
                else:
                    _count_redacted(original.get(k, {}), result[k])
        elif isinstance(result, list):
            for o, r in zip(original if isinstance(original, list) else [], result):
                _count_redacted(o, r)

    _count_redacted(data, masked)

    # Serialize output
    out_fmt = to_fmt or detected_fmt
    try:
        output_text = _cf.serialize(masked, out_fmt)
    except Exception as exc:
        msg = f"error: could not serialize masked config as {out_fmt}: {exc}"
        if raw:
            print(json.dumps({"error": msg}))
        else:
            print(msg, file=sys.stderr)
        return EXIT_ERROR

    if raw:
        print(json.dumps({
            "file": label,
            "pattern": pattern,
            "format": out_fmt,
            "redacted_count": redacted_count[0],
            "output": output_text,
        }, indent=2))
    else:
        print(output_text, end="" if output_text.endswith("\n") else "\n")

    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# cf --hash-field: replace field values with their hash (yq issue #2283)
# ---------------------------------------------------------------------------


def _run_cf_hash_field(args) -> int:
    """Hash config field values whose key names match a regex pattern.

    Replaces scalar values with ``algo:hexdigest`` strings so configs can be
    shared or stored in audit logs without exposing sensitive data.  Unlike
    --mask (which replaces with a fixed string), hashed values are
    deterministic and can be compared across environments.

    Example: devbench cf prod.yaml --hash-field 'password|secret|token'
    """
    from . import configforge as _cf

    raw = getattr(args, "raw", False)
    pattern = args.hash_pattern
    algorithm = getattr(args, "hash_algorithm", "sha256")
    to_fmt = getattr(args, "to", None)
    from_fmt = getattr(args, "from_fmt", "auto")
    parse_opts = _cf_parse_opts(args)

    # Read input
    content, file_path = _cf_read_file_or_content(args)
    if content is None:
        return EXIT_ERROR
    label = str(file_path) if file_path else "stdin"

    # Parse
    try:
        parsed = _cf.parse_text(content, fmt=None if from_fmt == "auto" else from_fmt, **parse_opts)
        data = parsed.get("data", parsed)
        detected_fmt = parsed.get("format") or "yaml"
    except Exception as exc:
        msg = f"error: could not parse config: {exc}"
        if raw:
            print(json.dumps({"error": msg}))
        else:
            print(msg, file=sys.stderr)
        return EXIT_ERROR

    # Validate regex
    import re as _re
    try:
        _re.compile(pattern)
    except _re.error as exc:
        msg = f"error: invalid regex pattern '{pattern}': {exc}"
        if raw:
            print(json.dumps({"error": msg}))
        else:
            print(msg, file=sys.stderr)
        return EXIT_ERROR

    # Hash fields
    try:
        hashed = _cf.hash_field_values(data, pattern, algorithm)
    except ValueError as exc:
        msg = f"error: {exc}"
        if raw:
            print(json.dumps({"error": msg}))
        else:
            print(msg, file=sys.stderr)
        return EXIT_ERROR

    # Count hashed fields
    hashed_count = [0]

    def _count_hashed(original, result):
        if isinstance(result, dict):
            for k in result:
                if isinstance(result[k], str) and result[k] != original.get(k, result[k]) and ":" in result[k]:
                    hashed_count[0] += 1
                else:
                    _count_hashed(original.get(k, {}), result[k])
        elif isinstance(result, list):
            for o, r in zip(original if isinstance(original, list) else [], result):
                _count_hashed(o, r)

    _count_hashed(data, hashed)

    # Serialize output
    out_fmt = to_fmt or detected_fmt
    try:
        output_text = _cf.serialize(hashed, out_fmt)
    except Exception as exc:
        msg = f"error: could not serialize as {out_fmt}: {exc}"
        if raw:
            print(json.dumps({"error": msg}))
        else:
            print(msg, file=sys.stderr)
        return EXIT_ERROR

    if raw:
        print(json.dumps({
            "file": label,
            "pattern": pattern,
            "algorithm": algorithm,
            "format": out_fmt,
            "hashed_count": hashed_count[0],
            "output": output_text,
        }, indent=2))
    else:
        print(output_text, end="" if output_text.endswith("\n") else "\n")

    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# cf --schema: validate a config against a JSON Schema file
# ---------------------------------------------------------------------------


def _run_cf_schema(args) -> int:
    """Validate a config file against a JSON Schema.

    Parses the input config (any of 11 formats), loads the schema file
    (JSON or YAML), and runs jsonschema.Draft7Validator.  Exit 0 = valid,
    exit 1 = invalid — suitable for CI/CD pre-flight checks.
    Requires: pip install jsonschema
    """
    from . import configforge as _cf

    raw = getattr(args, "raw", False)
    schema_path = args.schema_file
    from_fmt = getattr(args, "from_fmt", "auto")
    parse_opts = _cf_parse_opts(args)

    # Read the config input
    content, file_path = _cf_read_file_or_content(args)
    if content is None:
        return EXIT_ERROR
    label = str(file_path) if file_path else "stdin"

    # Parse the config
    try:
        parsed = _cf.parse_text(
            content,
            fmt=None if from_fmt == "auto" else from_fmt,
            **parse_opts,
        )
        data = parsed.get("data", parsed)
    except Exception as exc:
        msg = f"error: could not parse config: {exc}"
        if raw:
            print(json.dumps({"valid": False, "errors": [msg]}))
        else:
            print(msg, file=sys.stderr)
        return EXIT_ERROR

    # Load the JSON Schema (JSON or YAML)
    try:
        schema_text = Path(schema_path).read_text(encoding="utf-8")
        schema_ext = Path(schema_path).suffix.lower()
        if schema_ext in (".yaml", ".yml"):
            import yaml as _yaml  # noqa: PLC0415
            schema = _yaml.safe_load(schema_text)
        else:
            schema = json.loads(schema_text)
    except OSError as exc:
        msg = f"error: could not read schema file '{schema_path}': {exc}"
        if raw:
            print(json.dumps({"valid": False, "errors": [msg]}))
        else:
            print(msg, file=sys.stderr)
        return EXIT_ERROR
    except Exception as exc:
        msg = f"error: could not parse schema: {exc}"
        if raw:
            print(json.dumps({"valid": False, "errors": [msg]}))
        else:
            print(msg, file=sys.stderr)
        return EXIT_ERROR

    # Run schema validation
    result = _cf.schema_validate(data, schema)

    if raw:
        print(json.dumps({"file": label, "schema": schema_path, **result}, indent=2))
    else:
        if result["valid"]:
            print(f"{label}: valid  (matches schema: {schema_path})")
        else:
            print(f"{label}: INVALID  (schema: {schema_path})")
            for err in result["errors"]:
                print(f"  - {err}", file=sys.stderr)

    return EXIT_SUCCESS if result["valid"] else EXIT_ERROR


# ---------------------------------------------------------------------------
# cf --assert: assert that config key(s) equal expected values
# ---------------------------------------------------------------------------


def _run_cf_assert(args) -> int:
    """Assert that one or more config keys equal expected values.

    Parses the input config (any of 11 formats), resolves each PATH using
    dot-notation, and compares the actual value against the expected VALUE.
    The expected value is coerced using the same JSON-aware logic as --set
    (numbers, booleans, null, strings), so ``--assert replicas=3`` matches
    an integer 3, not the string "3".

    Exit 0 = all assertions pass.
    Exit 1 = any assertion fails or a key is missing.

    Use --raw for machine-readable JSON: {assertions: [...], all_passed: bool}.

    Examples:
        devbench cf deploy.yaml --assert spec.replicas=3
        devbench cf config.yaml --assert db.host=prod --assert db.port=5432
        devbench cf app.toml --assert server.debug=false --raw
    """
    from . import configforge as _cf

    raw = getattr(args, "raw", False)
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
    results = []
    all_passed = True

    for assertion in args.asserts:
        if "=" not in assertion:
            print(
                f"error: invalid assert format '{assertion}' — expected PATH=VALUE",
                file=sys.stderr,
            )
            return EXIT_ERROR

        path, expected_str = assertion.split("=", 1)
        path = path.strip()
        expected = _cf._coerce_set_value(expected_str)

        missing = False
        actual = None
        try:
            actual = _cf._get_by_path(data, path)
        except (KeyError, IndexError, TypeError):
            missing = True

        passed = (not missing) and (actual == expected)
        if not passed:
            all_passed = False

        results.append(
            {
                "path": path,
                "expected": expected,
                "actual": actual,
                "passed": passed,
                "missing": missing,
            }
        )

    if raw:
        print(json.dumps({"assertions": results, "all_passed": all_passed}, indent=2))
    else:
        for r in results:
            if r["passed"]:
                print(f"PASS  {r['path']} == {r['expected']!r}")
            elif r["missing"]:
                print(
                    f"FAIL  {r['path']}: key not found (expected {r['expected']!r})",
                    file=sys.stderr,
                )
            else:
                print(
                    f"FAIL  {r['path']}: got {r['actual']!r}, expected {r['expected']!r}",
                    file=sys.stderr,
                )

    return EXIT_SUCCESS if all_passed else EXIT_ERROR


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
# cf --path-exists: check whether a path exists in the config
# ---------------------------------------------------------------------------


def _run_cf_path_exists(args) -> int:
    """Check whether a dot-notation PATH exists in the config.

    Exit 0 = path exists, exit 1 = path not found (or on parse error).
    Use --raw for JSON output {path, exists}.

    Examples:
        devbench cf deploy.yaml --path-exists spec.replicas
        devbench cf config.toml --path-exists database.host --raw
        if devbench cf config.yaml --path-exists tls.cert; then echo "TLS configured"; fi
    """
    from . import configforge as _cf

    raw = getattr(args, "raw", False)
    path = args.path_exists

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
    exists = True
    try:
        _cf._get_by_path(data, path)
    except (KeyError, IndexError, TypeError):
        exists = False

    if raw:
        print(json.dumps({"path": path, "exists": exists}))
    else:
        if exists:
            print(f"EXISTS  {path}")
        else:
            print(f"MISSING {path}", file=sys.stderr)

    return EXIT_SUCCESS if exists else EXIT_ERROR


# ---------------------------------------------------------------------------
# cf --shell-export: emit shell-safe export statements
# ---------------------------------------------------------------------------


def _run_cf_shell_export(args) -> int:
    """Convert a config to shell-safe ``export KEY="value"`` statements.

    Keys are uppercased and non-alphanumeric characters (dots, dashes,
    spaces) are replaced with underscores.  Values are shell-quoted via
    shlex.quote so they survive special characters, spaces, and newlines.

    Combine with --flatten to export nested configs:
        source <(devbench cf config.yaml --flatten --shell-export)

    Use --raw for JSON output {exports: [{key, value}]}.

    Examples:
        devbench cf .env --shell-export
        devbench cf config.yaml --flatten --shell-export
        devbench cf app.toml --from toml --flatten --shell-export --raw
        source <(devbench cf secrets.yaml --flatten --shell-export)
    """
    import re
    import shlex
    from . import configforge as _cf

    raw = getattr(args, "raw", False)

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

    # Flatten nested dicts to dot-notation before exporting
    sep = getattr(args, "sep", ".")
    if isinstance(data, dict):
        flat = _cf._flatten_dict(data, sep=sep)
    else:
        print("error: --shell-export requires a mapping (dict) config, not a list or scalar", file=sys.stderr)
        return EXIT_ERROR

    def _to_env_key(k: str) -> str:
        """Uppercase and replace non-alphanumeric chars with underscores."""
        return re.sub(r"[^A-Z0-9_]", "_", k.upper())

    bash_arrays = getattr(args, "bash_arrays", False)

    def _scalar_str(v) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        return str(v)

    exports = []
    for k, v in flat.items():
        env_key = _to_env_key(k)
        if isinstance(v, list):
            exports.append({"key": env_key, "value": None, "list": [_scalar_str(i) for i in v]})
        else:
            exports.append({"key": env_key, "value": _scalar_str(v), "list": None})

    if raw:
        print(json.dumps({"exports": [
            {"key": e["key"], "value": e["value"], "items": e["list"]} for e in exports
        ]}, indent=2))
    else:
        for entry in exports:
            if entry["list"] is not None:
                items = entry["list"]
                if bash_arrays:
                    quoted_items = " ".join(shlex.quote(i) for i in items)
                    print(f"declare -a {entry['key']}=({quoted_items})")
                    print(f"export {entry['key']}")
                else:
                    for idx, item in enumerate(items):
                        print(f"export {entry['key']}_{idx}={shlex.quote(item)}")
                    print(f"export {entry['key']}_COUNT={len(items)}")
            else:
                print(f"export {entry['key']}={shlex.quote(entry['value'])}")

    return EXIT_SUCCESS


def _run_cf_select(args) -> int:
    """Filter list items by a field condition.

    Operators:
      FIELD=VALUE    keep items where item[FIELD] == VALUE
      FIELD!=VALUE   keep items where item[FIELD] != VALUE
      FIELD=/pat/    keep items where item[FIELD] matches regex /pat/ (case-insensitive)
      FIELD!=/pat/   keep items where item[FIELD] does NOT match regex /pat/
      FIELD~VALUE    keep items where item[FIELD] is an array containing VALUE
      FIELD!~VALUE   keep items where item[FIELD] is an array NOT containing VALUE

    Value is coerced to int/bool/null for comparison. Exit 0=matches, 1=no matches.

    Examples:
        devbench cf pods.yaml --select status=Running
        devbench cf countries.yaml --select tags~commonwealth
        devbench cf deploy.yaml --get spec.containers --select name=nginx
        devbench cf deploy.yaml --get spec.containers --select name=/^prod-/
        devbench cf services.yaml --select enabled!=false --to json
        devbench cf config.yaml --select image=/alpine/ --each name
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
    detected_fmt = parsed.get("format", "yaml")

    if getattr(args, "get", None):
        try:
            data = _cf._get_by_path(data, args.get)
        except (KeyError, IndexError) as exc:
            default = getattr(args, "get_default", None)
            if default is not None:
                sys.stdout.write(default + "\n")
                return EXIT_SUCCESS
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_ERROR

    if not isinstance(data, list):
        print("error: --select requires a list; input is not a list (use --get PATH to navigate to one)",
              file=sys.stderr)
        return EXIT_ERROR

    expr = args.select_expr
    # Parse operator: !~ before != before ~ before = to avoid ambiguity
    if "!~" in expr:
        field, raw_val = expr.split("!~", 1)
        op = "not_contains"
    elif "!=" in expr:
        field, raw_val = expr.split("!=", 1)
        op = "neq"
    elif "~" in expr:
        field, raw_val = expr.split("~", 1)
        op = "contains"
    elif "=" in expr:
        field, raw_val = expr.split("=", 1)
        op = "eq"
    else:
        print(f"error: invalid --select expression {expr!r}; "
              "expected FIELD=VALUE, FIELD!=VALUE, FIELD=/regex/, FIELD~VALUE, or FIELD!~VALUE",
              file=sys.stderr)
        return EXIT_ERROR

    # Detect /pattern/ regex syntax for eq and neq operators
    import re as _re
    regex_pat = None
    if op in ("eq", "neq") and raw_val.startswith("/") and raw_val.endswith("/") and len(raw_val) >= 2:
        try:
            regex_pat = _re.compile(raw_val[1:-1], _re.IGNORECASE)
            op = "regex_match" if op == "eq" else "regex_not_match"
        except _re.error as exc:
            print(f"error: invalid regex {raw_val!r}: {exc}", file=sys.stderr)
            return EXIT_ERROR

    coerced_val = _cf._coerce_set_value(raw_val) if regex_pat is None else None

    def _item_matches(item):
        if not isinstance(item, dict):
            return False
        try:
            item_val = _cf._get_by_path(item, field)
        except (KeyError, IndexError, TypeError):
            return False
        if op == "regex_match":
            return bool(regex_pat.search(str(item_val)))
        if op == "regex_not_match":
            return not regex_pat.search(str(item_val))
        if op == "eq":
            return item_val == coerced_val
        if op == "neq":
            return item_val != coerced_val
        if op == "contains":
            return isinstance(item_val, list) and coerced_val in item_val
        if op == "not_contains":
            return not (isinstance(item_val, list) and coerced_val in item_val)
        return False

    filtered = [item for item in data if _item_matches(item)]

    if not filtered:
        return EXIT_ERROR  # exit 1 = no matches (grep semantics)

    to_fmt = getattr(args, "to", None) or detected_fmt
    indent = getattr(args, "indent", 2)
    compact = getattr(args, "compact", False)

    # serialize() treats Python lists as multi-doc YAML streams, so handle
    # YAML and JSON directly here to produce proper sequence output.
    if to_fmt in ("yaml", "yml"):
        import yaml as _yaml
        output_text = _yaml.dump(filtered, default_flow_style=False, allow_unicode=True, indent=indent)
    elif to_fmt in ("json", "jsonc"):
        output_text = (json.dumps(filtered) if compact else json.dumps(filtered, indent=indent)) + "\n"
    else:
        try:
            output_text = _cf.serialize(filtered, to_fmt, **_cf_serialize_options(args))
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_ERROR
    if not output_text.endswith("\n"):
        output_text += "\n"
    sys.stdout.write(output_text)
    return EXIT_SUCCESS


def _run_cf_each(args) -> int:
    """Extract a field (KEY) from every element in a list and output the results.

    Equivalent to jq '[.[] | .key]' or yq '.[].key'.  Navigates to --get
    PATH first if provided.  Optionally applies --select filtering before
    extraction so you can chain: --select status=Running --each metadata.name.
    Items that do not contain KEY are silently omitted.

    Examples:
        devbench cf deploy.yaml --get spec.containers --each name
        devbench cf pods.yaml --select status=Running --each metadata.name
        devbench cf services.yaml --each spec.ports.0.port --to json
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
    detected_fmt = parsed.get("format", "yaml")

    # Navigate to path via --get if specified
    if getattr(args, "get", None):
        try:
            data = _cf._get_by_path(data, args.get)
        except (KeyError, IndexError) as exc:
            default = getattr(args, "get_default", None)
            if default is not None:
                sys.stdout.write(default + "\n")
                return EXIT_SUCCESS
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_ERROR

    # Apply --select filter before --each if both are present
    if getattr(args, "select_expr", None):
        expr = args.select_expr
        if "!~" in expr:
            field, raw_val = expr.split("!~", 1)
            op = "not_contains"
        elif "!=" in expr:
            field, raw_val = expr.split("!=", 1)
            op = "neq"
        elif "~" in expr:
            field, raw_val = expr.split("~", 1)
            op = "contains"
        elif "=" in expr:
            field, raw_val = expr.split("=", 1)
            op = "eq"
        else:
            print(f"error: invalid --select expression {expr!r}; "
                  "expected FIELD=VALUE, FIELD!=VALUE, FIELD~VALUE, or FIELD!~VALUE",
                  file=sys.stderr)
            return EXIT_ERROR
        coerced_val = _cf._coerce_set_value(raw_val)

        def _item_matches(item):
            if not isinstance(item, dict):
                return False
            try:
                item_val = _cf._get_by_path(item, field)
            except (KeyError, IndexError, TypeError):
                return False
            if op == "eq":
                return item_val == coerced_val
            if op == "neq":
                return item_val != coerced_val
            if op == "contains":
                return isinstance(item_val, list) and coerced_val in item_val
            if op == "not_contains":
                return not (isinstance(item_val, list) and coerced_val in item_val)
            return False

        if isinstance(data, list):
            data = [item for item in data if _item_matches(item)]

    if not isinstance(data, list):
        print("error: --each requires a list; input is not a list (use --get PATH to navigate to one)",
              file=sys.stderr)
        return EXIT_ERROR

    key = args.each_key
    extracted = []
    for item in data:
        try:
            extracted.append(_cf._get_by_path(item, key))
        except (KeyError, IndexError, TypeError):
            pass  # silently skip items missing the key

    to_fmt = getattr(args, "to", None) or detected_fmt
    indent = getattr(args, "indent", 2)
    compact = getattr(args, "compact", False)
    raw = getattr(args, "raw", False)

    # Scalar list with --raw: one value per line
    if raw and all(not isinstance(v, (dict, list)) for v in extracted):
        for v in extracted:
            sys.stdout.write(str(v) + "\n")
        return EXIT_SUCCESS

    if to_fmt in ("yaml", "yml"):
        import yaml as _yaml
        output_text = _yaml.dump(extracted, default_flow_style=False, allow_unicode=True, indent=indent)
    elif to_fmt in ("json", "jsonc", "json5"):
        output_text = (json.dumps(extracted) if compact else json.dumps(extracted, indent=indent)) + "\n"
    else:
        try:
            output_text = _cf.serialize(extracted, to_fmt, **_cf_serialize_options(args))
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_ERROR
    if not output_text.endswith("\n"):
        output_text += "\n"
    sys.stdout.write(output_text)
    return EXIT_SUCCESS


def _run_cf_template(args) -> int:
    """Render a template file using config values as context.

    Template syntax:
      ${key} or $key  — Python string.Template (built-in, always available)
      {{ key }}       — Jinja2 (if jinja2 package is installed)

    Dot-path keys are available with dots replaced by underscores:
      database.host → ${database_host}  or  ${DATABASE_HOST}

    The full nested config dict is also available as ``config`` in Jinja2:
      {{ config.database.host }}

    Examples:
        devbench cf app.yaml --template deploy.tmpl > deploy.sh
        devbench cf secrets.yaml --template .env.tmpl > .env
        devbench cf config.json --from json --template nginx.conf.tmpl > nginx.conf
    """
    import re
    import string as _string
    from . import configforge as _cf

    template_path = args.template_file

    try:
        template_text = Path(template_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"error: template file not found: {template_path}", file=sys.stderr)
        return EXIT_ERROR
    except OSError as exc:
        print(f"error: cannot read template file: {exc}", file=sys.stderr)
        return EXIT_ERROR

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

    # Flatten to dot-notation for template variables
    flat = _cf._flatten_dict(data, sep=".") if isinstance(data, dict) else {}

    def _to_str(v) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        return str(v)

    # Build context: both lower and UPPER variants
    context: dict = {}
    for k, v in flat.items():
        str_val = _to_str(v)
        lower_key = re.sub(r"[^a-z0-9]", "_", k.lower())
        upper_key = re.sub(r"[^A-Z0-9]", "_", k.upper())
        context[lower_key] = str_val
        context[upper_key] = str_val

    # Try Jinja2 if template contains {{ or {%
    use_jinja2 = "{{" in template_text or "{%" in template_text
    if use_jinja2:
        try:
            import jinja2

            env = jinja2.Environment(
                undefined=jinja2.Undefined,
                keep_trailing_newline=True,
            )
            tmpl = env.from_string(template_text)
            result = tmpl.render(config=data, **context)
            print(result, end="")
            return EXIT_SUCCESS
        except ImportError:
            pass  # fall through to string.Template
        except jinja2.TemplateError as exc:
            print(f"error: Jinja2 template rendering failed: {exc}", file=sys.stderr)
            return EXIT_ERROR

    # Fall back to Python string.Template (${key} and $key syntax)
    try:
        tmpl = _string.Template(template_text)
        result = tmpl.safe_substitute(context)
    except (KeyError, ValueError) as exc:
        print(f"error: template substitution failed: {exc}", file=sys.stderr)
        return EXIT_ERROR

    print(result, end="")
    return EXIT_SUCCESS


def _run_cf_wrap_in(args) -> int:
    """Wrap the entire parsed config under a dotted key path.

    Examples:
        devbench cf config.yaml --wrap-in data
        # → {data: {original_config...}}

        devbench cf values.yaml --wrap-in spec.template.spec --to json
        # → {"spec": {"template": {"spec": {original...}}}}

    Useful for Kubernetes ConfigMap/patch generation, Helm value overrides,
    and Terraform module wrapping where a sub-document must be nested.
    """
    from . import configforge as _cf

    content, file_path = _cf_read_file_or_content(args)
    if content is None:
        return EXIT_ERROR

    _ext_map = {".yaml": "yaml", ".yml": "yaml", ".json": "json", ".toml": "toml",
                ".xml": "xml", ".csv": "csv", ".ini": "ini", ".env": "env",
                ".hcl": "hcl", ".properties": "properties", ".plist": "plist",
                ".jsonc": "jsonc", ".json5": "json5"}
    from_fmt_arg = getattr(args, "from_fmt", "auto")
    if from_fmt_arg == "auto" and file_path:
        from_fmt_arg = _ext_map.get(file_path.suffix.lower(), "auto")
    fmt = None if from_fmt_arg == "auto" else from_fmt_arg
    try:
        parsed = _cf.parse_text(content, fmt=fmt, **_cf_parse_opts(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    data = parsed.get("data", parsed)

    # Build the nested wrapper from the dotted key path (innermost first)
    key_path = args.wrap_in
    parts = key_path.split(".")
    wrapped = data
    for part in reversed(parts):
        if not part:
            print(f"error: --wrap-in path has empty segment: {key_path!r}", file=sys.stderr)
            return EXIT_ERROR
        wrapped = {part: wrapped}

    to_fmt = getattr(args, "to", None)  # --to arg uses dest="to"
    if not to_fmt:
        # Infer from input file extension or detected format
        if file_path:
            ext_map = {".yaml": "yaml", ".yml": "yaml", ".json": "json", ".toml": "toml",
                       ".xml": "xml", ".csv": "csv", ".ini": "ini", ".env": "env",
                       ".hcl": "hcl", ".properties": "properties", ".plist": "plist"}
            to_fmt = ext_map.get(file_path.suffix.lower(), "yaml")
        else:
            detected = _cf.detect_format(content)
            to_fmt = detected if detected != "unknown" else "yaml"

    raw = getattr(args, "raw", False)
    if raw:
        import json
        sys.stdout.write(json.dumps(wrapped) + "\n")
        return EXIT_SUCCESS

    try:
        output_text = _cf.serialize(wrapped, to_fmt, **_cf_serialize_options(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if not output_text.endswith("\n"):
        output_text += "\n"
    sys.stdout.write(output_text)
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# cf --sort-by / --unique / --unique-by: list operations
# ---------------------------------------------------------------------------

def _cf_list_output(data, args, detected_fmt) -> str:
    """Serialize a list to the requested output format."""
    from . import configforge as _cf
    to_fmt = getattr(args, "to", None) or detected_fmt
    indent = getattr(args, "indent", 2)
    compact = getattr(args, "compact", False)
    if to_fmt in ("yaml", "yml"):
        import yaml as _yaml
        return _yaml.dump(data, default_flow_style=False, allow_unicode=True, indent=indent)
    if to_fmt in ("json", "jsonc", "json5"):
        return (json.dumps(data) if compact else json.dumps(data, indent=indent)) + "\n"
    try:
        return _cf.serialize(data, to_fmt, **_cf_serialize_options(args))
    except ValueError as exc:
        raise ValueError(str(exc)) from exc


def _run_cf_sort_by(args) -> int:
    """Sort a list of objects by a field value.

    Examples:
        devbench cf pods.yaml --sort-by metadata.name
        devbench cf services.yaml --sort-by spec.replicas --sort-desc
        devbench cf deploy.yaml --get spec.containers --sort-by name
    """
    from . import configforge as _cf
    content, _ = _cf_read_file_or_content(args)
    if content is None:
        return EXIT_ERROR
    from_fmt = getattr(args, "from_fmt", "auto")
    try:
        parsed = _cf.parse_text(content, fmt=None if from_fmt == "auto" else from_fmt, **_cf_parse_opts(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    data = parsed.get("data", parsed)
    detected_fmt = parsed.get("format", "yaml")

    if getattr(args, "get", None):
        try:
            data = _cf._get_by_path(data, args.get)
        except (KeyError, IndexError) as exc:
            default = getattr(args, "get_default", None)
            if default is not None:
                sys.stdout.write(default + "\n")
                return EXIT_SUCCESS
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_ERROR

    if not isinstance(data, list):
        print("error: --sort-by requires a list; input is not a list (use --get PATH to navigate to one)",
              file=sys.stderr)
        return EXIT_ERROR

    field = args.sort_by
    desc = getattr(args, "sort_desc", False)

    def _sort_key(item):
        try:
            val = _cf._get_by_path(item, field)
        except (KeyError, IndexError, TypeError):
            return (2, "")  # items without the field sort last
        if isinstance(val, bool):
            return (1, int(val))
        if isinstance(val, (int, float)):
            return (0, val)
        return (1, str(val))

    sorted_data = sorted(data, key=_sort_key, reverse=desc)
    try:
        output_text = _cf_list_output(sorted_data, args, detected_fmt)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if not output_text.endswith("\n"):
        output_text += "\n"
    sys.stdout.write(output_text)
    return EXIT_SUCCESS


def _run_cf_unique(args) -> int:
    """Remove duplicate items from a list, optionally by a field value.

    Examples:
        devbench cf tags.yaml --unique
        devbench cf pods.yaml --unique-by metadata.name
        devbench cf deploy.yaml --get spec.containers --unique-by image
    """
    from . import configforge as _cf
    content, _ = _cf_read_file_or_content(args)
    if content is None:
        return EXIT_ERROR
    from_fmt = getattr(args, "from_fmt", "auto")
    try:
        parsed = _cf.parse_text(content, fmt=None if from_fmt == "auto" else from_fmt, **_cf_parse_opts(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    data = parsed.get("data", parsed)
    detected_fmt = parsed.get("format", "yaml")

    if getattr(args, "get", None):
        try:
            data = _cf._get_by_path(data, args.get)
        except (KeyError, IndexError) as exc:
            default = getattr(args, "get_default", None)
            if default is not None:
                sys.stdout.write(default + "\n")
                return EXIT_SUCCESS
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_ERROR

    if not isinstance(data, list):
        print("error: --unique/--unique-by requires a list; input is not a list (use --get PATH to navigate to one)",
              file=sys.stderr)
        return EXIT_ERROR

    unique_by_field = getattr(args, "unique_by", None)

    if unique_by_field:
        seen: set = set()
        result = []
        for item in data:
            try:
                val = _cf._get_by_path(item, unique_by_field)
                key = repr(val)
            except (KeyError, IndexError, TypeError):
                key = None  # items without the field are always kept
            if key is None or key not in seen:
                if key is not None:
                    seen.add(key)
                result.append(item)
    else:
        seen_exact: set = set()
        result = []
        for item in data:
            fingerprint = json.dumps(item, sort_keys=True, default=str)
            if fingerprint not in seen_exact:
                seen_exact.add(fingerprint)
                result.append(item)

    try:
        output_text = _cf_list_output(result, args, detected_fmt)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if not output_text.endswith("\n"):
        output_text += "\n"
    sys.stdout.write(output_text)
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# cf --join DELIM: join list items with a delimiter
# ---------------------------------------------------------------------------


def _run_cf_join(args) -> int:
    """Join list items into a single string using DELIM as separator.

    Composes with --get PATH (navigate to list), --select FIELD=VALUE (filter),
    and --each KEY (extract field) before joining.

    Examples:
        devbench cf config.yaml --get services --join ,
        devbench cf deps.yaml --get packages --join ' '
        devbench cf hosts.yaml --select env=prod --each name --join ,
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

    if getattr(args, "get", None):
        try:
            data = _cf._get_by_path(data, args.get)
        except (KeyError, IndexError) as exc:
            default = getattr(args, "get_default", None)
            if default is not None:
                sys.stdout.write(default + "\n")
                return EXIT_SUCCESS
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_ERROR

    if not isinstance(data, list):
        print("error: --join requires a list; input is not a list "
              "(use --get PATH to navigate to one)", file=sys.stderr)
        return EXIT_ERROR

    # Expand escape sequences in delimiter
    delim_raw = args.join_delim
    delim = delim_raw.replace("\\n", "\n").replace("\\t", "\t")

    # Convert each item to a string
    parts = []
    for item in data:
        if isinstance(item, bool):
            parts.append("true" if item else "false")
        elif item is None:
            parts.append("null")
        elif isinstance(item, (dict, list)):
            parts.append(json.dumps(item, ensure_ascii=False))
        else:
            parts.append(str(item))

    result = delim.join(parts)

    if getattr(args, "raw", False):
        print(json.dumps({"join": result, "count": len(data), "delimiter": delim_raw}))
    else:
        sys.stdout.write(result + "\n")
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# cf --schema-gen: generate JSON Schema Draft 7 from config
# ---------------------------------------------------------------------------


def _infer_json_schema(value) -> dict:
    """Recursively infer a JSON Schema Draft 7 definition from a Python value."""
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, str):
        return {"type": "string"}
    if isinstance(value, list):
        if not value:
            return {"type": "array", "items": {}}
        item_schemas = [_infer_json_schema(item) for item in value]
        # Unify: if all items share one type, merge them
        types = {s.get("type") for s in item_schemas}
        if len(types) == 1:
            single_type = list(types)[0]
            if single_type == "object":
                return {"type": "array", "items": _merge_object_schemas(item_schemas)}
            return {"type": "array", "items": item_schemas[0]}
        # Mixed types: deduplicate and use anyOf
        seen_keys: list[str] = []
        unique: list[dict] = []
        for s in item_schemas:
            key = json.dumps(s, sort_keys=True)
            if key not in seen_keys:
                seen_keys.append(key)
                unique.append(s)
        return {"type": "array", "items": (unique[0] if len(unique) == 1 else {"anyOf": unique})}
    if isinstance(value, dict):
        props = {k: _infer_json_schema(v) for k, v in value.items()}
        schema: dict = {"type": "object", "properties": props}
        if props:
            schema["required"] = list(value.keys())
        return schema
    return {"type": "string"}


def _merge_object_schemas(schemas: list) -> dict:
    """Merge object schemas: union properties, keep only fields required in ALL."""
    all_props: dict = {}
    for s in schemas:
        for k, v in s.get("properties", {}).items():
            if k not in all_props:
                all_props[k] = v
    required_sets = [set(s.get("required", [])) for s in schemas]
    common = set.intersection(*required_sets) if required_sets else set()
    result: dict = {"type": "object", "properties": all_props}
    if common:
        result["required"] = sorted(common)
    return result


def _run_cf_schema_gen(args) -> int:
    """Generate a JSON Schema Draft 7 document from any config file.

    Infers types, required fields, and array item shapes from the parsed data.
    Useful for validation setup, API documentation, and OpenAPI integration.

    Exit 0 on success.
    --to yaml outputs the schema as YAML.
    --raw outputs compact JSON.

    Examples:
        devbench cf config.yaml --schema-gen > config-schema.json
        devbench cf deploy.yaml --schema-gen --to yaml
        devbench cf app.toml --schema-gen --raw | jq .properties
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
    schema = {"$schema": "http://json-schema.org/draft-07/schema#"}
    schema.update(_infer_json_schema(data))

    to_fmt = getattr(args, "to", None)
    raw = getattr(args, "raw", False)

    if to_fmt in ("yaml", "yml"):
        import yaml as _yaml
        output = _yaml.dump(schema, default_flow_style=False, allow_unicode=True)
        sys.stdout.write(output)
        if not output.endswith("\n"):
            sys.stdout.write("\n")
    else:
        indent = None if raw else 2
        print(json.dumps(schema, indent=indent))

    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# cf --replace-value OLD NEW: find-and-replace values recursively
# ---------------------------------------------------------------------------


def _replace_values_recursive(obj, old_str: str, new_val):
    """Recursively replace all leaf values that match old_str with new_val."""
    if isinstance(obj, dict):
        return {k: _replace_values_recursive(v, old_str, new_val) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_values_recursive(item, old_str, new_val) for item in obj]
    # Leaf: compare as string or direct equality
    if obj == old_str or str(obj) == old_str:
        return new_val
    return obj


def _count_value_matches(obj, old_str: str) -> int:
    """Count how many leaf values match old_str."""
    if isinstance(obj, dict):
        return sum(_count_value_matches(v, old_str) for v in obj.values())
    if isinstance(obj, list):
        return sum(_count_value_matches(item, old_str) for item in obj)
    return 1 if (obj == old_str or str(obj) == old_str) else 0


def _run_cf_replace_value(args) -> int:
    """Find and replace all matching leaf values across the entire config.

    Traverses every dict value and list element recursively.  A leaf matches
    when its string representation equals OLD.  NEW is JSON-coerced so you
    can replace strings with numbers or booleans.

    Exit 0 = at least one replacement made.
    Exit 1 = no matches found.
    Combine with --in-place / --backup to edit files in-place.
    --raw outputs {replaced, old, new} instead of the converted config.

    Examples:
        devbench cf deploy.yaml --replace-value nginx:1.19 nginx:1.21
        devbench cf config.yaml --replace-value prod staging --in-place
        devbench cf manifest.yaml --replace-value false true --to json
    """
    from . import configforge as _cf

    content, file_path = _cf_read_file_or_content(args)
    if content is None:
        return EXIT_ERROR

    old_str, new_raw = args.replace_value
    new_val = _cf._coerce_set_value(new_raw)

    from_fmt = getattr(args, "from_fmt", "auto")
    try:
        parsed = _cf.parse_text(content, fmt=None if from_fmt == "auto" else from_fmt,
                                **_cf_parse_opts(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    data = parsed.get("data", parsed)
    detected_fmt = parsed.get("format", "yaml")
    match_count = _count_value_matches(data, old_str)

    if match_count == 0:
        raw = getattr(args, "raw", False)
        if raw:
            print(json.dumps({"replaced": 0, "old": old_str, "new": new_val}))
        else:
            print(f"no matches found for {old_str!r}", file=sys.stderr)
        return EXIT_ERROR

    updated = _replace_values_recursive(data, old_str, new_val)

    raw = getattr(args, "raw", False)
    if raw:
        print(json.dumps({"replaced": match_count, "old": old_str, "new": new_val}))
        return EXIT_SUCCESS

    to_fmt = getattr(args, "to", None) or detected_fmt
    try:
        output_text = _cf.serialize(updated, to_fmt, **_cf_serialize_options(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if not output_text.endswith("\n"):
        output_text += "\n"

    in_place = getattr(args, "in_place", False)
    backup_suffix = getattr(args, "backup_suffix", None)
    if in_place and file_path:
        _cf_write_in_place(file_path, output_text, backup_suffix)
        print(f"replaced {match_count} value(s): {old_str!r} → {new_raw!r}")
    else:
        sys.stdout.write(output_text)

    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Shell completion
# ---------------------------------------------------------------------------

_CF_FLAGS = (
    "--to --from --get --default --set --append --delete --rename --merge --list-merge "
    "--in-place -i --backup --diff --validate --count --length --type --has --keys "
    "--recursive -R --pick --select --each --join --grep --grep-case-sensitive "
    "--flatten --unflatten --sep --env-expand "
    "--batch --stream --output-dir --sort-keys --sort-keys-reverse --indent "
    "--sort-by --sort-desc --unique --unique-by "
    "--flatten-xml --no-comments --yaml12 --template-safe --block-scalars "
    "--null-handling --list-formats --check-env --schema --mask --mask-value --hash-field --hash-algorithm --assert "
    "--path-exists --shell-export --bash-arrays --compact -c --template --wrap-in "
    "--csv-delimiter --tsv --schema-gen --replace-value "
    "--serve --port --host --api --api-port "
    "--raw -r --pretty -p --help"
)
_CF_FORMATS = "json jsonc json5 yaml toml xml csv ini env hcl properties plist"
_SUBCOMMANDS = (
    "detect json base64 jwt hash url timestamp uuid diff "
    "cf token chunk list batch license completion"
)


def _run_completion(shell: str) -> int:
    """Print a shell completion script for devbench to stdout."""
    if shell == "bash":
        print(_BASH_COMPLETION)
    elif shell == "zsh":
        print(_ZSH_COMPLETION)
    elif shell == "fish":
        print(_FISH_COMPLETION)
    return EXIT_SUCCESS


_BASH_COMPLETION = f"""\
# devbench bash completion
# Add to ~/.bashrc or ~/.bash_profile:
#   eval "$(devbench completion bash)"
# Or source directly:
#   source <(devbench completion bash)

_devbench_complete() {{
    local cur prev subcmd
    COMPREPLY=()
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"

    # Find the subcommand (first non-flag word after 'devbench')
    subcmd=""
    local i
    for (( i=1; i < COMP_CWORD; i++ )); do
        if [[ "${{COMP_WORDS[$i]}}" != -* ]]; then
            subcmd="${{COMP_WORDS[$i]}}"
            break
        fi
    done

    local formats="{_CF_FORMATS}"
    local subcommands="{_SUBCOMMANDS}"

    case "$subcmd" in
        cf)
            case "$prev" in
                --to|--from)
                    COMPREPLY=( $(compgen -W "$formats" -- "$cur") )
                    return 0 ;;
                --null-handling)
                    COMPREPLY=( $(compgen -W "skip comment empty error" -- "$cur") )
                    return 0 ;;
                --list-merge)
                    COMPREPLY=( $(compgen -W "replace append merge" -- "$cur") )
                    return 0 ;;
                --indent)
                    COMPREPLY=( $(compgen -W "2 4 8" -- "$cur") )
                    return 0 ;;
                --sep)
                    COMPREPLY=( $(compgen -W ". __" -- "$cur") )
                    return 0 ;;
                --merge|--diff|--output-dir)
                    COMPREPLY=( $(compgen -f -- "$cur") )
                    return 0 ;;
                --port|--api-port|--get|--set|--delete|--count|--type|--pick|--grep|--append|\
                --each|--select|--default|--rename|--assert|--mask|--mask-value|--path-exists|\
                --backup|--sep|--indent|--replace-value|--wrap-in|--template|--csv-delimiter|\
                --has|--sort-by|--unique-by|--schema-gen)
                    return 0 ;;
            esac
            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "{_CF_FLAGS}" -- "$cur") )
            else
                COMPREPLY=( $(compgen -f -- "$cur") )
            fi
            ;;
        completion)
            COMPREPLY=( $(compgen -W "bash zsh fish" -- "$cur") )
            ;;
        "")
            COMPREPLY=( $(compgen -W "$subcommands --list -l --version -V --help" -- "$cur") )
            ;;
        *)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "--raw -r --pretty -p --help" -- "$cur") )
            fi
            ;;
    esac
}}

complete -F _devbench_complete devbench
"""

_ZSH_COMPLETION = f"""\
#compdef devbench
# devbench zsh completion
# Add to ~/.zshrc:
#   eval "$(devbench completion zsh)"
# Or source directly:
#   source <(devbench completion zsh)

_devbench() {{
    local state line
    typeset -A opt_args

    _arguments -C \\
        '--list[List all available tools]' \\
        '--version[Show version and exit]' \\
        '--help[Show help message]' \\
        '1:command:->command' \\
        '*::args:->args'

    case $state in
        command)
            local -a commands
            commands=(
                'detect:Auto-detect content type and apply tool'
                'json:Format and pretty-print JSON'
                'base64:Encode or decode base64'
                'jwt:Decode JWT tokens'
                'hash:Generate md5/sha256/sha512 hash'
                'url:Encode or decode URLs'
                'timestamp:Convert Unix timestamps to ISO 8601'
                'uuid:Generate UUIDs'
                'diff:Compare two texts side-by-side'
                'cf:Convert config files — yq/dasel alternative'
                'token:Count tokens with tiktoken'
                'chunk:Chunk text into token-limited segments'
                'list:List all available tools'
                'batch:Batch process multiple files'
                'license:License key management'
                'completion:Generate shell completion script'
            )
            _describe 'command' commands
            ;;
        args)
            case ${{line[1]}} in
                cf)
                    _arguments \\
                        '--to=[Output format]:format:({_CF_FORMATS})' \\
                        '--from=[Input format (auto-detect)]:format:({_CF_FORMATS})' \\
                        '--get=[Get value at dotted path]:path:' \\
                        '--default=[Fallback when --get path is missing]:value:' \\
                        '--select=[Filter list by FIELD=VALUE or FIELD!=VALUE condition]:expr:' \\
                        '--each=[Extract KEY from each list element]:key:' \\
                        '--join=[Join list items with DELIM separator]:delim:' \\
                        '--set=[Set value: --set PATH VALUE]:path value:' \\
                        '--append=[Append value: --append PATH VALUE]:path value:' \\
                        '--delete=[Delete value at path]:path:' \\
                        '--rename=[Rename key: OLD_PATH NEW_PATH]:old_path new_path:' \\
                        '--merge=[Merge overlay file]:file:_files' \\
                        '--list-merge=[List merge strategy]:mode:(replace append merge)' \\
                        '--diff=[Structural diff against file]:file:_files' \\
                        '--validate[Validate config is parseable]' \\
                        '--count=[Count items at path]:path:' \\
                        '--type=[JSON Schema type of value at path]:path:' \\
                        '--keys[List top-level config keys]' \\
                        '--recursive[Recursive glob / --keys]' \\
                        '-R[Recursive glob / --keys]' \\
                        '--pick=[Project fields]:path:' \\
                        '--grep=[Search config keys/values by regex]:pattern:' \\
                        '--grep-case-sensitive[Case-sensitive --grep]' \\
                        '--flatten[Flatten nested keys to dotted notation]' \\
                        '--unflatten[Expand dotted keys back to nested]' \\
                        '--sep=[Key separator (default .)]:sep:' \\
                        '--env-expand[Expand ${{VAR}} references]' \\
                        '--batch[Treat input as glob pattern]' \\
                        '--stream[Streaming batch mode (memory-efficient)]' \\
                        '--output-dir=[Output directory for batch]:dir:_directories' \\
                        '--sort-keys[Sort keys alphabetically]' \\
                        '--sort-keys-reverse[Sort keys in reverse alphabetical order]' \\
                        '--in-place[Edit file in-place]' \\
                        '-i[Edit file in-place]' \\
                        '--backup=[Backup suffix before in-place edit]:suffix:' \\
                        '--indent=[Indentation width]:width:(2 4 8)' \\
                        '--flatten-xml[Flatten nested XML to dotted keys]' \\
                        '--no-comments[Strip comments from output]' \\
                        '--yaml12[YAML 1.2 mode: only true/false are booleans]' \\
                        '--template-safe[Quote Jinja/Helm/Ansible template expressions]' \\
                        '--block-scalars[Force YAML block scalar (|) style for multiline strings]' \\
                        '--null-handling=[Null handling strategy]:mode:(skip comment empty error)' \\
                        '--list-formats[List all supported formats]' \\
                        '--check-env[Show environment info (Python, formats, deps)]' \\
                        '--schema=[JSON Schema file for validation]:schema:_files' \\
                        '--mask=[Regex pattern to redact matching key values]:pattern:' \\
                        '--mask-value=[Replacement text for masked values]:text:' \\
                        '--hash-field=[Regex pattern to hash matching key values]:pattern:' \\
                        '--hash-algorithm=[Hash algorithm for --hash-field]:algo:(md5 sha1 sha256 sha512 blake2b)' \\
                        '--assert=[Assert PATH=VALUE (exit 0=pass, 1=fail)]:assertion:' \\
                        '--path-exists=[Check if a path exists in the config]:path:' \\
                        '--has=[Check if a key path exists (exit 0=found, 1=missing)]:path:' \\
                        '--shell-export[Output as shell export KEY=VALUE statements]' \\
                        '--bash-arrays[Use bash declare -a syntax for array values with --shell-export]' \\
                        '--sort-by=[Sort list by a field value]:field:' \\
                        '--sort-desc[Reverse sort order for --sort-by (descending)]' \\
                        '--unique[Deduplicate list items]' \\
                        '--unique-by=[Deduplicate list of objects by a field]:field:' \\
                        '--compact[Compact/minified JSON output (no whitespace)]' \\
                        '-c[Compact/minified JSON output (no whitespace)]' \\
                        '--template=[Render template file using config as context]:template:_files' \\
                        '--wrap-in=[Wrap entire config under a dotted key path]:key:' \\
                        '--csv-delimiter=[Override CSV field delimiter (tab, pipe, semicolon)]:char:' \\
                        '--tsv[Treat input as tab-separated (TSV). Shorthand for --csv-delimiter TAB]' \\
                        '--schema-gen[Generate JSON Schema Draft 7 from config structure]' \\
                        '--replace-value=[Find and replace all matching values (OLD NEW)]:old new:' \\
                        '--serve[Launch the web UI]' \\
                        '--port=[Web UI port (default 8080)]:port:' \\
                        '--api[Launch JSON HTTP API]' \\
                        '--api-port=[API port (default 8081)]:port:' \\
                        '--raw[Machine-readable output]' \\
                        '-r[Machine-readable output]' \\
                        '*:file:_files'
                    ;;
                completion)
                    _arguments '1:shell:(bash zsh fish)'
                    ;;
            esac
            ;;
    esac
}}

_devbench "$@"
"""

_FISH_COMPLETION = f"""\
# devbench fish completion
# Install:
#   devbench completion fish > ~/.config/fish/completions/devbench.fish
# Or add to config.fish:
#   devbench completion fish | source

# Global options
complete -c devbench -n '__fish_use_subcommand' -l list -d 'List all tools'
complete -c devbench -n '__fish_use_subcommand' -l version -d 'Show version'
complete -c devbench -n '__fish_use_subcommand' -l help -d 'Show help'

# Subcommands
complete -c devbench -n '__fish_use_subcommand' -f -a detect    -d 'Auto-detect content type and apply tool'
complete -c devbench -n '__fish_use_subcommand' -f -a json      -d 'Format and pretty-print JSON'
complete -c devbench -n '__fish_use_subcommand' -f -a base64    -d 'Encode or decode base64'
complete -c devbench -n '__fish_use_subcommand' -f -a jwt       -d 'Decode JWT tokens'
complete -c devbench -n '__fish_use_subcommand' -f -a hash      -d 'Generate md5/sha256/sha512 hash'
complete -c devbench -n '__fish_use_subcommand' -f -a url       -d 'Encode or decode URLs'
complete -c devbench -n '__fish_use_subcommand' -f -a timestamp -d 'Convert Unix timestamps'
complete -c devbench -n '__fish_use_subcommand' -f -a uuid      -d 'Generate UUIDs'
complete -c devbench -n '__fish_use_subcommand' -f -a diff      -d 'Compare two texts'
complete -c devbench -n '__fish_use_subcommand' -f -a cf        -d 'Convert config files — yq/dasel alternative'
complete -c devbench -n '__fish_use_subcommand' -f -a token     -d 'Count tokens with tiktoken'
complete -c devbench -n '__fish_use_subcommand' -f -a chunk     -d 'Chunk text into token-limited segments'
complete -c devbench -n '__fish_use_subcommand' -f -a list      -d 'List all available tools'
complete -c devbench -n '__fish_use_subcommand' -f -a batch     -d 'Batch process multiple files'
complete -c devbench -n '__fish_use_subcommand' -f -a license   -d 'License key management'
complete -c devbench -n '__fish_use_subcommand' -f -a completion -d 'Generate shell completion script'

# Helper: detect when we are inside the cf subcommand
function __devbench_seen_cf
    set -l cmd (commandline -opc)
    contains -- cf $cmd
end

# cf: format options
set -l _db_formats {_CF_FORMATS}
complete -c devbench -n __devbench_seen_cf -l to   -d 'Output format' -r -f -a "$_db_formats"
complete -c devbench -n __devbench_seen_cf -l from -d 'Input format'  -r -f -a "$_db_formats"

# cf: CRUD flags
complete -c devbench -n __devbench_seen_cf -l get     -d 'Get value at dotted path'  -r
complete -c devbench -n __devbench_seen_cf -l default -d 'Fallback when --get path is missing'  -r
complete -c devbench -n __devbench_seen_cf -l set     -d 'Set value at dotted path'  -r
complete -c devbench -n __devbench_seen_cf -l append  -d 'Append value at path'      -r
complete -c devbench -n __devbench_seen_cf -l delete  -d 'Delete value at path'      -r
complete -c devbench -n __devbench_seen_cf -l rename  -d 'Rename key: OLD_PATH NEW_PATH'  -r
complete -c devbench -n __devbench_seen_cf -l merge   -d 'Merge overlay file'        -r -F
complete -c devbench -n __devbench_seen_cf -l list-merge -d 'List merge strategy'    -r -f -a 'replace append merge'
complete -c devbench -n __devbench_seen_cf -l diff    -d 'Structural diff vs file'   -r -F

# cf: query / search flags
complete -c devbench -n __devbench_seen_cf -l validate             -d 'Validate config is parseable'
complete -c devbench -n __devbench_seen_cf -l count                -d 'Count items at path'            -r
complete -c devbench -n __devbench_seen_cf -l type                 -d 'JSON Schema type of value at path'  -r
complete -c devbench -n __devbench_seen_cf -l keys                 -d 'List top-level config keys'
complete -c devbench -n __devbench_seen_cf -l recursive            -d 'Recursive glob / --keys'
complete -c devbench -n __devbench_seen_cf -s R                    -d 'Recursive glob / --keys'
complete -c devbench -n __devbench_seen_cf -l pick                 -d 'Project specific fields'         -r
complete -c devbench -n __devbench_seen_cf -l select               -d 'Filter list by FIELD=VALUE or FIELD!=VALUE'  -r
complete -c devbench -n __devbench_seen_cf -l each                 -d 'Extract KEY from each list element'  -r
complete -c devbench -n __devbench_seen_cf -l join                 -d 'Join list items with DELIM separator' -r
complete -c devbench -n __devbench_seen_cf -l grep                 -d 'Search keys/values by regex'     -r
complete -c devbench -n __devbench_seen_cf -l grep-case-sensitive  -d 'Case-sensitive --grep'

# cf: transform flags
complete -c devbench -n __devbench_seen_cf -l flatten          -d 'Flatten nested keys to dotted notation'
complete -c devbench -n __devbench_seen_cf -l unflatten        -d 'Expand dotted keys back to nested'
complete -c devbench -n __devbench_seen_cf -l sep              -d 'Key separator' -r -f -a '. __'
complete -c devbench -n __devbench_seen_cf -l env-expand       -d 'Expand ${{VAR}} env references'
complete -c devbench -n __devbench_seen_cf -l sort-keys        -d 'Sort keys alphabetically'
complete -c devbench -n __devbench_seen_cf -l sort-keys-reverse -d 'Sort keys in reverse alphabetical order'
complete -c devbench -n __devbench_seen_cf -l has              -d 'Check if key path exists (exit 0=found, 1=missing)'  -r
complete -c devbench -n __devbench_seen_cf -l sort-by          -d 'Sort list by a field value'  -r
complete -c devbench -n __devbench_seen_cf -l sort-desc        -d 'Reverse sort order for --sort-by (descending)'
complete -c devbench -n __devbench_seen_cf -l unique           -d 'Deduplicate list items'
complete -c devbench -n __devbench_seen_cf -l unique-by        -d 'Deduplicate object list by a field'  -r
complete -c devbench -n __devbench_seen_cf -l bash-arrays      -d 'Use bash declare -a syntax with --shell-export'

# cf: batch flags
complete -c devbench -n __devbench_seen_cf -l batch      -d 'Treat input as glob pattern'
complete -c devbench -n __devbench_seen_cf -l stream     -d 'Streaming batch mode (memory-efficient)'
complete -c devbench -n __devbench_seen_cf -l output-dir -d 'Output directory for batch'  -r -a '(__fish_complete_directories)'

# cf: output flags
complete -c devbench -n __devbench_seen_cf -l indent        -d 'Indentation width'    -r -f -a '2 4 8'
complete -c devbench -n __devbench_seen_cf -l flatten-xml   -d 'Flatten nested XML'
complete -c devbench -n __devbench_seen_cf -l no-comments   -d 'Strip comments'
complete -c devbench -n __devbench_seen_cf -l yaml12        -d 'YAML 1.2 (true/false only)'
complete -c devbench -n __devbench_seen_cf -l template-safe -d 'Quote Jinja/Helm/Ansible templates'
complete -c devbench -n __devbench_seen_cf -l block-scalars -d 'Force | block scalar style for multiline strings'
complete -c devbench -n __devbench_seen_cf -l null-handling -d 'Null handling mode'   -r -f -a 'skip comment empty error'

# cf: in-place edit
complete -c devbench -n __devbench_seen_cf -l in-place -d 'Edit file in-place'
complete -c devbench -n __devbench_seen_cf -s i        -d 'Edit file in-place'
complete -c devbench -n __devbench_seen_cf -l backup   -d 'Backup suffix before in-place edit'  -r

# cf: server / misc
complete -c devbench -n __devbench_seen_cf -l list-formats -d 'List all supported formats'
complete -c devbench -n __devbench_seen_cf -l check-env    -d 'Show environment info (Python, formats, deps)'
complete -c devbench -n __devbench_seen_cf -l schema       -d 'JSON Schema file for validation'  -r
complete -c devbench -n __devbench_seen_cf -l mask         -d 'Redact values for matching key names (regex)'  -r
complete -c devbench -n __devbench_seen_cf -l mask-value   -d 'Replacement text for masked values'  -r
complete -c devbench -n __devbench_seen_cf -l hash-field   -d 'Hash values for matching key names (regex)'  -r
complete -c devbench -n __devbench_seen_cf -l hash-algorithm -d 'Hash algorithm for --hash-field (sha256/md5/sha512/blake2b)'  -r
complete -c devbench -n __devbench_seen_cf -l assert       -d 'Assert PATH=VALUE (exit 0=pass, 1=fail)'  -r
complete -c devbench -n __devbench_seen_cf -l path-exists  -d 'Check if path exists in config (exit 0/1)'  -r
complete -c devbench -n __devbench_seen_cf -l shell-export -d 'Output as shell export KEY=VALUE statements'
complete -c devbench -n __devbench_seen_cf -l compact      -d 'Compact/minified JSON output (no whitespace)'
complete -c devbench -n __devbench_seen_cf -s c            -d 'Compact/minified JSON output (no whitespace)'
complete -c devbench -n __devbench_seen_cf -l template     -d 'Render template file using config as context'  -r -F
complete -c devbench -n __devbench_seen_cf -l wrap-in      -d 'Wrap config under a dotted key path'           -r
complete -c devbench -n __devbench_seen_cf -l csv-delimiter -d 'Override CSV field delimiter (\\t, |, ;)'       -r
complete -c devbench -n __devbench_seen_cf -l tsv          -d 'Treat input as tab-separated (TSV)'
complete -c devbench -n __devbench_seen_cf -l schema-gen   -d 'Generate JSON Schema Draft 7 from config structure'
complete -c devbench -n __devbench_seen_cf -l replace-value -d 'Find and replace all matching values (OLD NEW)'  -r
complete -c devbench -n __devbench_seen_cf -l serve        -d 'Launch the web UI'
complete -c devbench -n __devbench_seen_cf -l port         -d 'Web UI port (default 8080)'  -r
complete -c devbench -n __devbench_seen_cf -l api          -d 'Launch JSON HTTP API'
complete -c devbench -n __devbench_seen_cf -l api-port     -d 'API port (default 8081)'     -r
complete -c devbench -n __devbench_seen_cf -l raw          -d 'Machine-readable output'
complete -c devbench -n __devbench_seen_cf -s r            -d 'Machine-readable output'

# completion subcommand
function __devbench_seen_completion
    set -l cmd (commandline -opc)
    contains -- completion $cmd
end
complete -c devbench -n __devbench_seen_completion -f -a 'bash zsh fish' -d 'Shell type'
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def entry_point() -> NoReturn:
    """Console_scripts entry point."""
    sys.exit(main())


if __name__ == "__main__":
    sys.exit(main())