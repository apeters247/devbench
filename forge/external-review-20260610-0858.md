# External Review — 2026-06-10 08:58 UTC

## Rotation
45–59 min → Reddit mac developer tool complaints

## User Complaint Found
**Source:** yq GitHub issue #2201 — "Merge new fields only is missing comments"

> User wants to merge a defaults/template config onto a live config file, but only
> add keys that don't exist yet — without overwriting values users have already set.
> Plain `yq . * defaults.yaml live.yaml` merges but always lets the overlay win on
> scalar values. Comments are also lost in the process.

This maps directly to a pain point with `devbench cf --merge`: overlay scalars always
win, so users cannot safely populate default keys without clobbering existing config.

## What Was Built
**Feature: `--merge-new-only` flag**

Added to `devbench cf --merge` to address the "populate defaults without overwriting"
use case from yq issue #2201.

### Behavior
- `--merge-new-only`: only add keys absent from the base; never overwrite existing
  scalar values. Recursion still descends into nested dicts to find missing sub-keys.
- Composes with `--list-merge` and `--in-place` as expected.
- Works cross-format (YAML base + JSON overlay, etc.).

### Files Changed
- `core/configforge.py`: `_deep_merge()` gains `new_only: bool = False` parameter.
  When `True`, existing scalars in base are never replaced; nested dict recursion
  still happens to discover missing sub-keys.
- `core/cli.py`: `--merge-new-only` argument added; wired to `_run_cf_merge()`.
- `tests/test_configforge.py`: 3 new tests added.

### Example
```bash
# base.yaml: host: localhost, port: 5432
# defaults.yaml: host: db.prod, port: 9999, timeout: 30
devbench cf base.yaml --merge defaults.yaml --merge-new-only
# → host: localhost (preserved), port: 5432 (preserved), timeout: 30 (added)
```

## Code Review: Builder's Last Change (ace44d7)
**`fix: --select + --sort-by / --unique now compose correctly`**

- Dispatch ordering fix: `--select` now evaluated before `--sort-by` / `--unique` so
  filter → sort and filter → dedup both compose correctly.
- `_apply_select_filter()` helper: operator precedence is correct (`!~` before `~`,
  `!=` before `=`). Regex detection guard (`len(raw_val) >= 2`) handles edge cases.
- `--count + --select` composition also fixed in `_run_cf_count`.
- **No bugs found.** Code is correct.

## Test Results
- Before: 1322 passed, 7 skipped, 2 xfailed
- After:  1325 passed, 7 skipped, 2 xfailed (+3 new tests)
