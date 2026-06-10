# Commercial Research — 2026-06-10T11:00Z

**Rotation index:** 2  
**Topic:** Distribution channels — indie macOS app distribution 2026, Homebrew custom tap, payment platform comparison  
**Queries run:**
1. indie macOS app distribution channels 2026 beyond App Store
2. homebrew cask distribute paid CLI tool custom tap 2026
3. polar.sh gumroad developer tool payment platform comparison 2026
4. polar.sh pricing change 2026 new fee structure tiered plans
5. gumroad alternative developer tool one-time purchase 2026 lowest fees

---

## Phase 2: Review Analysis

### 1. What users hate most about existing distribution channels

**CRITICAL NEW FINDING: Polar.sh pricing changed in May 2026**  
Previous research (10:17Z) cited Polar at 4% + $0.40 as the best developer platform. **This is now OUTDATED.**  
Polar restructured pricing on May 27, 2026:
- **New Starter (free tier)**: 5% + $0.50 — same as Lemon Squeezy and Fungies.io
- **Grandfathered Early Member**: 4% + $0.40 indefinitely (but ONLY for organizations created BEFORE May 27, 2026)
- To get sub-5% rates: must pay $20/mo (Pro), $100/mo (Growth), or $400/mo (Scale) — not worth it at low volume

**Impact on ConfigForge pricing math (per $19 sale):**
| Platform | Fee | Net to seller |
|----------|-----|---------------|
| Polar Starter (new acct, post May 27) | 5% + $0.50 = $1.45 | $17.55 |
| Lemon Squeezy | 5% + $0.50 = $1.45 | $17.55 |
| Fungies.io | 5% + $0.50 = $1.45 | $17.55 |
| Polar Early Member (grandfathered pre-May 27) | 4% + $0.40 = $1.16 | $17.84 |
| Gumroad | 10% + $0.50 = $2.40 | $16.60 |

**Previous research error**: The "Polar saves $1,640 per 1k sales" claim assumed 4% pricing. For new accounts today (June 10, 2026), Polar at 5% + $0.50 saves only **$950 per 1,000 sales** vs Gumroad — still compelling, but the gap is smaller.

**Gumroad:**
- 10% fee is still the worst in the market — unchanged
- Not developer-optimized; creator/content roots
- Gumroad Discover charges 30% for marketplace-sourced sales (irrelevant for developer SEO traffic)

**Lemon Squeezy:**
- Post-Stripe acquisition (July 2024): support degraded, roadmap stalled
- 5% + $0.50 now matches Polar Starter — but developer experience is inferior
- Community migration away from LemonSqueezy continues in 2026

### 2. What users wish existed

- **Zero-friction one-time purchase** with global tax compliance — Polar, Fungies.io, and Lemon Squeezy all solve this
- **Developer-native checkout** (GitHub integration, webhooks, license key API) — Polar's unique advantage
- **Homebrew formula for CLI Python tools** — strongly preferred over manual download; zero friction for the target DevOps audience

### 3. Pricing platform objections

- Gumroad's 10% is still the loudest objection
- **Fungies.io** is an emerging alternative that equals Polar Starter fees (5% + $0.50) but adds 50+ payment methods (SEPA, ACH, Buy Now Pay Later) — may have broader international reach
- **ThriveCart** ($495 one-time → ~2.9% + $0.30 Stripe fees) breaks even vs Gumroad at ~45 sales; breaks even vs Polar at ~340 sales. Not worth it for pre-revenue launch.

### 4. Onboarding / distribution friction

- **Homebrew formula (not cask)**: CLI tools use formulae; September 2026 notarization requirement applies ONLY to .app casks. ConfigForge custom tap remains unblocked. (Confirmed again this cycle.)
- **PyPI**: Twine 6.x current; `twine upload dist/*` still the correct command. Zero blockers, zero cost, instant global reach.
- **Custom tap naming**: `brew tap apeters247/devbench` requires a GitHub repo named `homebrew-devbench` — the `homebrew-` prefix is treated specially by brew CLI (prefix stripped from display name).

### 5. Competitor weaknesses (distribution lens)

| Channel | New 2026 finding | ConfigForge impact |
|---------|-----------------|-------------------|
| Polar.sh | Raised fees to 5% + $0.50 for new accounts (May 2026) | Still best choice for developer tools; GitHub integration > fee difference |
| Lemon Squeezy | Same fees as new Polar; worse dev experience | Skip; Polar or Fungies.io better |
| Fungies.io | 5% + $0.50, 50+ payment methods, full MoR, built for devs | New viable option — worth evaluating vs Polar |
| Setapp | Requires SDK integration that dismantles existing license system | GUI-only; confirmed no-go for v1.0 CLI |
| Homebrew official | Open-source only | Custom tap confirmed correct path |

