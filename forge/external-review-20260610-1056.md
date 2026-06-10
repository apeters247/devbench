# External Review — 2026-06-10 10:56 UTC

## Rotation
Minute 51 → Reddit mac developer tool complaints

## User Complaint Found
**Source:** yq GitHub issue #2564 (Jan 2026)
**Complaint:** "Deep merge operators (*=, *+) fail to deduplicate keys, resulting in duplicate mapping entries. When merging a YAML file with itself or when overlay shares list items with base, yq produces duplicate values in the output."

## Feature Implemented: `--merge-dedupe-lists`

Added `--merge-dedupe-lists` flag to `devbench cf --merge` command. When combined with `--list-merge append`, it deduplicates list items after appending, preserving first occurrence.

**Example:**
```bash
# base.yaml: tags: [python, yaml]
# overlay.yaml: tags: [yaml, toml]
devbench cf base.yaml --merge overlay.yaml --list-merge append --merge-dedupe-lists
# Result: tags: [python, yaml, toml]  (no duplicate "yaml")

# Without flag (default behavior preserved):
devbench cf base.yaml --merge overlay.yaml --list-merge append
# Result: tags: [python, yaml, yaml, toml]
```

**Files changed:**
- `core/configforge.py`: Added `dedupe_lists` param to `_deep_merge()`, deduplicates when `list_mode="append"`
- `core/cli.py`: Added `--merge-dedupe-lists` arg, passes to `_deep_merge`, updated flag categories + zsh/fish completions
- `tests/test_configforge.py`: 3 new tests covering deduplication, no-flag behavior, self-merge scenario

## Test Fix: `test_batch_convert_progress`
The test was asserting `[1/2]` in `captured.out` but `batch_convert()` correctly writes progress to `sys.stderr`. Fixed assertions to check `captured.err`.

## Builder's Last Change Review
Reviewed `git diff HEAD~1 -- core/cli.py`. Builder added:
- `--explicit-start` / `--explicit-end` YAML markers (kislyuk/yq #93)
- `--yaml-width N` to prevent line wrapping (mikefarah/yq #452/#278)
- Stdin sentinel `-` for `_get_input()`
- `formats_status` changed from `bool` to `dict` with `access` field (`rw`/`r`)

No bugs found in the builder's changes. The `formats_status` dict change correctly updates the `sum()` call and `_run_cf_check_env` rendering.

## Test Results
- Before: 1 FAILED, 1343 passed, 7 skipped, 2 xfailed
- After:  **1347 passed, 7 skipped, 2 xfailed** (0 failures)
- New tests added: 3 (`test_merge_dedupe_lists_*`)
