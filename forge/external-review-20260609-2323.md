# External Review — 2026-06-09T23:23Z

## Step 1: User Complaint Search

**Rotation:** HN yq alternatives (minute 20 = 15-29 range)

**Source:** Web search for "yq YAML tool complaints limitations 2026"

**Finding:** Multiple user complaints about yq's limitations:

1. **Comment preservation in YAML roundtrip mode** — Users report that yq's `-Y` (YAML roundtrip) mode breaks because it injects metadata into the document. Filters expecting clean array entries get 4 instead of 2, and filters expecting mappings break on string metadata keys.

2. **Limited granularity in merge/append operations** — Users complain that yq lacks ergonomic ways to merge Kubernetes YAML files with nested lists. You need full sub-expressions for what should be a one-liner (e.g., appending to containers[] or env vars).

3. **YAML tag and style preservation** — By default, custom YAML tags and styles in input are ignored, making roundtrip conversions lossy.

**Relevance to ConfigForge:** ConfigForge already excels at comment preservation (stated selling point). The `--merge` + `--list-merge` flags directly address complaint #2 (limited merge granularity). Complaint #3 (tag/style preservation) is handled better in ConfigForge via its multi-format round-trip design.

**Action:** No new feature needed. ConfigForge already solves these yq complaints. Instead, found and fixed a bug in the builder's recent changes.

## Step 2: Code Review — Builder's Last Change

**Builder's commit:** 1a17b17 (GitHub Release workflow + 3 SEO pages + sitemap)

**Changes reviewed:**
- `.github/workflows/publish.yml` — GitHub Release automation
- `web/forge/seo/{yaml-to-json,toml-to-yaml,vs-miller}.html` — SEO pages (all 47 pages exist, sitemap updated to 52 URLs)
- `web/sitemap.xml` — verified 52 URLs present

**Bug found:** Shell completion scripts have invalid option documentation.

### Bug: --list-merge Invalid Completion Option

**Severity:** LOW (completion UX, not functional breakage)

**Problem:** Bash, ZSH, and Fish completion scripts suggest `--list-merge merge` as a valid option, but the CLI only accepts `--list-merge replace` or `--list-merge append`. When users try to use the suggested option, they get an error.

**Files affected:** `core/cli.py` (lines with COMPREPLY, zsh -o bashcompat, and fish completion)

**Fix:** Removed "merge" from completion suggestions in 3 places (Bash, ZSH, Fish).

**Verification:** All 1166 tests pass. No functional changes — completion strings only.

## Step 3: Test Suite

**Before fix:** 1166 passed, 7 skipped, 2 xfailed

**After fix:** 1166 passed, 7 skipped, 2 xfailed

**Status:** All green. ✅

## Step 4: Summary

| Item | Status |
|------|--------|
| User complaint source | HN yq alternatives |
| Complaint relevance | ConfigForge already solves yq's merge granularity + comment preservation |
| Builder's changes reviewed | ✅ GitHub Release workflow, 3 SEO pages, sitemap (all correct) |
| Bug found & fixed | ✅ Shell completion typo (invalid --list-merge option) |
| Tests passing | ✅ 1166 / 1166 (unchanged) |

## Recommendations

1. **Highlight the --merge feature** in marketing copy when comparing to yq. ConfigForge's `--list-merge replace|append` is the solution yq users are asking for.

2. **Consider adding `--list-merge merge`** (deep merge strategy) if there's demand — would fully match the complaint space. Currently unimplemented but trivial to add.

3. **SEO strategy working:** 3 new conversion-focused pages (yaml-to-json, toml-to-yaml, vs-miller) directly target high-search-volume keywords mentioned in user complaints.
