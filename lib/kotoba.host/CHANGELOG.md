# Changelog

## Unreleased — 2026-07-09

### Changed: `kotoba.host` now depends on `kami.physics` (kotoba-lang/webgpu) directly

**Why.** `kotoba-lang/physics`'s `kotoba.physics` — the collision-layer/matrix implementation
this repo used for `resolve-collisions!` — was found to be a duplicate of
`kotoba-lang/webgpu`'s internal `kami.physics` (byte-identical after normalizing the
`kotoba.*`→`kami.*` namespace prefix; see `kotoba-lang/physics`'s CHANGELOG.md for the full
diff/history writeup). As part of consolidating that duplication, `kotoba-lang/physics` is now
a thin re-export of `kami.physics` rather than carrying its own copy.

Since this repo is the one real consumer of that namespace, it's repointed to depend on
`kotoba-lang/webgpu` directly instead of going through the now-redundant `kotoba-lang/physics`
middle hop — one fewer indirection, and it depends on the same canonical implementation
`kotoba-lang/physics` itself now re-exports.

**What changed.**
- `deps.edn`: replaced `io.github.kotoba-lang/physics {:local/root "../physics"}` with
  `io.github.kotoba-lang/webgpu {:local/root "../webgpu"}`.
- `src/kotoba/host.cljk`: `[kotoba.physics :as phys]` → `[kami.physics :as phys]` (same public
  API — `default-layers`, `separate` — no call-site changes needed).
- `.github/workflows/ci.yml`: sibling-checkout clone steps now clone `webgpu` (+ its own
  transitive deps `org-w3-webgpu` and `expr`) instead of `physics`.
- `test/`: unchanged and still passing — proof the repoint is behaviour-preserving.

This repo could still depend on `kotoba-lang/physics` instead (it remains a valid, behaviourally
identical re-export) — depending on `kotoba-lang/webgpu` directly was chosen simply because it
removes an unnecessary indirection now that the underlying implementation is the same either way.
