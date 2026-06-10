# External Review — 2026-06-10 14:43 UTC

## Source
yq GitHub issue #2456 — "Expose INI quote-preservation and related parser options"
URL: https://github.com/mikefarah/yq/issues/2456

## User Complaint
When INI files contain quoted string values (`color_theme = "Default"`), yq strips
the quotes during round-trip. The user wants the quoting convention preserved so
downstream tools that depend on quoted values continue to work.

## Analysis
In devbench, Python's `configparser` treats surrounding double-quotes as literal
characters, so `color_theme = "Default"` is parsed as the string `'"Default"'`
(with quotes included). This means:
- INI → INI round-trip already preserves quotes ✅
- INI → YAML/JSON shows ugly literal quote chars: `color_theme: '"Default"'` ❌
- Users converting INI to other formats get confusing output

The existing `--ini-quote-strings` flag adds quotes to ALL strings on output, but
doesn't address the parse-time quote handling.

## What Was Built
**New `--ini-strip-quotes` flag** (`core/configforge.py`, `core/cli.py`):
- Strips surrounding double-quotes from INI values during parse
- Only strips values fully wrapped in double-quotes (`"Default"` → `Default`)
- Partial quotes like `say "hello"` are left intact
- After stripping, `_infer_type` runs normally (so `"1.0"` → `1.0` float)
- Makes INI → YAML/JSON cross-format conversion clean and human-readable

```bash
# Before (literal quotes in output):
devbench cf config.ini -t yaml
# color_theme: '"Default"'

# After with new flag:
devbench cf config.ini -t yaml --ini-strip-quotes
# color_theme: Default
```

## Tests Added
4 new tests in `tests/test_configforge.py` (lines ~3123–3160):
- `test_ini_strip_quotes_basic` — strips quotes in YAML output
- `test_ini_strip_quotes_json_output` — clean JSON, numerics inferred properly
- `test_ini_strip_quotes_only_full_quotes` — partial quotes not stripped
- `test_ini_strip_quotes_off_by_default` — default behavior unchanged

## Builder's Last Change Review (HEAD~1)
`git diff HEAD~1 --stat` showed massive build/lib sync + core/cli.py (+74 lines),
core/configforge.py (+10 lines), core/tools.py (+286 lines), tests (+330 lines).
Main changes: blank-line/comment preservation fixes for `--set/--append/--delete`.
No edge-case issues found — unicode, empty input, piped stdin all handled by
existing branch guards in the yq#1248 fix.

## Test Results
- Before: 1395 passed, 7 skipped, 2 xfailed
- After: 1399 passed, 7 skipped, 2 xfailed (+4 new tests, all green)

## Distribution
Wheel builds cleanly: `devbench-1.0.0-py3-none-any.whl`
