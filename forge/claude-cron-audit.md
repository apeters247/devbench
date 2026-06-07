# ConfigForge / Devbench — Cron Job Audit

**Reviewer:** Product Manager (Claude)
**Date:** 2026-06-07
**Inputs reviewed:** crontab + `~/.hermes/cron/jobs.json` (3 jobs), `PLAN.md` (329 lines), `forge/user_complaints.md`, `core/` + `web/` trees, full test suite.
**Test state at review:** `868 passed, 9 skipped in 15.22s` — green, stable across ~15 cycles.

---

## TL;DR (read this first)

The two builder crons have run **85 combined cycles** (Build: 46, Polish: 39) and the Overseer 10. The test suite is pristine (868 passing) and there are 16 SEO pages and a polished landing page. **And yet a stranger cannot install, download, or buy this product right now.** The crons are optimizing artifact counts (tests, SEO pages, file mtimes) for a product with **zero working distribution surface**. The single most damaging fact, verified live:

- `git rev-parse` → **`fatal: not a git repository`**
- `scripts/install.sh` advertises `curl … github.com/apeters247/devbench.git` and `naxiai.com/install.sh` → **the repo does not exist and the URL is unverified**
- `forge/release-checklist.md` describes publishing `devbench` to **PyPI** → **never published; `pip install devbench` from a clean machine fails**
- The landing page (`web/index.html`) tells visitors to run `curl -s naxiai.com/tools/devbench/demo/` and `pip install devbench` → **both 404 / fail.**

The crons have verified "pip install **-e .**" (editable, from the local checkout) ~30 times and called distribution "DONE." That is not distribution. It is a developer running their own uncommitted code.

---

## QUESTION 1 — Top 3 improvements to the cron INSTRUCTIONS

### Improvement #1 — Replace "produce an artifact" success metric with a "can a stranger use it" gate

**The flaw in the current prompts:** Both builder prompts define "done" as *a file exists / a test passes / an mtime advanced* (e.g. PLAN.md §4: `done = grep -c '\.properties' core/configforge.py > 0`). The Overseer explicitly counts `forge/seo/*.md`. None of the three jobs ever verifies the **commercial funnel actually resolves end-to-end from outside this box.** Result: 16 SEO pages driving traffic to an install command that fails.

