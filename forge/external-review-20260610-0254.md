# External Review — 2026-06-10 02:54 UTC

## Rotation: Reddit mac developer tool complaints (minute 49)

## User Complaint Found
**Source**: Reddit / developer community (YAML list parsing in bash)
**Pain point**: `--shell-export` converted YAML list values using Python's `str()` repr, producing unusable output like `export SERVERS='['"'"'nginx'"'"', '"'"'apache'"'"']'` — a shell-quoted Python list, not a real bash value.

**Root cause**: `_run_cf_shell_export` called `str(v)` on list values from `_flatten_dict`, which preserves lists as Python objects. The result was syntactically valid shell but semantically useless.

## Fix Implemented

### `core/cli.py` — `_run_cf_shell_export`
- Lists now output as **indexed env vars** (default, exportable, sh-compatible):
  ```
  export SERVERS_0=nginx
  export SERVERS_1=apache
  export SERVERS_COUNT=2
  ```
- New `--bash-arrays` flag outputs **bash array syntax** (bash 3.1+):
  ```
  declare -a SERVERS=(nginx apache)
  export SERVERS
  ```
- `--raw` JSON output now has `items` field for lists, `value: null` (previously `value: "['nginx', ...]"`)
- Help text updated for `--shell-export` to document list behavior

### `tests/test_core.py` — 4 new tests
- `test_shell_export_list_becomes_indexed_vars` — confirms indexed vars + COUNT
- `test_shell_export_bash_arrays` — confirms `declare -a` syntax
- `test_shell_export_list_with_spaces` — confirms shlex.quote on items with spaces
- `test_shell_export_raw_with_list` — confirms JSON `items` field, `value: null`

## Builder's Last Change Review (HEAD~1)
**Commit**: `d5ecfc3` — `--sort-keys-reverse`, `--compact`, `--template`, `--get --default`, `--select` + 4 new flags

**New features added by builder**:
- `--schema-gen` — infer JSON Schema Draft 7 from config structure
- `--replace-value OLD NEW` — recursive find-and-replace of leaf values
- `--sort-by FIELD` — sort list of objects by field (with `--sort-desc`)
- `--unique` / `--unique-by FIELD` — deduplicate list items

**Review findings**: Code is correct. `_replace_values_recursive` handles dicts, lists, and scalars. `_infer_json_schema` properly merges object schemas from uniform arrays. `--raw` on `--replace-value` outputs stats-only (intentional per docstring). No bugs found.

## Test Results
- Before: 1201 passed, 7 skipped, 2 xfailed
- After: 1205 passed, 7 skipped, 2 xfailed (+4 new shell-export list tests)
