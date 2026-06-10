# External Review — 2026-06-10 13:49 UTC

## Rotation: yq GitHub Issues (min 43, 30-44 range)

### Source Issue
**yq#2459** — "Conversion from TOML to JSON still omits empty tables"

Users found that yq silently drops empty TOML tables that appear in the middle
of a document when converting to JSON. Devbench already preserved empty tables
in the TOML→JSON direction, but had the same bug in the reverse direction
(JSON→TOML and YAML→TOML).

---

## BUILT

### Fix: Empty TOML tables preserved in serializer (yq#2459)
**File:** `core/configforge.py` — `_to_toml()` function

**Bug:** The `[section]` header was only emitted when `scalar_lines` was
non-empty. Empty tables (`{}`) have no scalars and no deferred children,
so they were silently dropped.

```toml
# Before fix — [cache] lost in roundtrip:
[server]
host = "localhost"
[db]
port = 5432

# After fix — [cache] preserved:
[server]
host = "localhost"
[cache]
[db]
port = 5432
```

**Fix:** Changed condition from `scalar_lines` to `scalar_lines or not deferred`.
This correctly distinguishes:
- Genuinely empty tables (no scalars, no sub-tables) → emit `[section]` ✓
- Intermediate-only tables like `[tool]` in pyproject.toml (no scalars, HAS sub-tables) → still implicit ✓

**Test added:** `test_toml_empty_tables_preserved` in `tests/test_configforge.py`
covering serializer output, TOML→JSON→TOML roundtrip, and intermediate-table suppression.

---

## Code Review: Builder's Last Change (c5f82cc)

**Change:** Auto-enable `block_scalars` when `--set` receives a multiline string in YAML output.

**Assessment:** Correct and well-scoped.
- `yaml12` format also benefits and works correctly (it's an option flag, not a separate to_fmt string).
- `not ser_opts.get("block_scalars")` guard correctly respects explicit `--block-scalars` flag.
- Test checks real content (`result["key"] == "line1\nline2"` roundtrip), not just isinstance.
- No edge cases found.

---

## Test Results
- Before: 1362 passed, 7 skipped, 2 xfailed
- After:  **1363 passed**, 7 skipped, 2 xfailed
- New test: `test_toml_empty_tables_preserved`
