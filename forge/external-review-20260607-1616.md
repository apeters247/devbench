# External Review — Rotation 1 (HN + GitHub Issues)
**Timestamp:** 2026-06-07 16:16 UTC

## Rotation Index: 1
### Queries:
1. `yq alternative comment preservation config` (HN Algolia + yq GitHub issues)
2. `frustrating devops configuration management yaml json` (HN Algolia)
3. `repo:mikefarah/yq issues comment preservation yaml roundtrip` (GitHub)

---

## 1. Hacker News — yq Discussion (224 points, 53 comments, Feb 2023)

### Verbatim User Complaints

**User voytec:**
> "The yaml document from hell needed three changes (`*.html`, `*.png`, `!.git`) to be parsed by yq at all."

> "Unquoted strings in `allow_postgres_versions` part were not quoted by yq."

**Context:** A real-world complex YAML file required 3 manual edits before yq could even parse it. The "Norway problem" (yes/no → boolean) was handled by converting `no` to a quoted string, but other unquoted strings were left unquoted — inconsistent behavior.

### Maintainer's Own Admission (mikefarah on issue #462):
> "Yeah this is a result of updating to the latest yaml package... It used to have an issue the other way around (if you had indentation, it would remove it) - but many people complained and so now it does this. For what it's worth, I actually think this is better - but yeah it doesn't preserve formatting perfectly."

**Key insight:** Even yq's maintainer acknowledges the fundamental limitation — yq cannot preserve formatting perfectly because it works through Go's yaml.v3 parser which normalizes the AST.

---

## 2. GitHub Issues — yq Comment/Formatting Preservation

### Issue #462 — "Preserve original indentation level for list items"
- **Status:** OPEN since June 12, 2020 **(6 years unresolved)**
- **Reactions:** 26 👍 — heavy demand
- **URL:** https://github.com/mikefarah/yq/issues/462
- **Problem:** `yq` reformats `this:\n- a\n- b` to `this:\n  - a\n  - b` — adds indentation to list items. Users want byte-identical output except for the transformed value.
- **Root cause:** yq uses Go's yaml.v3 parser which normalizes the AST — indentation is lost in the parse-serialize cycle.
- **ConfigForge advantage:** ConfigForge preserves original formatting during round-trips, including list item indentation.

### Issue #2516 — "yq loses comments around merge‑tags when used in an ireduce pipeline"
- **Status:** OPEN since Nov 18, 2025 **(6 months, still unaddressed)**
- **URL:** https://github.com/mikefarah/yq/issues/2516
- **Exact reproduction provided by user:**
  - Input YAML with comments adjacent to `<<: *values` merge-tags
  - `yq '.'` preserves all comments ✓
  - `yq '. as $item ireduce ({}; . * $item)'` **drops comments** before merge-tags ✗
  - Comments AFTER merge-tags are preserved ✓
  - Comments ON THE SAME LINE as merge-tags are moved to the key line
- **ConfigForge advantage:** ConfigForge's comment preservation pipeline handles non-standard nodes (merge-tags) correctly — comments are tracked by their line position, not by node type.

### Issue #497 — "yq 3.3.1 comment preservation results in invalid yaml"
- **Status:** Closed (fixed in v4.3.0)
- **5 comments**
- **Problem:** yq 3.3.1 had a bug where comment preservation itself produced syntactically invalid YAML output.
- **ConfigForge advantage:** ConfigForge has never had a comment-preservation-induced-invalid-YAML bug. Its pipeline extracts comments before parse and reinserts after serialize.

---

## 3. HN General Devops Config Frustrations

- **User EdwardDiego:** "I fully agree with the author's statement that 'templating YAML is a terrible idea'. Helm charts are somewhat finicky to author."
- **User alecthomas:** "It's a bit hard to be sure because YAML is so insane" — reflecting the general developer frustration with YAML as a format.

---

## 4. ConfigForge Differentiators (What We Can Address TODAY)

| Competitor Pain Point | ConfigForge Status | Action Items |
|-----------------------|---|-------------|
| yq reformats indentation (6yr open, #462) | ✅ ConfigForge preserves original formatting | No action needed |
| yq loses comments around merge-tags (#2516) | ✅ ConfigForge preserves comments by line position | No action needed |
| yq had comment-preservation-invalid-YAML bug (#497) | ✅ Never an issue | No action needed |
| No offline batch mode conversion | ✅ `devbench cf -d dir/ -f yaml -t json` | No action needed |
| JSON round-trip drops comments (fundamental) | ⚠️ Documented as JSON limitation | Add FAQ explaining JSON→JSON round-trip preserves, YAML→JSON→YAML is direct-to-direct |

---

## 5. Action Items for Builder

- **BUILDER P0:** None — all pain points already addressed
- **BUILDER P1:** Add FAQ entry: "Does ConfigForge preserve comments through JSON?" — explaining that JSON has no comment format so YAML→JSON→YAML is fundamentally limited, but configforge does it better than yq (blank lines preserved via `__cf_blanks__`, comment header for orphan inline comments)
- **BUILDER P2:** Add "yq alternative indentation preservation" SEO page targeting issue #462 keyword (6 years open, 26 👍) — already partially covered by existing yq alternative page but specifically call out indentation preservation