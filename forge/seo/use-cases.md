---
title: "ConfigForge Real-World Use Cases — Kubernetes, Docker, Ansible, CI/CD"
description: "Real-world config conversion workflows: Kubernetes YAML to JSON, Docker Compose YAML to JSON, Ansible INI to YAML, CI/CD pipeline integration, batch conversions. ConfigForge CLI examples for each use case."
keywords: "convert kubernetes yaml to json, docker compose yaml to json, ansible ini to yaml, ci cd config conversion, batch config converter, real world config forge"
og_title: "ConfigForge Use Cases — K8s, Docker, Ansible, CI/CD"
og_description: "Real ConfigForge workflows: convert K8s YAML to JSON, Docker Compose YAML, Ansible INI inventory, CI/CD pipeline integration. Batch mode, type inference, offline."
---

# ConfigForge Real-World Use Cases: Convert Between 9 Config Formats

ConfigForge (`devbench cf`) converts configuration files between **9 formats** — JSON, YAML, TOML, XML, CSV, INI, .env, HCL, and Java .properties — bidirectionally, 100% offline, with comment preservation. Here are the real-world workflows where it saves you time and protects your data.

## 1. Convert Kubernetes YAML to JSON

**Scenario:** You maintain a Kubernetes manifests directory and need to feed your YAML configs into a JSON-only tool — a monitoring dashboard, a custom controller, or a CI pipeline step that reads JSON.

Kubernetes manifests often use multi-document YAML with `---` separators. Most converters either crash on multi-doc YAML or silently process only the first document. ConfigForge handles the full file:

```bash
# Convert a multi-doc Kubernetes YAML to JSON, preserving all documents
devbench cf --to json < deployment.yaml

# Batch convert an entire manifests directory
devbench batch --tool cf --files "manifests/*.yaml" --to json
```

**Why ConfigForge:** Works 100% offline — your cluster secrets never leave your machine. Handles multi-document `---` separators natively. Preserves YAML comments through the conversion where other tools strip them silently.

---

## 2. Convert Docker Compose YAML to JSON

**Scenario:** You need to transform `docker-compose.yml` into JSON for a custom deployment orchestrator, a configuration management system, or a CI pipeline that only accepts JSON.

```bash
# Convert docker-compose.yml to JSON for pipeline processing
devbench cf --to json < docker-compose.yml

# Auto-detect format and convert
cat docker-compose.yml | devbench cf --to json
```

**Why ConfigForge:** Converts inline anchors, environment variable formatting, and service definitions correctly. No upload to a third-party server — critical when your compose file contains image names, secrets, and internal network configs.

---

## 3. Convert Ansible Vars YAML to JSON

**Scenario:** You have Ansible playbooks with extensive variable files (`group_vars/all.yml`) that need to be consumed by a Python automation script or a dynamic inventory system that reads JSON.

```bash
# Convert Ansible vars YAML to JSON
devbench cf --to json < group_vars/all.yml

# Or convert to YAML for the reverse — JSON inventory to Ansible vars
devbench cf --to yaml < inventory.json
```

**Why ConfigForge:** Preserves the nested dict structure of Ansible variables. Comments explaining each variable are preserved in YAML output. Works in air-gapped environments where you can't reach external APIs.

---

## 4. CI/CD Pipeline Config Converter

**Scenario:** Your CI/CD pipeline (GitHub Actions, GitLab CI) generates or transforms config files between formats. You need a tool that runs reliably in a build runner without external dependencies.

```yaml
# GitHub Actions workflow step
- name: Convert configs for deployment
  run: |
    pip install devbench-cf
    devbench cf --to json < config/production.yml > dist/config.json
```

```bash
# Convert all TOML configs to JSON in a CI pipeline
devbench batch --tool cf --files "config/*.toml" --to json
```

**Why ConfigForge:** Zero external API calls — no rate limits, no network dependency, no service outages to worry about. Standard exit codes make failures fail the build. Batch mode handles directory-wide conversions in one command.

---

## 5. Convert Terraform HCL ↔ JSON

**Scenario:** You're working with Terraform configurations and need to convert HCL files to JSON for code generation tools, or convert generated JSON back to HCL for Terraform consumption.

```bash
# Convert Terraform HCL to JSON for tooling
devbench cf --to json --from hcl < main.tf

# Convert JSON back to HCL for Terraform
devbench cf --to hcl --from json < plan.json
```

**Why ConfigForge:** HCL support covers Terraform `.tf` files without needing the full Terraform CLI. Bidirectional conversion lets you round-trip between HCL and JSON for code generation pipelines.

---

## 6. Convert Spring Boot .properties to YAML

**Scenario:** Your Java microservices project is migrating from Spring Boot's `application.properties` to `application.yml` for better readability and hierarchical structure. You have dozens of property files to convert.

```bash
# Convert a single properties file to YAML
devbench cf --to yaml --from properties < application.properties

# Batch convert all property files in a project
devbench batch --tool cf --files "src/**/*.properties" --to yaml
```

