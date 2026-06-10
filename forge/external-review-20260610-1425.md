# External Review — 2026-06-10 14:25 UTC

## Rotation: HN yq alternatives (minute 18, slot 15-29)

### User Complaint
**Source:** Hacker News — multiple threads on yq naming confusion
**URL:** https://news.ycombinator.com/item?id=21986072 (and related)

Two incompatible `yq` implementations (mikefarah/Go vs kislyuk/Python) share the same name.
Users coming from yq/jq muscle-memory type `.server.port` and get confusing errors in devbench
which expects `server.port` (no leading dot).

### Fix Implemented
**`core/configforge.py` — `_split_path()`**: Strip leading dot from path so yq-style paths
work as drop-in replacements:
- `.server.port` → `['server', 'port']` (same as `server.port`)
- `.items[0].name` → `['items', '0', 'name']`
- `.` → `[]` → returns root document (yq's `. ` idiom)

This makes devbench a drop-in for common yq `--get`/`--set`/`--delete`/`--append` invocations.

### Tests Added (4 new)
- `test_get_leading_dot_yq_style` — `.server.port` works like `server.port`
- `test_get_leading_dot_bracket_notation` — `.items[0].name` with bracket index
- `test_get_dot_only_returns_root` — `.` returns full document
- `test_set_leading_dot_yq_style` — `--set .server.port 9200` works

### Builder's Last Change Review (HEAD~1)
**Change:** Preserve blank lines + comments in --set/--append/--delete (yq#1248)
**Assessment:** Correct. Extracts comments/blanks before mutation, reinserts after serialization.
**Edge cases verified:**
- Guard `if detected_fmt == "yaml" and _cf.HAS_YAML` correctly handles missing ruamel.yaml
- `if blanks:` / `if comments:` guards prevent no-op reinsertion overhead
- No issue found with unicode (ruamel.yaml handles it natively)

### Test Suite
- Before: 1367 passed, 7 skipped, 2 xfailed
- After:  1371 passed, 7 skipped, 2 xfailed (+4 new tests)

### Distribution
- Wheel build: `devbench-1.0.0-py3-none-any.whl` — built successfully
- PyPI: not yet published (manual step required)
