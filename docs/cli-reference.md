# DevBench CLI Reference

DevBench 1.0.0 — 11-format config converter + 9 developer utilities in one CLI.

```
pip install devbench
devbench --help
```

---

## Global flags

| Flag | Description |
|------|-------------|
| `--list`, `-l` | List all available tools |
| `--version`, `-V` | Show version and exit |
| `--raw`, `-r` | Output raw text instead of JSON envelope |
| `--pretty`, `-p` | Pretty-print JSON output |

---

## Subcommands

### `devbench cf` — ConfigForge (11-format config converter)

Convert between JSON, YAML, TOML, XML, CSV, INI, ENV, HCL, .properties, PLIST, JSONC.

```bash
devbench cf input.yaml --to json
devbench cf input.json --to yaml --to toml  # chain: JSON → TOML
echo 'key: value' | devbench cf --to json
```

#### Format flags

| Flag | Default | Description |
|------|---------|-------------|
| `--to FORMAT` | auto | Output format: `json jsonc yaml toml xml csv ini env hcl properties plist` |
| `--from FORMAT` | `auto` | Input format (auto-detected by default) |
| `--list-formats` | — | List all 11 supported formats |
| `--check-env` | — | Show environment: Python, available formats, optional deps. `--raw` for JSON |

#### Output shaping

| Flag | Default | Description |
|------|---------|-------------|
| `--indent N` | `2` | Indentation width for YAML/JSON output |
| `--sort-keys` | off | Sort keys in output |
| `--no-comments` | off | Strip comments (default: preserve) |
| `--flatten-xml` | off | Flatten nested XML to dotted keys |
| `--null-handling MODE` | `skip` | How to represent null in TOML: `skip comment empty error` |
| `--no-infer-dates` | off | Keep ISO-8601 date strings as strings (TOML) |
| `--yaml12` | off | YAML 1.2 booleans only: `true/false` (not `yes/no/on/off`) |
| `--template-safe` | off | Pre-quote `{{ var }}` Jinja/Helm/Ansible expressions before parsing |
| `--env-expand` | off | Substitute `${VAR}` and `$VAR` references from environment |

#### Read operations

```bash
devbench cf deploy.yaml --get spec.replicas
devbench cf config.toml --keys
devbench cf config.toml --keys --recursive
devbench cf deploy.yaml --pick spec.replicas metadata.name --to yaml
devbench cf deploy.yaml --count spec.template.spec.containers
```

| Flag | Description |
|------|-------------|
| `--get PATH` | Extract a value by dot-notation path. Raw scalar or JSON for dicts/lists |
| `--keys` | List all top-level config keys |
| `--keys --recursive` | List every nested key in dot-notation |
| `--pick PATH [PATH…]` | Extract one or more paths. Single path → bare value; multiple → new dict |
| `--count PATH` | Count items at PATH: list length, dict keys, or 1 for scalars |

Dot-notation escape: `\\.` for a literal dot in a key name (e.g. `com\\.example\\.app`).

#### Write / CRUD operations

```bash
devbench cf config.yaml --set server.port 9090
devbench cf config.yaml --set server.port 9090 --in-place
devbench cf config.yaml --set server.port 9090 --in-place --backup
devbench cf config.yaml --append server.hosts '"db.internal"'
devbench cf config.yaml --delete server.debug
devbench cf base.yaml --merge override.yaml
```

| Flag | Description |
|------|-------------|
| `--set PATH VALUE` | Set a key value. VALUE is parsed as JSON (strings need no quoting) |
| `--append PATH VALUE` | Append VALUE to the list at PATH. Creates the list if absent |
| `--delete PATH` | Delete a key |
| `--merge OVERLAY` | Deep-merge OVERLAY file onto the base input |
| `--list-merge MODE` | How to merge lists with `--merge`: `replace` (default) or `append` |
| `--in-place`, `-i` | Write result back to source file (requires a file path, not stdin) |
| `--backup [SUFFIX]` | Before `--in-place`, save original to `FILE<SUFFIX>` (default: `.bak`) |

#### Search and compare

```bash
devbench cf deploy.yaml --grep 'image'
devbench cf '*.yaml' --batch --grep 'password' --raw
devbench cf a.yaml --diff b.json
```

| Flag | Description |
|------|-------------|
| `--grep PATTERN` | Search keys and values matching a regex. Exit 0=match, 1=no match |
| `--grep-case-sensitive` | Make `--grep` case-sensitive (default: case-insensitive) |
| `--diff FILE` | Structural diff across any two config formats. Exit 0=identical, 1=diff |

#### Transforms

```bash
devbench cf config.yaml --flatten --to json
devbench cf flat.json --unflatten --to yaml
devbench cf config.yaml --flatten --sep __   # DATABASE__HOST style
```

| Flag | Description |
|------|-------------|
| `--flatten` | Flatten nested config to dotted-key pairs: `{a: {b: 1}}` → `{'a.b': 1}` |
| `--unflatten` | Expand flat dotted pairs to nested config (inverse of `--flatten`) |
| `--sep SEP` | Key separator for `--flatten`/`--unflatten` (default: `.`) |

#### Validation and CI/CD

```bash
devbench cf config.yaml --validate
devbench cf '*.yaml' --batch --validate
devbench cf '*.yaml' --batch --validate --raw   # JSON report
REPLICAS=$(devbench cf deploy.yaml --count spec.replicas)
```

| Flag | Description |
|------|-------------|
| `--validate` | Validate that config is parseable. Exit 0=valid, 1=invalid |

#### Batch mode

