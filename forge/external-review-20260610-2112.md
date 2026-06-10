# External Review — 2026-06-10 21:12 UTC

## Source
yq GitHub issue #2448 — user complaint: "I want to get keys and values from nested YAML
structure (`block1.root.rp1`, `block1.root.rp2`) without knowing the key names in advance."
Maintainer required a complex reduce/merge operator chain to solve this. DevBench now solves
it with a simple `*` wildcard in `--get`.

## Feature Implemented: Wildcard `*` support in `--get`

### Problem
Users with deeply nested configs couldn't extract values without knowing the full key path.
`devbench cf config.yaml --get "services.web.port"` requires knowing `web` exists. There was
no way to get all service ports without listing each service explicitly.

### Solution
Added `_get_by_glob()` to `configforge.py` (after `_get_by_path`). Supports `*` at any
path segment — fans out over all dict keys or list indices at that level.

```bash
# Get all values under services (without knowing service names)
devbench cf config.yaml --get "services.*"
# → services.web: {"port": 80}
# → services.api: {"port": 8080}

# Get every database host across all environments
devbench cf config.yaml --get "*.database.host"
# → prod.database.host: db.prod.example.com
# → staging.database.host: db.stg.example.com
```

CLI integration: `_run_cf_get` detects `*` in split path, calls `_get_by_glob`, prints
`dot.path: value` per match. `--default` still works when no matches found.

### Files Changed
- `core/configforge.py` — added `_get_by_glob()` (~35 lines)
- `core/cli.py` — updated `_run_cf_get` to use glob path when `*` is present
- `tests/test_configforge.py` — 8 new tests (unit + CLI)

## Builder Review (HEAD~1)
Changes: Added `-f`/`-o` short flags for `--from`/`--to`; parameterized `_check_port_available`
error message with `command_hint`. Clean, low-risk. No edge case issues.

## Test Suite
- Before: 1376 passed, 7 skipped, 2 xfailed
- After:  1383 passed, 7 skipped, 2 xfailed (+7 net new tests)
- All green.

## Weak Assertions Fixed
None needed — no standalone `is not None` or bare `isinstance` assertions were weak in context.
