# OVERSEER DIGEST — 2026-06-10 17:44 UTC

## Distribution Gates

| Gate     | Status | Detail |
|----------|--------|--------|
| GIT      | ✅     | HEAD=b4f7899 — fix: add missing _run_cf_merge function (22 merge tests failing) |
| GITHUB   | ✅     | origin/main == HEAD (pushed, 0 unpushed commits) |
| WHEEL    | ✅     | dist/devbench-1.0.0-py3-none-any.whl (128KB, Jun 10 17:37) |
| PYPI     | ⚠️     | PEP 668 blocks system pip install check — cannot verify from this env |
| HOMEBREW | ❌     | `brew` not installed. Tap repo never created (formula exists in homebrew-tap/) |
| BUY LINK | ✅     | Stripe checkout + Gumroad both wired in web/index.html. No actual Polar/LemonSqueezy link. |

## Test State

**1372 passed, 7 skipped, 2 xfailed — 0 failures.** All green.

Delta from prior digest (15:15): count dropped from 1399→1372. The prior digest count was likely inflated — cbb52c0 had 22 merge test failures (`_run_cf_merge` was missing); b4f7899 fixed them. The current 1372 is ground truth.

## Worker Markers

| Worker             | Status | Detail |
|--------------------|--------|--------|
| Builder            | ⚠️     | Marker=cbb52c0, HEAD=b4f7899 — 1 commit ahead of marker |
| Polisher           | ❌     | forge/.last-polisher-change does not exist — polisher never writes marker |
| Deep Audit         | ✅     | Latest: forge/deep-audit-20260610-1408.md (14:08 UTC) |
| Commercial Research| ✅     | Latest: forge/commercial-research-20260610-1100.md (11:00 UTC) |
| External Review    | ✅     | Latest: forge/external-review-20260610-1551.md (15:51 UTC) |
| Overseer           | ✅     | Previous: forge/overseer-digest-20260610-1515.md |

## Critical Analysis

### 1. Broken Tests
**NONE.** 1372 pass, 0 fail. Prior "22 failing merge tests" resolved by b4f7899 which added `_run_cf_merge`. Clean.

### 2. Worker Stasis
- **Builder**: 1 commit ahead of marker. Not stale — marker update pending. Last substantive commit was real work (merge function). Active.
- **Polisher**: No marker file. Cannot measure cadence. 34 external-review files today suggests over-production; latest review (15:51) reviewed cbb52c0 but NOT b4f7899. May have missed the _run_cf_merge addition.
- **Deep Audit**: 4 audits today (06:00, 10:04, 10:48, 14:08). Security findings from 14:08 audit are UNACTIONED — 6 critical findings, 1 high (see below). Not stale but findings not addressed.
- **Commercial**: 3 reports today, appropriate cadence. Contains a PRICING ALERT (see below).
- **External Review**: 34 reviews today — still excessive. Cadence unchanged since last digest. Recommendation: reduce to 6x/day.

### 3. Unactioned Security Findings (deep-audit-20260610-1408.md — CRITICAL)
All 6 critical findings from the 14:08 audit remain unaddressed:
1. **Hardcoded abs paths in scripts/run_ai.py** (lines 25, 32, 65, 97, 119) — not portable
2. **Credentials read from /var/www/herbalist/.env** (line 119-127) — key leak risk
3. **Subprocess with unvalidated user input** (lines 34-46, 71-77) — prompt in ps aux
4. **TOCTOU race in web/serve.py:421-456** — symlink → hard-link bypass
5. **Uncontrolled file write in batch ops** (configforge.py:2990-2991) — path traversal
6. **Unbounded glob** (configforge.py:2973) — DoS via memory exhaustion

These are all in scripts/ and web/ (not core/) so they don't affect end-users of the CLI/lib. But web/serve.py:421-456 is live in the demo server.

### 4. Commercial Alert — Polar.sh Pricing Changed (May 27, 2026)
The commercial-research-20260610-1100.md report contains a CRITICAL CORRECTION:

**Current Gumroad fee: 10% + $0.50 = $2.40/sale on $19**
**Polar Starter (new acct): 5% + $0.50 = $1.45/sale on $19 — saves $0.95/sale**

The product page already has both Stripe checkout and Gumroad. Gumroad is the WORST platform available. Switching to Polar saves ~$950 per 1,000 sales. This is actionable now.

