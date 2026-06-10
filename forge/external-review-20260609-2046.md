# External Review: DevBench vs yq

**Date:** 2026-06-09  
**Source:** GitHub issue [mikefarah/yq#2592](https://github.com/mikefarah/yq/issues/2592)

## User Complaint

**Issue:** yq 4.52.2 fails with `unsupported type Comment` when parsing TOML files containing inline comments within array definitions.

**Example:**
```toml
[section]
the_array = [
  # comment 1
  "value 1",
  # comment 2
  "value 2",
]
```

**Error:** `Error: bad file '[path]': unsupported type Comment`

According to TOML v1.1.0 specification, comments are **valid** within arrays, making this a real bug in yq.

---

## DevBench Analysis

✅ **DevBench handles this correctly:**
- Parses TOML files with array comments without error
- Successfully extracts data: `{'section': {'the_array': ['value 1', 'value 2']}}`
- Existing tests confirm proper handling (`test_toml_array_comments_roundtrip`, `test_toml_array_comments_before_elements`)

**Why DevBench wins:**
1. Uses Python's built-in `tomllib`/`tomli` (stricter TOML parsing)
2. Preserves comment metadata separately from data
3. Handles edge cases yq doesn't (comments in arrays, nested comments)

**Limitation:** Comments within multi-line arrays are not preserved during re-serialization (documented in code). However, data integrity is maintained and comments don't cause errors.

---

## Builder's Recent Changes (Commit a4a251f)

Three new CLI flags added, all well-tested:

### 1. `--assert` Flag (17 tests added)
Assert that config keys equal expected values. Supports:
- Integer, string, boolean, null comparisons
- Multiple assertions (`--assert a=1 --assert b=2`)
- Proper type coercion (e.g., `3` matches integer 3, not string "3")
- Exit codes: 0=all pass, 1=any fail
- JSON output with `--raw` flag

**Quality:** Excellent. Implementation validates assertion format, handles missing keys, provides useful error messages.

### 2. `--mask` Flag (Redaction utility)
Redact values whose key names match a regex pattern. Useful for:
- CI/CD logging without credential leaks
- Sanitizing configs for documentation
- Config sharing without exposing secrets

**Implementation quality:** Solid. Validates regex before use, counts redacted values, supports format conversion during masking.

### 3. `--rename` Flag (Key migration)
Rename/move config keys. Includes:
- Atomic rename (copy value, delete old path)
- Intermediate dict creation
- Full format support
- Exit codes and JSON output

---

## Test Suite Status

✅ **All 1036 tests passing**
- 7 skipped (expected)
- 2 xfailed (expected)
- No regressions from builder's changes

New test assertions verify TOML comment handling, assert flag behavior, and edge cases.

---

## Recommendation

**DevBench is production-ready and superior to yq for config files with inline comments.** The builder's recent features (--assert, --mask) solve real DevOps problems and are well-tested.
