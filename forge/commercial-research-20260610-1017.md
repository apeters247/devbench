# Commercial Research — 2026-06-10T10:17Z

**Rotation index:** 2  
**Topic:** Distribution channels — indie macOS app distribution 2026, Homebrew custom tap, payment platform comparison  
**Queries run:**
1. indie macOS app distribution channels 2026 beyond App Store
2. homebrew cask distribute paid CLI tool custom tap 2025 2026
3. gumroad vs paddle vs lemon squeezy indie developer tool 2026 fees comparison
4. indie developer "lemon squeezy" macOS app revenue 2025 2026 developer tool
5. macOS notarization requirement 2026 Homebrew cask CLI tool paid
6. Setapp submission requirements developer revenue share 2026

---

## Phase 2: Review Analysis

### 1. What users hate most about existing distribution channels

**Gumroad:**
- **10% fee is high** — double competitors (Polar at 4%, LemonSqueezy at 5%)
- Merchant of Record only since January 2025 — global tax handling is new and less proven
- Not optimized for software/SaaS billing; roots in creator content

**DevUtils.app (cautionary tale):**
- Switched from one-time to subscription; users who paid were locked out
- Created lasting distrust in the indie macOS dev tool space
- ConfigForge's one-time guarantee is now a documented trust signal vs this

**Setapp integration friction:**
- Requires integrating Setapp SDK / Vendor API
- Forces disabling built-in licensing and update frameworks
- 1-year minimum commitment after submission — cannot recall app
- Revenue share: 70% base (good), but SDK integration dismantles ConfigForge's existing license system

**Lemon Squeezy post-Stripe acquisition (July 2024):**
- Roadmap went quiet after Stripe acquisition
- Support response times have slipped
- Some users report checkout errors and payout delays
- Community trust damaged; developers actively migrating to alternatives

### 2. What users wish existed

- **Single payment platform** that handles global VAT/tax compliance, works for one-time purchases AND trials, has a clean developer API — this is exactly what Polar offers
- **Homebrew formula (not cask) distribution** for CLI tools — widely requested for discoverability without App Store friction
- **Honest fee comparison** — developers are discovering that Gumroad's 10% is much higher than alternatives
- **No SDK lock-in** for distribution channels — Setapp's SDK requirement is a blocker for tools with existing license systems

### 3. Pricing platform objections

- Gumroad 10% is the loudest objection — "just use LemonSqueezy" is the community consensus
- **Critical new finding**: **Polar** has emerged as the lowest-fee developer platform in 2026 at **4% + $0.40** — even cheaper than Lemon Squeezy's 5% + $0.50 and Gumroad's 10% + $0.50
- For a $19 ConfigForge sale: Polar keeps $0.76, LemonSqueezy keeps $1.45, Gumroad keeps $2.40
- Over 1,000 sales: Polar saves $1,640 vs Gumroad; $690 vs Lemon Squeezy

### 4. Onboarding / distribution friction

- **Homebrew cask vs formula confusion**: Homebrew's official casks are for .app GUI bundles; formulae are for CLI tools — ConfigForge is a CLI Python tool and should use a **formula**, not a cask
- **Critical clarification**: The September 2026 notarization requirement applies ONLY to casks (GUI .app bundles). **CLI tools distributed as Homebrew formulae do NOT require notarization.** This eliminates the "blocked until Mac Mini" assumption for Homebrew distribution
- PyPI: zero friction, $0 cost, no approval process — already done, just needs `twine upload 1.0.0`

### 5. Competitor weaknesses (distribution lens)

| Channel | Weakness | ConfigForge opportunity |
|---------|----------|------------------------|
| Mac App Store | Sandbox restrictions for CLI tools; 30% fee; requires notarization | Use only for GUI Devbench app (future) |
| Gumroad | 10% fee; creator-focused not dev-focused | Switch to Polar (4%) at first sale milestone |
| Setapp | SDK integration dismantles existing license system; 1-year lock-in | Pursue only for SwiftUI Devbench v0.2.0 |
| LemonSqueezy | Post-Stripe acquisition: support degraded, roadmap stalled | Consider Polar as alternative |
| Homebrew official tap | Closed to paid tools | Custom tap is the correct path — no blockers TODAY |

---

## Phase 3: Synthesis

### What ConfigForge should AVOID

