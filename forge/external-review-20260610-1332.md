# External Review — 2026-06-10 13:32 UTC

## Rotation: HN yq alternatives (minute 26)

### Source Complaint
**GitHub mikefarah/yq issue #2025** — "Why is yq putting multiline separator indicator (`|-`) to complex object replacements?"

User ran:
```
yq -i '.test.this = "bla: bla\ntwice: bla"' test.yaml
```
Expected a quoted inline string; got a block scalar with `|-`. Broader pattern: when users pass multiline string values to yq's `--set` equivalent, the YAML output style is surprising.

**DevBench analog found:** `devbench cf --set key $'line1\nline2' input.yaml` was producing:
```yaml
key: 'line1

  line2'
```
This is valid YAML but ugly single-quoted multi-line — worse than yq's `|-` output.

---

## Fix Implemented

**File:** `core/cli.py` — `_run_cf_set()`

When `--set` is given a value containing a newline and the output format is YAML, automatically enable `block_scalars=True` (previously only available as an explicit `--block-scalars` flag).

**After fix:**
```yaml
key: |-
  line1
  line2
```

Clean, readable, and consistent with yq's behavior. Single-line values are unaffected.

---

## Builder's Last Change Review

Commit `636a316`: `feat: add buy CTA to SEO footer; fix dead Gumroad link in index.html`

- Changed `<a href="#">` to `<a href="https://naxiai.gumroad.com/l/devbench">` with `target="_blank" rel="noopener"`
- No functional code changes; HTML-only fix
- No bugs or edge cases found

---

## Test Results

| Stage | Result |
|-------|--------|
| Before fix | 1361 passed, 7 skipped, 2 xfailed |
| New test added | `test_set_multiline_value_uses_block_scalar` |
| After fix | **1362 passed, 7 skipped, 2 xfailed** |

All tests pass. No regressions.
