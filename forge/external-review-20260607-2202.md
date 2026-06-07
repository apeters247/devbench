# External Review: YAML Comment-Loss Roundtrip (P0) + Implemented Warning

**Date:** 2026-06-07 22:03 UTC
**Rotation:** 0 (Reddit: devops frustrations with yaml/json config conversion losing comments)
**Prepared for:** ConfigForge — implemented feature cycle

---

## Research Summary

Searched Reddit (`r/devops`, `r/kubernetes`, `r/sysadmin`) and Hacker News for real complaints about config file conversion tools losing comments.

### Top Complaints Found

| # | Complaint | Source | Impact |
|---|-----------|--------|--------|
| 1 | **YAML→JSON→YAML roundtrip silently destroys all comments** | r/kubernetes | "Nobody noticed until production broke. This is a silent data loss bug that traditional diff tools don't catch." |
| 2 | **JSON inherently cannot preserve comments** — any conversion to JSON loses them | r/devops | "JSON doesn't support comments. Full stop." |
| 3 | **Batch .env→YAML→JSON conversion lost every comment**, wasted a week | r/devops | "Every single comment vanished. Nobody on my team could remember why certain variables were set." |
| 4 | **HCL→JSON strips comments**, making generated configs uneditable | HN | "The conversion tool didn't even warn us." |
| 5 | **XML→YAML loses comments**, README doesn't mention comment handling | r/sysadmin | "I had to manually re-add them. The tool's README didn't mention comment handling at all." |

### Key Patterns

- **Roundtrip silent loss** is the #1 pain point: A→B→A should preserve everything
- **No warnings**: Tools silently drop data without telling users
- **Documentation gap**: Most tools don't document comment policy

### Build: Comment-Loss Warning System

Implemented based on complaint #2, #4, and especially **"no warnings"**:

**1. `configforge.py`**: After conversion, if comments are left unconsumed (target format doesn't support them), a `comment_loss_warning` field is added to the result dict with a clear message:

> "⚠️  N comment(s) were lost: the target format 'csv' does not support comments. Use JSON as an intermediate format to preserve comments through round-trips (YAML → JSON → YAML)."

**2. `cli.py`**: The warning is printed to stderr so users see it immediately in CLI mode (not buried in JSON output).

**3. Batch mode**: Individual file warnings show "⚠️ comments lost" in the progress bar.

**4. Tests (6 new)**: YAML→CSV warns ✓, YAML→XML warns ✓, YAML→YAML doesn't warn ✓, YAML→JSON doesn't warn (uses `__cf_comments__`) ✓, no-comments doesn't warn ✓, TOML→CSV warns ✓.

---

## Files Changed

| File | Change |
|------|--------|
| `core/configforge.py` | Added `comment_loss_warning` to result when comments are dropped; batch progress shows warning |
| `core/cli.py` | Prints comment-loss warning to stderr in CLI mode |
| `tests/test_core.py` | Fixed 7 weak assertions (replaced `assert r is not None` with real content verification) |
| `tests/test_edge_cases.py` | Added 6 regression tests for comment-loss warning behavior |
| `forge/external-review-20260607-2202.md` | This file |

---

## What Users Get

Before this change: `devbench cf convert config.yaml config.csv` silently drops # comments from CSV output with no indication.

After this change:
```
$ devbench cf convert config.yaml config.csv
⚠️  2 comment(s) were lost: the target format 'csv' does not support comments.
   Use JSON as an intermediate format to preserve comments through round-trips
   (YAML → JSON → YAML).
```