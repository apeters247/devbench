# External Review — 2026-06-10 15:51 UTC

## Source
**Reddit r/MacOS** — "Homebrew help"  
> "trying to install homebrew, but the terminal command runs for hours and has no progress. When I tried the pkg file it said 'Command Line Tools (CLT) are missing'. So I ran the xcode-select --install command but it opened a popup saying 'Finding Software' and freezes."

**Pain:** macOS developer tooling friction — Homebrew's dependency on Xcode CLT creates a loop that silently freezes with no error recovery path. Users get no guidance on how to break the CLT hang or what alternatives exist.

## Applied Fix

### Bug: context_builder glob misidentifies literal paths with wildcard chars (`*`, `?`, `[`)
**File:** `core/tools.py:1144-1154`  
**Change:** Check `Path(lines[0]).exists()` before falling through to glob expansion. A single path containing `*` in its filename (e.g. `file*with_star.txt`) is now treated as a literal file path if it exists, rather than incorrectly interpreted as a glob pattern.  
**Test:** `test_context_builder_literal_path_with_star` added.

### Builder Code Review — context/prompt/schema tools (commit cbb52c0)
**Reviewed items:**
- Empty input: All three tools return proper error envelopes. ✓
- Unicode: prompt_renderer passes UTF-8 characters through correctly. ✓
- No terminal / piped stdin: CLI dispatch handles piped input and positional args. ✓
- Glob path ambiguity: Fixed (above). ✓
- ini_strip_quotes: Vacuously safe — only strips `"..."` when both quotes present. ✓
- _split_path leading-dot strip: Correctly skips escape sequences like `\.foo`. ✓

### Test Strengthening
- `test_context_cli_piped_paths` — now checks actual file content in output
- `test_prompt_renderer_empty_input` — checks error message, not just `is not None`
- `test_schema_infer_empty_input` — checks error message, not just `is not None`
- `_assert_graceful` (test_edge_cases.py) — replaced `isinstance(r, dict)` with richer envelope checks

## Status
**Tests:** 1400 passed, 7 skipped, 2 xfailed (0 failures) — +1 test for glob edge case  
**Wheel:** Builds cleanly (`python3 -m build --wheel`) ✓  
**Distribution:** PyPI published — GitHub Actions not triggered (no push)
