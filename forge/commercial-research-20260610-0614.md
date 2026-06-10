# Commercial Research — 2026-06-10T06:14Z

**Rotation index:** 1  
**Topic:** Config file converter market — yq vs jq comparison pricing, config file converter mac app store  
**Queries run:**
1. yq vs jq comparison developer tools 2026 pricing
2. config file converter mac app store 2026
3. yq jq dasel config converter complaints alternatives 2026
4. yq TOML write support missing developer complaint 2025 2026
5. "config converter" CLI tool developer one-time purchase pricing 2025 2026
6. HN thread: "I started using yq over jq. Any significant differences?" (id=38462960)
7. HN thread: "Show HN: Qq: like jq, but can transcode between many formats" (id=40781894)

---

## Phase 2: Review Analysis

### 1. What users hate most about existing tools

**yq (mikefarah/yq — Go):**
- **Syntax breakage between v3→v4**: "yq changed its syntax between version 3 and 4 to be more like jq (but not quite the same for some reason)" — scripts break silently on upgrade
- **No TOML write/output**: mikefarah/yq reads TOML but cannot output TOML as of 2026 — a multi-year open issue (#1364). kislyuk/yq does support TOML output via tomlkit but requires Python + jq
- **Missing if-then-else**: described as "a poor design (or omission)" — no conditionals for complex transforms
- **HCL/Terraform not supported** (confirmed from HN Qq thread)

**jq:**
- **Startup latency**: "jq is just really slow to start, with version 1.6 being especially abysmally slow to start, 10x times slower than 1.5"
- **JSON-only**: requires piping through jq+yq combo for YAML, adding complexity
- **Steep learning curve**: filter DSL syntax is non-obvious for quick operations

**kislyuk/yq:**
- **Dependency burden**: requires both Python AND jq — too heavy for containerized/minimal environments
- **Wrapper pattern**: doesn't own its own data path, relies on jq for actual processing

**Dasel:**
- **Drops comments** on read/write — confirmed by prior research (already a CompareForge page built)
- **Format coverage gaps**: does not cover all 11 formats ConfigForge handles

**Tool fragmentation (meta-complaint):**
- "I think there may already exist a jq alternative for every letter of English alphabet" — users are exhausted by the proliferation of similar tools without clear differentiation

### 2. What users wish existed

- A **single tool** that specializes purely at transcoding between all major formats (CSV/JSON/YAML/TOML/XML/HCL/properties/ini) without a query language requirement
- **TOML write support** from a tool that already reads YAML/JSON well
- **Interactive mode** (praised heavily in Qq HN thread: "the interactive mode that qq has is really slick…worked pretty smoothly") — suggests live playground/web demo is a real differentiator
- A **"transcoded test suite that all these tools could run against"** — users want quality signals
- Granular **format maturity indicators** ("which formats does this tool actually handle well?")
- Better CSV handling (BOM support, consistent array→table behavior)

### 3. Pricing objections

- **No pricing objections found** — yq, jq, dasel are all free/open-source; zero commercial CLI config tools found in this space with paid models
- **$0 is the expectation** for CLI tools in this category
- Mac App Store search for "config file converter" returned media converters (Permute, Smart Converter) — no developer config format converters found
- **Opportunity:** ConfigForge at $19 one-time is the ONLY commercial offering in this specific niche; there's nothing to compare against which means no anchoring problem but also no proof of demand

### 4. Onboarding friction

- yq users frequently confused by which "yq" they have (mikefarah vs kislyuk — two separate tools with the same name)
- kislyuk/yq installation is confusing: `pip install yq` installs the Python wrapper, not the Go binary
- jq filter syntax requires learning a mini-language before doing simple operations
- **Opportunity for ConfigForge**: `devbench cf file.yaml --get key` is immediately intuitive vs yq's `yq '.key' file.yaml` — no filter DSL

### 5. Competitor weaknesses

| Tool | Weakness | ConfigForge advantage |
|------|----------|-----------------------|
| mikefarah/yq | No TOML write, no HCL output | Full TOML read+write, HCL |
| kislyuk/yq | Requires Python + jq, wrapper not owner | Self-contained, pure Python |
| jq | JSON-only, slow startup, steep DSL | All 11 formats, flag-based syntax |
| dasel | Drops comments, fewer formats | Comment preservation (YAML+INI) |
| qq | Newer, less adoption, no Mac App | Established PyPI package |
| online converters | Privacy concerns, no offline | Fully offline, private |

---

## Phase 3: Synthesis

### What ConfigForge should AVOID

1. **Avoid chasing yq's query DSL** — users are already fatigued by DSL tools; ConfigForge's flag-based CLI (`--get`, `--set`, `--select`) is a deliberate competitive advantage, not a gap
2. **Avoid overselling "11 formats"** as a headline if format quality is uneven — users want quality signals per format, not a raw count; the `--check-env` output is good, should be surfaced more
3. **Avoid tool proliferation confusion** — don't ship as multiple pip packages or with multiple entry points (the `configforge` vs `devbench` dual-entrypoint already causes confusion per deep audit MEDIUM-4)
4. **Avoid silent wrong results** — HIGH-1 from deep audit (--select regex with --each/--join returns wrong results without error) is exactly the failure mode users hate most; fix is P0

### What ConfigForge should BUILD

1. **Fix HIGH-1 immediately** (BUILDER P1): `_apply_select_filter` regex support for `--each`/`--join` — this is silent data corruption, the #1 user complaint in the market
2. **Maturity table in docs** — list format support level (read+write, read-only, experimental) per format in `--check-env` JSON and CLI docs; users explicitly asked for this in HN Qq thread
3. **Interactive web demo prominence** — the HN Qq thread made clear interactive mode is a strong differentiator; ensure web/serve.py demo is linked prominently from landing page and README
4. **"Why not yq?" one-liner** — surface the TOML write advantage more aggressively: "yq can't output TOML. ConfigForge can." is a specific, Google-indexable differentiator
5. **Delete `configforge` entry point** (POLISHER P0): MEDIUM-4 from deep audit — the dual entry point is a maintenance liability and confuses the product story; `devbench cf` should be the single CLI
6. **SEO for TOML write gap** — yq TOML write issue #1364 has been open for years; "yaml to toml cli command line" and "convert yaml to toml without yq" are high-intent searches that ConfigForge already ranks for partially but can deepen

### Pricing model

- **$19 one-time** is correct positioning — matches developer tool norms (indie mac utilities, similar CLI tools when commercial)
- There is NO existing paid CLI config converter to compare against — ConfigForge is the only one; this means the risk is not "too expensive vs competitor" but "why pay at all for what free tools exist"
- **Framing matters**: position against "time lost piping yq + jq + sed to convert between formats" not against "free yq"
- The Gumroad listing gap is costing revenue daily — the code is complete

### Distribution channel

- **Mac App Store for config file converters has zero competition** — no config format converter app found in the store; opportunity exists but requires native macOS wrapper (blocked on Mac Mini)
- **PyPI is the correct first channel** — developers find CLI tools via `pip search` and GitHub README `pip install` instructions; Homebrew is second
- **No pricing proof of demand exists** yet — first Gumroad sale is the critical signal

---

## Phase 4: Actionable Recommendations

**BUILDER P1:**
- Fix `_apply_select_filter` regex support (HIGH-1 from deep audit) — silent wrong results on `--select /pat/ --each` is the exact failure mode that kills developer trust

**POLISHER P0:**
- Remove `configforge` console_scripts entry point from `pyproject.toml`/`setup.py`; deprecate `configforge.main()` — streamlines product story, eliminates MEDIUM-4 maintenance liability
- Add SEO page: "yaml-to-toml-cli.html" targeting "yq can't write TOML" pain point — the specific yq issue #1364 complaint is a gift of indexable search intent

**Human P0 (unchanged from prior cycles):**
- Create Gumroad $19 product
- `twine upload` rebuilt 1.0.0 wheel to PyPI
- Create `homebrew-devbench` GitHub repo and push formula
- Tag v1.0.0 on GitHub

---

## Phase 5: Distribution Channel Lessons

1. **PyPI + Homebrew** are the two CLI distribution channels with developer reach; Mac App Store is an untapped opportunity but requires native app wrapper
2. The "two yq" confusion (mikefarah vs kislyuk) is a lesson: **own a unique name** and don't shadow existing pip package names — `devbench` is clean on PyPI
3. **Interactive playground drives adoption** — every successful CLI tool in this space has a web playground that new users try before installing; ConfigForge's web demo is built but not prominently surfaced

---

## Pipeline macOS App Ideas

Based on this research cycle:

1. **ConfigForge native macOS app**: menu bar tool for drag-and-drop format conversion — no competitor in Mac App Store; immediate white-space opportunity
2. **"TOML Writer"**: focused single-purpose app targeting the yq TOML write gap — positions directly against a named, open GitHub issue
3. **Config Diff Tool**: cross-format structural diff as a native app — DevBench's `--diff` flag is unique but buried in a CLI; a macOS app showing YAML vs JSON diff side by side would be immediately understandable

---

## Comparison to Previous Research (forge/commercial-research-20260609-1003.md)

Previous research (2026-06-09 10:03Z, rotation 0: macOS menu bar utility market) found:
- Setapp is the dominant paid distribution channel for macOS utilities
- $19 one-time is validated for indie developer tools
- SEO is the primary acquisition channel given zero ad spend

This cycle adds:
- **TOML write gap in yq is a documented, multi-year pain point** — stronger SEO target than previously known
- **No paid config converter CLI tools exist** — ConfigForge is genuinely first in this specific niche
- **Interactive demo is a proven differentiator** in this tool category
- **Tool fragmentation fatigue is real** — "every letter of the alphabet" comment — ConfigForge must differentiate on quality and completeness, not just another format count
- **Mac App Store has zero config format converter apps** — the distribution gap is wider than expected
