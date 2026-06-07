# ConfigForge: Why I Built a 9-Format Offline Config Converter

**TL;DR:** I got tired of juggling `yq`, `jq`, and sketchy online converters.
So I built ConfigForge — an offline, comment-preserving config file converter
that handles YAML, JSON, TOML, XML, CSV, INI, .env, HCL, and .properties.
It's part of the Devbench toolkit, $19 one-time, no subscription.

---

## The Breaking Point

It was 2 AM on a Tuesday. I was migrating a Kubernetes cluster from
Helm charts to a custom orchestrator, and I had 47 `.yaml` files that
needed to become JSON. Simple, right?

I reached for `yq`:

```bash
yq -o json deployment.yaml
```

Lost all my comments.

I tried an online converter. It asked me to create an account. I closed
the tab.

I wrote a Python script with `json.dumps(yaml.safe_load(f))`. It handled
the conversion fine — but when I went back to YAML, every single inline
documentation comment was gone. The `# DO NOT CHANGE` warnings. The
`# This env var controls the replica count` notes. Pfft. Gone.

That's when I realized: **there is no config converter that treats comments
as first-class citizens.** Every tool on the market — `yq`, `jq`, online
converters, hand-rolled scripts — discards comments the instant you
touch a file.

So I built one.

---

## What ConfigForge Does

ConfigForge converts config files between 9 formats:

```
YAML ↔ JSON ↔ TOML ↔ XML ↔ CSV ↔ INI ↔ .env ↔ HCL ↔ .properties
```

All offline. All local. No data leaves your machine.

The killer feature? **Comment preservation.** When you go YAML → JSON →
YAML, your comments survive the round trip. The `# DO NOT CHANGE`
warnings stay exactly where you put them.

## Why Not Just Use yq?

`yq` is great for simple YAML→JSON queries. But:

| Feature | ConfigForge | yq | jq | Online |
|---------|-------------|-----|-----|--------|
| Comment preservation | ✅ | ❌ | N/A | ❌ |
| 9 formats | ✅ | 2 (YAML+JSON) | 1 (JSON) | Varies |
| Offline | ✅ | ✅ | ✅ | ❌ |
| Batch glob mode | ✅ | Partial | ❌ | ❌ |
| Streaming (10K+ files) | ✅ | ❌ | ❌ | ❌ |
| Type inference (INI→TOML) | ✅ | N/A | N/A | ❌ |
| No account required | ✅ | ✅ | ✅ | ❌ |
| Price | $19 one-time | Free | Free | Free (data theft) |

## The Architecture

Under the hood, ConfigForge uses a unified internal representation —
every format is parsed into the same dict structure, then serialized
to the target format. This means:

1. **Format symmetry:** YAML→JSON→TOML is a two-step process, not a
   custom path. Any format can convert to any other format.

2. **Comment extraction:** Before parsing, ConfigForge strips and stores
   comments (YAML inline `#` and block-level, INI `;` and `#`). After
   serialization, they're re-injected at the correct positions.

3. **Type inference:** INI and .env files are all strings by nature.
   ConfigForge detects booleans (`true`/`false`), integers (`42`),
   floats (`3.14`), dates (ISO 8601), and null values, converting them
   to proper typed equivalents in TOML, JSON, or YAML.

## The CLI

```bash
# Basic conversion
devbench cf config.yaml --to json > config.json

# Batch convert 300 Kubernetes manifests
devbench cf *.yaml --to json --batch --output-dir ./json-output/

# Streaming mode for 10K+ files
devbench cf ./configs/*.yaml --to toml --batch --stream

# Detect format automatically
devbench cf detect mystery.conf

# Advanced options
devbench cf settings.yaml --to toml \
  --indent 4 \
  --flatten-xml \
  --sort-keys \
  --null-handling skip
```

## The Web Demo

Prefer a GUI? Every Devbench install comes with a local web server:

```bash
devbench cf --serve --port 8080
# Opens at http://localhost:8080
```

Paste config, detect format, convert, copy. All runs locally —
no data sent anywhere.

## The REST API

Integrate ConfigForge into your CI/CD or dev tools:

```bash
curl -X POST http://localhost:8081/api/v1/convert \
  -H "Content-Type: application/json" \
  -d '{"source": "timeout: 30\ndebug: true", "to_format": "toml"}'
```

## Who Is This For?

- **DevOps engineers** wrangling Kubernetes YAMLs, Docker Compose files,
  Ansible playbooks, Terraform HCL
- **Developers** migrating between config formats (INI→TOML, JSON→YAML,
  XML→anything)
- **Security-conscious teams** who refuse to paste production configs
  into online converters
- **Anyone with 100+ config files** who needs reliable batch conversion

## What's Next

- **macOS .app** — native SwiftUI menubar app (pending Mac Mini delivery)
- **Gumroad / Stripe** — $19 one-time purchase, license key via email
- **macOS .dmg** — signed, notarized, ready to distribute

## Try It

```bash
curl -sSL https://naxiai.com/install.sh | bash
devbench cf --help
```

Or try the web demo: **[naxiai.com/tools/devbench/demo](https://naxiai.com/tools/devbench/demo)**

---

*Built by [Andrew Peters](https://naxiai.com) — no VC, no ads, no data collection.
$19 one-time. Configs stay on your machine.*

---

## Discussion Threads

- **Hacker News:** Show HN — comment inline
- **Reddit r/devops:** Config file conversion without losing your mind
- **Reddit r/selfhosted:** The offline config converter you've been waiting for
- **Twitter/X:** @andrew_l_peters