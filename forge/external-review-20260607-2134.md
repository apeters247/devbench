# External Review: yq (mikefarah/yq) — Comment Preservation & YAML Roundtrip Issues
**Date:** 2026-06-07 21:34 UTC
**Prepared for:** ConfigForge positioning analysis

---

## Overview

This review examines open GitHub issues in the [mikefarah/yq](https://github.com/mikefarah/yq) repository related to **comment preservation**, **blank line loss**, **formatting fidelity**, and **YAML roundtrip correctness**. These are the areas where yq's architecture (parse → manipulate → serialize through an abstract syntax tree) fundamentally struggles, and where ConfigForge can differentiate.

---

## Key Open Issues (Ranked by Community Demand)

### 1. [#515 — yq write strips completely blank lines from the output](https://github.com/mikefarah/yq/issues/515)
- **State:** Open (since 2020-08-13)
- **👍 Reactions:** **151** (highest of all formatting/comment issues)
- **Comments:** 39
- **Labels:** `enhancement`
- **Broken behavior:** When `yq write` makes changes to a YAML file, all blank lines between keys are stripped. The YAML spec allows blank lines for readability, but yq's internal model discards them during serialization.
- **Example:**
  ```yaml
  # Input:
  foo:
    bar: 1

    baz: 2

  # Output after `yq w - foo.baz 3`:
  foo:
    bar: 1
    baz: 3
  ```
- **Maintainer stance:** This has been open for ~6 years with no fix. The comment thread (39 comments) shows repeated community frustration, with workarounds but no resolution.

### 2. [#465 — Preserve formatting with in place writing](https://github.com/mikefarah/yq/issues/465)
- **State:** Open (since 2020-06-15)
- **👍 Reactions:** **113** (second highest)
- **Comments:** 12
- **Labels:** `bug`
- **Broken behavior:** `yq w -i` removes blank lines *and* changes spacing before comments. The space between `nodeSelector:` and its inline comment `# +doc-gen:break` is collapsed. Section-separating blank lines vanish entirely.
- **Example:** Blank lines between `logLevel`, `annotations`, `podAnnotations` blocks are all stripped. Inline comment spacing (`# +doc-gen:break`) gets mangled.
- **Significance:** This is labeled as a **bug** (not just enhancement), yet has been open for 6 years unresolved.

### 3. [#442 — yq is losing comments during merge](https://github.com/mikefarah/yq/issues/442)
- **State:** Open (since 2020-05-13)
- **👍 Reactions:** **5**
- **Comments:** 1
- **Broken behavior:** When merging two YAML files with `yq merge`, all comments from the second file are discarded entirely. The first file's comments survive, but the merge target's documentation is lost.
- **Significance:** Core YAML workflow (merging configs) destroys metadata.

### 4. [#462 — Preserve original indentation level for list items](https://github.com/mikefarah/yq/issues/462)
- **State:** Open (since 2020-06-10)
- **👍 Reactions:** **26**
- **Comments:** 18
- **Broken behavior:** yq changes indentation levels for list items on write. Files that use 2-space or 4-space indentation get reformatted to yq's default.
- **Significance:** Creates large noisy diffs in version control when the only change is a small value update — pure formatting churn.

### 5. [#566 — Multiline strings (block scalars) not preserved with trailing whitespace](https://github.com/mikefarah/yq/issues/566)
- **State:** Open (since 2020-10-16)
- **👍 Reactions:** **23** (21 👍 + reactions)
- **Comments:** 13
- **Labels:** `bug`
- **Broken behavior:** Block scalar strings (`|` style) with trailing whitespace are converted to quoted strings. Roundtrip breaks the original format.
- **Example:** `this: |\n  should \n  really work` → `this: "should \\nreally work"`

### 6. [#1726 — Comments are missing when querying sub nodes](https://github.com/mikefarah/yq/issues/1726)
- **State:** Open (since 2023-07-13)
- **👍 Reactions:** **1**
- **Comments:** 1
- **Labels:** `bug`, `v4`
- **Broken behavior:** When querying a sub-node that has comments, "foot comments" (comments at the end of a block) are incorrectly associated with the parent node instead of the correct child. Querying `.foo.bar` drops a comment that appears at the end of the `bar` block, while querying `.foo` preserves it.

### 7. [#2516 — yq loses comments around merge‑tags when used in `ireduce`](https://github.com/mikefarah/yq/issues/2516)
- **State:** Open (since 2025-11-18)
- **👍 Reactions:** **0** (new issue)
- **Comments:** 0
- **Labels:** `bug`, `v4`
- **Broken behavior:** Using `ireduce` to merge documents causes comments before `<<` merge keys to be dropped. Simple `yq '.'` preserves them, but the pipeline operator discards them. Comments on the same line as keys get misplaced.

### 8. [#2608 — Single string scalar output not quoted (breaking roundtrip safety)](https://github.com/mikefarah/yq/issues/2608)
- **State:** Open (since 2026-02-13)
- **👍 Reactions:** **0** (new issue)
- **Comments:** 1
- **Labels:** `bug`, `v4`
- **Broken behavior:** When a YAML file consists of a single string scalar, `yq eval` outputs the string *unquoted*, which causes it to be reinterpreted as YAML syntax rather than as a string value. E.g. `"this: should really work"` → output `this: should really work` (parsed as a mapping).

---

## Other Related Issues (Recently Handled / Closed)

| Issue | Title | Status | Relevance |
|-------|-------|--------|-----------|
| #2572 | Spurious blank line in yq v4.50.1 output | Closed | Blank-line regression fixed |
| #2588 | TOML: comments inside table cause hierarchy flattening | Closed | Comment-scope bug in TOML parser |
| #2589 | Fix TOML table scope after comments | Closed | Fix merged |
| #2619 | Preserve empty lines in HCL | Open (PR) | Same class of problem in HCL format |
| #2686 | Preserve empty TOML arrays in tables | Closed | Roundtrip fix for empty arrays |

---

## Root Cause Analysis

yq's architecture relies on parsing YAML into a Go data structure (using `goccy/go-yaml`), manipulating it, and then re-serializing. This fundamental design choice creates several systemic problems:

1. **Comments are metadata, not data** — yq (and most YAML libraries) treat comments as incidental decorations on the AST, not as first-class citizens. They are stored as auxiliary fields (`HeadComment`, `LineComment`, `FootComment`) on nodes, but transformations and pipelines easily lose this attachment.

2. **Blank lines have no semantic meaning in the data model** — YAML's blank lines are purely stylistic, so the data model discards them entirely. There is no mechanism to preserve structural whitespace.

3. **Formatting details (indentation, quoting style, scalar style) are fragile** — The serializer makes best-effort guesses for output style, but these guesses are wrong in many edge cases (string scalars, trailing whitespace, block scalars).

4. **Incremental / targeted editing is impossible** — yq cannot make a single small change while keeping everything else exactly as it was. It must re-serialize the entire document, which inevitably introduces formatting differences.

5. **Architecture delegation** — yq depends on the `goccy/go-yaml` library for its comment model. Any limitations in that library cascade directly to yq. The comment preservation model fundamentally requires the parser to retain positional metadata, and the serializer to reproduce it faithfully — neither is a design goal of standard YAML libraries.

---

## How ConfigForge Can Position as the Solution

ConfigForge has a unique opportunity to exploit this gap. Here's a positioning strategy:

### Core Value Proposition
**"Edit YAML without breaking it. Zero formatting changes, zero comment loss, zero surprises."**

### Key Differentiators (Mapped to yq's Pain Points)

| yq Weakness | ConfigForge Solution | Marketing Angle |
|-------------|---------------------|-----------------|
| Blank lines stripped (#515, #465) | **Surgical AST patching** — parse once, modify only the target node, re-emit byte-for-byte identical output | "Your YAML, unchanged™. Blank lines, spacing, and formatting always preserved." |
| Comments lost during merge (#442) | **Comment-aware merge** — comments are first-class citizens in the data model | "Merging configs shouldn't mean losing documentation." |
| Formatting churn on write (#462) | **Source-fidelity serializer** — preserve original indentation, quoting, and style | "Zero-diff edits. Your git history stays clean." |
| Block scalar mangling (#566) | **Style-preserving re-encoding** — block scalars stay block scalars | "Block scalars, flow mappings, quoted strings — all preserved exactly as written." |
| Sub-node comment misattribution (#1726) | **Correct comment scoping** — foot comments anchored to the right AST node | "Comments stay where you put them, even in sub-queries." |
| Roundtrip safety failures (#2608) | **Type-safe quoting** — strings that look like YAML syntax are quoted on output | "What you put in is what you get out. Roundtrip guaranteed." |
| Implicit data-model assumptions | **Explicit document model** — comments, blank lines, and formatting are stored as an ordered sequence of line-level tokens, not discarded during parsing | "YAML isn't just data. It's a document." |

### Target Audience Messaging

1. **DevOps/Platform teams** who manage Helm values, Kubernetes manifests, and CI/CD configs — they need tooling that won't blow up their git history with formatting noise.
2. **Config-heavy monorepo teams** who do bulk config migrations / transformations — comment loss is a real documentation loss.
3. **YAML linting/tooling ecosystem** — yq is often used as a preprocessing step; any format corruption cascades.
4. **Technical writers / docs-as-code teams** — YAML comments are often the only documentation embedded in config files.

### Potential Headlines / Positioning Statements

- **"yq was designed for querying. ConfigForge was designed for editing."**
- **"151 people upvoted 'don't delete my blank lines.' We heard them."**
- **"Your YAML comments are documentation. They shouldn't vanish during a config edit."**
- **"Stop fixing formatting noise. Edit configs, not whitespace."**

### Recommended Next Steps

1. Build a side-by-side demo comparing `yq eval` vs ConfigForge on the exact examples from issues #515, #465, and #442.
2. Publish a blog post: *"6 Years and 151 Upvotes: Why yq Can't Preserve Your YAML (And How ConfigForge Does)"*
3. Mention the specific issue numbers in documentation (/cc comparison matrix) so users searching for these problems find ConfigForge.
4. Target a comment-fidelity guarantee in ConfigForge's README — something concrete like *"ConfigForge guarantees 100% comment preservation across all edit operations."*

---

## Appendix: Complete List of Open Issues in This Category

| # | Title | 👍 | Open Since | Last Update |
|---|-------|----|-----------|-------------|
| 515 | yq write strips completely blank lines from the output | **151** | 2020-08-13 | 2026-05-01 |
| 465 | Preserve formatting with in place writing | **113** | 2020-06-15 | 2026-04-28 |
| 462 | Preserve original indentation level for list items | **26** | 2020-06-10 | 2025-10-05 |
| 566 | Multiline strings not preserved with trailing whitespace | **23** | 2020-10-16 | 2025-11-28 |
| 442 | yq is losing comments during merge | **5** | 2020-05-13 | 2020-12-03 |
| 1726 | Comments missing when querying sub nodes | **1** | 2023-07-13 | 2023-07-28 |
| 2516 | yq loses comments around merge-tags in `ireduce` | **0** | 2025-11-18 | 2025-11-18 |
| 2608 | Single string scalar not quoted (roundtrip safety) | **0** | 2026-02-13 | 2026-04-10 |

**Total reactions on open issues: ~319 👍** — clear, sustained community demand.

---

*Report generated by Hermes Agent automated review process.*
