# Changelog

## Unreleased — 2026-08-03

### Added: `kami.gpu.launch` — launch geometry from the hardware descriptor

`kami.gpu` owns the capability question (can this backend run this pass).
`kami.gpu.launch` owns the shape question (given that it can, how should the
dispatch be shaped), which the tier table cannot answer: a pass running at 8%
of a device's bandwidth is still a pass the device can run.

- `workgroup-size` derives the size from the device's own limits and reports
  the binding constraint, including when the subgroup floor overrides a
  smaller shared-memory or problem-size answer.
- `coalescing` reports utilization rather than a boolean.
- `swizzled-tiles` / `swizzle-locality` order a 2-D dispatch along a
  space-filling curve, reusing `kotoba-lang/traversal` rather than growing a
  second Morton implementation here, and carry the measured locality gain.
- `reduction-passes` sizes the partials buffer for the first pass, not the
  last.

New dependencies: `kotoba-lang/machine`, `kotoba-lang/traversal`.
CI no longer clones `webgpu`, `org-w3-webgpu` and `expr` — those siblings
stopped being dependencies when `kami.gpu` moved here, and the workflow had
been cloning them ever since.

## Unreleased — 2026-07-09

### Changed: `kotoba.gpu` is now a thin re-export of `kami.gpu` (kotoba-lang/webgpu)

**Why.** Like `kotoba-lang/sprite-gpu` and `kotoba-lang/webgl`, this repo's `kotoba.gpu` traces back
to the same abandoned 2026-07-02 "clj-wgsl Phase-4" split-migration as `kotoba-lang/webgpu`'s
internal `src/kami/gpu.cljk`, and the two copies diverged silently after independent "restore"
commits.

Diffing the two (normalizing `kotoba.*` → `kami.*`) found **no functional bug** on either side —
every `def`/`defn` body is byte-identical. The diff is entirely in docstrings: `kami.gpu` documents
native WebGPU (`+ native (wgpu)`) and native Metal/Vulkan/DX12 targets (`native via wgpu + naga`)
that this repo's copy's docstring doesn't mention, reflecting `kotoba-lang/webgpu`'s more current
commit (`2b96271`, "capability-gated render-graph contract — one EDN, every GPU backend"). This
repo's own git history has no commits between its restore and CI/lint housekeeping — all real
development happened in `kotoba-lang/webgpu`.

Consumer evidence: `network-isekai`, `net-babiniku`, and every other live production consumer
depend on `kotoba-lang/webgpu` (i.e. `kami.gpu`), not this repo. This repo's only confirmed
consumers were other `kotoba-lang` scaffolding repos (`webgl`), which is being repointed to
`kotoba-lang/webgpu` directly in the same consolidation pass.

**What changed.**
- `deps.edn`: added `io.github.kotoba-lang/webgpu {:local/root "../webgpu"}`.
- `src/kotoba/gpu.cljk`: replaced the duplicated implementation with a thin re-export of
  `kami.gpu` — same public API (`caps-webgpu`, `caps-native`, `caps-console`, `caps-webgl2`,
  `tiers`, `missing-caps`, `pass-runnable?`, `resolve-graph`, `resolve-for`, `caps-from-device`,
  `requires`), so anything still requiring `kotoba.gpu` keeps working unmodified, but it can never
  drift from the canonical copy again.

This repo itself is **not** being archived or deleted — that's a separate decision, out of scope
here. It remains usable standalone; it just no longer maintains a second copy of the logic.
