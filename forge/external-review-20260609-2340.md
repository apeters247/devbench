# External Review — 2026-06-09 23:37

## Rotation & Source
Minute 37 → **yq GitHub Issues** rotation
Source: GitHub issue #2283 "Add Hash Function"

## Finding
User complained that yq lacks additional hash algorithms beyond basic MD5/SHA variants.
ConfigForge already had MD5, SHA-1, SHA-256, SHA-512. 

## Implementation
**Added to hash_generator:**
- Blake2b (256-bit, faster than SHA-256, cryptographically secure)
- CRC32 (checksum for quick validation, useful for file integrity checks)

Both integrate seamlessly with existing output format.

## Code Review of Builder's Changes
Builder added:
1. **--list-merge=merge**: Deep-merges list items by position, preserves non-conflicting fields. Solves Kubernetes container override pain point (Issue #2390 equivalent).
2. **Updated completions**: bash, zsh, fish shells updated for new mode
3. **New test**: Verifies merge mode preserves sidecar while updating app image

Code quality: ✅ Well-scoped, good test coverage, backward-compatible (default still "replace")

## Test Results
1169 passed, 7 skipped, 2 xfailed

## Fixes Applied
None needed — all tests pass, no failures.