---

## Phase 3: Synthesis

### CORRECTION to previous research (10:17Z)

**Previous research claimed: "Polar saves $1,640 per 1k sales vs Gumroad"**  
**Corrected finding: Polar saves $950 per 1k sales vs Gumroad** (for new accounts created after May 27, 2026 at 5% + $0.50)  

The previous research cited 4% + $0.40 pricing, which is now only available to grandfathered "Early Member" organizations (created before May 27, 2026). New accounts get 5% + $0.50.

**This does NOT change the recommendation to use Polar over Gumroad** — Polar is still:
- $950/1k sales cheaper than Gumroad (vs $1,640 previously stated)
- Developer-native (GitHub integration, license key API, open-source tooling)
- MoR with global tax compliance (no EU VAT self-filing)
- Better API for programmatic license key generation

### What ConfigForge should AVOID

1. **Do not use Lemon Squeezy** — tied with Polar on fees (5% + $0.50) but inferior developer experience post-Stripe acquisition. No reason to choose it over Polar.

2. **Do not wait for "low fees" to materialize from Polar** — The 4% pricing that previous research cited is no longer available for new accounts. Plan on 5% + $0.50 for Polar.

3. **Do not invest in ThriveCart at launch** — Break-even vs Polar requires ~340 sales. Pre-revenue, the $495 upfront cost is not justified. Revisit at 500+ sales.

4. **Do not treat Setapp as a near-term channel** — SDK integration dismantles the existing license system. GUI-only path, v0.2.0 minimum.

5. **Do not overlook Fungies.io as a Polar alternative** — Equal fees (5% + $0.50), 50+ payment methods including SEPA/ACH, full MoR. Worth having as backup or primary if Polar integration is slow.

### What ConfigForge should BUILD / DO

1. **IMMEDIATE (unchanged from prior cycle): Run `twine upload dist/devbench-1.0.0-*`** — zero blockers, unlocks all Homebrew formula distribution (formula references PyPI tarball).

2. **IMMEDIATE: Create Homebrew custom tap `apeters247/homebrew-devbench`** — formula, no notarization, no Mac Mini needed. Closes "dasel is one brew install away" gap.

3. **NEAR-TERM: Set up Polar at $19** — Despite fee increase, still best for developer tools. GitHub integration, license key webhooks, MoR tax compliance. Accept 5% + $0.50 as the real number going forward.

4. **NEAR-TERM (new): Evaluate Fungies.io as alternative or supplementary channel** — Equal Polar fees + more payment methods. SEPA/ACH coverage reaches European DevOps engineers who prefer direct bank payment.

5. **MEDIUM-TERM: Add "Buy" link to `web/index.html`** — 65 SEO pages with no buy destination is the critical conversion gap. Even a placeholder Gumroad $19 link is better than nothing while Polar/Fungies setup completes.

### Pricing model

- **$19 one-time via Polar** remains correct — Polar fees now 5% + $0.50, net $17.55/sale
- **Gumroad as fallback only** — 10%, net $16.60/sale; $0.95 less per sale than Polar
- **Do NOT raise price** to compensate for fees — developer CLI tools have strong one-time price expectations; $19 is validated

### Distribution channel priority ranking (revised 2026-06-10T11:00Z)

1. **PyPI** — UNBLOCKED, run `twine upload` (2 min) — biggest DevOps reach, unique moat vs yq/dasel
2. **Homebrew custom tap** — UNBLOCKED (formula, no notarization) — #1 CLI discoverability channel
3. **Polar** ($19 one-time, 5% + $0.50 for new accounts) — best developer payment platform despite fee increase
4. **Fungies.io** (5% + $0.50, 50+ payment methods) — viable alternative if Polar integration is slow
5. **Gumroad** ($19 one-time, 10%) — highest fee, acceptable as placeholder at launch
6. **GitHub Releases** — DONE (v1.0.0 tag + publish.yml) — credibility signal
7. **Setapp** — FUTURE GUI only (v0.2.0)
8. **Mac App Store** — FUTURE GUI only (notarization + Mac Mini required)

---

## Phase 4: Report

### Key Discoveries This Cycle

1. **CORRECTION: Polar fee is now 5% + $0.50 for new accounts** (changed May 27, 2026). The "4% + $0.40" cited in the 10:17Z research cycle is only for organizations grandfathered before that date. New accounts get 5% + $0.50 — same as Lemon Squeezy. **Previous saving estimate of $1,640/1k vs Gumroad should be corrected to $950/1k.**

