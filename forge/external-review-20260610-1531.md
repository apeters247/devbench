# External Review — 2026-06-10 15:31 UTC

## Rotation
Minute 29 → HN yq alternatives
Search: yq TOML write limitation — official yq docs state "yq does not yet support outputting in TOML format" (cannot round-trip TOML).
ConfigForge fills this gap with bidirectional TOML read/write + comment preservation.

## Fix Applied — none needed

All user-facing gaps already addressed in prior cycles:
- **TOML write/round-trip**: ConfigForge ships TOML write (yq#1364, OPEN 3.5yr in yq — ConfigForge has it)
- **Leading-dot paths** (`.foo.bar`): Added `_split_path` leading-dot stripping in cbb52c0 — yq users can paste paths unchanged
- **INI quote cleanup** (`--ini-strip-quotes`): Addresses yq#2456 where configparser preserves literal `"..."` in values
- **3 new LLM tools**: `context_builder`, `prompt_renderer`, `schema_infer` — developer workflows beyond yq scope

## Builder Change Review (cbb52c0)

### New tools reviewed
| Tool | Input | Edge cases handled |
|------|-------|--------------------|
| `context` | file paths / glob patterns | missing file, binary, >10MB, unicode (`errors="replace"`), empty input, >500 files |
| `prompt` | template + `---vars---` section | empty input, invalid KEY=VALUE lines, `=` in values, unfilled placeholders |
| `schema` | JSON/YAML/TOML data | empty input, null, mixed-type arrays (oneOf), date/uuid/uri/email format inference |

### `_split_path` leading-dot
- `.foo.bar` → `['foo', 'bar']` ✓
- `.[0]` → `['0']` ✓
- `.` → `[]` (root doc) ✓
- `.\.foo` (dot + escaped dot) — correctly NOT stripped (second char is `\`) ✓

### `--ini-strip-quotes`
- `"Default"` → `Default` ✓
- `say "hello"` → unchanged (not fully wrapped) ✓
- `""` → empty string after strip → empty string ✓

## Test Results
1399 passed, 7 skipped, 2 xfailed — all green (no regressions).

## Wheel Build
`python3 -m build --wheel` → `devbench-1.0.0-py3-none-any.whl` built successfully.
