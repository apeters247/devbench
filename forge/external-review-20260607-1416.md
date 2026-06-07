# External Review — Rotation 1 (HN: Config Tool Complaints)

**Date**: 2026-06-07 14:16 UTC
**Rotation Index**: 1
**Queries**: `site:news.ycombinator.com yq jq alternative config file format conversion`, `site:news.ycombinator.com frustrating devops configuration management tools`

---

## 1. Searches Performed

- **HN Algolia**: yq, "yq YAML tool", "yaml config converter", yq Show HN
- **GitHub Issues**: mikefarah/yq — comment preservation, indentation, format conversion

---

## 2. Verbatim User Complaints Found

### A. HN Discussion: "yq: command-line YAML, JSON, XML, CSV and properties processor" (224 pts, 53 comments)

| Complaint | Source | Verbatim Quote |
|-----------|--------|----------------|
| yq can't parse real-world YAML without edits | voytec (Feb 2023) | *"The yaml document from hell needed three changes (*.html, *.png, !.git) to be parsed by yq at all."* |
| yq doesn't quote unquoted strings properly | voytec | *"'Norway problem' is not a problem as 'no' was converted to a quoted string. Unquoted strings in 'allow_postgres_versions' part were not quoted by yq."* |
| gojq doesn't preserve key order | 0cf8612b2e1e | *"gojq does not preserve key order or offer option to sort keys. Which is a non-starter for me."* |
| YAML templating is painful | wrldos | *"Templating YAML is up there with putting lead in gas and invading Ukraine."* |
| JMESpath abandoned; fragmented standards | justin_oaks | *"The JSON expressions used by MySQL and AWS CLI (JMESpath) are extremely limited compared to jq. Not only do we end up learning multiple JSON path variations, but most are nearly useless."* |
| YAML/JSON burnout | pacha (Show HN: Cels) | *"I'm pretty sure my health is taking a hit from too much exposure to YAML and JSON. We still don't have a straightforward way to patch these formats."* |

### B. GitHub Issues — mikefarah/yq

| Issue | Status | Age | Complaints |
|-------|--------|-----|------------|
| **#462**: Preserve original indentation level for list items | **OPEN** | 6 years (since Jun 2020) | yq reformats list item indentation (e.g., `- a` → `  - a`). 26 reactions. Maintainer: *"just a known issue."* User stristr: *"yq is not suitable as a 'Swiss army knife utility' for large-scale changes if using it results in large-scale changes that consist largely of whitespace."* |
| **#2516**: yq loses comments around merge‑tags in ireduce pipeline | **OPEN** | 7 months (Nov 2025) | Comments *preceding* merge-keys (`<<`) are silently dropped when using `ireduce`. Comments moved from key line to wrong node. |
| **#497**: yq 3.3.1 comment preservation results in invalid yaml | Closed | 2021 | Historical evidence that comment preservation has always been fragile in yq. |

---

## 3. Which Pain Points ConfigForge Can Address TODAY

| Pain Point | ConfigForge Status | Action Needed? |
|------------|-------------------|----------------|
| ✅ **Comment preservation** | Already verified: 919 comments survive YAML round-trip (helm_values.yaml test) | None — this is a proven differentiator vs yq |
| ✅ **Indentation preservation** | ConfigForge preserves original indentation (list items keep their level) — already tested | None — already works |
| ✅ **Multi-format conversion** (9/11 formats) | Exceeds yq (which supports YAML/JSON/XML/CSV/properties) and matches jq+plugins | None — already a strength |
| ✅ **Offline, private, no network** | Already a core feature | None |
| ✅ **Multi-doc YAML round-trip** | Already tested: 19-doc K8s manifest round-trips correctly | None |
| ✅ **Big integer precision** | Already tested: 12345678901234567890 survives YAML→JSON→YAML | None |
| ✅ **Null normalization** | Already tested: YAML `~` → JSON `null` (not string "None") | None |
| ⚠️ **Key order preservation** | Needs verification — if ConfigForge preserves insertion order, this is a key differentiator vs gojq | **Verify and document** |
| ⚠️ **YAML "document from hell"** | Needs testing against Ruud van Asseldonk's edge cases | **BUILDER P1**: Add regression tests based on "the YAML document from hell" |
| ⚠️ **Unquoted string type inference** | ConfigForge should handle ambiguous YAML strings (like "no"/"yes"/version numbers) correctly | **BUILDER P1**: Add edge case tests for Norwegian/boolean YAML strings |

---

## 4. Action Items for Builder

```
BUILDER P0: Add regression test for yq#2516's scenario — comments preceding merge-keys (`<<`) should NOT be dropped on ireduce-style YAML merge operations. ConfigForge likely handles this correctly; needs a test to prove it.

BUILDER P1: Test ConfigForge against "the YAML document from hell" (ruudvanasseldonk.com/2023/01/11/the-yaml-document-from-hell) — yq required 3 edits to even parse it. If ConfigForge handles it natively, document this as a key differentiator.

BUILDER P1: Add edge-case tests for Norwegian/boolean YAML strings ("no", "yes", "true", "false", version numbers like "2.0") to verify type inference doesn't mangle them. yq unquotes some and quotes others inconsistently.

BUILDER P2: Verify and document key-order preservation in all output formats — gojq's failure to preserve key order is a "non-starter" for human review. If ConfigForge preserves it, add a comparison table to landing page.
```

---

## 5. Comparison Summary

| Capability | yq | jq/gojq | ConfigForge |
|-----------|----|---------|-------------|
| Comment preservation | ❌ Loses comments (#2516, #497) | N/A (JSON only) | ✅ Verified (919 comments survive) |
| Indentation preservation | ❌ Known issue (#462, 6 yrs open) | N/A | ✅ Preserved |
| Key order preservation | ✅ | ❌ gojq | ⚠️ Needs verification |
| Formats supported | 5 | 1 (JSON, +plugins) | **9-11** |
| Parse hell-YAML | ❌ Required 3 edits | N/A | ⚠️ Needs testing |
| Offline | ✅ | ✅ | ✅ |
| Batch conversion | ⚠️ Limited | ❌ | ✅ |