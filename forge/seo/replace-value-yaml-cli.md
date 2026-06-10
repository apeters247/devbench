---
title: "Find and Replace YAML Value from CLI — devbench cf --replace-value"
description: "Replace a value across an entire YAML, JSON, or TOML config file from the command line — no sed, no Python script. devbench cf --replace-value finds every occurrence and rewrites the file in place."
keywords: "find and replace yaml value command line, replace value in yaml cli, sed yaml replace, yq replace value, change config value terminal"
og_title: "Find and Replace YAML Value from CLI"
og_description: "Replace any string value across a YAML, JSON, TOML, or INI config file in one command. devbench cf --replace-value. No sed gymnastics required."
---

# Find and Replace a YAML (or JSON/TOML) Value from the Command Line

You have a config file and you need to replace a value everywhere it appears — renaming an environment, rotating a URL, swapping a version string. The instinct is to reach for `sed`, but `sed` is text-substitution: it doesn't parse YAML structure, it silently mangles quoted strings, and it has no idea what "a value" vs "a key name" means.

`devbench cf --replace-value` is the right tool. It understands config structure: it replaces *values* (not key names, not comments, not partial substrings) and writes output in the same format it read.

## Basic Usage

```bash
# Replace "staging" with "production" everywhere in values
devbench cf config.yaml --replace-value staging production

# Write back to the same file
devbench cf config.yaml --replace-value staging production --in-place

# Works across all 11 formats
devbench cf config.json --replace-value "http://old-api.internal" "https://api.prod.example.com" --in-place
devbench cf pyproject.toml --replace-value "0.9.0" "1.0.0" --in-place
```

## Why Not `sed`?

`sed -i 's/staging/production/g' config.yaml` has serious problems for config files:

1. **Replaces key names too** — if your YAML has `staging_timeout: 30`, sed turns the key into `production_timeout: 30`
2. **Breaks quoted strings** — YAML single vs double quote differences trip up naive text replacement
3. **Corrupts comments** — comments mentioning the old value are silently changed too
4. **No format awareness** — a TOML datetime or YAML anchor looks like any other text to sed

`devbench cf --replace-value` operates on the parsed data model, so only leaf *values* are matched. Key names, comments, and YAML anchors are left alone.

## Targeting Specific Subtrees with `--get`

Replace values only within a subtree by combining `--get` with `--replace-value`:

```bash
# Replace values only inside the `env` block — don't touch the rest of the file
devbench cf deploy.yaml --get env --replace-value old-cluster new-cluster
```

## Scripting: Bulk Rotation Across Many Files

```bash
# Replace an API base URL in every YAML file in the project
find . -name "*.yaml" -o -name "*.yml" | xargs -I{} devbench cf {} \
  --replace-value "https://api-v1.internal" "https://api-v2.internal" --in-place

# Rotate a shared secret string across TOML and JSON configs
for f in config/*.{toml,json}; do
  devbench cf "$f" --replace-value "old-secret-token" "new-secret-token" --in-place
done
```

## Comparison with Other Tools

| Approach | Config-aware | Preserves keys | Preserves comments | All formats |
|----------|-------------|----------------|-------------------|-------------|
| `sed -i 's/a/b/g'` | ❌ | ❌ | Replaces too | ❌ |
| `yq '(.[] | select(. == "a")) = "b"'` | ✅ (YAML only) | ✅ | ⚠️ Partial | ❌ |
| `devbench cf --replace-value a b` | ✅ | ✅ | ✅ Untouched | ✅ 11 formats |

## Install

```bash
pip install devbench-cf
# or
pip install devbench          # includes all tools
```

Once installed, `devbench cf` is on your PATH. Works on macOS, Linux, and Windows. Python 3.10–3.13.

## Related Commands

- `--set PATH VALUE` — overwrite a specific path by key (not by value)
- `--delete PATH` — remove a key/value pair
- `--merge OVERLAY` — deep-merge a second file onto the first
- `--in-place` — write result back to the source file (works with `--replace-value`, `--set`, `--delete`, `--merge`)
