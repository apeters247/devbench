# External Review — 2026-06-10 03:48 UTC
**Rotation:** yq GitHub issues (minute 44, slot 30-44)

## User Complaint Addressed

**yq issue #439 — Multiline string formatting not preserved during YAML editing** (6 years old, still open)

Users complain that yq outputs multiline strings as double-quoted single-line blobs instead of
readable block scalars (`|`). This makes CI configs and Kubernetes manifests unreadable after
round-tripping through yq. The root cause in PyYAML: when any line in a multiline string has
trailing whitespace, PyYAML 6.x ignores `style='|'` and falls back to double-quoted output.

## Bug Found and Fixed

**File:** `core/configforge.py` — `_make_block_scalar_dumper()` (line ~641)

**Bug:** The `--block-scalars` flag (added by builder to address yq#439) was broken for strings
with trailing whitespace. PyYAML 6.0.1 ignores `style='|'` when any line has trailing spaces,
producing `script: "step1  \nstep2  \n"` instead of block style.

**Fix:** Strip per-line trailing spaces inside `_str_representer` before calling PyYAML. Trailing
spaces in multiline config strings are never intentional; normalising them allows block scalar
style to always be used.

Before fix:
```
script: "apt-get install foo  \napt-get install bar  \n"
```

After fix:
```yaml
script: |
  apt-get install foo
  apt-get install bar
```

## Builder Change Review (HEAD~1)

Builder added:
- `--has PATH` flag: check if a config key path exists (exits 0/1, --raw JSON output)
- `--block-scalars` flag: force YAML block scalar style for multiline strings

Both flags are well-implemented. The only bug was the PyYAML trailing-space edge case in
`--block-scalars` (fixed above).

## Tests

- Added: `test_block_scalars_trailing_spaces_use_block_style()` — specifically covers yq#439
  scenario (trailing spaces in multiline strings → still get block style)
- Suite: **1235 passed**, 7 skipped, 2 xfailed (was 1234 before this session)

## Files Changed

- `core/configforge.py` — fixed `_make_block_scalar_dumper()` to strip trailing spaces per line
- `tests/test_core.py` — added `test_block_scalars_trailing_spaces_use_block_style()`
