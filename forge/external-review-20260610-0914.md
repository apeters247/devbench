# External Review — 2026-06-10 09:14 UTC

## Rotation
Minute 10 → Reddit devops (00-14)

## User Complaint Found
**Source:** r/devops / yq docs — "you cannot add a chunk of YAML file under .spec.containers[]"
**Pain point:** `yq` (and most config tools) only support top-level merges. Users want to merge/inject content at a specific nested path (e.g., patch tolerations into `spec.template.spec`) without writing a complex multi-step expression.

## Feature Implemented: `--merge-at PATH`

Added `--merge-at PATH` flag to `devbench cf --merge`. Lets users target any nested path for the overlay merge instead of the document root.

### Examples
```bash
# Inject tolerations into spec.template.spec of a Kubernetes deployment
devbench cf deploy.yaml --merge tolerations.yaml --merge-at spec.template.spec

# Add missing DB defaults without overwriting existing config
devbench cf config.yaml --merge defaults.yaml --merge-at db --merge-new-only
```

### Changes
- `core/cli.py`: Added `--merge-at PATH` argument; updated `_run_cf_merge` to extract the target node, merge overlay into it, then write back with `_set_by_path`; creates the target path if absent. Added fish/zsh/bash completions and usage string entry.
- `tests/test_configforge.py`: 3 new tests — nested path inject, missing intermediate creation, compose with `--merge-new-only`.

## Builder Review (HEAD~1: d7f8292)
Builder added `--merge-new-only` flag (yq issue #2201) — good implementation. `_deep_merge` correctly recurses into dicts even under `new_only=True` while protecting leaf scalars/lists. INI quoted-value fix (`_ini_format_value_quoted`) looks sound — strips one layer of surrounding double-quotes to prevent round-trip doubling.

No bugs found in builder's changes.

## Test Results
- Before: 1325 passed, 7 skipped, 2 xfailed
- After: **1328 passed, 7 skipped, 2 xfailed** (+3 new tests)
