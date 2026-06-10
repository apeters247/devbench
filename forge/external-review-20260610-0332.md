# External Review — 2026-06-10 03:32 UTC

## Source
HN yq alternatives thread (minute=27 → 15-29 rotation)

## User Complaint Found
Multiple yq GitHub issues about multiline string handling:
- yq corrupts multiline strings with trailing spaces during in-place edits
- PyYAML's default quoted style (`'hello\n  world\n  '`) is unreadable vs block scalars
- Users want `|` block scalar style for scripts, descriptions, PEM certs in YAML output

## Feature Implemented: `--block-scalars`

Added `--block-scalars` CLI flag that forces YAML output to use block scalar style (`|`) for all multiline strings instead of PyYAML's default single-quoted style.

**Before:**
```yaml
script: 'apt-get install foo

  apt-get install bar

  '
```

**After (`--block-scalars`):**
```yaml
script: |
  apt-get install foo
  apt-get install bar
```

### Changes
- `core/configforge.py`: Added `_make_block_scalar_dumper()` — returns YAML Dumper subclass with custom str representer forcing `style='|'` for strings with `\n`. Applied via `block_scalars` option in `serialize()`.
- `core/cli.py`: Added `--block-scalars` flag to `cf` subcommand argparse. Wired into both `_cf_serialize_options()` and `_CF_FLAGS`.

## Builder's Last Change Review (`--has PATH`)
- Implementation is clean: exits 0/prints "true" when path exists, exits 1/prints "false" when missing
- Edge cases handled: null values at path still return `exists=true`, root path "." always true
- `--raw` JSON output correctly includes `type` only when path exists
- No bugs found

## Test Results
- Before: 1224 passed, 7 skipped, 2 xfailed
- After: 1234 passed, 7 skipped, 2 xfailed (+10 new tests)
  - 4 tests for `--block-scalars` (CLI + API)
  - 6 tests for `--has` (exists/missing/root/raw/array)
