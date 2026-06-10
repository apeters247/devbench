# External Review — 2026-06-10 04:23 UTC

## Rotation: HN yq alternatives (minute 18)

## User Complaint Found

**Source**: codegenes.net — "How to Fix yq 2.12.0 In-Place Edit (-i) Flag Overwriting YAML Files"

**Complaint**: yq's `-i` (in-place) flag causes data loss. The tool truncates the original file first, then writes the new content. If the write fails mid-way (disk full, permission error, etc.), the original is gone. The article documents files being replaced with empty content after `yq -i '.app.version = "1.1.0"' config.yaml`.

## Fix Implemented

**File**: `core/cli.py` — `_cf_write_in_place()` (line ~1459)

**Before**: Used `file_path.write_text(output_text)` — opens file in write mode (truncates), then writes. Same race condition as yq.

**After**: Atomic write via `tempfile.mkstemp()` → write to sibling `.devbench.tmp` → `os.chmod()` to preserve permissions → `tmp_path.replace(file_path)` (atomic rename on POSIX). If write fails, the original file is never touched. Temp file is cleaned up on error.

**Tests added** (`tests/test_core.py`):
- `test_cf_in_place_atomic_no_tmp_file_left` — verifies no `.devbench.tmp` files left after successful write
- `test_cf_in_place_preserves_file_on_success` — verifies correct content after in-place edit

## Builder Code Review (HEAD~1)

Builder added: `--block-scalars`, `--length`, `--hash-field`, `--hash-algorithm`, 3 SEO pages, sitemap update.

**No bugs found.** Key observations:
- `_make_block_scalar_dumper()` correctly strips per-line trailing spaces before block scalar serialization (fixes yq#566)
- `hash_field_values()` correctly uses `usedforsecurity=False` for md5/sha1 to avoid FIPS-mode crashes
- `_run_cf_length()` correctly returns 0 for null, len() for str/list/dict, 1 for other scalars (matches jq semantics)
- `BlockScalarDumper` inherits from `yaml.Dumper` and overrides only the str representer — correct

## Test Suite

- **Before**: 1243 passed, 7 skipped, 2 xfailed
- **After**: 1245 passed, 7 skipped, 2 xfailed (+2 new tests)
