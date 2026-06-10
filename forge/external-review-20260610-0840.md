# External Review — 2026-06-10 08:40 UTC

## Source
yq GitHub Issues rotation (minute 36 = 30-44 bucket)
Issue: mikefarah/yq#2456 — "Expose INI quote-preservation and related parser options"

## User Complaint
> "When round-tripping an INI file with -p=ini -o=ini, quoted values like
> `color_theme = "Default"` are written back as `color_theme = Default`
> (quotes removed). This breaks tools that ship configs with quoted strings."

## Bug Found in DevBench
`_ini_format_value_quoted` in `configforge.py` was **double-quoting** values that
`configparser` had already preserved with surrounding double-quotes. For example:

Input:  `theme = "Default"`
Before fix: `theme = "\"Default\""` (double-wrapped) ← BUG
After fix:  `theme = "Default"` (clean round-trip) ← CORRECT

**Root cause**: ConfigParser preserves `"Default"` as the literal value string
`"Default"` (with quote chars). `_ini_format_value_quoted` then escaped those
inner quotes and wrapped in outer quotes, producing `"\"Default\""`.

## Fix Applied
`core/configforge.py`: `_ini_format_value_quoted()` now strips one layer of
surrounding double-quotes from the string before re-quoting, preventing the
double-wrap on round-trips while still adding quotes to bare values.

## Code Review: Builder's Last Commit
Builder commit: `10d7df0` — yaml-to-toml SEO page + 6 dispatch ordering tests (1307 tests)

Changes reviewed in `core/cli.py`:
- **`--count --select` composition**: Moved `--count` dispatch before `--select`
  in `_main_dispatch`. `_run_cf_count` now applies `--select` filter before
  counting. Correct ordering, no issues.
- **`--select` regex support** (`FIELD=/pattern/`): Correctly implemented with
  case-insensitive matching. Error path for bad regex returns `[]` and prints
  to stderr. Solid.
- **Unrecognised `--select` expression**: Changed from silently returning
  unmodified data to printing error + returning `[]`. Better UX.
- **`--each --raw` fix**: Only outputs raw scalar when `--to` is not explicitly
  set. Correct edge case handling.
- **`--sort-by` multi-field sort**: Comma-separated fields work correctly via
  tuple key. `--unique`/`--unique-by` applied before sort. Correct.

No bugs found in builder's changes.

## Tests Added (6 new tests, 1313 total)
- `test_ini_quote_strings_bare_values` — bare values get quoted with flag
- `test_ini_quote_strings_already_quoted_round_trip` — pre-quoted values don't double-wrap
- `test_ini_quote_strings_numerics_not_quoted` — numbers/booleans stay unquoted
- `test_select_regex_match` — `FIELD=/pattern/` keeps matching items
- `test_select_regex_not_match` — `FIELD!=/pattern/` excludes matching items
- `test_select_regex_case_insensitive` — regex matching is case-insensitive

## Test Results
1313 passed, 7 skipped, 2 xfailed — all green
