# Changelog

## Unreleased — 2026-07-09

### Documented: `kotoba.shaders` vs. `kami.shaders` (kotoba-lang/webgpu) — no code change

Investigated as part of the same dedup pass that fixed real drift in `kotoba-lang/sprite-gpu`,
`kotoba-lang/gpu`, and `kotoba-lang/webgl` (all traced to the abandoned 2026-07-02 "clj-wgsl
Phase-4" split-migration + independent "restore" commits). Findings:

- **Content**: byte-identical to `kotoba-lang/webgpu`'s `src/kami/shaders.cljk` (normalizing
  `kotoba.*`→`kami.*`), except docstring wording.
- **History**: `kami.shaders` received real feature work 2026-06-24 (`be5de28`→`500c33f`, "lit +
  shadow shaders single-sourced web↔native (parity by source, drift fixed)"). This repo's own
  copy was wiped by the Phase-4 scaffold and restored on 2026-07-02 (`2fb3bdc`) to content that
  already matched that fully-developed state — the restore was not behind.
- **Tests**: equivalent `test/shader_test.cljk` on both sides.
- **Consumers**: a repo-wide `grep -rn "kotoba-lang/shaders" --include=deps.edn` across `orgs/`
  and a source-level grep for `kotoba.shaders` requires found **zero external consumers**.

**Decision**: no code change. Converting to a live re-export (the `sprite-gpu`/`gpu`/`webgl`
pattern) would add plumbing with no consumer to benefit from it, given the content is already in
sync. Left as a self-contained, currently-matching duplicate. See README.md for the full writeup;
re-evaluate if a real external consumer of `kotoba.shaders` appears.
