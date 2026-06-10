# External Review — 2026-06-10 04:56 UTC

## Rotation: Reddit mac developer tool complaints (45-59 min)

## User Complaint Found
**Source**: mikefarah/yq GitHub issue #517 (via HN discussion thread)
**Complaint**: Users need to filter YAML list items where an array field *contains* a specific value, but yq lacked native support. The workaround required piping to jq:
```
yq r -j data.yml | jq -r '.[]|select(.tags[]|select(.=="commonwealth")).name'
```

## Feature Implemented: `--select FIELD~VALUE` (array contains)

Extended `--select` to support two new operators:
- `FIELD~VALUE` — keep items where `item[FIELD]` is an array **containing** VALUE
- `FIELD!~VALUE` — keep items where `item[FIELD]` is an array **not containing** VALUE

### Example (from the issue):
```yaml
# countries.yaml
- country: Australia
  tags: [oceania, commonwealth]
- country: Canada
  tags: [north america, commonwealth]
- country: Philippines
  tags: [oceania, republic]
```
```bash
devbench cf countries.yaml --select tags~commonwealth
# → Australia, Canada

devbench cf countries.yaml --select tags!~commonwealth
# → Philippines

# Chain with --each (yq equivalent: .[] | select(.tags[] == "commonwealth") | .country)
devbench cf countries.yaml --select tags~commonwealth --each country
```

### Files Changed
- `core/cli.py`: Updated `_run_cf_select()` and embedded select in `_run_cf_each()` to parse `!~` and `~` operators; updated `--select` help text
- `tests/test_core.py`: Added 5 new tests covering array contains, not-contains, no-match exit code, chaining with --each, and non-array field behavior

## Builder Code Review (HEAD~1)
**Changes**: Large sync — `--length`, `--hash-field`, `--ini-quote-strings`, atomic `--in-place` writes, batch mode updates.

**Atomic in-place write** (key fix): `_cf_write_in_place` now uses `tempfile.mkstemp` + `os.rename` — correct and safe, prevents file truncation on failed writes.

**No bugs found** in the builder's changes. Implementation is solid.

## Test Results
- Before: 1257 passed, 7 skipped, 2 xfailed
- After: 1262 passed, 7 skipped, 2 xfailed (+5 new tests)
