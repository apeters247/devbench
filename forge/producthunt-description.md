# Product Hunt Launch — ConfigForge

## Product Details

**Product Name:** ConfigForge (part of Devbench)
**Tagline:** The config file converter that doesn't sell your data — 9 formats, 100% offline, $19 one-time
**Category:** Developer Tools
**Pricing:** $19 one-time (Gumroad + Mac App Store)
**Website:** https://naxiai.com/tools/devbench/
**Twitter/X:** @naxiai

## Short Description (under 140 chars)

Convert YAML, JSON, TOML, XML, CSV, INI, .env, HCL, and .properties — 100% offline CLI + web UI for $19.

## Long Description

### The Problem

Config file conversion is broken. Developers juggle yq for YAML, jq for JSON, custom scripts for INI→TOML, and sketchy online converters that ask for your email, display popup ads, and probably sell your production configs.

Everyone's #1 complaint: **"No offline tool that just works."**

Every conversion tool either:
- Strips your YAML comments (yq, pyyaml, ruamel — all of them)
- Asks you to sign up for a "free trial"
- Uploads your config to a third-party server
- Handles only ONE format pair (JSON↔YAML, nothing for INI→TOML)
- Can't batch-convert 47 files at once

### The Solution: ConfigForge

ConfigForge is a **fully offline** config file converter that handles **9 formats** bidirectionally. No data leaves your machine. No signup. No ads. One `pip install devbench` and you're done.

#### What you can do:

**One-command conversions:**
```bash
# Pipe anything, get JSON
echo 'name: Hello\nversion: 1.0' | devbench cf

# Convert between any 2 of 9 formats
devbench cf --to toml < app.yaml
devbench cf --to json --from ini < config.ini

# Batch-convert 1000+ files
devbench cf --batch --stream --to yaml '*.json'
```

**Interactive web UI:**
```bash
devbench cf --serve
# Opens at http://localhost:8080 — paste, convert, copy
```

**REST API for automation:**
```bash
curl -X POST http://localhost:8081/api/v1/convert \
  -H 'Content-Type: application/json' \
  -d '{"source":"name: test","to_format":"json"}'
```

#### What makes ConfigForge different from yq/jq/online converters?

| Feature | ConfigForge | yq | jq | Online |
|---------|-------------|-----|-----|--------|
| Formats | **9** | 2 | 1 | Depends |
| YAML comment preservation | ✅ Yes | ❌ Strips | N/A | ❌ Strips |
| INI→TOML type inference | ✅ Booleans, numbers, dates | ❌ | ❌ | ❌ |
| Batch mode | ✅ Glob + streaming | ⚠️ Slow | ❌ | ❌ |
| Offline | ✅ Zero network calls | ✅ | ✅ | ❌ Uploads data |
| XML flattening | ✅ Smart | ❌ | ❌ | ❌ |
| Multi-doc YAML | ✅ --- separators | ⚠️ Splits files | ❌ | ❌ |
| Unicode preservation | ✅ No escape sequences | ❌ \\uXXXX | ⚠️ | ❌ |
| Null handling | ✅ 4 modes (skip, comment, empty, error) | ❌ ~ → "None" | ⚠️ | ❌ |
| Web UI | ✅ Built-in | ❌ | ❌ | ✅ (but ads) |
| REST API | ✅ Built-in | ❌ | ❌ | ❌ |
| Price | **$19 one-time** | Free | Free | Free (data is product) |

#### Tech specs

- **9 formats:** JSON, YAML, TOML, XML, CSV, INI, .env, HCL, .properties
- **99+% comment preservation** in YAML round-trips (JSON→YAML carries comments)
- **Cross-platform:** macOS, Linux, Windows (Python 3.10+)
- **No external dependencies** for 7 formats — `pip install devbench`
- **Optional formats** (HCL, .properties) via pure Python or `hcl2` venv
- **Batch streaming** handles 10K+ files without running out of memory

## First Comment / Story

> "I built ConfigForge because I was tired of juggling yq, jq, and sketchy online converters. My configs have the database passwords in them — I'm not pasting those into a random website.
>
> The killer feature is comment preservation. You write documentation in your YAML comments, run it through a converter that strips them all, and suddenly nobody knows what the `max_connections: 50` parameter does. ConfigForge carries comments through JSON round-trips.
>
> 9 formats, one tool, $19 one-time. Fully offline. Nothing leaves your machine."

## Screenshots to Include

1. **Web demo**: ConfigForge demo page showing YAML input and JSON output side by side
2. **CLI conversion**: Terminal showing `devbench cf --to toml < app.yaml` with output
3. **Batch mode**: Terminal showing batch conversion of 47 INI files to TOML with progress bar
4. **Format comparison table**: The table above as a clean image

## Tags

config-converter, yaml, json, toml, developer-tools, cli, offline, privacy, devops, kubernetes