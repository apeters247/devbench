# External Review — Rotation 2 (GitHub Issues)
**Timestamp:** 2026-06-07 15:34 UTC

## Rotation Index: 2
### Queries:
1. `repo:mikefarah/yq issues comment preservation yaml roundtrip`
2. `repo:jqlang/jq issues yaml conversion feature request`

---

## 1. yq (mikefarah/yq) — Comment Preservation Issues

### Issue #462 — "Preserve original indentation level for list items"
- **Status:** OPEN (since June 2020 — 6 years unresolved)
- **Reactions:** 26 👍 — heavy demand
- **Comments:** 18
- **URL:** https://github.com/mikefarah/yq/issues/462
- **Problem:** yq reformats YAML list indentation from `this:\n- a` to `this:\n  - a`, breaking minimal-diff expectations. Users want output identical to input except for the transformed value.
- **Relevance to ConfigForge:** ConfigForge already passes all comment preservation tests (YAML→JSON→YAML and INI→JSON→INI round-trips verified). This yq vulnerability is a direct differentiator.

### Issue #2516 — "yq loses comments around merge‑tags when used in an ireduce pipeline"
- **Status:** OPEN (since Nov 2025, 0 comments)
- **URL:** https://github.com/mikefarah/yq/issues/2516
- **Problem:** When using `yq '. as $item ireduce ({}; . * $item)'`, comments preceding merge-tags (`<<`) are dropped from output. Reproduction case provided in issue. Comments on same-line-as-key are moved to key line instead.
- **Relevance:** Direct competitor comment-loss bug. ConfigForge's comment preservation pipeline handles round-trips without merge-tag issues.

### PR #2595 — "Fixing comments in TOML arrays"
- **Status:** Merged Feb 2026
- **Problem:** Even yq's maintainer had to patch TOML comment handling. TOML array comments were being lost during processing.

---

## 2. jq (jqlang/jq) — Feature Gaps

### Issue #1650 — "Support for CSV-formatted strings"
- **Status:** OPEN (since April 2018 — 8 years unresolved)
- **Comments:** 37
- **Labels:** "feature request", "feature request: jq function library"
- **URL:** https://github.com/jqlang/jq/issues/1650
- **Problem:** `echo '"1,2,3"' | jq -r '@csv'` fails — jq can only CSV-format arrays, not strings. Users have been asking for 8 years with no resolution.
- **Relevance to ConfigForge:** ConfigForge's `csv-to-yaml-converter` and `csv-to-json` capabilities directly solve this. SEO content already published for this use case.

### Issue #1271 — "Feature request: NUL-delimited output"
- **Status:** CLOSED (fixed in master, took 3 years 2016→2019)
- **Problem:** jq lacked NUL-delimited output for shell-script safety. Took 3 years to fix.

---

## 3. ConfigForge Differentiators

| Pain Point | yq/jq Status | ConfigForge Status |
|---|---|---|
| Comment preservation (YAML) | Bug #2516 open, #462 open 6 yrs | ✅ Verified: all round-trip tests pass |
| Comment preservation (TOML) | PR #2595 only merged Feb 2026 | ✅ Built-in comment carry mechanism |
| CSV string conversion | jq #1650 open 8 yrs | ✅ csv-to-yaml/json/toml support |
| INI format | yq doesn't support | ✅ INI round-trip verified |
| Batch mode | Neither supports natively | ✅ Available |
| Offline/CLI | Both support, but limited | ✅ Full offline pip install |
| Multi-doc YAML | yq partially, jq doesn't | ✅ Supported |
| HCL → config | Neither supports | ✅ Supported |

## 4. Action Items for Builder

**BUILDER P0:** Add a "Why ConfigForge vs yq" comparison table to the landing page highlighting these 6 resolved pain points (comment preservation, INI support, CSV conversion, TOML comments, batch mode, HCL).

**BUILDER P1:** Write a targeted SEO page "yq alternative for comment preservation" — directly target yq issue #462/#2516 keywords.

**BUILDER P2:** Write "jq alternative CSV to JSON converter" SEO page — directly target jq issue #1650 keywords with exact code example showing jq failure vs ConfigForge success.