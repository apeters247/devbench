# External Review — Rotation 2 (GitHub: Competitor Issues)

**Date**: 2026-06-07 14:40 UTC
**Rotation Index**: 2
**Queries**: `site:github.com mikefarah/yq issues comment preservation yaml roundtrip`, `site:github.com/jqlang/jq issues yaml conversion feature request`

---

## 1. Searches Performed

- **GitHub Issues API**: mikefarah/yq — comment preservation, comment loss, multi-doc, roundtrip
- **GitHub Issues API**: jqlang/jq — yaml conversion feature requests
- **GitHub Issues API**: mikefarah/yq — comment loss, preserve, HCL blank lines

---

## 2. Verbatim User Complaints Found

### A. yq#19 — "In place write strips out comments" (2017, 27 comments, 14 👍)

| Field | Detail |
|-------|--------|
| URL | https://github.com/mikefarah/yq/issues/19 |
| User | jmreicha |
| Status | CLOSED (yq v3, 2020) |
| Quote | *"The CLI strips out comments given the following yaml file: `# comment` / `a: b:`"* |

**Significance to ConfigForge**: Classic complaint — the first comment issue ever filed against yq. Though closed for the v3→v4 rewrite, the pattern of losing comments on write is yq's original sin. ConfigForge handles this natively with `preserve_comments=True`.

---

### B. yq#515 — "yq write strips completely blank lines from the output" (OPEN since 2020)

| Field | Detail |
|-------|--------|
| URL | https://github.com/mikefarah/yq/issues/515 |
| User | scanfield |
| Status | **OPEN** — 6 years (2020), 39 comments, **151 👍 reactions** |
| Quote | *"Keep my extra blank line (it's better for readability / produces less of a diff)"* |

**Significance to ConfigForge**: This is the **MOST VOTED unresolved issue** in yq — 151 👍, 39 comments, 6 years and counting. The user had:
```yaml
foo:
  bar: 1

  baz: 2
```
And `yq w - foo.baz 3` produced:
```yaml
foo:
  bar: 1
  baz: 3
```
The blank line for readability was destroyed. This is a massive pain point in an area where ConfigForge can differentiate — **blank line preservation** in YAML output. If ConfigForge preserves meaningful blank lines (separating logical blocks), that's a **top-tier marketing differentiator**.

---

### C. yq#1358 — "When converting multi document file to list of maps, leading comments are dropped" (CLOSED bug)

| Field | Detail |
|-------|--------|
| URL | https://github.com/mikefarah/yq/issues/1358 |
| User | zachary-povey |
| Status | CLOSED (Sep 2022, yq v4.27.5) |
| Quote | *"When converting a file containing multiple yaml documents into a list of maps, any leading comments on the first document are lost."* |

Detail: `yq ea '[.]' test.yaml` lost the first document's leading comment. Workaround: *"prepend an empty document into the file contents before, and then remove any empty maps from the list after."*