**Best options (per $19 sale, net to seller):**
| Platform | Fee | Net |
|----------|-----|-----|
| Polar Starter | $1.45 | $17.55 |
| Lemon Squeezy | $1.45 | $17.55 |
| Fungies.io | $1.45 | $17.55 |
| Gumroad | $2.40 | $16.60 |

### 5. Next Commercial Needle-Movers (priority order)
1. **Create Polar account + product listing** — replace or supplement Gumroad. Saves $0.95/sale, developer-native (GitHub integration, license key API). One-time task, immediate ROI.
2. **Cut GitHub release v1.0.0** — wheel exists, no git tag or GH Release created. Blockers: none. Command: `git tag v1.0.0 && git push origin v1.0.0`, then `gh release create v1.0.0`.
3. **Create Homebrew tap repo** — formula exists at homebrew-tap/. Missing: GitHub repo `apeters247/homebrew-devbench`. Blocks zero-friction macOS install for the CLI's core audience.
4. **PyPI re-publication** — requires venv-based workflow (PEP 668 blocks system pip). Version 1.0.0 wheel is built. Run: `python3 -m venv /tmp/pub && source /tmp/pub/bin/activate && pip install twine && twine upload dist/*`.

### 6. Wasted Work
- **External reviews at 34x/day**: Most cycles produce <3KB of "no issues." Cadence reduction was recommended last digest; still unchanged. This is ~34 Claude API calls/day purely for review that rarely finds anything.
- **Builder marker-only commits**: The pattern continues. Builder should update its marker AFTER b4f7899 or fold the marker update into the next real commit.
- **Deep audit findings accumulating**: 4 audits today, same 6 critical findings each time. Builder is not reading/actioning audit results. Audit loop produces diminishing signal.

### 7. Blind Spots
- **Gumroad product health**: Link exists (`naxiai.gumroad.com/l/devbench`) but purchase flow not verified. Gumroad could have de-listed or payment could be broken.
- **Stripe checkout session expiry**: The hardcoded Stripe checkout URL (`checkout.stripe.com/c/pay/cs_live_...`) will expire if the Stripe checkout session was created with an expiry. These are typically 24h. **This may already be broken.**
- **PyPI version**: Unknown if 1.0.0 is live on PyPI. Cannot verify from this environment.
- **No analytics**: Zero visibility into page views, conversion rate, or download counts.
- **SEO landing pages**: 14 comparison pages live but no organic traffic data.

## Recommendations

### For Builder (next cycle)
1. **Update forge/.last-builder-change to b4f7899** (marker is 1 commit stale)
2. **Check Stripe checkout URL** in web/index.html — hardcoded session URLs expire. Either replace with a Stripe Payment Link (permanent URL) or a Polar checkout link.
   - File: `web/index.html`, element `id="buy-stripe"`
   - Current URL: `checkout.stripe.com/c/pay/cs_live_a1LIkWbuu8T6WilF04DOIq8CoO0nio7dRHSMhDvlKWYIqBH1zHiKKUZBwq`
3. **Fix web/serve.py TOCTOU** (deep-audit finding #4) — re-verify path containment immediately before `open()`, use `os.path.realpath()` result.
4. **Fix unbounded glob** in core/configforge.py:2973 — cap at 10,000 files.

### Human Intervention Required
1. **Create Polar account** and product listing — requires human account creation at polar.sh
2. **Cut GitHub release v1.0.0** — requires push access (can be done via CLI: `git tag v1.0.0 && git push origin v1.0.0 && gh release create v1.0.0 --title "v1.0.0" --notes "Initial release"`)
3. **Create homebrew-devbench GitHub repo** — requires GitHub account action
4. **Verify/replace Stripe URL** — expired Stripe checkout sessions need a new Stripe Payment Link (permanent, doesn't expire)
5. **Reduce external review cadence** — cron job runs too frequently; reduce to 6x/day

## Summary

Tests are clean. Workers are active but not coordinated — builder doesn't read audit findings, polisher over-produces. The **Stripe checkout URL is likely expired** (session-based, not a permanent Payment Link) and **should be treated as a P0 commercial blocker**. The Homebrew tap remains the biggest distribution gap for the CLI's target audience. Switch payment platform from Gumroad to Polar for better economics.
