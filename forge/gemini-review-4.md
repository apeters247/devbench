# GEMINI-STYLE REVIEW: configforge.py — full code audit (manual fallback)
## Generated: 2026-06-06T20:47Z (all Gemini models 429 quota exhausted)

## Bugs (with line numbers)

### HIGH SEVERITY

1. **`_toml_key` double-escape risk (line 757)** — `re.fullmatch(r"[A-Za-z0-9_-]+", k)` is too strict: TOML bare keys also support `A-Z`, `0-9` which are included, but the regex correctly reflects this. However, quoted keys in TOML cannot contain raw double quotes — the `\\\"` escape in line 759 produces literal `\"` which is correct. **Actually this is correct — no bug.**

2. **`_reinsert_yaml_comments` fragile index shifting (lines 116-157)** — The `inserted` set is shifted by `{j + 1 if j >= i else j for j in inserted}` after each insertion. If two comments target different lines, the second insertion's offset shifts the first. This is a known fragility: inserting one comment shifts all subsequent line indices. Only tested for small comment sets; may misplace comments on large files.

3. **`_extract_yaml_comments` `any_key_before` O(n²) (line 85)** — Called for every comment line. For a 10,000-line YAML file this is 5M iterations. While not a correctness bug, it's a performance issue.

4. **`detect_format` ambiguous TOML vs INI (lines 244-267)** — The 80% threshold for typed values (`toml_indicators / total_values > 0.8`) is arbitrary. An INI file with mostly strings and a few booleans will be misclassified as TOML. This caused the `test_toml_inline_quad_nested` test to fail because `a.b.c.d = 1` wasn't detected.

5. **`_from_dict_to_xml` cross-profile injection (lines 834-872)** — XML element names are sanitized with `_xml_name()` (re.sub replaces non-word chars with `_`), but no validation for XML-specific forbidden names like `xml`, `Xml`, `XML` as element start. If a key is `xml` it becomes `<xml>...</xml>` which is technically allowed as a non-reserved name but confusing.

### MEDIUM SEVERITY

6. **INI `#` and `;` in values (line 173)** — The comment extraction in `_extract_ini_comments` always checks for `#` and `;` markers on every line, even inside quoted values. The guard `before.count('"') % 2 == 0` is insufficient for nested quotes or escaped quotes (`\\"`) in values.

7. **ENV newline value split (lines 504-522)** — The ENV parser splits on `\n` at line 504, then processes each line individually. An env value containing a literal newline (quoted) across multiple lines (`KEY="line1\nline2"`) is split across two lines and the quoted continuation is lost or corrupted. Unquoted multiline values are similarly broken.

8. **`detect_format` multi-doc YAML (lines 313-327)** — The detection checks for `:` in text or `---` prefix. If text contains `:` but is not actually YAML (e.g. a TOML file with `key = "value: 123"`), it may incorrectly return "yaml".

9. **CSV fieldnames from first row (lines 526-562)** — When no header is detected, field names are generated as `col0`, `col1`, etc. These generic names don't carry through to structured output well. No configurable column naming.

10. **`batch_convert` single-file error non-fatal (lines 947-988)** — If one file in a batch fails, the error is logged but the batch continues. No `--fail-fast` option. Files after a failure are still processed, which is correct for batch but some users expect abort-on-error.

## Missing Features

11. **No JSON schema validation** — ConfigForge doesn't validate that converted output conforms to any schema. Users expect `forge --schema schema.json input.yaml` to validate.

12. **No `--dry-run` flag** — Batch mode (`batch_convert`) has no dry-run option. Users converting 300 files want to preview before committing.

13. **No progress percentage in batch_convert** — Line 960 prints `[idx/total]` but no percentage or ETA. For 1000+ files this is bare-minimum UX.

14. **No preserve-order option for dicts** — `sort_keys` exists but there's no `--preserve-order` option. Python 3.7+ dicts are insertion-ordered, but JSON output uses `sort_keys=False` by default which preserves insertion order. Actually this works.

15. **YAML comment reinsertion doesn't handle duplicate keys at different depths** — `_reinsert_yaml_comments` uses `line.startswith(key + ":")` which matches the first occurrence in flat iteration. For nested YAML where the same key appears at different levels, the comment may be attached to the wrong occurrence.

## Edge Cases NOT Covered

16. **TOML table-array with special characters in field names** — `[[items]]` with keys containing spaces/dots in inline tables inside table-arrays.
17. **XML `<?xml ...?>` processing instruction preservation** — Currently stripped during parsing.
18. **CSV quoted fields with embedded newlines** — The CSV parser (csv.DictReader) handles this, but detect_format's delimiter sniffing uses only first 4096 bytes and may fail.
19. **YAML `null` vs `~` vs `Null` vs `NULL`** — All should map to Python None, but YAML treats `Null` as a string in some parsers.
20. **TOML date with timezone offset vs local** — `_coerce_dates` normalizes Z to +00:00 (line 436) which is correct for Python 3.10, but `datetime.fromisoformat` before 3.11 doesn't accept Z directly.

---

_Generated by: Manual fallback (all Gemini models 429 quota exhausted)_