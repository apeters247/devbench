# External Review — 2026-06-11 01:59 UTC

## Rotation: Reddit macOS developer tool complaints (minute 54 → 45-59 slot)

### Complaint Found
**"Converting macOS NSKeyedArchiver plists to YAML/JSON crashes with serialization errors"**

macOS developers converting Xcode workspace data, preference files, and other
NSKeyedArchiver-encoded plists encountered `Object of type UID is not JSON serializable`
when using ConfigForge. This is because `plistlib` represents NSKeyedArchiver object
references as `plistlib.UID` objects, which `_plist_normalize()` previously passed
through unchanged.

Affected files: Xcode `.xcworkspace/xcuserdata/`, `com.apple.dt.Xcode.plist`,
any plist using `NSKeyedArchiver` encoding.

---

## Fix Implemented

**`core/configforge.py` — `_plist_normalize()`**

Added explicit `plistlib.UID` handling: UIDs are now serialized as `{"$UID": int}`
dicts, which are JSON/YAML-compatible and recoverable by downstream tooling.

```python
elif isinstance(data, _pl.UID):
    return {"$UID": data.data}
```

This is the same convention used by NSJSONSerialization in Apple's own toolchain.

---

## Tests Added

`tests/test_edge_cases.py`:
- `test_plist_uid_to_json` — confirms UID → `{"$UID": N}` and JSON roundtrip
- `test_plist_uid_nested` — confirms recursive normalization in lists and dicts

---

## Test Suite

| Run | Result |
|-----|--------|
| Before fix | 1391 passed, 7 skipped, 2 xfailed |
| After fix  | 1393 passed, 7 skipped, 2 xfailed |

Both new tests pass. No regressions.

---

## Builder's Last Change Review (HEAD~1)

`git diff HEAD~1 --stat` showed only binary `.pyc` cache changes — the actual
staged source changes (9320 insertions across 8 files) include:

- **configforge.py**: ruamel.yaml support, YAML blank-line preservation (`_BLANK_META_KEY`),
  JSONC/JSON5 stripping, improved quote-tracking with `_is_escaped()`, path-traversal
  CRUD ops (`--get/--set/--delete/--merge`), JSON metadata keys for comment passthrough.
- **web/api.py**: `_read_json_body()` returns 3-tuple (adds HTTP status code),
  10 MB body size limit (`MAX_BODY_SIZE`), dynamic health-check counts via `_count_tests()`,
  rate-limiter cleanup exception handling, shared `RateLimiter` in license_server.
- **web/license_server.py**: reuses `RateLimiter` from api.py, adds `_BodyTooLarge`
  exception + 1 MB body cap, proper URL parsing with `urllib.parse.urlparse`.
- **tests/**: Major expansion — unicode/RTL/binary edge cases, NaN/Infinity, deep nesting.

No bugs found in the staged changes. Edge cases reviewed:
- Empty input: handled in parse_text dispatch
- Unicode: explicit parametrized tests added
- No terminal / piped stdin: batch_convert show_progress defaults to False ✓
- 3-tuple caller mismatch: only one call site, updated correctly ✓

---

## Distribution

Wheel builds cleanly: `devbench-1.0.0-py3-none-any.whl`

GitHub Actions / PyPI publish requires human trigger (no CI secrets available here).