**Why ConfigForge:** Built-in Java .properties support handles all three separator styles (`key=value`, `key:value`, `key value`), continuation lines, Unicode escapes, and preserves comment blocks. Pure-Python implementation — no Java runtime required.

---

## 7. Convert .env → JSON

**Scenario:** Your Docker deployment system generates hundreds of `.env` files that need to be imported into a JSON-based monitoring dashboard or configuration service.

```bash
# Convert .env to JSON
devbench cf --to json --from env < production.env

# Convert JSON back to .env for Docker injection
devbench cf --to env --from json < config.json
```

**Why ConfigForge:** Properly handles quoted values, whitespace in values, and multiline env vars. Runs entirely offline — your secrets in `.env` files never reach a network.

---

## 8. Legacy INI → YAML Modernization

**Scenario:** You're modernizing a legacy Python or PHP application that uses INI config files and migrating to YAML or TOML for new development.

```bash
# Convert INI to clean YAML
devbench cf --to yaml --from ini < legacy.ini

# Convert INI to typed TOML (booleans, numbers stay typed)
devbench cf --to toml --from ini < config.ini
```

**Why ConfigForge:** INI → TOML type inference converts `enabled = 1` to `enabled = true`, `timeout = 30` to `timeout = 30` (integer), and `debug = true` to `debug = true` (boolean). Other converters leave everything as strings.

---

## 9. Batch Directory Conversion

**Scenario:** You have 300+ config files across multiple formats that need to be converted to a single format for a migration project.

```bash
# Convert all YAML files in a project tree to JSON
devbench batch --tool cf --files "configs/**/*.yaml" --to json

# Convert all INI files to TOML in one command
devbench batch --tool cf --files "legacy/**/*.ini" --to toml
```

**Why ConfigForge:** Native batch mode with glob patterns and per-file error reporting. One command converts hundreds of files with a single startup cost — no shell loops, no error-prone `find -exec` pipelines.

---

## Feature Comparison: ConfigForge vs Alternatives

| Workflow | ConfigForge | kubectl | yq | jq | Online Converters |
|---|---|---|---|---|---|
| **K8s YAML → JSON** | ✅ Native, multi-doc | ✅ `kubectl get -o json` | ⚠️ Manual | ❌ | ⚠️ Data upload |
| **Docker Compose → JSON** | ✅ Native | ❌ | ⚠️ Limited | ❌ | ⚠️ Data upload |
| **HCL ↔ JSON** | ✅ HCL support | ❌ | ❌ | ❌ | ❌ |
| **.properties ↔ YAML** | ✅ Native | ❌ | ❌ | ❌ | ❌ |
| **.env → JSON** | ✅ Native | ❌ | ❌ | ❌ | ❌ |
| **INI → TOML** | ✅ Typed conversion | ❌ | ❌ | ❌ | ❌ |
| **Batch directory** | ✅ Glob + progress | ❌ | ⚠️ Shell loop | ⚠️ Shell loop | ❌ |
| **Comment preservation** | ✅ YAML, INI, .env | ❌ | ⚠️ Partial | ❌ | ❌ |
| **100% offline** | ✅ Zero API calls | ✅ | ✅ | ✅ | ❌ Requires web |
| **Multi-doc YAML** | ✅ Full support | ✅ | ⚠️ Split mode | ❌ | ❌ |
| **Formats supported** | **9** | 1 (YAML) | 2 (YAML, JSON) | 1 (JSON) | Usually 1-2 |
| **Install** | `pip install` | `kubectl` | Binary | `apt`/`brew` | Browser |

---

## Why ConfigForge Is the Right Tool for These Workflows

ConfigForge exists because no single tool handles the full spectrum of real-world config conversion:

- **9 formats, one CLI:** Stop juggling `yq` for YAML, `jq` for JSON, `tomlq` for TOML, and custom scripts for INI and `.env`. ConfigForge does all 9 in a single pip-installable command.
- **100% offline, zero telemetry:** Your configs — secrets, credentials, internal hostnames — never leave your machine. No API calls, no data harvesting, no compliance risk.
- **Comment preservation:** The documentation in your YAML and INI files survives round-trip conversions. Safety warnings, author notes, and TODOs stay intact.
- **Batch mode:** Convert 300 files or a single file with the same command. Sequential per-file processing with progress reporting and error isolation.
- **Type-aware:** INI → TOML conversion infers booleans, integers, floats, and datetime values. Not just string-copy semantics.

```bash
# Install in one command
pip install devbench-cf

# Then convert anything to anything, 100% offline
devbench cf --to yaml --from json < data.json > config.yaml
```

Whether you're a **DevOps engineer converting Kubernetes YAML to JSON** for a monitoring stack, a **backend developer migrating Spring Boot .properties to YAML**, or a **platform team batch-converting 300 config files for a migration**, ConfigForge is the single CLI tool that handles your workflow.

---

_Generated by: Claude Opus 4.8 (high effort)_