**Missing commercial signals they should track (none are currently measured):**
- Does `pip install devbench` resolve against **PyPI** (not `-e .`)?
- Does the **GitHub repo** exist and is the working tree committed? (It is not even `git init`'d.)
- Does `curl -sSf https://naxiai.com/install.sh` return 200?
- Does a **wheel built from `python3 -m build`** install and run in a clean venv?
- Conversion **fidelity on real-world files** (see #2) — the actual product promise.

**Fix:** Add a hard "Distribution Reality Check" to the **Overseer** prompt (exact commands in Q3) that runs every cycle and forces the digest to answer one yes/no line: **"Can a stranger install and run ConfigForge in 60 seconds right now?"** Until that is `yes`, SEO/landing-page work is explicitly **deprioritized** — you do not pour traffic into a broken funnel.

### Improvement #2 — Validate the differentiator against REAL files, not synthetic edge cases

**The flaw:** 877 tests, almost all hand-authored synthetic edge cases. The product's entire pitch (`forge/user_complaints.md`) is "we handle the **real** files yq/jq/online tools mangle": Kubernetes manifests with anchors and `---` multi-doc, Helm `values.yaml` with 200 lines of comments, Spring `build.xml`, `package.json`→`Cargo.toml`. **No cron ever downloads a single real-world config and round-trips it.** The crons literally cannot tell you whether the tool delivers on its one promise.

This is also the **#1 UX pain point users WILL hit:** they convert their documented `values.yaml`, the round-trip silently drops comments or mangles indentation (complaints §1, §3, §6 — all CRITICAL/HIGH), and they churn. Verified gap: `grep -ci ruamel core/configforge.py` = **0** — comment preservation is hand-rolled string handling, the exact fragile approach every complaint warns about.

**Fix:** Add a **real-fixture fidelity harness** to the **Devbench Build** prompt (Q3). It downloads ~6 canonical configs, round-trips each (`yaml→json→yaml`), and counts (a) comment-count delta, (b) `diff` line count, (c) crashes. Track **"real-file fidelity failures"** as a first-class metric in PLAN.md §8, replacing the meaningless "test count" celebrations.

### Improvement #3 — Point the crons at the actual unaddressed pain points, with verifiable done-criteria

**The flaw:** The crons have declared the backlog "COMPLETE" and gone IDLE for 9+ consecutive cycles, while `forge/user_complaints.md` lists CRITICAL/HIGH items that are **demonstrably not done**:
- **Multi-doc YAML (`---`)** — complaint #11 (HIGH). `grep` shows partial handling; CF Polish's own R5 notes flagged it "partial." No round-trip test on a real 15-resource manifest.
- **Big-integer precision** — complaint #12. `grep -ci 'precision\|Decimal' core/configforge.py` = **0**. Unhandled.
- **Comment preservation correctness** — claimed done, never measured against ruamel or a real documented file.

Instead of fixing these, the crons spawned `test_edge_cases_round7.py`, `test_missed_edge_cases_5.py`, etc. (busywork on already-green code) and triggered **six file-ownership collisions** (PLAN.md §2).

**Fix:** Rewrite both builder prompts' "FOR EACH CYCLE" section so step 3 ("pick highest-priority item not done") reads from a **concrete, verifiable open-pain-point checklist** (Q3) instead of "grep for output files." A pain point is "done" only when a real-fixture round-trip test proves it — not when a markdown report says so.

---

## QUESTION 2 — The single biggest gap vs. a $19 paid product (brutal)

**There is no product anyone can buy or install.**

ConfigForge is an **uncommitted Python package sitting in a non-git directory on one server**, fronted by a landing page with a $19 Stripe/Gumroad button whose install instructions all 404, whose flagship deliverable (a **signed, notarized macOS .app**) is blocked on a Mac Mini that "arrives in ~3 days" (and has said "~3 days" since the plan was written), and whose only working artifact is `pip install -e .` from a local checkout — i.e. *the author running their own code.*

Be specific about why $19 never changes hands:

1. **No distribution surface exists.** Not on PyPI. Not on GitHub (`git init` has not even been run). `naxiai.com/install.sh` is unverified. The `.dmg` doesn't exist. You cannot pay $19 for a URL that 404s.
2. **The only proven path is a developer experience, not a $19 purchase.** A developer who *does* clone and `pip install -e .` got there for free. The thing you charge $19 for — a double-click signed Mac app — is exactly the thing that doesn't exist. The crons built the *checkout* (license server, Gumroad webhook, download page, 8 endpoints) before building **the thing being sold.** That is a cart with no product on the shelf.
3. **Even the moat is unproven.** The differentiator is "comment-preserving, offline, unified, type-aware." Comment preservation is hand-rolled regex (no ruamel, `grep`=0) and has **never been run against a real documented Kubernetes/Helm file.** For all 868 green tests, nobody has demonstrated the one workflow the entire complaints doc is about. A $19 buyer's first action is to throw their real `values.yaml` at it; if comments vanish, the refund request and the bad HN comment both arrive within the hour.

**The brutal one-liner:** *868 passing tests and 16 SEO pages are worth exactly $0 because there is nothing at the other end of the buy button.* The crons spent 85 cycles polishing the storefront window of a shop with no door. Fix distribution + prove fidelity on real files, and only *then* does SEO/landing-page work start compounding.

---

## QUESTION 3 — Exact commands to add to each cron's prompt

### → Add to **Overseer** (`2c0257e7e45c`) — new STEP 0, runs before everything else

Insert this block at the top of the Overseer prompt, and make the STEP 4 digest answer the final yes/no line.

```bash
# === STEP 0: DISTRIBUTION REALITY CHECK (run every cycle, report verbatim) ===
echo "## Distribution reality $(date -u +%FT%TZ)"

# 1. Is the working tree even version-controlled?
git -C /var/www/devbench rev-parse --is-inside-work-tree 2>/dev/null \
  && echo "GIT: ok" || echo "GIT: DEAD — repo is not initialized (cannot publish, cannot push)"

# 2. Does the advertised GitHub repo actually exist?
git ls-remote https://github.com/apeters247/devbench.git >/dev/null 2>&1 \
  && echo "GITHUB: ok" || echo "GITHUB: DEAD — install.sh and release-checklist reference a repo that 404s"

# 3. Is it installable from PyPI (the real funnel, NOT pip install -e)?
python3 -m pip download devbench --no-deps -d /tmp/pypi-check 2>&1 \
  | grep -qi "no matching distribution" \
  && echo "PYPI: DEAD — 'pip install devbench' fails for every user" || echo "PYPI: ok"

# 4. Does the landing-page install one-liner resolve?
curl -sSf -o /dev/null -w "%{http_code}" https://naxiai.com/install.sh 2>/dev/null \
  | grep -q 200 && echo "INSTALL.SH URL: ok" || echo "INSTALL.SH URL: DEAD — landing page instructs a 404"

# 5. Does a built wheel install + run in a CLEAN venv (not editable)?
cd /var/www/devbench && python3 -m build >/dev/null 2>&1 \
  && python3 -m venv /tmp/clean_$$ \
  && /tmp/clean_$$/bin/pip install dist/*.whl >/dev/null 2>&1 \
  && /tmp/clean_$$/bin/devbench cf --help >/dev/null 2>&1 \
  && echo "CLEAN-VENV WHEEL: ok" || echo "CLEAN-VENV WHEEL: DEAD — only 'pip install -e .' works"
```

**Add to the Overseer's STEP 4 digest, mandatory final line:**
> `INSTALLABLE BY A STRANGER IN 60s: yes/no` — if **no**, write to PLAN.md §4: *"FREEZE all SEO/landing-page work. Distribution is broken. Both builders: fix distribution before any other task."*

### → Add to **Devbench Build** (`2bc756a55221`) — new PRIORITY 0 (before the existing P1)

```bash
# === PRIORITY 0a — MAKE IT VERSION-CONTROLLED AND PUBLISHABLE ===
cd /var/www/devbench
[ -d .git ] || (git init && git add -A && git commit -m "Initial ConfigForge/Devbench commit")
# Create the public repo the install path already advertises (requires gh auth):
gh repo create apeters247/devbench --public --source=. --push 2>&1 | tail -2

# === PRIORITY 0b — PROVE A CLEAN-INSTALL, NOT pip install -e ===
cd /var/www/devbench && python3 -m build
python3 -m venv /tmp/devbench_clean && rm -rf /tmp/devbench_clean && python3 -m venv /tmp/devbench_clean
/tmp/devbench_clean/bin/pip install dist/*.whl
/tmp/devbench_clean/bin/devbench cf --help
/tmp/devbench_clean/bin/python -c "import devbench; print(devbench.__version__)"
# If this fails, the package is not shippable — fix packaging before logging IDLE.

# === PRIORITY 0c — REAL-WORLD FIDELITY HARNESS (the actual product promise) ===
mkdir -p /tmp/cf_fixtures && cd /tmp/cf_fixtures
curl -sSL -o k8s.yaml      https://raw.githubusercontent.com/kubernetes/examples/master/guestbook/all-in-one/guestbook-all-in-one.yaml
curl -sSL -o compose.yaml  https://raw.githubusercontent.com/docker/awesome-compose/master/nginx-flask-mysql/compose.yaml
curl -sSL -o pkg.json      https://raw.githubusercontent.com/expressjs/express/master/package.json
fail=0
for f in k8s.yaml compose.yaml; do
  before=$(grep -c '#' "$f")
  python3 -m devbench cf "$f" --to json --from yaml \
    | python3 -m devbench cf - --to yaml --from json > "$f.rt" 2>"$f.err" || { echo "CRASH: $f"; fail=$((fail+1)); continue; }
  after=$(grep -c '#' "$f.rt")
  delta=$(diff "$f" "$f.rt" | grep -c '^[<>]')
  echo "$f: comments $before->$after  diff_lines=$delta"
  [ "$before" != "$after" ] && { echo "  COMMENT LOSS on real file"; fail=$((fail+1)); }
done
# JSON->TOML real file (complaint #4, currently unanswered on SO):
python3 -m devbench cf pkg.json --to toml --from json >/dev/null 2>&1 || { echo "JSON->TOML FAILED on package.json"; fail=$((fail+1)); }
echo "REAL-FILE FIDELITY FAILURES: $fail"   # report this number in PLAN.md §8 every cycle
```

> Log the `REAL-FILE FIDELITY FAILURES` count in PLAN.md §8 as a tracked metric. Do **not** log IDLE while it is `> 0`.

### → Add to **ConfigForge Polish** (`abad25b085c4`) — new PRIORITY 0 (correctness, owns `configforge.py`)

```bash
# === P0a — PROVE COMMENT PRESERVATION AGAINST ruamel + a real documented file ===
python3 -m pip install ruamel.yaml >/dev/null 2>&1
cd /tmp && curl -sSL -o helm_values.yaml \
  https://raw.githubusercontent.com/prometheus-community/helm-charts/main/charts/prometheus/values.yaml
b=$(grep -c '#' helm_values.yaml)
python3 -m devbench cf helm_values.yaml --to json --from yaml \
  | python3 -m devbench cf - --to yaml --from json > helm_values.rt.yaml
a=$(grep -c '#' helm_values.rt.yaml)
echo "Helm values.yaml comments: $b -> $a  (MUST be equal; this is the #1 complaint)"
[ "$b" = "$a" ] || echo "FAIL: comment-preservation moat is broken on a real Helm file"

# === P0b — IMPLEMENT THE STILL-OPEN PAIN POINTS (verifiable done-criteria) ===
# Multi-doc YAML (complaint #11): a 15-resource manifest must round-trip all docs.
grep -c 'load_all\|safe_load_all\|multi' core/configforge.py   # must be > 0 AND have a real-fixture test
# Big-integer precision (complaint #12): 12345678901234567890 must survive yaml->json->yaml.
printf 'big: 12345678901234567890\n' > /tmp/bigint.yaml
python3 -m devbench cf /tmp/bigint.yaml --to json --from yaml | grep -q 12345678901234567890 \
  && echo "BIGINT: ok" || echo "BIGINT: DEAD (complaint #12 unaddressed; grep Decimal=0)"
# Null normalization (complaint #10): yaml ~ -> json null (not "None").
printf 'k: ~\n' > /tmp/null.yaml
python3 -m devbench cf /tmp/null.yaml --to json --from yaml | grep -q '"k": null' \
  && echo "NULL: ok" || echo "NULL: check ~ -> null mapping"
```

> Each pain point is "done" **only** when the command above prints `ok` AND a regression test in `tests/test_pain_points.py` round-trips a **real downloaded fixture** (not a synthetic one-liner). Stop appending `test_*edge*_roundN.py` files to already-green code.

---

## Meta-finding for the human operator (andrew)

The cron design has a **reward-hacking problem**: success is defined as "produce a file / pass a test / advance an mtime," so the agents rationally generate SEO pages and edge-case tests (cheap, always "succeeds") while the genuinely hard, valuable work (publish to PyPI, create the GitHub repo, build the signed app, prove fidelity on real files) is either "blocked" or never attempted. Symptoms in the logs: **9 consecutive IDLE cycles, 6 file-ownership collisions, 13+ analysis-only "burn cycles," and a 2-hour Overseer that keeps re-confirming the same green baseline.**

Two structural fixes beyond the prompt edits above:
1. **Change the definition of done in all three prompts** from "artifact exists" to "external user outcome verified" (the Q3 gates do this).
2. **Reduce cadence.** 15-minute builders on a complete codebase produce collisions and IDLE spam. Until the distribution gates pass, the Overseer itself recommended 60-minute cadence (PLAN.md §5, 08:30Z) — do that, or pause the builders and run a single one-shot "fix distribution" task.

**Priority order to actually ship and earn the $19:**
1. `git init` + push to GitHub (unblocks install.sh, ~5 min).
2. Build wheel, verify clean-venv install, publish to PyPI / Test PyPI (unblocks `pip install devbench`).
3. Run the real-fixture fidelity harness; fix what it surfaces (this is the moat).
4. *Then* the macOS .app (the actual $19 SKU) when the Mac Mini arrives.
5. SEO/landing page compounds only after 1–4 — not before.
