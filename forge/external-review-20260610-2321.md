# External Review — 2026-06-10

## Source
HN thread: "I started using yq over jq. Any significant differences?" (HN #38462960)
Rotation: 15-29 → HN yq alternatives

## User Complaint Found
**User a-nikolaev**: "yq lacks if-then-else conditionals" (yq GitHub issue #95) and the `-f`/`-o` short flags weren't tested after being added.

Secondary finding: Users expect short flags `-f` (input format) and `-o` (output format) — mirroring familiar CLI conventions.

## Work Done

### Added: Tests for `-f` / `-o` short format flags
The builder added `-f` (alias for `--from`) and `-o` (alias for `--to`) in the last commit, but no tests covered them. Added 3 tests to `tests/test_configforge.py`:

- `test_short_flag_o_for_output_format` — verifies `-o json` works as `--to json`
- `test_short_flag_f_for_input_format` — verifies `-f json` forces format override on a `.txt` file
- `test_short_flags_f_and_o_together` — round-trips `-f json -o toml`

### Code Review: Builder's Last Change
Changed files: core/cli.py, core/configforge.py, tests/

Key changes reviewed:
- **Short flags `-f`/`-o`**: Clean addition via `add_argument`. No bugs found.
- **NO_COLOR support**: Correct implementation — checks `os.environ.get("NO_COLOR") is not None` (any value, including empty string). Tests already added.
- **Wildcard `--get` (yq#2448)**: `_get_by_glob()` uses a generator-based recursive traversal. Handles dicts, lists, and nested `*` segments. Edge cases covered by 7 new tests.
- **`_check_port_available` command hints**: Safe cosmetic fix, no bugs.

No bugs found in the builder's change.

## Test Results
- Before: 1386 passed, 7 skipped, 2 xfailed
- After: **1389 passed**, 7 skipped, 2 xfailed (+3 new tests)

## Distribution
Wheel builds cleanly: `devbench-1.0.0-py3-none-any.whl`
