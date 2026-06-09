# homebrew-devbench

Custom Homebrew tap for [devbench](https://naxiai.com/tools/devbench/) — ConfigForge, the 11-format config converter.

## Install

```bash
brew tap apeters247/devbench
brew install devbench
```

## Usage

```bash
# Convert YAML to JSON
devbench cf deployment.yaml -t json

# Convert JSON to TOML (pipe)
cat package.json | devbench cf -t toml

# Convert .env to YAML
devbench cf production.env -t yaml

# Extract a value
devbench cf config.yaml --get server.port

# Edit in-place
devbench cf config.yaml --set server.port 8080 --in-place

# Batch convert
devbench cf '*.yaml' -t json --batch --output-dir out/

# YAML 1.2 strict booleans (prevent Norway problem)
devbench cf config.yaml -t json --yaml12
```

## Supported Formats

JSON · JSONC · YAML · TOML · XML · CSV · INI · .env · HCL · .properties · plist (11 total)

## Why ConfigForge?

| Feature | ConfigForge | yq | dasel |
|---------|-------------|-----|-------|
| TOML write | ✅ | ❌ | ❌ |
| Comment preservation | ✅ | Partial | ❌ |
| Formats | 11 | 7 | 8 |
| Batch/streaming | ✅ | ❌ | ❌ |
| YAML 1.2 strict booleans | ✅ | ❌ | ❌ |
| plist support | ✅ | ❌ | ❌ |

## Tap Setup (for maintainers)

This tap lives at `github.com/apeters247/homebrew-devbench`. To update after a new PyPI release:

1. Upload to PyPI: `python3 -m twine upload dist/devbench-X.Y.Z.tar.gz`
2. Get the new SHA256: `curl -s https://pypi.org/pypi/devbench/X.Y.Z/json | python3 -c "import json,sys; data=json.load(sys.stdin); [print(f[\"digests\"][\"sha256\"]) for f in data[\"urls\"] if f[\"packagetype\"]==\"sdist\"]"`
3. Update `Formula/devbench.rb`: bump `url`, `sha256`, `version`
4. Commit and tag: `git tag vX.Y.Z && git push origin vX.Y.Z`

## License

MIT
