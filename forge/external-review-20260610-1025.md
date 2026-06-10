# External Review — 2026-06-10 10:25 UTC

## Rotation: HN yq alternatives (minute 20 → 15-29 slot)

### Source Complaint
**mikefarah/yq issue #2247** — "Looking for a way to escape period for yaml params that have dots in them"

User tried to set a Kubernetes annotation key `cert-manager.io/cluster-issuer` via yq:
```
yq -i '.globals.ingressAnnotations.certmanager.io/cluster-issuer="letsencrypt"'
```
Expected: key `cert-manager.io/cluster-issuer` under `ingressAnnotations`  
Got: nested path `cert-manager > io/cert-manager` (dot treated as separator)

yq has no escape mechanism for dotted key names as of 2024.

### Devbench Status
Devbench already implements `\.` escape syntax in `_split_path()` (configforge.py:1927).
The feature exists but had **zero CLI-level test coverage** for this exact use case.

### What Was Built
Added 3 new tests to `tests/test_core.py` covering the Kubernetes annotation use case:

1. `test_cf_get_dotted_key_escaped` — `--get` retrieves `cert-manager.io/cluster-issuer` correctly
2. `test_cf_set_dotted_key_escaped` — `--set` writes dotted key without splitting into nested path
3. `test_cf_dotted_key_not_split_into_nested` — regression guard: asserts yq#2247 failure mode doesn't occur

### Bug Fixed
`test_batch_convert_progress` (tests/test_configforge.py:274) was failing:
- Root cause: called `batch_convert()` without `show_progress=True` then checked stdout for `[batch]`
- Fix: added `show_progress=True` kwarg; check accepts both stdout and stderr since function uses both

### Builder's Last Change Review (HEAD~1)
Builder added `--explicit-start`, `--explicit-end`, `--yaml-width` flags referencing yq issues #93, #452, #278.
- **Correct**: `yaml.dump(explicit_start=True)` and `width=sys.maxsize` for `--yaml-width 0` work as expected
- **Edge case**: `_get_env_info()` formats dict was changed from `dict[str, bool]` to `dict[str, dict]` — the `check-env` display updated to match. Verified no regressions.
- **Import cleanup**: `import copy` moved to top of file from inside function — correct fix.

## Test Results
1335 passed, 7 skipped, 2 xfailed — 0 failures