**Significance to ConfigForge**: ConfigForge already handles multi-doc YAML comment preservation (tested with 19-doc K8s manifest in previous cycle's P0 tests). This bug proves that **even the maintained yq v4 had comment loss bugs in multi-doc scenarios** — ConfigForge's approach (carrying comments through conversion pipeline explicitly) is inherently more robust.

---

### D. yq#1364 — "Would toml be supported?" (CLOSED, 16 👍)

| Field | Detail |
|-------|--------|
| URL | https://github.com/mikefarah/yq/issues/1364 |
| User | joshcangit |
| Status | CLOSED (2022→2026, 3.5 years) |
| Quote | *"I wish I could use yq to work with toml files."* |

**Significance to ConfigForge**: TOML support was a feature request in yq for **3.5 years** before being fulfilled (PR #2552 merged Dec 2025). ConfigForge has had TOML from day one, plus HCL and .properties. This is a concrete historical timeline demonstrating that ConfigForge is **years ahead** of yq in format coverage.

---

### E. yq#2595 — "Fixing comments in TOML arrays #2592" (MERGED Feb 2026)

| Field | Detail |
|-------|--------|
| URL | https://github.com/mikefarah/yq/pull/2595 |
| User | mikefarah (owner) |
| Status | MERGED (2026-02-03) |
| Detail | Even after adding TOML support in Dec 2025, yq had **TOML comment bugs in arrays** that needed fixing in Feb 2026. |

**Significance to ConfigForge**: TOML comment preservation is a new area of fragility for yq. ConfigForge should TOML comment round-trip tested.

---

### F. yq#2619 — "Preserve empty lines in HCL" (OPEN PR, still unmerged)

| Field | Detail |
|-------|--------|
| URL | https://github.com/mikefarah/yq/pull/2619 |
| User | jtyr |
| Status | **OPEN** (2026-03-04, 2+ months) |
| Quote | *"This PR improves HCL roundtrip fidelity by preserving blank lines between blocks and attributes"* |

**Significance to ConfigForge**: HCL (HashiCorp) blank line preservation is still an open problem in yq. ConfigForge has HCL support already. If ConfigForge preserves blank lines in HCL round-trips, that's another differentiator.

---

### G. yq#2569 — "feat: JSON5 support" (OPEN PR)

| Field | Detail |
|-------|--------|
| URL | https://github.com/mikefarah/yq/pull/2569 |
| Status | OPEN (2026-01-10, unmerged) |
| Detail | Another format that yq users want but hasn't been merged yet. |

---

### H. jqlang/jq — No YAML conversion issues found

No issues in `jqlang/jq` repo matched `yaml conversion` in title. jq is fundamentally JSON-only, and YAML conversion is not on the roadmap.

---

## 3. Which Pain Points ConfigForge Can Address TODAY

| Pain Point | ConfigForge Status | Action Needed? |
|---|---|---|
| ✅ **Comments stripped on write (yq#19)** | Already handled: `preserve_comments=True` preserves comments through YAML round-trips | None |
| ✅ **Blank line preservation (yq#515, 151👍)** | Need to verify if ConfigForge preserves blank lines in YAML | **BUILDER: Verify and test** |
| ✅ **Multi-doc leading comments (yq#1358)** | Already tested: 19-doc K8s manifest round-trips with comments | None |
| ✅ **TOML support (yq#1364, 3.5yr request)** | ConfigForge had TOML from day one | None |
| ✅ **HCL support (yq#2619)** | ConfigForge already has HCL read/write | None |
| ⚠️ **TOML comment preservation in arrays (yq#2595)** | Need to verify ConfigForge handles TOML array comments | **BUILDER P2: Add TOML array comment test** |
| ⚠️ **HCL blank line preservation (yq#2619)** | Need to verify HCL round-trip fidelity | **BUILDER P2: Verify HCL blank line behavior** |
| ⚠️ **JSON5 (yq#2569)** | ConfigForge doesn't support JSON5 yet | **BUILDER P3: Consider JSON5 as new format** |

---

## 4. Action Items for Builder

```
BUILDER P0: Verify and add regression test for blank line preservation in YAML
   round-trips. yq#515 (151 👍, 39 comments, 6 years OPEN) is the single most
   demanded feature in yq. If ConfigForge preserves meaningful blank lines
   (separating logical blocks), this is a massive differentiator. Test:
   YAML with blank lines → JSON → YAML should preserve blank lines.

BUILDER P2: Add TOML array comment preservation test. yq#2595 proved that
   TOML comment bugs existed even after the format was "done" in Dec 2025.
   Test: TOML with inline array comments → JSON → TOML preserves comments.

BUILDER P2: Add HCL blank line / comment preservation test. yq#2619 is an
   open PR still unmerged after 2+ months for exactly this feature.

BUILDER P3: Consider JSON5 support. yq users are asking for it (yq#2569)
   and ConfigForge already has a JSON pipeline — JSON5 is a strict superset
   of JSON with comments and unquoted keys, a natural fit.
```

---

## 5. Comparison Summary

| Capability | yq | jq/gojq | ConfigForge |
|---|---|---|---|
| Comment preservation | ❌ Fragile (#19, #1358, #2595) | N/A (JSON only) | ✅ Verified (YAML, INI) |
| Blank line preservation | ❌ #515 OPEN 6yr (151👍) | N/A | ⚠️ Needs test |
| TOML support | ✅ Added Dec 2025 (3.5yr late) | ❌ | ✅ From day one |
| HCL support | ✅ | ❌ | ✅ |
| JSON5 support | ⚠️ PR#2569 open | ❌ | ❌ |
| Multi-doc YAML comments | ❌ #1358 fixed, fragile | N/A | ✅ Tested with 19-doc K8s |
| Formats total | ~7 (YAML/JSON/XML/CSV/TSV/TOML/PROPS) | 1 (+plugins) | **11** |