# Changelog

## Unreleased — 2026-07-09

### Documented: `kotoba.render-shaders` vs. `kami.render-shaders` (kotoba-lang/webgpu) — no code change

Investigated as part of the same dedup pass that fixed real drift in `kotoba-lang/sprite-gpu`,
`kotoba-lang/gpu`, and `kotoba-lang/webgl` (all traced to the abandoned 2026-07-02 "clj-wgsl
Phase-4" split-migration + independent "restore" commits). Findings:

- **Content**: byte-identical to `kotoba-lang/webgpu`'s `src/kami/render_shaders.cljk` (normalizing
  `kotoba.*`→`kami.*`), except docstring wording.
- **History**: `kami.render-shaders` received real feature/bugfix work 2026-06-24→25
  (including a fix for `metahuman_skin`'s invalid uniform layout, `a275ba5`). This repo's own
  copy was wiped by the Phase-4 scaffold and restored on 2026-07-02 (`338d406`) to content that
  already matched that fully-developed state — the restore was not behind.
- **Tests**: equivalent naga-validity gate on both sides; `kami.render-shaders` additionally has
  a token-equivalence gate against the shipping native `kami-render` `.wgsl` (not applicable
  here — no co-located `kami-engine` checkout).
- **Consumers**: a repo-wide `grep -rn "kotoba-lang/render-shaders" --include=deps.edn` across
  `orgs/` and a source-level grep for `kotoba.render-shaders` requires found **zero external
  consumers**.

**Decision**: no code change. Converting to a live re-export (the `sprite-gpu`/`gpu`/`webgl`
pattern) would add plumbing with no consumer to benefit from it, given the content is already in
sync. Left as a self-contained, currently-matching duplicate. See README.md for the full writeup;
re-evaluate if a real external consumer of `kotoba.render-shaders` appears.