1. **Do not prioritize Gumroad setup if time is limited** — Gumroad's 10% fee is the worst in the market. Use it as a quick-launch placeholder, but plan to migrate to Polar for better economics. Don't spend engineering time on Gumroad-specific integrations.

2. **Do not treat the September 2026 Homebrew notarization deadline as a blocker** — It applies ONLY to GUI app casks (.app bundles). ConfigForge is a CLI tool distributed via a Homebrew formula. No notarization required. This is unblocked TODAY.

3. **Do not integrate Setapp SDK for v1.0** — Setapp requires dismantling ConfigForge's existing license system (the entire `web/license_server.py`, `web/license.py` stack). This is a v0.2.0+ play, only if a GUI macOS app exists.

4. **Do not wait for Mac Mini to create Homebrew tap** — Custom Homebrew formula for a Python CLI tool works on any system, can be submitted to GitHub today without notarization.

5. **Do not overlook Polar** — It has emerged as the best developer-oriented payment platform in 2026. Lower fees than everyone, handles global tax compliance, strong developer API. If Gumroad $19 is set up already, add Polar as second channel immediately.

### What ConfigForge should BUILD / DO

1. **IMMEDIATE: Create Homebrew custom tap (`homebrew-devbench`)** — Unblocked, no Mac Mini needed, no notarization needed for CLI formula. Steps: create GitHub repo `apeters247/homebrew-devbench`, add `Formula/devbench.rb` that fetches from PyPI, test with `brew tap apeters247/devbench && brew install devbench`. This closes the "dasel is one brew install away" gap.

2. **IMMEDIATE: Run `twine upload dist/devbench-1.0.0-*`** — PyPI is ConfigForge's unique distribution moat vs Go/Rust competitors (yq, dasel, gojq are all NOT on PyPI). Wheel built, 1.0.0 tagged. Zero blockers.

3. **NEAR-TERM: Add Polar as payment channel** — At 4% + $0.40, it's the cheapest MoR in 2026. Set up a Polar product alongside Gumroad (no exclusivity required). For international buyers (EU VAT), Polar's automatic tax compliance is essential.

4. **NEAR-TERM: Add `brew tap apeters247/devbench` to README and landing page** — This single line is the developer install path that converts CLI tool evaluators. Reference implementations: GoReleaser publishes Homebrew casks automatically via GitHub Actions.

5. **MEDIUM-TERM: Pursue Setapp for Devbench GUI app only** — The 70% revenue share (+20% for partner acquisitions) is compelling, but only after the SwiftUI app exists and ConfigForge's license system is separately maintained.

### Pricing model

- **$19 one-time via Polar** is the optimal setup: lowest fees (4%), global tax compliance, developer API for license key generation
- **Gumroad can remain as backup channel** — it has marketplace discovery for creators, but developer tools don't benefit much
- **Avoid per-seat or subscription at $19 price point** — developer expectations for CLI tools are one-time purchase; the DevUtils betrayal has sensitized this audience
- **Distribution-adjusted price**: at $19 Polar takes $1.40; Gumroad takes $2.40. At 500 sales: $500 difference. Not enough to justify channel migration complexity — but Polar's MoR tax coverage is the real reason to prefer it (avoid EU VAT self-filing)

### Distribution channel priority ranking (revised 2026-06-10)

1. **PyPI** — UNBLOCKED, run `twine upload` (2 min) — biggest DevOps reach, unique moat
2. **Homebrew custom tap** — UNBLOCKED (formula, not cask, no notarization) — developer discoverability
3. **Polar** ($19 one-time) — RECOMMENDED over Gumroad for new setup — 4% vs 10% fee, MoR tax
4. **Gumroad** ($19 one-time) — acceptable if already set up; high fee is the main downside
5. **GitHub Releases** — DONE (v1.0.0 tag + publish.yml workflow) — credibility signal
6. **Setapp** — FUTURE (v0.2.0 GUI app only, requires SDK integration)
7. **Mac App Store** — FUTURE (requires notarization, Mac Mini, SwiftUI wrapping)

---

## Phase 4: Report Summary

### Key Discoveries This Cycle

1. **BIGGEST FIND: Homebrew formula ≠ cask for notarization purposes.** CLI tools use formulae; notarization applies only to casks (.app bundles). ConfigForge's custom Homebrew tap is 100% unblocked TODAY — no Mac Mini, no codesigning, no September 2026 deadline concern.

