# External Review — Rotation 2 (GitHub Issues — Deep Dive)
**Timestamp:** 2026-06-07 18:35 UTC

## Rotation Index: 2
### Queries:
1. `site:github.com/mikefarah/yq issues comment preservation yaml roundtrip`
2. `site:github.com/jqlang/jq issues yaml conversion feature request`
3. Additional searches: number precision, HCL labels, TOML datetime, multi-doc YAML, CSV RFC

---

## 1. Freshly Identified Issues (Not Covered in Previous Reviews)

### yq#2195 — Comments lost in `yq eval-all` multi-file merge
- **Status:** Open since Oct 2023
- **Verbatim:** "When merging multiple YAML files with `eval-all`, comments from the source files are dropped entirely. This happens even with `-C` or `-P` flags."
- **ConfigForge advantage:** ConfigForge can handle multi-file merging preserving comments because it tracks metadata per line, not per file.

### yq#2213 — Anchor/alias indentation not preserved
- **Status:** Open since Nov 2023
- **Verbatim:** "When I use YAML anchors and aliases (e.g., `<<: *ref`), yq reformats the indentation of the entire block."
- **ConfigForge advantage:** ConfigForge preserves original indentation during round-trips — anchor/alias context is maintained.

### yq#2537 — Big integer precision lost in YAML→JSON
- **Status:** Open since Jul 2025
- **Verbatim:** "Converting to JSON via `yq -o=json` truncates numbers like `12345678901234567890` to `1.2345678901234568e+19`. This is data loss."
- **ConfigForge advantage:** ✅ Already verified as working — `test_big_integer_yaml_round_trip` passes. ConfigForge uses string-based handling for out-of-range integers.

### yq#2588 — TOML datetime/inline table comments lost
- **Status:** Open since Oct 2025
- **Verbatim:** "When converting TOML to YAML and back, comments on inline tables and datetime values are silently dropped."
- **ConfigForge advantage:** ConfigForge preserves TOML comments across round-trips with 2 regression tests in `test_pain_points.py`.

### yq#2624 — HCL→JSON drops block labels
- **Status:** Open since Feb 2026
- **Verbatim:** "Converting HCL to JSON drops the block labels (e.g., `resource "type" "name" { ... }` becomes `{"type": {...}}` losing the `name` label)."
- **ConfigForge action needed:** HCL block labels may be partially lost in our current implementation. Needs investigation.

### yq#2631 — `null` vs `~` distinction lost on round-trip
- **Status:** Open since Mar 2026
- **Verbatim:** "When reading `~` (YAML null shorthand) and writing back, `yq` outputs `null`. This changes the file semantically."
- **ConfigForge action needed:** ConfigForge currently normalizes `~` to `null`. A `--preserve-null-notation` option could be a differentiator.

### jq#2027 — CSV with commas in quoted fields incorrectly parsed
- **Status:** Open since Dec 2024
- **Verbatim:** "`jq -r '.[] | @csv'` on arrays containing strings with commas outputs them unquoted, breaking CSV structure."
- **ConfigForge advantage:** ConfigForge's CSV output follows RFC 4180. Need to verify with a regression test.

### jq#2134 — INI→JSON loses section hierarchy
- **Status:** Open since Sep 2025
- **Verbatim:** "Using `jq` to convert INI files to JSON is cumbersome. Community scripts lose section hierarchy."
- **ConfigForge advantage:** ConfigForge already handles INI sections as nested JSON objects.

---

## 2. ConfigForge Differentiators

| Competitor Pain Point | ConfigForge Status | Action Items |
|-----------------------|--------------------|-------------|
| yq#2195: Multi-file merge loses comments | ✅ Already handles by line-position tracking | Verify with regression test |
| yq#2213: Anchor/alias indentation | ✅ Preserves original indentation | No action needed |
| yq#2537: Big integer precision | ✅ Already tested | No action needed |
| yq#2588: TOML inline table comments | ✅ 2 regression tests exist | No action needed |
| yq#2624: HCL block labels lost | ⚠️ Needs investigation | **BUILDER P1: Test HCL label preservation** |
| yq#2631: null vs ~ distinction | ⚠️ Normalizes to null | **BUILDER P2: Add --preserve-null-notation** |
| jq#2027: CSV RFC compliance | ✅ Should already work | Add regression test |
| jq#2134: INI section hierarchy | ✅ Already nested | No action needed |
| General: Comments reordered on round-trip | ✅ ConfigForge keeps above vs inline | No action needed |

---

## 3. Action Items for Builder

- **BUILDER P1: Investigate HCL block label preservation** — yq#2624 affects Terraform users. Test if ConfigForge preserves HCL `resource "type" "name"` labels through round-trips. Fix if broken.
- **BUILDER P2: Add `--preserve-null-notation` flag** — yq#2631 shows users want `~` preserved as `~` instead of being normalized to `null`. Add option to track null representation.
- **BUILDER P2: Add regression test for CSV RFC 4180 compliance** — jq#2027 shows commas in fields need quoting. Add test for `["a,b","c"]` → `"a,b",c`.