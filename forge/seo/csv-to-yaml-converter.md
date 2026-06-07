---
title: "CSV to YAML Converter — Free CLI Tool for Server Inventory & Data Configs"
description: "Convert CSV spreadsheets to YAML with proper list-of-dicts structure. CLI tool for Ansible inventory, server configs, and batch data transformation. 100% offline, no data uploaded."
keywords: "csv to yaml converter, csv to yaml cli, convert csv to yaml batch, csv to ansible yaml, csv to yaml list of dicts, spreadsheet to yaml config"
og_title: "CSV to YAML Converter — Free Offline CLI"
og_description: "Convert CSV files to properly structured YAML lists and maps. Handles headers, nested keys, quoted values, and batch conversion. Perfect for server inventories and data configs."
---

# CSV to YAML Converter: Free Offline CLI Tool

Need to convert a spreadsheet of server configurations into Ansible inventory YAML? Converting 200-row CSV exports into structured config files? You need a **CSV to YAML converter** that understands headers, types, and proper YAML structure.

## The Problem with CSV → YAML

A Stack Overflow user asked: *"I have a CSV file with 200 rows of server configurations. Each row needs to become a YAML block. Python libraries exist but I want a simple CLI. Is there anything?"*

Most converters produce flat, unreadable output. ConfigForge generates proper YAML lists of dicts, ready to use in Ansible, Kubernetes, or Docker Compose.

## Install

```bash
pip install devbench-cf
```

Or try the web demo: [ConfigForge Web Demo](https://naxiai.com/tools/devbench/demo/)

## Example: CSV Server Inventory to YAML

**Input: `servers.csv`**

```csv
name,host,port,region,environment,enabled,os
web-01,10.0.1.10,443,us-east-1,production,true,ubuntu
web-02,10.0.1.11,443,us-east-1,production,true,ubuntu
db-01,10.0.2.10,5432,us-east-1,production,true,debian
cache-01,10.0.3.10,6379,eu-west-1,staging,false,alpine
dev-01,10.0.4.10,8080,eu-west-1,development,true,ubuntu
```

**Convert to YAML:**

```bash
devbench cf servers.csv --to yaml
```

**Output: `servers.yaml`**

```yaml
servers:
  - name: web-01
    host: 10.0.1.10
    port: 443
    region: us-east-1
    environment: production
    enabled: true
    os: ubuntu
  - name: web-02
    host: 10.0.1.11
    port: 443
    region: us-east-1
    environment: production
    enabled: true
    os: ubuntu
  - name: db-01
    host: 10.0.2.10
    port: 5432
    region: us-east-1
    environment: production
    enabled: true
    os: debian
  - name: cache-01
    host: 10.0.3.10
    port: 6379
    region: eu-west-1
    environment: staging
    enabled: false
    os: alpine
  - name: dev-01
    host: 10.0.4.10
    port: 8080
    region: eu-west-1
    environment: development
    enabled: true
    os: ubuntu
```

## Converting CSV to Ansible Inventory YAML

Ansible expects a specific structure. ConfigForge can help:

```bash
# Group servers by environment
devbench cf servers.csv --to yaml | grep -A 5 "environment: production"
```

Or pre-process your CSV for Ansible:

```yaml
# Convert CSV to structured Ansible inventory
all:
  children:
    production:
      hosts:
        web-01:
          ansible_host: 10.0.1.10
        db-01:
          ansible_host: 10.0.2.10
    staging:
      hosts:
        cache-01:
          ansible_host: 10.0.3.10
```

## Type Detection in CSV→YAML

ConfigForge detects types from CSV values just like it does for INI:

| CSV Value | YAML Output |
|-----------|-------------|
| `true`, `false`, `yes`, `no` | `true` / `false` (boolean) |
| `42`, `8080`, `-7` | `42` / `8080` (integer) |
| `3.14`, `0.5` | `3.14` / `0.5` (float) |
| `"quoted"`, `plain` | `"quoted"` / `plain` (string) |
| `"2024-01-15"` | `2024-01-15` (date) |
| Empty cell | (field omitted) |

## Batch Convert All CSV Files

```bash
# Convert every CSV in a directory
devbench cf data/*.csv --to yaml --out-dir ./yaml-output/

# With progress
devbench cf data/*.csv --to yaml --verbose
```

## Advanced: CSV with Nested Column Headers

For spreadsheets with dot-notation headers like `network.dns.primary`:

```csv
name,network.dns.primary,network.dns.secondary,storage.volume,storage.size_gb
web-01,8.8.8.8,8.8.4.4,/dev/sda1,100
db-01,10.0.0.1,10.0.0.2,/dev/xvdf,500
```

**Command:** `devbench cf servers.csv --to yaml` generates nested YAML:

```yaml
- name: web-01
  network:
    dns:
      primary: 8.8.8.8
      secondary: 8.8.4.4
  storage:
    volume: /dev/sda1
    size_gb: 100
- name: db-01
  network:
    dns:
      primary: 10.0.0.1
      secondary: 10.0.0.2
  storage:
    volume: /dev/xvdf
    size_gb: 500
```

## Comparison: ConfigForge vs Other CSV→YAML Tools

| Feature | ConfigForge | Python pandas | awk/sed | Online tools |
|---------|-------------|---------------|---------|-------------|
| Type inference | ✅ Auto booleans, numbers | ✅ With code | ❌ Strings | ❌ Strings |
| Nested headers | ✅ Dot-notation | ⚠️ Requires code | ❌ | ❌ |
| Batch mode | ✅ Glob `*.csv` | ⚠️ Script required | ✅ Loop | ❌ |
| Offline | ✅ Zero network | ✅ | ✅ | ❌ Upload |
| One-command | ✅ `devbench cf` | ❌ Write script | ❌ Debug each | ✅ Browser |
| Unicode support | ✅ Full | ✅ | ⚠️ Locale | ⚠️ |

## Common Use Cases

### Ansible Dynamic Inventory

```bash
# Convert Terraform CSV output to Ansible YAML inventory
terraform output -csv > instances.csv
devbench cf instances.csv --to yaml > inventory.yaml
```

### Kubernetes Config Generation

```bash
# Convert deployment spreadsheet to YAML blocks
devbench cf deployments.csv --to yaml > deployments.yaml
```

### CI/CD Pipeline Integration

```bash
# In CI
pip install devbench-cf
devbench cf reports/*.csv --to yaml --out-dir ./converted/
```

## Related Resources

- [ConfigForge vs jq](/tools/devbench/forge/seo/vs-jq.html)
- [ConfigForge Real-World Use Cases](/tools/devbench/forge/seo/use-cases.html)
- [XML to YAML Conversion Guide](/tools/devbench/forge/seo/xml-to-yaml-guide.html)

## Quick Reference

```bash
# Simple convert
devbench cf data.csv --to yaml > output.yaml

# Batch mode
devbench cf *.csv --to yaml --out-dir yaml-files/

# With format override
devbench cf data.csv --to yaml --from csv

# Expand nested headers
devbench cf data.csv --to yaml --expand-dots
```

---

*ConfigForge — convert config files between 9 formats. CSV to YAML included. One-time purchase $19.*