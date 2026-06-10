---
title: "Positional Merge YAML Lists CLI — devbench cf --list-merge merge"
description: "Merge two YAML (or JSON/TOML) files and combine their arrays by position rather than appending. devbench cf --merge --list-merge merge. Ideal for Kubernetes patch workflows."
keywords: "merge yaml lists by position, positional yaml merge cli, yaml list merge strategy, merge yaml arrays command line, kubernetes yaml patch merge"
og_title: "Positional Merge YAML Lists from the CLI"
og_description: "Control how list values are merged when combining YAML, JSON, or TOML config files. devbench cf --merge supports append (default), replace, and positional merge strategies."
---

# Positional Merge for YAML Lists from the CLI

When you deep-merge two config files with overlapping list values, you have three different things you might want to happen:

1. **Append** — keep every item from both lists (good for log sinks, feature flags)
2. **Replace** — the overlay list completely overwrites the base list (good for env vars)
3. **Positional / merge** — overlay items are merged onto base items at the same index (good for Kubernetes container specs, where index 0 is always the main container)

`devbench cf --merge` supports all three via `--list-merge`:

```bash
devbench cf base.yaml --merge overlay.yaml --list-merge append   # default
devbench cf base.yaml --merge overlay.yaml --list-merge replace
devbench cf base.yaml --merge overlay.yaml --list-merge merge    # positional
```

## Example: Patching a Kubernetes Deployment

Base `deployment.yaml`:
```yaml
spec:
  containers:
    - name: app
      image: myapp:1.0.0
      env:
        - name: LOG_LEVEL
          value: info
    - name: sidecar
      image: envoy:1.28
```

Overlay `patch.yaml`:
```yaml
spec:
  containers:
    - image: myapp:1.1.0
      env:
        - name: LOG_LEVEL
          value: debug
```

```bash
devbench cf deployment.yaml --merge patch.yaml --list-merge merge
```

Output — container 0 is patched, container 1 is untouched, keys not present in the overlay are preserved:
```yaml
spec:
  containers:
    - name: app
      image: myapp:1.1.0
      env:
        - name: LOG_LEVEL
          value: debug
    - name: sidecar
      image: envoy:1.28
```

With `--list-merge append` (the default), you'd get *four* containers — that's almost never what you want for a Kubernetes patch.

## List Merge Strategy Comparison

| Strategy | What happens to list items | When to use |
|----------|---------------------------|-------------|
| `append` (default) | All base items + all overlay items | Feature flag lists, log sinks, additives |
| `replace` | Overlay list replaces base list entirely | Env var blocks, full rewrite |
| `merge` | Overlay items deep-merged onto base at same index | Kubernetes specs, Docker Compose service patches |

## Combining with `--select` for Targeted Patches

```bash
# Only patch containers matching name=app, leave others alone
devbench cf deployment.yaml --select spec.containers --merge patch.yaml --list-merge merge
```

## Comparison with Other Tools

`yq` and `dasel` perform simple append-or-replace list merging. Neither supports index-aligned positional merging without a custom expression.

`kubectl apply` strategic merge patch supports positional semantics for Kubernetes resources only. `devbench cf --list-merge merge` brings the same behaviour to *any* YAML/JSON/TOML file outside of Kubernetes tooling.

```bash
# Without devbench: multi-step yq pipeline for a simple container image patch
IMAGE="myapp:1.1.0"
yq eval ".spec.containers[0].image = \"$IMAGE\"" deployment.yaml

# With devbench: declarative overlay, no index magic needed
devbench cf deployment.yaml --merge patch.yaml --list-merge merge --in-place
```

## Install

```bash
pip install devbench-cf
# or
pip install devbench
```

Works on macOS, Linux, and Windows. Python 3.10–3.13.

## Related Commands

- `--merge OVERLAY` — deep-merge a second config file onto the base
- `--list-merge append|replace|merge` — control list merge behaviour (default: append)
- `--in-place` — write the merged result back to the source file
- `--set PATH VALUE` — set a specific value by path after merging
