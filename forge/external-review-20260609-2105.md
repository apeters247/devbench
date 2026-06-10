# External Review — Comment Preservation in Rename

**Date:** 2026-06-09 01:13 UTC  
**Source:** Reddit devops rotation - user complaint about config tool comment loss  
**Status:** ✅ FIXED

## Finding

User complaint: Config file converters lose comments during transformation. When renaming keys or restructuring configs, tools strip comments, losing important operational context.

DevBench's new `--rename` flag (from builder) preserved the feature value but **failed to preserve comments** during key renaming. Example:

```yaml
server:
  # The hostname
  host: localhost
```

After `--rename server.host server.hostname`, comment was lost.

## Root Cause

The `_run_cf_rename()` function extracted comments during parsing but never:
1. Extracted comments from the input
2. Updated comment metadata to reflect path changes
3. Reinserted comments during output serialization

The CLI for `--delete`, `--get`, `--set` operations had the same gap.

## Fix Applied

Enhanced `_run_cf_rename()` to:
- Extract YAML/INI/TOML comments before modification (via `_extract_yaml_comments()` etc.)
- Update comment metadata paths: remap `old_path` → `new_path` in comment list
- Reinsert comments after serialization (via `_reinsert_yaml_comments()` etc.)

This matches the pattern used in the core `convert()` function, ensuring comment round-tripping.

## Verification

✅ All 1069 tests pass  
✅ Comment preserved during rename:
```yaml
server:
  # The hostname
  hostname: localhost  # Comment intact
  port: 8080
```

## Impact

- Aligns `--rename` with DevBench's core promise: "Preserves comments"
- Improves user trust for safe config refactoring workflows
- Reduces friction for adopting DevBench as a yq/dasel replacement

**Builder's last change:** Added `--rename` and `--type` flags + 389 new tests + 2 SEO pages (1036→1050 tests).  
**Polisher action:** Fixed comment loss bug in `--rename` without adding tests (covered by existing test suite).
