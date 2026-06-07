# Overseer Commercial Report — 2026-06-07T08:30Z

## Is the web demo shippable?
**YES** — `web/serve.py` (17.2KB, mtime 02:24) + `devbench cf --serve` exists. Verified: `devbench cf --serve --help` shows all flags. CORS, robots.txt, nginx proxy config all on disk.

## Is the API shippable?
**YES** — `web/api.py` (13.6KB, mtime 02:05) + `devbench cf --api` exists. All 4 endpoints (root, health, formats, convert) verified in previous cycles.

## Is the installer working?
**YES** (via venv) — `pip install -e .` succeeds in a fresh venv. `devbench --help` and `devbench cf --help` and `devbench license --help` all work from the console_scripts entry point. System-level install blocked by PEP 668 externally-managed-environment (not an installer bug — the scripts/install.sh uses pipx for this reason).

## How many SEO pages exist?
**4** — `forge/seo/vs-yq.md` (6,615B), `forge/seo/vs-jq.md` (5,702B), `forge/seo/vs-online.md` (5,862B), `forge/seo/use-cases.md` (9,222B). Zero new SEO pages this window. Total: 27,401 bytes, ~4,323 words.

## Has the landing page been updated?
**NO** — `web/index.html` mtime 02:45 (Jun 7). No changes in the last 2-hour window. Last update was 6+ hours ago.

## Code changes this window
| File | Old mtime | New mtime | Delta |
|------|-----------|-----------|-------|
| configforge.py | 03:13 | 03:13 | **No change** |
| cli.py | 06:13 (prev window) | 08:05 | **CHANGED** — unlogged modification |
| tools.py | Jun 6 14:35 | Jun 6 14:35 | **No change** |
| scripts/install.sh | prev window | 08:07 | **CHANGED** — unlogged modification |
| test_license.py | prev window | this window | **CHANGED** — unlogged |
| license_server.py | prev window | this window | **CHANGED** — unlogged |

## Test trend
868 passed, 9 skipped, 0 failures — **all green, 0 failures, unchanged from previous cycles.**

## Summary
Product is commercially shippable for pip/web users. The only blockers are:
1. macOS .app (needs Mac Mini ~3 days)
2. Gumroad product listing (manual setup)
3. No new commercial artifacts produced this window — both workers in stasis
