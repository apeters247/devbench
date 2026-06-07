# Swift Bridge Fix — Implementation Plan

## Task 1: Contract Tests
Write tests/test_swift_bridge_contract.py that calls `devbench` as a subprocess exactly like Swift's PythonBridge does.

1. test_detect_envelope_keys() — verify JSON envelope has the keys Swift needs. But DO NOT rename detect's output keys (that breaks 874 tests). Instead, test that we can add a --swift flag later.
2. test_ui_tool_names_are_valid() — verify that tool names in ContentView.swift map to valid subcommands. The UI will be rewritten to use REAL tools (json, base64, jwt, hash, url, timestamp, uuid, diff, detect, cf). This test should verify those.
3. test_output_not_double_wrapped() — verify runTool returns the `output` field.
4. test_all_subcommands_produce_json() — verify every UI-relevant subcommand returns valid JSON.

## Task 2: CLI — Add --swift flag to detect
In core/cli.py, add `--swift` flag to the `detect` subcommand. When --swift is passed, emit a friendlier JSON envelope with keys: {tool_name, output, error, detection_type, metadata}. This keeps the default output unchanged (all 874 tests stay green).

## Task 3: Fix Swift DetectionResult
Edit ui/Sources/Bridge/PythonBridge.swift:
1. DevbenchTool enum matching real subcommands: detect, json, base64, jwt, hash, url, timestamp, uuid, diff, cf, list
2. DetectionResult struct matching the --swift envelope
3. runTool calls `devbench detect --swift` when using detect, parses envelope, returns `output` field

## Task 4: Update ContentView.swift Tool List
Replace the fictional tools (Format, Lint, Explain, Refactor, Document) with real ones:
- Auto-Detect → detect
- Convert → cf
- JSON, Base64, JWT, Hash, URL, Timestamp, UUID, Diff
- Keep the icon mapping, just update names and commands

## Task 5: GitHub Actions Workflow
Write .github/workflows/macos.yml with swift-build (macos-14) and python-contract (ubuntu-latest) jobs.

## Task 6: Verify
python3 -m pytest tests/ -q --tb=line
python3 snap_state.py