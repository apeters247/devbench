# External Review — Pkl Format Support

**Date**: 2026-06-09T17:52Z  
**Minute Rotation**: 52 → Reddit macOS developer tool complaints  
**Finding**: Apple's Pkl configuration language (2024) is emerging as a standard replacement for YAML/JSON/HCL in 2026 developer tools.

## User Complaint / Finding

Web search revealed Pkl as an emerging configuration language from Apple (released early 2024) that's designed to replace YAML, JSON, and HCL. DevBench currently supports 10 formats but was missing Pkl detection.

**Pkl Syntax**:
- Uses `key = value` assignments (no colons)
- Blocks with `{ nested = value }`
- No commas required
- Comments with `//`

## Implementation

Added **Pkl detection** to DevBench's format auto-detector:

### Changes
1. **detector.py** — Added `_try_pkl()` function to recognize Pkl syntax patterns
   - Detects `key = value` assignments without colons
   - Identifies block structures `{ ... }`
   - Handles Pkl comments (`//`)
   - Confidence threshold: 0.75 (high enough to avoid false positives)

2. **Reordered detection priority** in `detect()`:
   - Pkl detection now checked before URL (since `key = value` can look like domains)
   - Maintains backward compatibility with all existing format detection

3. **Added test coverage**:
   - `test_detector_pkl_simple` — simple Pkl config
   - `test_detector_pkl_with_comments` — Pkl with `//` comments
   - Both tests passing

### Note on Full Pkl Support
Pkl parsing would require the Apple Pkl library (Java-based, complex installation). Current implementation provides:
- ✅ Detection / recognition
- ✅ User notification that Pkl is detected
- ⏳ Full parse/convert support deferred pending library availability

Users can convert Pkl to supported formats using Pkl CLI:
```bash
pkl eval config.pkl -o json | devbench cf - --from json
```

## Test Results

- **Before**: 849 passed, 7 skipped, 2 xfailed
- **After**: 851 passed, 7 skipped, 2 xfailed ✅
- New tests: 2 (Pkl detection)
- No regressions

## Quality Assessment

- No breaking changes
- Detection is conservative (0.75 confidence threshold)
- Detected Pkl configs show helpful notification
- Backward compatible with all existing detection

