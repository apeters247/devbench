# External Review — 2026-06-09 14:26 UTC

## Rotation: HN yq Alternatives (15-29 min)

**Status**: No specific actionable user complaint found in HN threads during this rotation window. General YAML frustration is pervasive but lacks concrete feature requests.

## Test Suite Status
✅ **872 passed, 7 skipped, 2 xfailed** — All tests passing

## Builder's Last Commit Review
**Commit**: Multi-field config projection (--pick PATH [PATH...])

### Changes Reviewed
- `core/cli.py` — 272 lines added (new flags: --pick, --grep, --env-expand, --backup)
- `core/configforge.py` — 33 lines added (env var expansion, improved parsing)
- `core/detector.py` — 61 lines added (Pkl format detection reordering)
- `tests/test_core.py` — 492 lines added (coverage for new features)
- New SEO page: extract-yaml-field.html

### Code Quality Assessment
**✅ No bugs found.** Changes are well-structured:

1. **--pick flag** — Extracts specific config paths. Single path outputs raw value; multiple paths output dict. Edge case handling: checks for missing paths before processing. ✅
2. **--env-expand flag** — Substitutes ${VAR} and $VAR references. Safe handling of missing env vars (leaves as-is, no silent data loss). ✅
3. **--backup suffix** — Before --in-place writes, saves original. Error handling on backup creation failure. ✅
4. **Pkl detection improvement** — Reorders detection sequence to check Pkl before URL (prevents false positives where Pkl syntax resembles domains). Pattern matching uses multiple heuristics (assignment, blocks, no colons). ✅

### Implementation Quality
- All new functions have docstrings explaining behavior
- Error messages are clear and actionable
- Backup suffix defaults to ".bak" but allows customization
- env_expand works recursively across nested dicts/lists/strings
- No security concerns (env var substitution is straightforward, doesn't allow code execution)

## Recommendations
The feature set is solid and all tests pass. Consider next:
- Monitor GitHub issues for real-world usage patterns
- Benchmark env_expand performance on large configs (recursive walk)
- Document --pick vs --get in user guide (single-path behavior equivalence)

---
**Report generated**: 2026-06-09 14:26:03 UTC
