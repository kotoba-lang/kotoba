# Changelog

## Unreleased — 2026-07-09

### Changed: `kotoba.sprite-gpu` is now a thin re-export of `kami.sprite-gpu` (kotoba-lang/webgpu)

**Why.** This repo and `kotoba-lang/webgpu`'s internal `src/kami/sprite_gpu.cljk` both trace back
to the same source (a 2026-07-02 "clj-wgsl Phase-4" split-migration that was abandoned, followed by
a "restore" commit that recovered old content into each repo independently). Nothing ever
reconciled the two copies afterward, so they diverged silently.

Diffing the two (normalizing `kotoba.*` → `kami.*`) turned up a real, user-visible bug that only
one side had fixed:

- `kotoba-lang/webgpu` PR #10 (2026-07-08, commit `9bc1fb5`) fixed `prim->quad`'s `:rect` branch:
  `:w`/`:h` are FULL width/height in the sprite2d vocabulary (the Canvas2D reference painter,
  `kami.sprite2d.cljs`, draws `fillRect(dx - w/2, dy - h/2, w, h)`), but `:size` elsewhere is a
  half-extent — so `:rect` quads need `:w`/`:h` halved. Before the fix, they weren't, so `:rect`
  primitives rendered ~2x too large on each axis on the GPU-2D path vs. Canvas2D.
- This repo's copy (`src/kotoba/sprite_gpu.cljk`, restore commit `01e409e`) never got that fix —
  its `:rect` case still passed `:w`/`:h` straight through. This repo's own git history has no
  commits between the restore and CI/lint housekeeping, confirming it received zero feature or bug
  fix work after the split; all real development happened in `kotoba-lang/webgpu`.

Consumer evidence points the same way: `network-isekai`, `net-babiniku`, and every other live
production consumer depend on `kotoba-lang/webgpu` (i.e. `kami.sprite-gpu`), not this repo. This
repo's only confirmed consumers were other `kotoba-lang` scaffolding repos (`scene2d`, `webgl`),
which are being repointed to `kotoba-lang/webgpu` directly in the same consolidation pass.

**What changed.**
- `deps.edn`: dropped the standalone `kotoba-lang/wgsl` dep (no longer needed — the shader builder
  now lives behind `kami.sprite-gpu`), added `io.github.kotoba-lang/webgpu {:local/root "../webgpu"}`.
- `src/kotoba/sprite_gpu.cljk`: replaced the duplicated implementation with a thin re-export of
  `kami.sprite-gpu` — same public API (`prim->quad`, `anim-quad`, `prims->quads`, `draw-ops->quads`,
  `pack-instances`, `sprite-sdf-shader`, `shapes`), so anything still requiring `kotoba.sprite-gpu`
  keeps working unmodified, but now it can never drift from the canonical copy again.
- `test/sprite_gpu_test.cljk`: added a regression assertion for the `:rect` half-extent fix
  (`:size` is half of `:w`/`:h`), since the pre-existing test suite only checked `:shape` for the
  `:rect` case and would not have caught this bug.

This repo itself is **not** being archived or deleted — that's a separate decision, out of scope
here. It remains usable standalone; it just no longer maintains a second copy of the logic.
