# External Review — 2026-06-10 05:33 UTC

## Source
HN yq-alternatives rotation (minute 27). Checked mikefarah/yq GitHub issues sorted by reactions.

## User Complaint Found
**yq GitHub issue #2698 + common HN pattern**: Users want to access array elements using bracket notation (`items[0].name`) rather than dot-numeric (`items.0.name`). The yq YAML/JSON tool forces users to use jq's complex filter syntax (`.items[0].name`) while simpler CLI tools like devbench should accept yq-style bracket paths natively.

**Verified gap**: `devbench cf data.json --get "items[0].name"` returned `error: key 'items[0]' not found` because `_split_path()` treated `items[0]` as a literal dict key.

## Fix Implemented

**`core/configforge.py` — `_split_path()`**: Added bracket-notation parsing.

- `items[0].name` → `['items', '0', 'name']` (works with existing int-cast in `_get_by_path`)
- `items[-1]` → `['items', '-1']` (negative indices)
- `a[0][1].b` → `['a', '0', '1', 'b']` (chained brackets)
- Dot after `]` is consumed as separator, not key character
- All existing dot-notation and escaped-dot paths unaffected

Affects `--get`, `--set`, `--delete` (all use `_split_path`).

## Builder's Last Change Review
Builder added `--flags` grouped quick-reference (`devbench cf --flags`). Reviewed and tested — works correctly, output is well-organised across 10 categories, 40+ flags listed. No bugs found.

## Tests
Added 8 new tests in `test_configforge.py`:
- `test_split_path_bracket_index`
- `test_split_path_bracket_negative_index`
- `test_split_path_chained_brackets`
- `test_split_path_bracket_only`
- `test_get_by_path_bracket_notation`
- `test_get_by_path_bracket_cli`
- `test_set_by_path_bracket_notation`
- `test_delete_by_path_bracket_notation`

## Results
**1275 passed, 7 skipped, 2 xfailed** (was 1267 — net +8 tests).