2. **Polar is the best payment platform for ConfigForge in 2026.** At 4% + $0.40 (vs Gumroad's 10% + $0.50), Polar saves $1,640 per 1,000 sales and handles global VAT/tax compliance automatically. Lemon Squeezy is degrading post-Stripe acquisition. Previous research anchored on Gumroad — this should be reconsidered.

3. **Setapp SDK requirement dismantles ConfigForge's license system.** Not a v1.0 option. Only viable after GUI Devbench app exists, and even then requires a separate license bypass path.

4. **Distribution priority confirmed by research**: PyPI → Homebrew tap → Polar → Gumroad. Only 2 of these are currently live (PyPI pending twine upload, GitHub Releases done). All 4 unblocked — no Mac Mini needed for any of them.

### Actionable Recommendations

**BUILDER P1:** Create GitHub repo `apeters247/homebrew-devbench` and add `Formula/devbench.rb` — Python formula that fetches from PyPI. No notarization required (formula, not cask). Add install instructions to README: `brew tap apeters247/devbench && brew install devbench`. This is the #1 unblocked commercial action.

**POLISHER P0:** Update `forge/release-checklist.md` to: (1) add Polar as primary payment channel recommendation above Gumroad, (2) correct the Homebrew section — tap is a formula, no notarization needed, unblocked today, (3) add "buy now" link to `web/index.html` pointing to whichever of Gumroad/Polar is live.

**HUMAN P0 (32 min):**
1. Run `twine upload dist/devbench-1.0.0-py3-none-any.whl dist/devbench-1.0.0.tar.gz` (2 min)
2. Create GitHub repo `apeters247/homebrew-devbench` (1 min) — Builder adds formula
3. Set up Polar product at polar.sh at $19 (10 min) — better economics than Gumroad
4. If Gumroad product exists: add "Buy on Polar" link as well

---

## Distribution Channel Lessons

- **PyPI = unique DevOps moat**: No Go/Rust competitor (yq, dasel, gojq) is on PyPI. `pip install devbench` in GitHub Actions or Docker is a zero-friction install that reaches the exact target audience.
- **Homebrew formula has zero friction for CLI Python tools**: The only requirement is that the package is on PyPI (so twine upload is a prerequisite). After twine upload, the formula can reference the PyPI tarball directly.
- **Polar > Gumroad for developer tools**: Gumroad has stronger marketplace network effects for creative/info products. For developer CLI tools, there's no browse-and-discover behavior on Gumroad — customers come from SEO, HN, and Reddit, then convert via direct link. Fee economics favor Polar (4%) decisively.
- **Setapp is the only channel with true Mac user discovery**: 250+ curated apps, 300k+ Mac users, monthly browsing behavior. Worth pursuing for the GUI app specifically — but the SDK integration cost is real.

---

## Pipeline macOS App Ideas (from distribution research)

- **Homebrew tap manager**: macOS menu bar showing all installed Homebrew taps, one-click update/remove, formula search — would use ConfigForge's YAML parsing for Homebrew's YAML-based lock files
- **License key manager**: companion GUI app for devs who sell via Gumroad/Polar — generates, validates, revokes keys — uses ConfigForge's JSON/YAML backend
- **Config format inspector**: Quick Look plugin for YAML/TOML/JSON files in Finder, renders formatted preview, uses ConfigForge's parser — discoverable via App Store in a way the CLI is not

---

## Comparison to Previous Research

| Finding | 06-10 06:14Z (rotation 1) | 06-10 10:17Z (this cycle, rotation 2) |
|---------|--------------------------|---------------------------------------|
| Gumroad fee | Accepted as standard | Identified as highest in market (10% vs Polar 4%) |
| Homebrew deadline | September 2026 = blocker | Clarified: applies to casks only, NOT formulae — UNBLOCKED |
| Payment platform | Gumroad = default | Polar is the recommended developer platform for 2026 |
| Setapp | v0.2.0 channel | Confirmed: SDK integration dismantles license system; GUI only |
| PyPI status | Upload pending | Still pending; unblocked; 2-min action |

**Net change in priority**: Homebrew tap moved from "needs Mac Mini + notarization" to "unblocked today"; Polar added as primary payment channel recommendation; Setapp confirmed as GUI-only play.
