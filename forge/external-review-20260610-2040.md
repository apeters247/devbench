# External Review — 2026-06-10 20:40 UTC

## Source
yq GitHub issue #2452 (rotation: 30–44 min → yq issues 2440–2460)

**Complaint**: `sort_keys(..)` on YAML files containing ICU Message Format plural
translations (`{count, plural, one {# year} other {# years}}`) injects a spurious
blank line inside the string value, breaking CI pipelines that diff translation files.
User was on yq v4.47.1 / macOS / Homebrew.

## What Was Built

Added regression test `test_sort_keys_icu_plural_no_blank_lines` in
`tests/test_configforge.py` (after line 1928) that:

1. Exercises `convert(yaml_in, "yaml", "yaml", sort_keys=True)` on a YAML file with
   three ICU plural translation keys.
2. Asserts keys are sorted alphabetically.
3. Asserts `"\n\n"` does not appear in the output (no spurious blank lines).
4. Asserts each ICU plural string is preserved verbatim through the round-trip.

Our tool was already clean — no blank line bug — so this is a pure guard test.

## Builder Change Review (HEAD~1)

`core/cli.py` changes:
- Added `-o` short alias for `--to` (output format) ✓
- Added `-f` short alias for `--from` (input format) ✓
- Added `command_hint` param to `_check_port_available` — contextualises the
  port-conflict error to "cf --serve", "cf --api", or "license server" ✓

Edge-case check:
- Empty input: argparse requires an argument for `-f`/`-o`, correct behaviour
- Unicode flags: unaffected, purely CLI parsing
- Piped stdin: unaffected
- `"license server"` hint: correct, `devbench license server --port N` is the
  valid subcommand

No bugs found in builder change.

## Test Results
- Before: 1375 passed, 7 skipped, 2 xfailed
- After:  1376 passed, 7 skipped, 2 xfailed (+1 new test)

## Wheel Build
Successfully built `devbench-1.0.0-py3-none-any.whl`
