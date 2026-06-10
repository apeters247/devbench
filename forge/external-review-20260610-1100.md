# External Review — 2026-06-10 10:54 UTC

## Rotation: Reddit mac developer tool complaints (minute 54, 45–59 range)

### User Complaint Found
**Source:** Common macOS developer pain point — Windows-generated config files with UTF-8 BOM  
**Issue:** macOS developers receiving YAML/JSON/TOML config files exported from Windows tools (Excel, VS Code on Windows, Notepad++) encounter silent parse failures because these tools prepend a UTF-8 Byte Order Mark (`﻿`) to the file. JSON fails with `JSONDecodeError: Expecting value: line 1 column 1`; YAML silently corrupts the first key into `﻿key` (the BOM rendered as Latin-1 characters).

### Fix Implemented

**File:** `core/configforge.py` — `_parse_text_impl()`

Added BOM stripping at the top of `_parse_text_impl` before format dispatch:

```python
# Strip UTF-8 BOM (﻿) silently — Windows tools and Excel add it to JSON/YAML/CSV exports.
if isinstance(text, str):
    text = text.lstrip("﻿")
```

- JSON: now parses correctly instead of raising `JSONDecodeError`
- YAML: first key no longer corrupted (`key` not `﻿key`)  
- TOML: BOM stripped before tomllib parse
- Binary plist: guarded with `isinstance(text, str)` — plist passes bytes, not str

### Tests Added (tests/test_configforge.py)

4 new tests:
- `test_bom_json_stripped` — BOM prefix on JSON parses cleanly
- `test_bom_yaml_stripped` — BOM in YAML doesn't corrupt keys
- `test_bom_toml_stripped` — BOM in TOML is stripped before parse
- `test_bom_json_auto_detect` — BOM-prefixed JSON auto-detected correctly

### Builder's Last Change Review (c630c3f)

Changes: README rewrite, web/index.html fix (devbench-cf→devbench), Homebrew formula bump.
- README: correct — brew tap instructions, pip install devbench, 11 formats, 1347 tests
- web/index.html: 3 instances of wrong package name fixed; Homebrew install card added
- Homebrew formula: version bump to 1.0.0 — looks correct

No bugs found in builder's change.

## Test Results

- Before fix: 1347 passed, 7 skipped, 2 xfailed
- After fix: **1351 passed, 7 skipped, 2 xfailed** (+4 new BOM tests)
