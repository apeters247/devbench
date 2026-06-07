---
title: "INI to TOML Converter with Type Inference — Free Offline CLI Tool"
description: "Convert INI config files to TOML with proper type inference — booleans, numbers, dates, and arrays detected automatically. CLI tool for legacy app modernization, Python ConfigParser migration, and batch conversion. 100% offline."
keywords: "ini to toml converter, ini to toml cli, convert ini to toml with types, configparser to toml, batch ini to toml, ini to toml type inference, legacy config migration"
og_title: "INI to TOML Converter with Type Inference — Free CLI"
og_description: "Convert INI files to properly typed TOML. Booleans, integers, dates, arrays detected automatically. Batch mode for 47+ files. Offline and private."
---

# INI to TOML Converter with Type Inference

Converting INI configuration files to TOML is harder than it looks. Most converters just copy `key=value` pairs as strings — turning `enabled = true` into `enabled = "true"` instead of a real boolean. **ConfigForge** detects actual types and outputs proper TOML.

## The Type Problem

INI has no type system — everything is a string. TOML has native booleans (`true`/`false`), integers, floats, dates, and arrays. A naive converter gives you TOML that's just INI with brackets:

```toml
# Bad converter output — all strings!
enabled = "true"
timeout = "30"
pi = "3.14"
tags = '["a", "b"]'
last_run = "2024-01-15T10:00:00Z"
```

ConfigForge output — proper types:

```toml
# ConfigForge output — real types
enabled = true
timeout = 30
pi = 3.14
tags = ["a", "b"]
last_run = 2024-01-15T10:00:00Z
```

## Install

```bash
pip install devbench-cf
```

Or try the web demo: [ConfigForge Web Demo](https://naxiai.com/tools/devbench/demo/)

## Example: Convert a Legacy INI Config to TOML

**Input: `app.ini`**

```ini
[server]
host = localhost
port = 8080
debug = true
ssl = false

[database]
url = postgres://user:pass@localhost:5432/db
pool_size = 20
enable_logging = false
created_at = 2024-03-15T08:30:00Z

[features]
experimental = true
max_retries = 5
tags = ["api", "core", "v2"]
```

**Convert to TOML:**

```bash
devbench cf app.ini --to toml
```

**Output: `app.toml`**

```toml
[server]
host = "localhost"
port = 8080
debug = true
ssl = false

[database]
url = "postgres://user:pass@localhost:5432/db"
pool_size = 20
enable_logging = false
created_at = 2024-03-15T08:30:00Z

[features]
experimental = true
max_retries = 5
tags = ["api", "core", "v2"]
```

## Type Inference Rules

ConfigForge applies smart type inference, not regex guessing:

| INI Value | Detected Type | TOML Output |
|-----------|---------------|-------------|
| `true`, `false`, `yes`, `no`, `on`, `off` | Boolean | `key = true` |
| `42`, `-7`, `0` | Integer | `key = 42` |
| `3.14`, `-0.5`, `1e10` | Float | `key = 3.14` |
| `"hello"`, `'single'` | String (quotes stripped) | `key = "hello"` |
| `2024-01-15` (ISO date) | Date | `key = 2024-01-15` |
| `2024-01-15T10:00:00Z` | Datetime | `key = 2024-01-15T10:00:00Z` |
| `[1, 2, 3]` | Inline array | `key = [1, 2, 3]` |
| `["a", "b"]` | String array | `key = ["a", "b"]` |
| `plain text` | String | `key = "plain text"` |

## Batch Convert 47+ INI Files

Reddit user complaint: *"I have 47 INI files in a project that need to be TOML. Doing them one by one with sed/awk is insanity."*

```bash
# Convert entire directory
devbench cf configs/*.ini --to toml --out-dir ./toml-configs/

# Dry run first — preview what will change
devbench cf configs/*.ini --to toml --dry-run
```

## Convert Python ConfigParser INI to TOML

When modernizing a legacy Python app from `configparser` to TOML:

**Original `config.ini`:**
```ini
[logging]
level = INFO
file = /var/log/app.log
max_size = 10485760
backup_count = 5
```

**Command:**
```bash
devbench cf config.ini --to toml
```

**Result: `config.toml`:**
```toml
[logging]
level = "INFO"
file = "/var/log/app.log"
max_size = 10485760
backup_count = 5
```

## Comparison: ConfigForge vs Other INI→TOML Tools

| Feature | ConfigForge | sed/awk scripts | Python one-liners | Online converters |
|---------|-------------|-----------------|-------------------|-------------------|
| Type inference | ✅ Auto booleans, numbers, dates | ❌ Strings only | ❌ Strings only | ❌ Strings only |
| Batch mode | ✅ Glob `*.ini` | ✅ Loop | ✅ Loop | ❌ One-by-one |
| Array detection | ✅ `[a, b, c]` | ❌ | ❌ | ❌ |
| Section nesting | ✅ Nested tables | ⚠️ Basic | ⚠️ Basic | ⚠️ Basic |
| 100% offline | ✅ Zero network | ✅ | ✅ | ❌ Requires upload |
| Null handling | ✅ Configurable | ❌ | ❌ | ❌ |
| Unicode | ✅ Full support | ⚠️ | ⚠️ | ⚠️ |

## Use Cases

### Modernizing Django Settings

```bash
# Convert Django-like INI settings to TOML for new framework
devbench cf settings.ini --to toml > settings.toml
```

### PHP to Rust Migration

```bash
# Convert PHP project INI configs to Rust Cargo workspace TOML
devbench cf config/*.ini --to toml --out-dir ./rust-config/
```

### Ansible INI Inventory to TOML

```bash
devbench cf production.ini --to toml > inventory.toml
```

## Related Resources

- [JSON to TOML Converter](/tools/devbench/forge/seo/json-to-toml-converter.html)
- [ConfigForge vs Online Converters](/tools/devbench/forge/seo/vs-online.html)
- [Convert ENV to JSON](/tools/devbench/forge/seo/env-to-json-guide.html)
- [Ansible INI to YAML Migration](/tools/devbench/forge/seo/ansible-ini-to-yaml.html)

## Quick Reference

```bash
# Single file
devbench cf config.ini --to toml > config.toml

# With format hint
devbench cf unknown.ext --to toml --from ini

# Batch
devbench cf *.ini --to toml --out-dir out/

# Preview
devbench cf config.ini --to toml --dry-run
```

---

*ConfigForge — convert config files between 9 formats. Type-safe INI→TOML conversion included. One-time purchase $19.*