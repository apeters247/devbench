# Polisher Report — 2026-06-10T06:05Z

## Step 1: External Review

**Source:** HN thread "Show HN: Qq: like jq, but can transcode between many formats" (news.ycombinator.com/item?id=40781894)

**Complaint:** Users need complete, reliable format transcoding with consistent feature support across commands. One commenter noted "yq only supports toml output with scalars" and called for "a transcoded test suite that all these tools could run against" to ensure data integrity. The key signal: feature parity gaps (like regex filters not working in some subcommands) undermine trust.

**Action taken:** Bug fix — see Step 3.

---

## Step 3: Builder Code Review

**Builder's last commit:** `fix: --select --join now filters before joining; extract shared helper`

**Bug found:** When the builder extracted `_apply_select_filter` as a shared helper, regex support (`/pattern/` syntax) was accidentally dropped. The standalone `_run_cf_select` function supports regex matching (`FIELD=/regex/`), but the new shared helper silently fell back to exact-match behavior. Additionally, the helper silently returned unfiltered data on invalid expressions instead of emitting an error.

**Fix applied:**
- `core/cli.py` — added regex detection and `regex_match`/`regex_not_match` ops to `_apply_select_filter`, mirroring full `_run_cf_select` behavior. Invalid expressions now print an error and return `[]`.
- `tests/test_core.py` — added 2 tests: `test_cf_select_regex_with_each` and `test_cf_select_regex_with_join` verifying that `--select env=/prod/ --each name --join ,` and `--select host=/^alpha/ --each host --join " "` correctly filter by regex.

---

## Step 5: Final Test Results

**1295 passed, 7 skipped, 2 xfailed** (up from 1293 — 2 new tests added)

No failures.
