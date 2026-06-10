# External Review — 2026-06-10 18:36 UTC

## Source
yq GitHub issue #2453 — "ref variables cause multiplied output"

## User Complaint
A user tried to copy a field from a parent object to multiple nested list items using yq's `ref`
variable operator: `.top[] ref $p | $p.h[] ref $h | $h.hf = $p.f`. Instead of one output
document, yq produced six copies — the cartesian product of 2 outer × 3 inner list items.
Even a simpler workaround produced two copies. yq's variable/ref scoping is non-deterministic
for users and causes CI/CD pipeline bugs.

## DevBench Advantage (Design Level)
DevBench avoids this class of bug entirely: `--set`, `--get`, `--delete` always operate on
exactly one document and produce exactly one output. No variable scoping, no implicit looping,
no output multiplication. This is a meaningful differentiator vs yq for DevOps users who need
predictable automation.

## Bugs Found in Builder's Last Commit

### 1. Dead Code: `_SEXAG_RE` in `_make_yaml12_loader()` (configforge.py:708)
The builder added `_SEXAG_RE = re.compile(...)` but it was never used anywhere in the function.
The sexagesimal fix works correctly via `_YAML12_INT_RE` (strict int pattern that excludes
colons), but `_SEXAG_RE` was dead weight and confusing.

**Fix**: Removed the dead variable.

### 2. `--check` / `--dry-run` Without `--in-place` Silently Ignored
When a user ran `devbench cf file.yaml --set key val --check` (without `--in-place`), the
flags were silently dropped — the output went to stdout and the exit code was 0. This masks
CI/CD drift-detection failures where the user forgot `--in-place`.

**Fix**: Added early validation in `_main_dispatch` (cli.py) that errors with a clear message:
`error: --check and --dry-run require --in-place` when either flag is set without `--in-place`.

## Tests Added (2)
- `test_check_without_in_place_errors` — verifies rc=1 and error message contains `--check` and `--in-place`
- `test_dry_run_without_in_place_errors` — same for `--dry-run`

## Test Results
**1375 passed, 7 skipped, 2 xfailed** (up from 1373)

## Wheel Build
`Successfully built devbench-1.0.0-py3-none-any.whl` ✓
