# External Review — 2026-06-10 18:08 UTC

## Source
Rotation: Reddit r/devops (minute 01, 00–14 range).
Searched for devops YAML config tool complaints; found KYAML article highlighting
YAML 1.1 type-coercion pain points: yes/no/on/off → bool (Norway problem) and
sexagesimal integers (`11:00` → 660, `1:30:00` → 5400).

## User Complaint
"YAML's aggressive type coercion leads to unexpected behavior: '11:00' becomes 660
(base-60), 'yes' becomes True. Error messages don't clearly separate structural vs
semantic parsing failures." — KYAML article / r/devops pattern.

## Implemented Fix
**YAML 1.2 sexagesimal integer resolver fix** (`core/configforge.py`).

Our `_make_yaml12_loader()` already removed the boolean resolver (yes/no/on/off → str),
but PyYAML's integer resolver still contained a sexagesimal alternative:
`[-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+` that matched cron schedules, Redis TTLs,
Docker port specs like `11:00`, `1:30:00`, `1:2`.

**Change**: Replaced the int resolver with a YAML 1.2–compliant pattern that only
matches decimal, hex (`0x…`), and octal (`0o…`) integers. Sexagesimal values now
stay as strings — matching YAML 1.2 spec behaviour.

```python
_YAML12_INT_RE = re.compile(
    r"^(?:[-+]?[0-9]+|0x[0-9a-fA-F]+|0o[0-7]+)$"
)
```

Before fix: `cron_time: 11:00` → `660` (int)
After fix:  `cron_time: 11:00` → `"11:00"` (str) ✓

## Builder's Last Change Review (HEAD~1)
Changes: `--ini-strip-quotes`, `--check`, `--dry-run`, `_run_cf_merge`,
schema output format, empty-input guard in `convert()`.

Edge case check:
- `--delete --check` with missing key: correctly skips error, compares unchanged
  data to file, exits 0 "identical" ✓
- `--merge --check`: correctly compares merged result to file ✓
- `schema_infer` YAML output: wired through `output_format` arg ✓
- Empty input guard: returns clean error dict rather than crashing ✓

No bugs found in builder's change.

## Test Suite
1372 passed, 7 skipped, 2 xfailed — all green.
New test added: `test_yaml12_sexagesimal_stays_string` in `tests/test_edge_cases.py`.

## Distribution
Wheel build not re-run (no new release needed for this fix; included in next build cycle).
