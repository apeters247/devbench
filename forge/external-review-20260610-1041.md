# External Review — 2026-06-10 10:41 UTC

## Source
yq GitHub issue #2592 — "Recent update broke comments in arrays in TOML"
https://github.com/mikefarah/yq/issues/2592

User: TOML files with inline comments inside arrays (`# comment` before values) cause
yq to crash with "Error: bad file: unsupported type Comment" when using `yq . -oj`.
Filed 2026-02-02, affects yq 4.52.2 on Linux.

## Devbench Response
DevBench uses Python's stdlib `tomllib` which handles TOML comments in arrays correctly.
No fix needed for parsing. Added regression test to verify and advertise this advantage.

## Builder Review (HEAD~1)
The builder's last commit added `--explicit-start`, `--explicit-end`, and `--yaml-width` flags
to `core/cli.py` (kislyuk/yq#93 and mikefarah/yq#452/#278 fixes). **However, the options were
parsed in CLI but not wired into `configforge.py`'s YAML dump path** — the feature was inert.

## Fixes Applied

### 1. Implemented `--explicit-start` / `--explicit-end` / `--yaml-width` in configforge.py
- `core/configforge.py` YAML dump path now reads `explicit_start`, `explicit_end`, `yaml_width` options
- `yaml_width=0` maps to PyYAML `width=None` (no line wrapping)
- Both `yaml.dump()` and `yaml.dump_all()` receive the new kwargs

### 2. Added 6 new tests
- `test_toml_comments_in_arrays` — devbench parses TOML with `# comment` inside arrays (yq#2592)
- `test_yaml_explicit_start` — `---` marker emitted when `explicit_start=True`
- `test_yaml_explicit_end` — `...` marker emitted when `explicit_end=True`
- `test_yaml_explicit_start_and_end` — both markers together
- `test_yaml_width_unlimited` — `yaml_width=0` keeps 200-char URL on one line
- `test_yaml_width_custom` — `yaml_width=40` wraps long scalars

## Test Results
- Before: 1338 passed, 7 skipped, 2 xfailed
- After:  1344 passed, 7 skipped, 2 xfailed (+6 new tests, 0 failures)
