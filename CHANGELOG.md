# Changelog

## [0.1.0] - 2026-06-07

### Added
- ConfigForge: multi-format config file converter (JSON, YAML, TOML, XML, CSV, INI, ENV, HCL, .properties)
- Web demo server (`--serve` mode) with interactive config converter UI
- REST API server (`--api` mode) with CORS headers and rate limiting
- CLI installer via pip (`pip install devbench`)
- Auto-detect input format from file content
- Comment preservation through YAML/INI round-trips
- Batch conversion mode with glob support
- Streaming batch mode for 10K+ file workloads
- Type inference: booleans, numbers, dates, arrays in INI/CSV → typed output
- Multi-document YAML support (--- separators)
- Unicode preservation (allow_unicode=True by default)
- XML flatten mode (convert nested XML to dotted keys)
- Null value handling (skip/comment/empty/error options for TOML output)

### Fixed
- All edge cases: Unicode RTL, deep nesting, binary data, NaN/Inf, YAML anchors, TOML inline tables, XML CDATA/namespaces, CSV BOM, INI comments-in-values, ENV multiline
- Number precision preserved for large integers
- Null value handling: YAML null/~/None → JSON null → TOML consistently