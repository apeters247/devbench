# External Review — 2026-06-10 15:01 UTC

## Rotation
Minute 53 → Reddit macOS developer tool complaints
Search found: plist file parsing errors are a recurring macOS dev pain point.
DevBench has XML support but no plist-specific detection/label — noted for future work.

## Fix Applied — Builder Exit-Code Regression

### Root Cause
Last builder commit (cbb52c0) refactored the CLI dispatch to add `context`, `prompt`,
`schema` subcommands. It also narrowed the JSON-envelope error → exit-code logic from
ALL commands down to `cf` only. The original comment correctly noted that UI-backend
tools (json, diff, jwt, etc.) should exit 0 so Swift can always parse the envelope —
but `token` and `chunk` are script/CLI tools that need exit 1 on errors.

### Tests Broken (5 in test_llm_tools.py)
- `test_token_empty_input` — expected returncode=1, got 0
- `test_chunk_empty_input` — expected returncode=1, got 0
- `test_chunk_invalid_chunk_size` — expected returncode=1, got 0
- `test_chunk_invalid_overlap` — expected returncode=1, got 0
- `test_chunk_overlap_greater_than_size` — expected returncode=1, got 0

### Fix (core/cli.py lines ~275-285)
Extended `_ERROR_EXIT_COMMANDS` set to include `token`, `chunk`, `context`,
`prompt`, `schema` — the non-UI tools that scripts rely on for exit codes.
UI tools (json, diff, jwt, hash, url, timestamp, uuid, base64) remain exit 0.

## Builder Change Review (cbb52c0)
- **INI `--ini-strip-quotes`**: strips literal `"..."` from configparser values.
  Correct: handles `len >= 2`, preserves type inference. Edge case `""` → `""`
  after stripping → empty string. Intentional and fine.
- **Leading dot in `_split_path`**: `.foo.bar` → `foo.bar` (yq-style paths).
  Correctly skips stripping when second char is `\` (escaped dot in key).
  Returns `[]` for bare `.` (root document). Solid.
- **context/prompt/schema subcommands**: Added routing and argparse entries.
  New tools bundled correctly in TOOL_NAMES. Aliases registered.
  Edge cases (empty input, file not found) handled in tool functions.

## Test Results
1399 passed, 7 skipped, 2 xfailed — all green.

## Wheel Build
`python3 -m build --wheel` → `devbench-1.0.0-py3-none-any.whl` built successfully.
