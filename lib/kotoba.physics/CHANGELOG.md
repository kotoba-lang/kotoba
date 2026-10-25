# Changelog

## Unreleased — 2026-07-09

### Changed: `kotoba.physics` is now a thin re-export of `kami.physics` (kotoba-lang/webgpu)

**Why.** Like `kotoba-lang/sprite-gpu`, `kotoba-lang/gpu`, and `kotoba-lang/webgl`, this repo's
`kotoba.physics` traces back to the same abandoned 2026-07-02 "clj-wgsl Phase-4" split-migration
as `kotoba-lang/webgpu`'s internal `src/kami/physics.cljk`, and both were left as independent
copies after separate "restore" commits recovered them without reconciling against each other.

**Unlike those three repos, diffing this pair found no actual divergence.** Content comparison
(normalizing `kotoba.*` → `kami.*`):

```
diff <(sed 's/kotoba\.physics/kami.physics/; s/kotoba\./kami./g' physics/src/kotoba/physics.cljk) \
     webgpu/src/kami/physics.cljk
# (no output — byte-identical)
```

Git history confirms why: `kotoba-lang/webgpu`'s `kami.physics` was created once
(2026-06-24, `adf22a7`) as part of a bulk vendoring commit and has not been touched since except
by an unrelated commit that re-touched (not modified) it. `kotoba-lang/physics`'s own copy
originated in `c19f1be` ("Initial CLJC physics runtime"), was wiped by the Phase-4 scaffold, and
was restored byte-for-byte in `a1f15a1` (2026-07-02) — restoring back to the same content that
had already been vendored into `webgpu` a week earlier. So there was no bug-fix or feature race
to resolve, just a duplicate at identical risk of silently drifting on the next edit to either
side (the exact failure mode that hit sprite-gpu/gpu/webgl).

**Consumer check.** `kotoba-lang/host` is the one real consumer
(`io.github.kotoba-lang/physics {:local/root "../physics"}` in its `deps.edn`,
`[kotoba.physics :as phys]` in `src/kotoba/host.cljc`). A repo-wide
`grep -rn "kotoba-lang/physics" --include=deps.edn` found no other dependents. As part of this
change, `kotoba-lang/host` is repointed to depend on `kotoba-lang/webgpu` directly
(`[kami.physics :as phys]`) — cutting out the now-redundant middle hop — in a companion commit
on that repo.

**What changed.**
- `deps.edn`: dropped nothing (there was no prior WGSL-family dep here), added
  `io.github.kotoba-lang/webgpu {:local/root "../webgpu"}`.
- `src/kotoba/physics.cljk`: replaced the duplicated implementation with a thin re-export of
  `kami.physics` — same public API (`default-layers`, `collides?`, `radius`, `separate`).
- `test/physics_test.cljk`: unchanged and still passing — proof the re-export is
  behaviour-preserving.

This repo itself is **not** being archived or deleted — that's a separate decision, out of scope
here. It remains usable standalone; it just no longer maintains a second copy of the logic.
