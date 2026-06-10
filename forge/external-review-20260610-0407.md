# External Review — POLISHER

**Source**: yq GitHub issue #2283 — "Feature Request: Add Hash Function"
**Rotation**: 00-14 min → Reddit devops (no specific post found; fell back to yq issues)

## User Complaint
yq users want to hash field values (e.g. `.password |= hash("sha256")`) for:
- Anonymizing sensitive configs before sharing in bug reports
- Storing in audit logs without credential leaks
- Deterministic comparison of config values across environments

## What Was Built: `--hash-field`

Added `--hash-field PATTERN [--hash-algorithm ALGO]` to ConfigForge CLI and API.

```bash
devbench cf prod.yaml --hash-field 'password|secret|token'
# database:
#   password: sha256:ef92b778bafe...
#   host: localhost   # unchanged

devbench cf prod.yaml --hash-field password --hash-algorithm md5
devbench cf prod.yaml --hash-field secret --raw  # JSON output with hashed_count
```

Supported algorithms: md5, sha1, sha256 (default), sha512, blake2b.
Prefixes output with `algo:hexdigest` — deterministic and comparable.
Does NOT hash nested dicts/lists (recurses into them instead).

### Files Changed
- `core/configforge.py` — added `hash_field_values()` function
- `core/cli.py` — added `--hash-field`/`--hash-algorithm` args, `_run_cf_hash_field()` handler, completion entries
- `tests/test_core.py` — 8 new tests

## Builder's Last Change Review (HEAD~1)
Builder added: `--block-scalars` (fix yq multiline string corruption), `--has PATH` (key existence check), `--sort-by`, `--unique`, `--bash-arrays`, 3 SEO pages, sitemap update.

No bugs found. Block scalar dumper correctly strips trailing whitespace per-line before handing to PyYAML — this is the correct fix for yq issue #439. `--has` uses dot-notation consistently with `--get`.

## Test Results
- Before: 1235 passed, 7 skipped, 2 xfailed
- After:  1243 passed, 7 skipped, 2 xfailed (+8 for --hash-field)
