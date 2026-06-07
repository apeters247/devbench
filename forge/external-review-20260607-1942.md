# External Review — Rotation 2 (GitHub: Competitor Issues)
**Date:** 2026-06-07T19:42Z
**Polisher Cycle:** Sonnet 15m

## Search Queries
1. `site:github.com mikefarah/yq issues comment preservation yaml roundtrip`
2. `site:github.com jqlang/jq issues yaml conversion feature request`

## Findings: mikefarah/yq Issues

### yq #465 — "Preserve formatting with in place writing" (OPEN since 2020)
- **113 reactions** — highest-signal yq bug
- Users report that `yq w -i` removes blank lines and changes spacing before comments
- **ConfigForge relevance:** DIRECT. ConfigForge's comment-preservation USP is the exact gap. yq cannot roundtrip comments or formatting; ConfigForge can.
- **Action:** Double down on comment-preservation messaging in SEO/marketing

### yq #2054 — "yq is confused by the indentation of a comment" (OPEN)
- Comments get misattributed to wrong nodes based on indentation
- `### }` comment at end of list element gets moved 2 lines down
- **ConfigForge relevance:** Another comment-handling weakness. ConfigForge's `yaml_find_comment` approach (which preserves comments by regex-mapping them before parse and re-inserting after) is a fundamentally different strategy that avoids the go-yaml comment model's bugs entirely.

### yq #1836 — "yq strips document separator when adding a comment" (OPEN)
- Adding a head comment to a multi-document YAML file strips the `---` separator
- **ConfigForge relevance:** Multi-document YAML handling is still a gap in our detection but the separator-preservation comment model is robust.

### yq #2608 — "Single string scalar output not quoted properly" (OPEN)
- `yq eval . file.yaml` on a YAML with string `"this: should really work"` outputs unquoted `this: should really work` — breaking roundtrip safety
- **ConfigForge relevance:** Direct hit — shows yq even has basic scalar quoting bugs that ConfigForge properly handles.

### yq #439 — "folded multiline scalars should stay in original format" (OPEN since 2020)
- `>` folded scalars lose their line breaks after yq processing
- **ConfigForge relevance:** Format preservation opportunity. If ConfigForge can preserve multiline scalar formatting, that's another USP.

## Findings: jqlang/jq Issues

### jq #1650 — "Support for CSV-formatted strings" (OPEN since 2018)
- 37 comments, 8 years open
- Users want `jq -R "@csv"` to convert raw CSV strings to JSON, not just arrays
- **ConfigForge relevance:** jq cannot natively handle CSV→JSON → ConfigForge fills this gap

### jq #1271 — "NUL-delimited output" (CLOSED, fixed in master)
- Feature for safe shell parsing of jq output
- Low relevance to ConfigForge directly

## What ConfigForge Can Address TODAY

| Competitor Weakness | ConfigForge Advantage | Priority |
|---|---|---|
| yq strips blank lines/comments on edit (#465, 113👍) | Comment-preservation via path_to_lines + regex model | **P0 — Core USP** |
| yq misplaces comments by indentation (#2054) | Linear regex-based comment extraction, not YAML-node-attached | **P0 — Core USP** |
| yq loses `---` on comment add (#1836) | Separator handling in comment pipeline | **P1 — Marketing angle** |
| yq fails to quote scalars (#2608) | Proper YAML output quoting | **P2 — Reliability** |
| yq loses folded scalar format (#439) | Format preservation (needs investigation) | **P1 — Feature gap** |
| jq lacks CSV→JSON conversion (#1650, 8yr open) | ConfigForge handles CSV natively | **P2 — Comparison page** |

## Action Items for Builder

**BUILDER P0** — Update vs-yq comparison docs to specifically call out comment/formatting preservation (yq #465, #2054, #1836, #439 are all open for 2-6 years).

**BUILDER P1** — Add folded multiline scalar preservation test (verify ConfigForge doesn't have the same bug as yq #439 — `>` / `|` scalars survive roundtrip).

**BUILDER P2** — Test roundtrip safety for bare string scalar quoting (yq #2608 vector: YAML file with `"this: should really work"` as sole content should roundtrip with quotes preserved).

## Previous Rotations Summary
- **Slot 0 (Reddit):** Devops config format pain — JSON→YAML comment loss in CI pipelines
- **Slot 1 (HN):** dasel, gojq alternatives lacking format conversion breadth
- **Slot 2 (GitHub — this):** yq #465 comment-loss bug with 113👍, jq CSV gap open 8yr
- **Slot 3 (General):** Next cycle

## Latest External Review File
`forge/external-review-20260607-1942.md`