2. **Fungies.io is a viable new option at parity with Polar Starter** — 5% + $0.50, full MoR with 50+ payment methods (SEPA, ACH, BNPL). More payment method coverage than Polar for international buyers. Worth evaluating alongside Polar.

3. **ThriveCart one-time purchase model** — $495 upfront, then 2.9% + $0.30 Stripe only. Breaks even vs Polar at ~340 sales. Not viable pre-revenue; note for future roadmap at 500+ sales.

4. **All other distribution findings from 10:17Z confirmed unchanged** — Homebrew formula unblocked, Setapp requires SDK + GUI, PyPI is unique DevOps moat, custom tap is correct path.

### Actionable Recommendations

**BUILDER P1:** Create GitHub repo `apeters247/homebrew-devbench` + `Formula/devbench.rb`. Unblocked, no notarization, no Mac Mini. Add `brew tap apeters247/devbench && brew install devbench` to README. (Same as 10:17Z — still not done.)

**POLISHER P0:** 
- Correct PLAN.md and release-checklist.md: Polar fee is **5% + $0.50** (not 4% + $0.40) for new accounts. Update any "$1,640 per 1k savings" claims to "$950 per 1k savings."
- Add Fungies.io (5% + $0.50, 50+ payment methods) as an evaluated alternative to Polar.
- Ensure `web/index.html` has a "Buy now" link before any more SEO pages are added.

**HUMAN P0 (55 min — unchanged, still not done):**
1. `twine upload dist/devbench-1.0.0-py3-none-any.whl dist/devbench-1.0.0.tar.gz` (2 min)
2. Create GitHub repo `apeters247/homebrew-devbench` (1 min) — Builder adds formula
3. Set up Polar product at polar.sh at $19 — accept 5% + $0.50 as real fee (10 min)
4. Add "Buy" link to `web/index.html` — even Gumroad placeholder is better than nothing (5 min)

---

## Distribution Channel Lessons

- **Polar fee correction is material**: At 1,000 sales, the difference vs Gumroad drops from $1,640 (old claim) to $950 (correct for new accounts). Still choose Polar, but the economics are less dramatic.
- **Fungies.io deserves evaluation**: Newer platform, equal fees, broader payment methods. If Polar onboarding is slow or has issues, Fungies.io is a direct substitute.
- **PyPI remains the unique DevOps moat**: No Go/Rust competitor (yq, dasel, gojq) is on PyPI. CI/CD pipelines using `pip install devbench` is an install path no competitor offers.
- **Homebrew formula requires PyPI first**: The formula references the PyPI tarball. `twine upload` must happen before the Homebrew tap goes live. These are sequenced dependencies.

---

## Pipeline macOS App Ideas

- **Config validator menu bar app**: watches a directory for YAML/TOML changes, shows green/red indicator in menu bar when configs are invalid — uses ConfigForge's `--validate` CLI under the hood; no competition in App Store
- **Devbench Quick Actions extension**: Finder Quick Actions for right-click "Convert to JSON / YAML / TOML" on config files — macOS Extensions API, AppKit only, no SwiftUI required, no full app needed
- **Homebrew formula tracker**: shows outdated formulae in menu bar, one-click update — uses `brew outdated --json` output, parseable with ConfigForge's JSON tools

---

## Comparison to Previous Research

| Finding | 06-10 10:17Z (prior rotation 2) | 06-10 11:00Z (this cycle) |
|---------|--------------------------------|--------------------------|
| Polar fee | 4% + $0.40 | **CORRECTED: 5% + $0.50 for new accounts** (May 27, 2026 change) |
| Savings vs Gumroad (1k sales) | $1,640 | **CORRECTED: $950** (based on new 5% rate) |
| Grandfathered Polar accounts | Not researched | OLD accounts keep 4% + $0.40 indefinitely |
| Fungies.io | Not mentioned | New viable option at same 5% + $0.50 with 50+ payment methods |
| ThriveCart | Not mentioned | $495 one-time → 2.9% Stripe only; viable at 500+ sales |
| Homebrew formula | UNBLOCKED confirmed | UNBLOCKED confirmed (same finding) |
| Setapp | GUI only confirmed | GUI only confirmed (same finding) |
| Distribution P0 actions | All unblocked, 55 min | Same — still not executed |

**Net change**: Polar fee correction is the main update. Fungies.io added as new option. ThriveCart noted for future scale. All other findings confirmed.
