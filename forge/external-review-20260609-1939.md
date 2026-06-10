# External Review — Polisher Run 2026-06-09 19:39 UTC

## Rotation
Minute 36 → **GitHub Issues** (30-44 range) — searched yq issues for config file tool complaints.

## User Complaint Found
**Issue**: `sortKeys()` needs to consider yaml anchor — [yq#2086](https://github.com/mikefarah/yq/issues)

YAML anchors and aliases break when sort-keys is applied. When sorting keys, PyYAML expands the anchors inline rather than preserving the reference structure.

### Example Problem
```yaml
# Input with anchor
defaults: &defaults
  timeout: 30
  retries: 3
service1:
  <<: *defaults  # Merge anchor reference
  name: Service 1

# After sort_keys=True → anchor is lost
defaults:
  retries: 3
  timeout: 30
service1:
  name: Service 1
  retries: 3      # Expanded inline, no longer references &defaults
  timeout: 30
```

## Action Taken

### 1. **Identified the Issue in DevBench**
   - Confirmed DevBench has the same limitation with `--sort-keys` on YAML files containing anchors/aliases
   - Root cause: PyYAML's parser resolves anchors to concrete data; sort operation creates new dicts/lists, losing anchor metadata

### 2. **Added Documentation Test**
   - Created `test_yaml_sort_keys_known_limitation_anchors_lost()` in test_core.py
   - Explicitly documents this as a known limitation (matching yq behavior)
   - References the issue for future improvement tracking
   - Test validates that anchors are lost but data remains correct

### 3. **Added ruamel.yaml Import**
   - Added `HAS_RUAMEL_YAML` flag to detect ruamel.yaml availability
   - ruamel.yaml can preserve anchors (verified via testing)
   - Foundation for future fix: full pipeline migration to ruamel.yaml

## Test Results

### Before Changes
- 986 passed, 7 skipped, 2 xfailed

### After Changes
- **987 passed**, 7 skipped, 2 xfailed ✓
- New test documents the limitation
- All existing tests remain green

## Builder's Last Change (Reviewed)
- **--check-env flag** implementation looks solid
  - Proper environment detection (Python version, platform, architecture)
  - Optional dependency probing (pyyaml, python-hcl2, lxml, ruamel.yaml)
  - Format availability mapping (shows which formats work)
  - Both human-readable and JSON (--raw) output
  - Good CLI integration + shell completion

## Known Limitation Documented
This matches the behavior reported in yq#2086. A full fix would require:
1. Using ruamel.yaml for YAML I/O (preserves anchor metadata)
2. Custom sort logic that respects anchor structure
3. Anchor recreation on serialization

**Workaround**: Users should avoid `--sort-keys` on YAML files with `&anchor` and `*alias` references.

## Metrics
- **Lines added**: 35 (test + import + documentation)
- **Issues addressed**: 1
- **Tests added**: 1
- **Known limitations documented**: 1
