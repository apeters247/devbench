# Show HN: ConfigForge — 9-format config converter, 100% offline, comment-preserving

## Post Title (max 80 chars)

Show HN: ConfigForge – 9-format offline config converter with comment preservation

## Post Body

I got tired of juggling yq for YAML, jq for JSON, custom scripts for INI→TOML, and wondering whether "yamltojson.com" was selling my database configs.

So I built **ConfigForge** — a fully offline config file converter that handles 9 formats bidirectionally. No data leaves your machine. No signup. No ads.

```bash
# Install
pip install devbench

# Pipe anything, get JSON
echo 'name: Hello\nversion: 1.0' | devbench cf

# Convert INI with actual type inference (booleans stay boolean, not strings)
devbench cf --to toml --from ini < legacy.ini

# Batch convert 1000+ INI files to TOML with progress bar
devbench cf --batch --stream --to toml '*.ini'

# Launch interactive web UI
devbench cf --serve

# Or use the REST API
curl -X POST http://localhost:8081/api/v1/convert \
  -d '{"source":"name: test","to_format":"json","from_format":"yaml"}'
```

**The killer feature: comment preservation.** YAML comments are supposed to be documentation, but every parser strips them. ConfigForge carries comments through JSON intermediate representations — so your YAML→JSON→YAML round-trip keeps every `# DO NOT CHANGE` annotation intact.

**9 formats:** JSON, YAML, TOML, XML, CSV, INI, .env, HCL, .properties

**What makes it different from yq/jq/online tools:**

- Comment preservation in YAML round-trips (not just parsing — through JSON intermediate)
- INI→TOML type inference (booleans, numbers, dates — not string-copy semantics)
- Batch glob mode with streaming (handles 10K+ files)
- XML flattening (convert XML to clean YAML, not nested `<tag>` soup)
- Null handling with 4 modes (skip, comment as None, emit empty, raise error)
- Fully offline — zero network calls
- Built-in web UI (`--serve`) and REST API (`--api`)

Under the hood it uses ruamel.yaml for comment-aware YAML parsing, the stdlib json/tomllib/xml/csv modules, and pure-Python parsers for INI/.env/properties.

The project is open-core: CLI is free (MIT), macOS menubar app with all 9 developer tools is $19 one-time. No subscriptions.

**Links:**
- Web demo: https://naxiai.com/tools/devbench/
- GitHub: https://github.com/apeters247/devbench
- One-liner install: `curl https://naxiai.com/install.sh | bash`

Would love your feedback — especially on edge cases I might have missed. I've tested 42 conversion pairs with 830+ tests but I'm sure there are weird config files out there that'll break things.

## Common Questions (anticipate HN comments)

**Q: How is this different from yq?**
A: yq handles 2 formats (YAML↔JSON). ConfigForge handles 9. yq strips comments; ConfigForge preserves them through JSON round-trips. yq has no type inference for INI→TOML; ConfigForge converts `enabled=true` from INI to a real TOML boolean.

**Q: Why not just use jq?**
A: jq is a JSON processor, not a config converter. It can't produce TOML, INI, .env, HCL, or .properties output. If your input is YAML, you'd need yq first. ConfigForge is one tool for all formats.

**Q: Is it really free?**
A: The CLI is free (MIT license). The macOS menubar app (Devbench, includes ConfigForge + 8 other developer tools) is $19 one-time with no subscriptions.

**Q: Can it convert 10,000 files at once?**
A: Yes. `--batch --stream` mode processes files one at a time without loading everything into memory. Tested with 10K+ file directories.

**Q: Does it work on Windows?**
A: The Python package (`pip install devbench`) works on any platform with Python 3.10+. The macOS menubar app requires macOS 13+ (Apple Silicon or Intel).