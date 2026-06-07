I've hit a hard blocker: **this session is in "don't ask" permission mode, which auto-denies every non-read tool.** `Bash` (so `python3`/`pytest`), `Edit`, and `Write` are all denied. I confirmed Bash is denied even for `python3 -c`, and `Edit` is denied too. So I cannot implement the fixes in-place or run the test command myself.

I've completed the full analysis (read all 1120 lines of `configforge.py` and all ~480 tests across the 9 test files). Here is the complete, ready-to-apply work product.

## What the suite misses

The existing suite is extremely thorough. After auditing it against the code, the genuine gaps are all in **TOML serialization** (`_to_toml` / `_toml_scalar` / `_toml_inline`):

| # | Edge case | Current (buggy) behavior |
|---|-----------|--------------------------|
| 1 | Dict key with TOML-illegal chars: space, dot, unicode, empty (`{"my key": 1}`, `{"db.host": "x"}`) | Emits bare `my key = 1` → **invalid, non-re-parseable TOML** (and a dotted key silently becomes a nested table on round-trip) |
| 2 | Top-level scalar → TOML (`data` is a str/int/bool/None) | `_to_toml` returns `""` → **`success=True` with empty output = silent total data loss** |
| 3 | `None` nested inside a TOML array / inline-table (`{"vals":[1,None,3]}`) | `_toml_scalar(None)` falls through to `str(None)` → emits literal string `"None"` = **silent corruption** |

Only XML key-sanitization and top-level *scalar-list* → TOML are covered today; the TOML key, top-level-scalar, and nested-None cases are not.

## Fix for `core/configforge.py`

**(a)** Add a `_toml_key` helper and a `None` guard, immediately before `_toml_scalar` (currently line 750):

```python
def _toml_key(k) -> str:
    """Render a dict key as a TOML key.

    TOML bare keys may only contain A-Z a-z 0-9 _ and -. Anything else (spaces,
    dots, unicode, empty) must be a quoted key, otherwise the emitted document
    is not valid/re-parseable TOML."""
    k = str(k)
    if re.fullmatch(r"[A-Za-z0-9_-]+", k):
        return k
    esc = k.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
    return f'"{esc}"'
```

**(b)** In `_toml_scalar`, add at the very top of the function body (before `if isinstance(v, bool)`):

```python
    if v is None:
        # TOML has no null type. Reaching here means a None is nested inside an
        # array or inline table (top-level None keys are handled earlier via
        # null_handling). Refuse rather than silently emit the string "None".
        raise ValueError("TOML cannot represent a null value inside an array or inline table")
```

**(c)** In `_toml_inline`, quote the keys:
```python
    if isinstance(v, dict):
        parts = [f"{_toml_key(k)} = {_toml_inline(iv)}" for k, iv in v.items()]
```

**(d)** In `_to_toml`, apply `_toml_key` everywhere a key is emitted, and add the top-level-scalar guard. The replacements:
- root list-of-dicts: `parts = [f"{_toml_key(k)} = {_toml_inline(v)}" for k, v in item.items()]`
- `full_key = f"{prefix}.{_toml_key(k)}" if prefix else _toml_key(k)`
- scalar-list line: `lines.append(f"{_toml_key(k)} = [{', '.join(_toml_scalar(i) for i in v)}]")`
- null branch: `f"# {_toml_key(k)} = null"` and `f'{_toml_key(k)} = ""'`
- scalar else: `lines.append(f"{_toml_key(k)} = {_toml_scalar(v)}")`
- tablearray item: `lines.append(f"{_toml_key(ik)} = {_toml_inline(iv)}")`
- add a final branch after the `elif isinstance(data, dict):` block, before `return "\n".join(lines)`:
  ```python
      elif root:
          raise ValueError("TOML requires a dict (or list of dicts) at the top level")
  ```

These are all additive: normal keys (matching `[A-Za-z0-9_-]+`) pass through unchanged, so no existing test changes behavior.

## New test file: `tests/test_missed_edge_cases_5.py`

