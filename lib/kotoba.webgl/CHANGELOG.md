# Changelog

## Unreleased — 2026-07-09

### Changed: `kotoba.webgl` is now a thin re-export of `kami.webgl` (kotoba-lang/webgpu)

**Why.** Like `kotoba-lang/sprite-gpu` and `kotoba-lang/gpu`, this repo's `kotoba.webgl` traces
back to the same abandoned 2026-07-02 "clj-wgsl Phase-4" split-migration as
`kotoba-lang/webgpu`'s internal `src/kami/webgl.cljs`, and the two copies diverged silently after
independent "restore" commits.

**This pair is the exception in the three-repo dedup pass: the standalone copy (this repo) was
the more current/complete one, not `kotoba-lang/webgpu`'s.** Diffing the two (normalizing
`kotoba.*` → `kami.*`) found:

- This repo's `src/kotoba/webgl.cljk` was already `.cljc`: a `#?(:cljs (do …) :clj (do …))` split
  where the `:cljs` branch is the real browser WebGL2 executor and the `:clj` branch is a JVM-safe
  stand-in — `webgpu-available?`/`pick-backend`/`caps` return real answers, and the
  browser-only executors (`webgl2-context`, `program`, `sprite-renderer`, `render-2d!`,
  `scene-renderer`, `lit-renderer`) throw a clear `ex-info` instead of an opaque
  `js/navigator is unbound`. That split was directly tested (`test/webgl_test.cljk`).
- `kotoba-lang/webgpu`'s `src/kami/webgl.cljs` was plain `.cljs` — no `:clj` branch, so requiring
  it on the JVM (e.g. transitively, from a `bb`/`clj` test) would have thrown that opaque error.
  It also had zero JVM test coverage of its own for this reason.
- At the same time, `kami.webgl` had received real feature work this repo's copy never got
  (sky-gradient pass, 3D lit+shadow pass, embedded sprite GLSL — see `kotoba-lang/webgpu`'s
  CHANGELOG.md/commit history), and is what every live consumer (network-isekai, net-babiniku)
  actually depends on.

**Resolution.** Rather than pick a side and lose real functionality either way, the `.cljc` /
`:clj`-fallback structure from this repo was ported INTO `kotoba-lang/webgpu`'s `kami.webgl`
first (`src/kami/webgl.cljs` → `src/kami/webgl.cljk`, `src/kami/webgl/glsl.cljs` →
`src/kami/webgl/glsl.cljk`, plus a new `test/webgl_test.cljk` there). Once `kami.webgl` was at full
parity with (a superset of) this repo's copy, this repo was switched to re-export it.

**What changed.**
- `deps.edn`: dropped the direct `kotoba-lang/gpu` and `kotoba-lang/sprite-gpu` local-root deps
  (no longer needed — `kami.webgl` pulls in `kami.gpu`/`kami.sprite-gpu` itself), added
  `io.github.kotoba-lang/webgpu {:local/root "../webgpu"}`.
- `src/kotoba/webgl.cljk`: replaced the duplicated implementation with a thin re-export of
  `kami.webgl` — same public API (`webgpu-available?`, `webgl2-context`, `pick-backend`, `caps`,
  `program`, `sprite-renderer`, `render-2d!`, `scene-renderer`, `lit-renderer`).
- `src/kotoba/webgl/glsl.cljk`: thin re-export of `kami.webgl.glsl` (the embedded GLSL was already
  byte-identical between the two repos, so this is pure consolidation, not a behaviour change).
- `test/webgl_test.cljk` / `test/webgl_glsl_test.cljk`: unchanged and still passing — proof the
  re-export is behaviour-preserving.

This repo itself is **not** being archived or deleted — that's a separate decision, out of scope
here. It remains usable standalone; it just no longer maintains a second copy of the logic.
