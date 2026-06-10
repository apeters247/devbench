# External Review — 2026-06-10 09:48 UTC

**Rotation:** 30-44 → yq GitHub issues
**Source:** mikefarah/yq issues #452, #278, #142, #426 — long-line wrapping in YAML output

## Complaint Found

Multiple yq issues report that yq silently wraps long YAML scalar values at 80 characters by default. This corrupts:
- Long URLs (split mid-URL)
- Base64 blobs
- Connection strings
- Any scalar > 80 chars

Users worked around it with `-w/--width` in mikefarah/yq but kislyuk/yq and devbench had no equivalent.

## Fix Implemented

Added `--yaml-width N` flag to devbench:
- `--yaml-width 0` → no wrapping (maps 0 → `sys.maxsize` for PyYAML)
- `--yaml-width N` → explicit max column width
- Default unchanged: PyYAML's 80 (backwards-compatible)

### Files Changed
- `core/cli.py`: Added `--yaml-width` argument, passthrough in `_run_cf()`, flag categories, `_CF_FLAGS` string, zsh + fish completions
- `core/configforge.py`: `serialize()` picks up `yaml_width` option, passes as `width` to `yaml.dump()`/`yaml.dump_all()`

### Tests Added (4)
- `test_yaml_width_zero_prevents_line_wrapping` — 200-char URL stays on one line
- `test_yaml_width_default_wraps_long_scalars` — default behavior preserved
- `test_yaml_width_via_cli` — end-to-end CLI test with long registry URL
- `test_yaml_width_custom_value` — explicit 120-char width via CLI

## Builder's Last Change Review

Builder added `--explicit-start` / `--explicit-end` (fixes kislyuk/yq#93 where yq strips `---` from Kubernetes manifests). Clean implementation: option → CLI → serialize → yaml.dump kwargs. No issues found.

Also cleaned up a misplaced `import copy` (moved to top-level imports). 

## Test Results

- Before: 1328 passed, 7 skipped, 2 xfailed
- After: **1332 passed, 7 skipped, 2 xfailed** (+4 new tests, 0 failures)
