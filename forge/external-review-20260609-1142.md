# External Review — 2026-06-09T11:42Z
**Rotation:** yq GitHub issues (minute 34)
**Source complaint:** yq GitHub — users of yq and alternatives consistently request backup-on-in-place-edit; opening files for in-place modification without a safety net leads to data loss when scripts go wrong. Common ask: `yq -i.bak` behavior (BSD sed semantics: `--in-place <suffix>` creates a backup before overwriting).

## Feature Implemented: `--backup` flag for `--in-place` operations

### Problem
`devbench cf file.yaml --set key val --in-place` had no safety net — if the conversion fails mid-write or the user made an error, the original is gone. yq GitHub issues consistently request backup-before-overwrite for in-place edits.

### Solution
Added `--backup [SUFFIX]` flag to `devbench cf`:
- Default suffix `.bak`: `devbench cf file.yaml --set key val --in-place --backup` → creates `file.yaml.bak` before overwriting
- Custom suffix: `--backup .orig` → `file.yaml.orig`
- Works with all four in-place operations: `--set`, `--append`, `--delete`, `--merge`
- Uses `shutil.copy2` (preserves metadata/timestamps)
- If backup creation fails (e.g. disk full), exits with error before modifying the original

### Code changes
- `core/cli.py`: Added `--backup SUFFIX` arg (nargs="?", const=".bak") to `cf` subparser
- `core/cli.py`: New `_cf_write_in_place(file_path, output_text, backup_suffix)` helper
- `core/cli.py`: All 4 CRUD in-place write sites updated to use helper (lines ~1105, ~1147, ~1188, ~1240)
- `tests/test_core.py`: 4 new tests covering `.bak` default, custom `.orig` suffix, `--delete` op, and "no backup without flag"

## Builder's Last Change Review: `--diff` (cross-format structural config comparison)

**Commit:** 68d34cd — `builder: --diff flag for cross-format structural config comparison (803→814)`

### Review findings
- `_flatten_for_diff()`: Correctly handles nested dicts, lists (with `[idx]` notation), and dot-escape for keys containing dots. No issues found.
- `_run_cf_diff()`: Reads both files, parses independently (correctly using `from_fmt` only for file A, auto-detect for file B), diffs flattened maps. Clean.
- Edge case tested: YAML `ratio: 1.0` vs JSON `"ratio": 1.0` → both parse to Python float 1.0, correctly reported as `identical`. No false positives from numeric type coercion.
- Exit semantics: 0 = identical, 1 = differences — correct for CI pipeline use.
- `--raw` output: returns structured JSON with `{identical, formats, added, removed, changed}` — suitable for programmatic use.
- **One minor note**: when both files have identical content but different formats (e.g. YAML vs JSON), the output correctly says "identical" but doesn't report the format names. This is acceptable behavior — the `--raw` output does include `formats`.

**Verdict: No bugs. The --diff implementation is correct and production-ready.**

## Test Suite
- Before: 826 passed, 7 skipped, 2 xfailed
- After: **837 passed, 7 skipped, 2 xfailed** (+11: 4 backup tests + 7 validate/count tests from previous session already in tree)
- All gates green.
