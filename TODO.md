# Devbench — Remaining Tasks

---

## IMMEDIATE (needs Mac Mini)

- [ ] Build the macOS .app bundle (`python setup.py py2app` or Xcode archive)
- [ ] Sign the binary with a Developer ID Application certificate
- [ ] Notarize the signed binary with Apple (submit to ACNS)
- [ ] Staple the notarization ticket to the .app / .dmg
- [ ] Verify gatekeeper acceptance (`spctl --assess --verbose`)
- [ ] Produce a .dmg installer with a background and symlink to /Applications
- [ ] Smoke-test the signed/notarized .dmg on a clean macOS VM

---

## THIS WEEK

- [ ] Create Gumroad product page with screenshots, tagline, and pricing tiers
- [ ] Write Gumroad description (features, system requirements, refund policy)
- [ ] Set up Gumroad license key generation for macOS purchases
- [ ] Research and compile target SEO keywords ("macOS dev tool", "Python GUI builder", etc.)
- [ ] Add structured data (JSON-LD) to the landing page for rich search snippets
- [ ] Write App Store product page copy and choose screenshots
- [ ] Request App Store promotional codes for reviewers

---

## THIS MONTH

- [ ] Submit to the Mac App Store (App Store Connect + Xcode upload)
- [ ] Respond to App Store review feedback (if any)
- [ ] Launch on Product Hunt — prepare hunter outreach, GIF demo, first comment
- [ ] Launch on Hacker News — write "Show HN" post, prepare for discussion
- [ ] Monitor analytics and crash reports after launch
- [ ] Post-launch blog post / changelog

---

## ONGOING

- [ ] Fix bugs reported via Gumroad / App Store reviews / GitHub issues
- [ ] Add feature requests that align with the product vision
- [ ] Improve test coverage (unit + integration + UI)
- [ ] Update SEO keywords based on search console data
- [ ] Grow mailing list and send periodic updates
- [ ] Explore paid ads (Apple Search Ads, Google Ads) once baseline conversion is known
- [ ] Maintain compatibility with future macOS releases