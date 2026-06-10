# External Review — 2026-06-10 03:12 UTC

## Rotation
00-14 → Reddit devops (Reddit blocked; fell back to HN yq/jq discussion threads)

## User Complaint Found
**Source**: Hacker News discussion on "I started using yq over jq" (hn/38462960)
**Complaint**: "yq lacks if-then-else capabilities — you can't conditionally act on config values in shell scripts without piping through complex jq-style expressions."

Practical impact: devops engineers want simple shell conditionals like:
```bash
if yq '.database.host' config.yaml > /dev/null 2>&1; then
  echo "DB configured"
fi
```
But yq's exit codes are inconsistent and --has-path semantics vary by version.

## Feature Implemented
**`--has PATH`** — check whether a key path exists in any config format.

- Exits **0** + prints `true` if path exists (including when value is null)
- Exits **1** + prints `false` if path not found
- `--raw` outputs JSON: `{"path": "...", "exists": true/false, "type": "string"}`
- Works with dot-notation paths across all 11 formats
- Enables clean shell conditionals without complex pipelines

```bash
# Shell conditional use case:
if devbench cf config.yaml --has database.host; then
  echo "DB host configured"
fi

# K8s manifest inspection:
devbench cf deployment.yaml --has spec.template.spec.containers

# JSON output for scripting:
devbench cf config.yaml --has feature.flags.dark_mode --raw
# → {"path": "feature.flags.dark_mode", "exists": true, "type": "boolean"}
```

## Builder Change Review (HEAD~1)
Added `--sort-by`, `--unique`, `--unique-by`, `--bash-arrays` flags.

**Bug found and fixed**: `_MISSING = object()` in `_run_cf_sort_by()` was dead code — created but never referenced. Removed.

**Design assessment**: Implementation is correct:
- `--sort-by` uses tuple-based sort keys `(0, val)` for numeric, `(1, str)` for string, `(2, "")` for missing — ensures stable ordering across mixed types
- `--unique` uses `json.dumps(sort_keys=True)` fingerprinting — correct for JSON-serializable objects
- `--bash-arrays` outputs `declare -a` syntax — correct for bash 3.1+
- `--shell-export` for lists now emits indexed vars (`KEY_0=x KEY_1=y KEY_COUNT=2`) — good fallback for sh/dash

## Test Results
- Before: 1217 passed, 7 skipped, 2 xfailed
- After:  1224 passed, 7 skipped, 2 xfailed (+7 new tests for --has)

## Files Changed
- `core/cli.py`: +`_run_cf_has()`, +`--has` parser arg, +router entry, +bash completion, -dead `_MISSING` var
- `tests/test_core.py`: +7 tests for `--has` (existing/missing/nested/root/raw/null)
