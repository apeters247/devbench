# Polisher External Review — 2026-06-09 11:23Z

## Rotation
Minute 17 → HN yq alternatives (15-29 range)

## Source Complaint
**HN / yq v4 verbosity** — Users on Hacker News and yq issue threads complain that
appending to an array in yq v4 requires a full sub-expression (`.key += ["value"]`),
whereas yq v2 had simpler syntax.  The request: tools in this space should offer a
first-class `--append PATH VALUE` flag so scripts stay readable without jq-style
sub-expressions.

## What Was Built

### 1. `--append PATH VALUE` (core feature)

**`core/configforge.py` — `_append_to_path(data, path, value)`**
- Appends `value` to the list at `path` in a nested dict/list
- Creates a single-element list if the key is absent (ergonomic zero-to-one case)
- Raises `KeyError` with a meaningful message if the target is a non-list scalar
- Traverses nested dicts via dot-notation (same as `_get_by_path` / `_set_by_path`)

**`configforge.py` main()** — Added `--append PATH VALUE` argument and handler block
mirroring the `--set` handler pattern (parse, mutate, serialize, optional `--in-place`).

**`core/cli.py` — `_run_cf_append(args)`**
- Added `--append PATH VALUE` argument to the `cf` subcommand parser
- Added dispatch in `main()` routing (`if args.command == "cf" and getattr(args, "append_kv", None)`)
- Full handler parallel to `_run_cf_set`: read → parse → append → serialize → write/stdout

### 2. YAML format-detection bugfix (discovered during testing)

**`detect_format()` in `configforge.py` line ~1239**

The YAML detection regex was `r"^[\w\-\"]+:\s"` — requiring a space after the colon.
YAML keys whose value lives on the next line (lists, nested dicts) end with just `key:`
(no trailing space), so `detect_format("servers:\n  - alpha\n  - beta\n")` returned
`"unknown"`. This caused `--append`, `--set`, and `--get` to all fail silently on any
YAML file whose top-level keys map to lists or dicts.

Fix: changed regex to `r"^[\w\-\"]+:(?:\s|$)"` — matches both `key: value` and
`key:` (colon at end of line / before newline).

## Tests

11 new tests in `tests/test_configforge.py`:

| Test | What it checks |
|------|---------------|
| `test_append_to_path_existing_list` | Appends to an existing list |
| `test_append_to_path_creates_list_when_key_missing` | Creates new list for absent key |
| `test_append_to_path_nested_key` | Traverses nested dicts before appending |
| `test_append_to_path_non_list_raises` | Raises KeyError on non-list target |
| `test_append_to_path_json_value` | Appends numeric value correctly |
| `test_append_cli_yaml` | End-to-end: YAML list append via configforge main() |
| `test_append_cli_creates_new_list` | End-to-end: absent key becomes `["release"]` |
| `test_append_cli_in_place` | `--in-place` writes modified YAML to disk |
| `test_append_cli_json_value` | `"9090"` is coerced to integer 9090 before append |
| `test_append_cli_non_list_error` | Non-zero exit + stderr message on scalar target |
| `test_append_cli_json_format` | JSON input/output round-trip works |

## Test Results
- Before: 792 passed, 7 skipped, 2 xfailed
- After:  803 passed, 7 skipped, 2 xfailed
- **+11 new tests, 0 regressions**
