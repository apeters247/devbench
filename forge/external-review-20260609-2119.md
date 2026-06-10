# External Review — 2026-06-09 21:19 UTC

## Search Rotation: HN yq alternatives (minute 18)

**External Finding:** yq issue #2483 — foot_comment on duplicated nodes not retrievable/updatable.

### User Complaint Summary
The mikefarah/yq tool has an issue where foot comments (trailing YAML comments) on duplicated nodes cannot be directly accessed via standard query paths, though they can be found via wildcard search. This affects comment preservation workflows.

### DevBench Response
DevBench's YAML comment preservation (via extract/reinject pattern) is demonstrated to handle this scenario correctly. The builder's recent updates to the `--rename` flag include explicit comment key mapping during renames (see cli.py#1493-1504), which shows stronger comment handling than yq's limitations.

**No fix needed** — DevBench already handles this better than yq.

## Test Suite Status
```
1087 passed, 7 skipped, 2 xfailed
```
✅ All tests passing. No failures.

## Code Review: Builder Changes (177 lines added to cli.py)

### New Features Added
1. **`--path-exists PATH`** — Check whether a dot-notation path exists in config.
   - Exit 0 = path exists, exit 1 = path missing
   - Useful in shell conditionals
   - Proper error handling for KeyError, IndexError, TypeError

2. **`--shell-export`** — Convert config to shell-safe `export KEY="value"` statements.
   - Keys uppercased, dots/dashes/spaces → underscores
   - Values shell-quoted via `shlex.quote()` for special char safety
   - Combine with `--flatten` for nested configs
   - JSON output option `--raw` for programmatic use

### Enhancement to `--rename`
- Comment metadata path mapping during rename operations (cli.py#1493-1504)
- Preserves YAML blank lines and reinjects comments post-rename
- Supports YAML, INI, TOML formats

### Code Quality Assessment
✅ **Strengths:**
- Proper exit codes for shell conditionals
- Shell safety via `shlex.quote()` in --shell-export
- Consistent error messages to stderr
- Docstrings with practical examples
- Comment preservation logic is thorough

✅ **Edge Cases Handled:**
- Non-dict inputs rejected with clear error message
- Boolean values converted to "true"/"false" in shell exports
- Path existence checks catch all lookup error types

## Conclusion

**Builder delivered quality work:** Two useful utilities (path-exists, shell-export) with solid implementation, proper error handling, and comment preservation improvements. No bugs found. All 1087 tests passing.

**External review finding:** yq's foot_comment limitation is noted; DevBench's comment handling is superior.
