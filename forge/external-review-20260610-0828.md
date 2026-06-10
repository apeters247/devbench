# External Review — 2026-06-10 08:28 UTC

## Rotation: HN yq alternatives (minute 19)

**Source complaint (HN thread 34661762):**  
"I love yq and jq, but imo the core feature they're missing is queryability... My dream is yq but with JSONata and an interactive editor — simple `where value = x` filtering without learning jq syntax."

---

## What Was Built

### Feature: `--select --count` composition
HN users want "how many pods match status=Running?" without piping to `wc -l`. Implemented `--select EXPR --count PATH` composition:

```bash
devbench cf pods.yaml --select status=Running --count .
# → 2
```

**Implementation:**
- `_run_cf_count()` now applies `--select` filter before counting when `select_expr` is set
- Moved `--count` dispatch above `--select` in `_main_dispatch` so both flags coexist
- Added test: `test_main_select_count_composition`

---

## Bugs Fixed (15 test failures → 0)

### Bug 1: `configforge.main()` exit code remapping
`core/configforge.py:3282` mapped all `rc != 0` → `return 2` with a "backward compat" comment, breaking 9 tests expecting exit code 1 for errors (missing key, malformed input, no matches, etc.).

**Fix:** Changed `return 2` to `return rc` (pass exit code through unchanged).

### Bug 2: `--raw` overrides `--to json` in `--each`
`configforge.main()` adds `--raw` when delegating to `cli.main()`. In `_run_cf_each`, `--raw` caused scalar values to be output one-per-line, ignoring explicit `--to json`. 4 tests were getting `JSONDecodeError` when parsing the output.

**Fix:** `core/cli.py:3515` — added `and getattr(args, "to", None) is None` guard so explicit `--to FORMAT` takes priority over `--raw` scalar output.

---

## Test Results
- Before: 15 failures (9 exit-code, 4 JSONDecodeError, 2 other)
- After: **1302 passed, 7 skipped, 2 xfailed**

## Builder Review (HEAD~1)
Builder added:
- `_apply_select_filter()` helper (refactored from `_run_cf_each`) — correct extraction, no bugs found
- Multi-key `--sort-by team,score` syntax — implemented and working
- Minor: removed unreachable `return EXIT_SUCCESS` after `finally` block in `main()` — correct

No issues found in builder's changes.
