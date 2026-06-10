# External Review — 2026-06-10 12:21 UTC

## Rotation
Minute 18 → HN yq alternatives (15-29 window)

## Source
Hacker News comment by a-nikolaev (Nov 2023)
https://news.ycombinator.com/item?id=38464937

> "jq feels like a much more robust tool than yq. I understand that the task of processing YAML is much harder than JSON, but: yq changed its syntax between version 3 and 4 to be more like jq (but not quite the same for some reason); yq has no if-then-else which is a poor design (or omission) in my opinion. So yq works when you need to process YAML, it can even handle comments quite well. But for pure JSON processing jq is a better tool."

## Complaint Summary
User finds yq's syntax confusing, inconsistent across versions, and missing basic control flow. They prefer jq for JSON and tolerate yq only for YAML.

## ConfigForge Relevance
ConfigForge avoids the entire DSL-learning-curve complaint: instead of a custom query language with version-specific syntax, it uses simple CLI flags (`--get`, `--set`, `--merge`, `--select`, `--sort-by`, etc.) that are intuitive and stable. Users convert between 11 formats with `devbench cf -f json -t yaml input.json` — no jq/yq-like expression language to learn.

## Builder's Last Commit Review (4a136b1)

### Changes
- `--explicit-start`, `--explicit-end`, `--yaml-width` flags for YAML output
- `--merge-dedupe-lists` for merge deduplication
- `-` stdin sentinel in `_get_input`
- Format access levels (rw/r) in `_get_env_info`
- BOM handling, dotted-key escape (`\.`), TOML array comments
- Concurrent request tests
- Security fixes (body size limit, symlink check, error sanitization)
- Shell completions (zsh, fish, bash)

### Bugs Found & Fixed
1. **test_check_env_formats_all_available silently passing** — Builder changed `_get_env_info()` return type from `dict[str, bool]` to `dict[str, dict]`. The test iterated `for f, ok in data["formats"].items()` and checked `if not ok` — since dicts are always truthy, this never detected unavailable formats. Fixed in `tests/test_core.py:2077` to check `finfo["available"]`.

### Build Artifacts
- `build/` and `*.pyc` files tracked in git despite `.gitignore` entries (pre-existing, not introduced by this commit)

## Tests
1356 passed, 7 skipped, 2 xfailed — 0 failures.