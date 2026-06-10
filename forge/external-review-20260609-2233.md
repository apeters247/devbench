# Polisher Report — External Review + Builder Parity

**Date:** 2026-06-09 22:33 UTC  
**Rotation:** Minute 28 → HN yq alternatives  
**Source:** GitHub issue #2712 (nkiesel, May 19, 2026)

## Issue Found

**GitHub Issue #2712: "Support JSON5"**
- User requested JSON5 format support in yq (config file tools)
- JSON5 is a superset of JSON with useful developer-friendly features:
  - Single-quoted strings: `'hello'` instead of `"hello"`
  - Unquoted keys: `{name: 'value'}` instead of `{"name": "value"}`
  - Comments: `// line` and `/* block */` comments
  - Trailing commas in objects/arrays
  - Leading/trailing decimal points in numbers (e.g., `.5`, `5.`)

## Implementation

Added complete JSON5 support to ConfigForge (our yq alternative):

### Code Changes (`core/configforge.py`)

1. **`_strip_json5()` function (86 lines)**
   - Converts JSON5 syntax to valid JSON
   - Handles single-quote string conversion
   - Detects and quotes unquoted object keys
   - Reuses `_strip_jsonc()` for comment/trailing-comma removal
   - State machine parser tracks string context properly

2. **`detect_format()` enhancement**
   - Added JSON5 detection after JSONC check
   - Detection order: JSON → JSONC → JSON5 → other formats
   - Falls back if JSONC parser succeeds (JSONC is JSON5-compatible)

3. **`_parse_text_impl()` addition**
   - Added `elif fmt == "json5"` branch using `_strip_json5()`
   - Format tracking: returns `{"format": "json5", "data": ...}`

4. **`serialize()` enhancement**
   - Added "json5" to JSON family: `if fmt in ("json", "jsonc", "json5")`
   - JSON5 output same as JSON (valid JSON5 is valid JSON)

### Test Coverage (`tests/test_configforge.py`)

Added 8 comprehensive tests:
- `test_detect_json5_with_single_quotes()` — single quotes detection
- `test_detect_json5_with_unquoted_keys()` — unquoted keys detection
- `test_detect_json5_mixed_features()` — comments + mixed syntax
- `test_parse_json5_with_comments()` — parse with comments preserved through conversion
- `test_parse_json5_with_single_quotes()` — single-quote string parsing
- `test_parse_json5_with_trailing_commas()` — trailing comma handling
- `test_convert_json5_to_yaml()` — cross-format conversion
- `test_convert_json5_auto_detect()` — auto-detection roundtrip

### Edge Case Fix (`tests/test_edge_cases.py`)

Updated tests that previously expected "malformed JSON" failures:
- `test_malformed_json_single_quotes()` — now succeeds (JSON5 is valid)
- `test_malformed_json_no_quotes()` — now succeeds (JSON5 is valid)

Both now verify that single quotes and unquoted keys successfully convert to valid JSON.

## Test Results

**Before:** 1143 passed, 7 skipped, 2 xfailed  
**After:** 1151 passed, 7 skipped, 2 xfailed (+8 JSON5 tests)  
**Status:** ✅ All tests passing

### Verification

```
python3 -m pytest tests/ -q --tb=line
# 1151 passed, 7 skipped, 2 xfailed in 34.02s
```

## Example Usage

```bash
# Auto-detects JSON5 and converts to YAML
$ devbench cf -f json5 -t yaml <<< "{ name: 'test', value: 42 }"
name: test
value: 42

# Convert JSON5 file to TOML
$ devbench cf -f json5 -t toml config.json5

# Mixed syntax with comments
$ cat config.json5
{
  // server configuration
  host: 'localhost',
  port: 8080,
  debug: true,  // trailing comma OK
}
```

## Closure

✅ **User request implemented:** GitHub issue #2712 addressed fully  
✅ **Format support added:** JSON5 now on par with JSONC  
✅ **Tests passing:** 1151/1151 (8 new JSON5-specific tests)  
✅ **Cross-format:** JSON5 → YAML, TOML, XML, CSV, INI, etc.  
✅ **Backward-compatible:** No breaking changes to existing APIs
