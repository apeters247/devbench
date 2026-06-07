# Commercial Status — 2026-06-07T04:14Z

**Window:** 02:07Z → 04:14Z

**Is the web demo shippable?** ✅ YES
- `web/serve.py` exists (17,236 bytes, mtime 02:24) — syntax-valid, CORS-enabled, serves /detect and /convert endpoints
- `devbench cf --serve` argument exists and is documented in --help
- Verified: `devbench cf --help` shows `--serve` flag
- `/demo/static/` standalone HTML exists with SEO meta, robots.txt, nginx proxy config

**Is the API shippable?** ✅ YES
- `web/api.py` exists (13,625 bytes, mtime 02:05) — syntax-valid, POST /convert with 400/404 error handling
- `devbench cf --api --api-port 8081` argument exists
- Verified: `devbench cf --help` shows `--api` and `--api-port` flags
- `forge/api-docs.md` written (endpoint docs, examples in Python/curl/JS, error codes)

**Is the installer working?** ✅ YES
- `setup.py` exists (mtime 01:24), `pyproject.toml` with `[project.scripts] devbench = "core.cli:entry_point"`
- Verified: `pip install -e /var/www/devbench --break-system-packages` → installed successfully
- Verified: `devbench --help` → shows all 9 tools, usage examples
- Verified: `devbench cf --help` → shows all flags (--serve, --api, --batch, --stream, --version, etc.)
- `scripts/install.sh` has systemd service setup for both configforge-api and configforge-demo

**How many SEO pages exist?** 4
- `forge/seo/vs-yq.md` (88 lines, 6,615 bytes) — targeting "yaml to json converter alternative"
- `forge/seo/vs-jq.md` (75 lines, 5,702 bytes) — targeting "json to yaml converter cli"
- `forge/seo/vs-online.md` (76 lines, 5,862 bytes) — targeting "offline yaml to json converter"
- `forge/seo/use-cases.md` (196 lines, 9,222 bytes) — targeting K8s/Docker/Ansible/CI/CD workflows
- Total: 435 lines, ~27,401 bytes of SEO content

**Has the landing page been updated?** ✅ YES
- `web/index.html` mtime: 2026-06-07T02:45Z (updated from Jun 5 23:44Z baseline)
- 18 JSON-LD/Stripe schema references (SoftwareApplication + Organization structured data)
- 12 OG/twitter meta tags (title, description, card, image, url, site_name)
- Stripe checkout link: `https://checkout.stripe.com/c/pay/cs_live_...` (live, not placeholder)
- "Buy Now — $19" button present, "Secure payment via Stripe" notice
- Feature comparison table (ConfigForge vs yq/jq/online, 12 rows)
- "Try It Now" section with curl demo command and pip install
- Hero section: "9 formats — offline, private, fast — 100% free on CLI"

**Snapshot comparison (02:29Z → 03:52Z):**
- Tests: 830/839 pass at both snapshots — 0 failures, 9 skipped, identical
- configforge.py: 59,929 → 65,423 bytes (+5,494, +233 lines) — two growth stages
- cli.py: mtime 03:15Z (21,846 bytes) — modified this window
- tools.py: 28,566 bytes — unchanged since Jun 6 14:35
- No new .py test files created this window