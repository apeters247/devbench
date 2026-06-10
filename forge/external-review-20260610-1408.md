# External Review — 2026-06-10 14:08 UTC

## Source
Reddit r/devops — rotation: minute 01 (00-14 window)

## User Complaint Found
> "yq strips blank lines and adds extra indentation to comments when editing YAML in-place"
> (yq GitHub #1248 + r/devops reports on in-place YAML modification with yq)

DevOps engineers editing Kubernetes config, Helm values, and CI configs with `yq -i`
report that the tool destroys carefully spaced YAML formatting — blank lines between
sections vanish and comment indentation gets corrupted.

## Fix Implemented

**YAML blank line + comment preservation in `--set`, `--append`, `--delete` operations**

Previously only `--rename` preserved blank lines and comments when round-tripping YAML.
The three most-used edit operations (`--set`, `--append`, `--delete`) silently stripped
blank lines and comments, matching the yq complaint exactly.

### Files changed
- `core/cli.py`: Added `_extract_yaml_comments` + `_extract_yaml_blank_lines` before
  mutation and `_reinsert_yaml_blank_lines` + `_reinsert_yaml_comments` after serialize
  in `_run_cf_set`, `_run_cf_append`, and `_run_cf_delete` (same pattern `_run_cf_rename`
  already used).
- `tests/test_configforge.py`: Added 4 new tests:
  - `test_set_preserves_yaml_blank_lines`
  - `test_set_preserves_yaml_comments`
  - `test_delete_preserves_yaml_blank_lines`
  - `test_append_preserves_yaml_blank_lines`

## Builder's Last Change Review (e7d6817)
Fix: preserve empty TOML tables in serializer (yq#2459)

Condition changed: `scalar_lines` → `scalar_lines or not deferred`
- Correctly handles genuinely empty `{}` tables — emits `[section]` header
- Intermediate-only tables (e.g. `[tool]` with sub-tables) still stay implicit
- No edge case issues found; unicode/empty input handled by outer parse layer

## Test Results
- Before: 1363 passed, 7 skipped, 2 xfailed
- After:  1367 passed, 7 skipped, 2 xfailed (+4 new)

## Distribution
Wheel builds cleanly: `devbench-1.0.0-py3-none-any.whl`