```bash
devbench cf '*.yaml' --batch --to json
devbench cf '**/*.yaml' --batch --recursive --to toml
devbench cf '*.yaml' --batch --output-dir ./converted/
devbench cf '*.yaml' --batch --stream   # memory-efficient for 10K+ files
```

| Flag | Description |
|------|-------------|
| `--batch` | Treat input as a glob and convert every match |
| `--recursive`, `-R` | With `--batch`: recursively match subdirectories (`**` glob) |
| `--output-dir DIR` | Write converted files to DIR instead of stdout |
| `--stream` | Streaming mode for memory-efficient batch conversion (10K+ files) |

#### Server modes

```bash
devbench cf --serve              # browser UI at http://127.0.0.1:8080
devbench cf --serve --port 3000  # custom port
devbench cf --api                # JSON API at http://127.0.0.1:8081/convert
```

| Flag | Description |
|------|-------------|
| `--serve` | Launch the local web UI |
| `--port N` | Port for `--serve` (default: 8080) |
| `--api` | Launch the JSON HTTP API (POST /convert) |
| `--api-port N` | Port for `--api` (default: 8081) |
| `--host ADDR` | Bind address (default: 127.0.0.1; use 0.0.0.0 inside Docker) |

---

### Developer tools

| Command | Description |
|---------|-------------|
| `devbench json` | Format and validate JSON |
| `devbench base64` | Encode/decode base64 |
| `devbench jwt` | Decode JWT tokens |
| `devbench hash` | Generate md5/sha256/sha512 |
| `devbench url` | URL encode/decode |
| `devbench timestamp` | Unix timestamp converter |
| `devbench uuid` | UUID generator |
| `devbench diff` | Text diff |
| `devbench token` | Token counter (`--model cl100k_base`) |
| `devbench chunk` | Text chunker (`--chunk-size 500 --chunk-overlap 100`) |
| `devbench detect` | Auto-detect content type and apply the right tool |

All tools accept input as a positional argument or from stdin:

```bash
echo '{"key": "value"}' | devbench json
devbench base64 "hello world"
devbench timestamp 1717891200
```

---

### `devbench batch` — Batch process files

```bash
devbench batch --tool json --files *.log
devbench batch --tool json --json --files *.json   # JSON output
```

---

### `devbench completion` — Shell completions

```bash
# Bash (add to ~/.bashrc)
eval "$(devbench completion bash)"

# Zsh (add to ~/.zshrc)
eval "$(devbench completion zsh)"

# Fish (save to completions dir)
devbench completion fish > ~/.config/fish/completions/devbench.fish
```

Completions cover all `cf` flags, format names for `--to`/`--from`, mode choices for
`--null-handling`/`--list-merge`, and file completion for config paths.

---

### `devbench license` — License key management

```bash
devbench license activate CF-XXXX-YYYY-ZZZZ
devbench license verify CF-XXXX-YYYY-ZZZZ
devbench license trial --email user@example.com
devbench license server --port 9001
```

---

## CI/CD integration

### GitHub Actions

```yaml
- name: Install devbench
  run: pip install devbench

- name: Check environment
  run: devbench cf --check-env

- name: Validate configs
  run: devbench cf '**/*.yaml' --batch --recursive --validate

- name: Convert config
  run: devbench cf config.yaml --to json > config.json

- name: Extract replica count
  run: |
    REPLICAS=$(devbench cf deploy.yaml --count spec.replicas)
    echo "Deploying $REPLICAS replicas"
```

### Docker

```dockerfile
RUN pip install devbench
RUN devbench cf config.yaml --to json > /app/config.json
```

### Shell scripts

```bash
# Validate before deploy
devbench cf k8s/deployment.yaml --validate || exit 1

# Extract + use a value
PORT=$(devbench cf config.yaml --get server.port --raw)
echo "Starting on port $PORT"

# Search for secrets in configs
devbench cf '*.yaml' --batch --grep 'password|secret|token' --raw | jq '.matches | length'
```

---

## Format support

| Format | Extension | Read | Write | Comments | Notes |
|--------|-----------|------|-------|----------|-------|
| JSON | `.json` | ✓ | ✓ | — | |
| JSONC | `.jsonc` | ✓ | ✓ | ✓ | JSON with `//` and `/* */` comments |
| YAML | `.yaml` `.yml` | ✓ | ✓ | ✓ | Multi-doc, YAML 1.1/1.2 |
| TOML | `.toml` | ✓ | ✓ | ✓ | Full type inference (bool, int, float, datetime) |
| XML | `.xml` | ✓ | ✓ | — | Optional `--flatten-xml` |
| CSV | `.csv` | ✓ | ✓ | — | |
| INI | `.ini` `.cfg` | ✓ | ✓ | ✓ | Type inference (booleans, numbers) |
| ENV | `.env` | ✓ | ✓ | ✓ | Dotenv format |
| HCL | `.hcl` `.tf` | ✓ | ✓ | — | Terraform/HashiCorp HCL |
| .properties | `.properties` | ✓ | ✓ | ✓ | Java/Spring properties |
| PLIST | `.plist` | ✓ | ✓ | — | macOS/iOS property lists |

---

## Piped input

```bash
# From file
devbench cf config.yaml --to json

# From stdin
cat config.yaml | devbench cf --to json
echo '{"port": 8080}' | devbench cf --to yaml

# With process substitution
devbench cf <(kubectl get deployment -o yaml) --get spec.replicas
```

---

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success (or match found for `--grep`, `--diff` identical) |
| 1 | Error (or no match for `--grep`, differences found for `--diff`, invalid for `--validate`) |