```python
"""ConfigForge — edge cases MISSED by the existing suite (Round 6).

All three concern TOML serialization, reproducible against pre-fix code:
 1. Dict keys with TOML-illegal chars (space/dot/unicode) emitted bare -> invalid TOML.
 2. A top-level scalar serialized to TOML silently produced "" with success=True.
 3. A None nested in a TOML array/inline-table was corrupted into the string "None".
"""
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from core.configforge import convert

def _j(t): return json.loads(t)

# ═══ 1. TOML keys with special characters must be quoted ═══
def test_toml_key_with_space_is_wellformed():
    r = convert(json.dumps({"my key": "v", "ok": 1}), "toml")
    assert r["success"], r.get("error")
    back = convert(r["output"], "json", "toml")
    assert back["success"], back.get("error")
    d = _j(back["output"]); assert d["my key"] == "v" and d["ok"] == 1

def test_toml_key_with_dot_is_quoted():
    r = convert(json.dumps({"db.host": "localhost"}), "toml")
    assert r["success"], r.get("error")
    back = convert(r["output"], "json", "toml")
    assert back["success"], back.get("error")
    d = _j(back["output"]); assert d["db.host"] == "localhost" and "db" not in d

def test_toml_section_name_with_space_is_quoted():
    r = convert(json.dumps({"my section": {"a": 1}}), "toml")
    assert r["success"], r.get("error")
    back = convert(r["output"], "json", "toml")
    assert back["success"], back.get("error")
    assert _j(back["output"])["my section"]["a"] == 1

def test_toml_nested_key_with_space_in_table():
    r = convert(json.dumps({"server": {"my key": "v"}}), "toml")
    assert r["success"], r.get("error")
    back = convert(r["output"], "json", "toml")
    assert back["success"], back.get("error")
    assert _j(back["output"])["server"]["my key"] == "v"

def test_toml_unicode_key_is_quoted():
    r = convert(json.dumps({"café": 1}), "toml")
    assert r["success"], r.get("error")
    back = convert(r["output"], "json", "toml")
    assert back["success"], back.get("error")
    assert _j(back["output"])["café"] == 1

def test_toml_inline_table_key_with_space():
    r = convert(json.dumps([{"my key": 1}]), "toml")
    assert r["success"], r.get("error")
    assert '"my key" = 1' in r["output"]
    assert "my key = 1" not in r["output"]

def test_toml_normal_keys_stay_bare():
    r = convert(json.dumps({"host": "x", "port": 8080}), "toml")
    assert r["success"], r.get("error")
    assert "host = " in r["output"] and '"host"' not in r["output"]

# ═══ 2. Top-level scalar → TOML must fail gracefully (force JSON source so the
#        serializer guard is exercised, not format auto-detection) ═══
def test_toml_toplevel_string_fails_gracefully():
    r = convert('"hello"', "toml", "json"); assert not r["success"] and r["error"]

def test_toml_toplevel_number_fails_gracefully():
    r = convert("42", "toml", "json"); assert not r["success"] and r["error"]

def test_toml_toplevel_bool_fails_gracefully():
    r = convert("true", "toml", "json"); assert not r["success"] and r["error"]

def test_toml_toplevel_null_fails_gracefully():
    r = convert("null", "toml", "json"); assert not r["success"] and r["error"]

def test_toml_dict_still_ok():
    r = convert(json.dumps({"a": 1}), "toml")
    assert r["success"], r.get("error"); assert "a = 1" in r["output"]

# ═══ 3. None nested in a TOML array / inline-table must not corrupt ═══
def test_toml_none_in_array_fails_gracefully():
    r = convert(json.dumps({"vals": [1, None, 3]}), "toml")
    assert not r["success"], r.get("output"); assert r["error"]

def test_toml_none_in_inline_table_fails_gracefully():
    r = convert(json.dumps([{"meta": {"k": None}}]), "toml")
    assert not r["success"], r.get("output"); assert r["error"]

def test_toml_array_without_none_still_ok():
    r = convert(json.dumps({"vals": [1, 2, 3]}), "toml")
    assert r["success"], r.get("error"); assert "vals = [1, 2, 3]" in r["output"]
```

## What I need from you

To finish — implement the fixes, write the test file, and run `python3 -m pytest tests/ -q --tb=line` — I need write/execute permissions. Please pick one:

- **Switch out of "don't ask" mode** (e.g. `acceptEdits` or a mode that allows `Edit`/`Write`/`Bash`), then tell me to proceed and I'll apply everything and run the suite, or
- **Apply the patch + test file above yourself** and run the command.

I have **not** verified these against a live run (I couldn't execute pytest), but I traced each change against the existing parametrized tests (`test_all_format_combinations`, `test_all_conversions_*`, `test_toml_*`) and they only touch the special-case paths, so existing tests should remain green. Want me to proceed once permissions are enabled?

---
_Generated by: Claude Opus 4.8 (high effort)_
