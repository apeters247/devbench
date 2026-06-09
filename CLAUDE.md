# ConfigForge / DevBench

11-format config file converter with comment preservation + 9 developer tools.
yq/dasel alternative with TOML write support.

## Quick Start
```bash
pip install devbench   # or: pip install devbench[all]
devbench cf -f json -t yaml input.json
devbench tools                          # show 9 LLM utilities
devbench --help
```

## Project Structure
- `core/` — Main package: configforge.py (converter), cli.py (entry point), tools.py (9 utils), models.py (data models), detector.py (format detection)
- `web/` — Flask web demo + license server
- `forge/` — AI agent workspace: markers, task files, reports, SEO pages
- `tests/` — pytest suite (792 tests, 7 skipped, 2 xfailed)
- `homebrew-tap/` — Homebrew formula for macOS
- `dist/` — Built wheel + sdist
- `web/static/` — Landing page HTML/CSS

## Building
```bash
python3 -m build
```

## Testing
```bash
python3 -m pytest -q --tb=short
```

## Key Architecture
- `configforge.py` — `parse_text()` dispatches by format, `convert()` chains parse→dump, `detect_format()` probes content. Supports `--yaml12` and `--template-safe` flags.
- `cli.py` — `entry_point()` routes subcommands (`cf`, `tools`, `serve`, `license`). `cf` subcommand: `--get/--set/--delete/--merge` CRUD ops.
- `tools.py` — 9 developer utilities: token counter, text chunker, JSON formatter, text diff, URL codec, timestamp converter, UUID gen, hash gen, base64 codec.

## Distribution Channels (from forge/release-checklist.md)
1. PyPI (done — wheel builds)
2. Homebrew tap (formula written, repo not created)
3. Gumroad ($19, not listed yet)
4. GitHub releases
5. SEO landing pages (14 comparison pages live)

## Workers (cron jobs)
- **Builder**: writes code, every 15min via Claude Code
- **Polisher**: reviews + external analysis, every 15min
- **Deep Audit**: full codebase scan, every 4h
- **Overseer**: state monitoring + critical analysis, every 2h
- **Commercial Research**: market intel, every 4h
- **Gemini Reviewer**: parallel code review, every 30min