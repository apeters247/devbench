# External Review — 2026-06-07T19:19Z

**Rotation index:** 1 (HN: config tool complaints)

**Queries executed:**
1. `site:news.ycombinator.com yq jq alternative config file format conversion` → HN Algolia
2. `site:news.ycombinator.com frustrating devops configuration management tools` → HN Algolia
3. `site:news.ycombinator.com yq comment preservation parsing` → HN Algolia

## Source: HN Story "yq: command-line YAML, JSON, XML, CSV and properties processor" (224 pts)

Retrieved comments from: https://hn.algolia.com/?query=yq&tags=story_34656022

### Verbatim User Complaints

**voytec** (top comment):
> "The yaml document from hell needed three changes ("*.html", "*.png", "!.git") to be parsed by yq at all."
> Links to: https://ruudvanasseldonk.com/2023/01/11/the-yaml-document-from-hell

**theonemind**:
> Uses `gojq` with `--yaml-input/--yaml-output` for JSON↔YAML — prefers full jq syntax compat. Mentions yq's `-s` (slurp) has different semantics from jq's `-s`. "Slightly altered semantics would just trip me up."

**daurnimator**:
> Prefers the Python-based yq (kislyuk/yq) which wraps jq for full jq compatibility. Says OP's yq only has "partial functionality."

**scarface74**:
> "Every normal yaml processor I've tried struggles with CloudFormation. I end up using the cfn-flip command line program/Python module to deal with CFT Yaml."

**CathalMullan**:
> Recommends **dasel** (TomWright/dasel) as alternative for querying/modifying JSON, YAML, TOML, XML, CSV.

**raydiatian**:
> "I think my dream is yq but with JSONata and an interactive editor." Wants `WHERE value = x` query syntax.

### Competitor Mentions

| Tool | Formats | Comment Preservation | Notes |
|------|---------|---------------------|-------|
| **gojq** | JSON↔YAML (via --yaml-input/--yaml-output) | ❌ | Full jq syntax, 100% UI compat |
| **dasel** (TomWright/dasel) | JSON, YAML, TOML, XML, CSV | ❌ | Query/modify, single binary |
| **kislyuk/yq** (Python) | JSON, YAML, XML (via jq wrapper) | ❌ | Wraps jq for full query compat |
| **cfn-flip** | CloudFormation YAML ↔ JSON | ❌ | AWS-specific |
| **csvq** | CSV query | ❌ | SQL-like CSV analysis |

**Key insight: dasel is the closest multi-format competitor** — 5 formats (JSON, YAML, TOML, XML, CSV) vs ConfigForge's 9 (adds INI, .env, HCL, .properties). No comment preservation.

## What ConfigForge Could Address TODAY

1. **"YAML document from hell" dissatisfaction** → ConfigForge's YAML parser (via ruamel.yaml) handles tricky YAML better than yq. Promote "ConfigForge handles the YAML document from hell" as SEO/feature messaging.

2. **CloudFormation YAML** → ConfigForge handles CloudFormation JSON/YAML conversion. SEO keyword: "CloudFormation YAML converter".

3. **dasel competitor gap** → No "ConfigForge vs dasel" comparison page exists. dasel users want 5-format query/modify — ConfigForge offers 9-format conversion + comment preservation.

4. **gojq users** → gojq does JSON↔YAML but lacks TOML/XML/CSV/INI/env/properties/HCL. ConfigForge complements gojq for format conversion.

## Action Items for Builder

- **BUILDER P1**: Create "vs dasel" comparison SEO page (`web/forge/seo/vs-dasel.html`). dasel is the most directly comparable multi-format CLI tool.
- **BUILDER P2**: Create "CloudFormation YAML converter" SEO page or section. scarface74's complaint about every YAML processor struggling with CloudFormation is a real pain point.
- **BUILDER P2**: Add "YAML document from hell" test to edge case suite — test ConfigForge against the known yq-failing YAML patterns (unquoted `*.html`, `*.png`, `!.git`).
- **BUILDER P3**: Add dasel to the comparison table on the landing page if not already present.