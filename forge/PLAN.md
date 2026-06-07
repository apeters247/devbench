# ConfigForge Polish Plan

## Section 1: Mission
Make ConfigForge findable and trusted. SEO content, landing page, new format support, user-facing quality signals.

## Section 2: User Complaints (from forge/user_complaints.md)
Top pain points: comment loss on round-trip, no offline converter, no unified CLI tool, YAML indentation mangling, TOML type blindness, XML verbosity, batch conversion, Unicode mangling, null handling, multi-doc YAML, number precision.

## Section 3: Deliverables Status

### PRIORITY 1 — SEO Content (14 pages, 11,718 words)
- [x] forge/seo/vs-yq.md — "yaml to json converter alternative", "yq vs configforge" (updated format count to 9)
- [x] forge/seo/vs-jq.md — "json to yaml converter", "jq alternative"
- [x] forge/seo/vs-online.md — "offline config converter", "yaml to json offline"
- [x] forge/seo/use-cases.md — "convert kubernetes yaml to json", specific workflows
- [x] forge/seo/json-to-yaml-converter.md — tutorial + pipeline examples + comparison vs jq
- [x] forge/seo/toml-vs-yaml.md — side-by-side comparison, when to use each
- [x] forge/seo/kubernetes-config-converter.md — K8s YAML/YTT/Helm conversions
- [x] forge/seo/docker-compose-converter.md — Compose YAML to JSON/K8s conversions
- [x] forge/seo/ansible-ini-to-yaml.md — migration guide from INI inventory to YAML
- [x] forge/seo/json-to-toml-converter.md — "convert json to toml" (package.json → Cargo.toml)
- [x] forge/seo/ini-to-toml-converter.md — "convert ini to toml" with type inference
- [x] forge/seo/csv-to-yaml-converter.md — "convert csv to yaml" batch workflow
- [x] forge/seo/xml-to-yaml-guide.md — "convert xml to yaml" smart flattening
- [x] forge/seo/env-to-json-guide.md — "convert env to json" batch monitoring

### PRIORITY 2 — Landing Page (web/index.html, web/pricing.html)
- [x] Hero section: "Convert config files between 9 formats — offline, private, fast"
- [x] "Try it now" section with curl command
- [x] Feature comparison table (9 formats vs yq/jq/online)
- [x] JSON-LD structured data (SoftwareApplication schema)
- [x] OG tags with proper title, description, image
- [x] Stripe checkout button for $19
- [x] 14 SEO comparison page links in landing page (all format-specific pages)
- [x] Standalone pricing page at web/pricing.html with Free CLI/Devbench Pro tiers + feature table

### PRIORITY 3 — New Formats
- [x] HCL (HashiCorp) — Terraform users
- [x] Java .properties — Spring Boot, Android
- [x] Both: read/write, detect_format, SUPPORTED_FORMATS, tests

### PRIORITY 4 — Quality Signals
- [x] Telemetry opt-out: DEVEBENCH_NO_TELEMETRY=1 env var
- [x] Error enrichment: _enrich_error_message() with actionable suggestions
- [x] ConfigForge embedded CLI --version shown semver
- [x] ConfigForge help text with 5+ real-world examples
- [x] Comment preservation (YAML, INI)
- [x] Main CLI `devbench --version` shows semver (core/__init__.py has __version__)
- [x] Stale format lists in cli.py updated (missing hcl/properties in error msg + help text)

## Section 4: Cycle Instructions
Every 15min cycle:
1. Read PLAN.md section 4 and Overseer's latest digest
2. Run: python3 -m pytest tests/ -q --tb=line
3. Pick HIGHEST priority item not done
4. Implement
5. Run tests again (no regressions)
6. Update PLAN.md sections 3 and 5

## Section 5: Latest Cycle Log
### Cycle — 2026-06-07 11:06Z (this cycle)
- ✅ Fixed landing page: 14/14 SEO pages now linked (previously only 9 linked; 5 format-specific pages were invisible to Google crawler)
- ✅ Created standalone pricing page: web/pricing.html — Free CLI tier (ConfigForge, open source) + Devbench Pro ($19, macOS menubar app), feature comparison table, JSON-LD Product schema, OG tags, Stripe checkout CTA
- ✅ Tests: 868 passed, 9 skipped — no regressions
- ✅ PLAN.md Sections 3 and 5 updated

### Cycle — 2026-06-07 10:34Z (previous cycle)
- ✅ Created 5 new SEO content pages targeting format-pair keywords:
  - forge/seo/json-to-toml-converter.md (182 lines, ~755 words) — "convert json to toml" for Node→Rust migrations
  - forge/seo/ini-to-toml-converter.md (182 lines, ~786 words) — "convert ini to toml" with type inference table
  - forge/seo/csv-to-yaml-converter.md (180 lines, ~728 words) — "convert csv to yaml" for Ansible inventory
  - forge/seo/xml-to-yaml-guide.md (245 lines, ~746 words) — "convert xml to yaml" smart flattening
  - forge/seo/env-to-json-guide.md (176 lines, ~740 words) — "convert env to json" batch monitoring
- ✅ Added frontmatter (title, description, keywords, OG tags) to 4 existing older SEO pages (vs-yq, vs-jq, vs-online, use-cases)
- ✅ Built SEO HTML rendering pipeline: scripts/build_seo_html.py
- ✅ Converted all 14 SEO .md pages → .html in web/forge/seo/ with proper site header/footer + OG meta tags
- ✅ Landing page (web/index.html): added 10 new SEO comparison page links (5 format pairs + 5 existing), fixed footer links
- ✅ SEO expanded from 9 pages (7,963 words) → 14 pages (11,718 words) — 47% word increase
- ✅ Tests: 868 passed, 9 skipped — no regressions
- ✅ PLAN.md Sections 3 and 5 updated