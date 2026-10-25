# ADR-0001 — Declarative WebGPU from EDN (hiccup for the GPU)

- Status: accepted
- Date: 2026-06-22

## Context

The kami stack renders games in two places: native (Rust + wgpu, via
`kami-clj-play3d` / `kami-script-runtime`) and the web (`isekai.network`). The web
path previously routed rendering through the monolithic `kami-web` wasm (18 crates,
2.3 MB). That tripped a wasm-allocator OOB during boot and, more fundamentally,
coupled the web look to a Rust binary — at odds with the engine principle that
*description is data (CLJ/EDN/Datomic) and only the hot execution core is native*.

WebGPU in the browser is a **JS API**. ClojureScript can call it directly. So the
web renderer needs no Rust and no wasm at all.

## Decision

Render from a **pure EDN render-IR**, interpreted by a thin per-platform executor.

1. **The render-IR is EDN data, not CLJ code** (`kami.webgpu.ir`, `.cljc`). Like
   hiccup's `[:div …]`, the description is data: portable across Clojure /
   ClojureScript / Rust / JS, storable as Datomic datoms (`as-of`, query, fork),
   serializable, and composable with `assoc`/`update`/`merge`.

2. **The web executor is ClojureScript over the WebGPU JS API** (`kami.webgpu`,
   `.cljs`): `init!` builds the device/pipeline once; `draw!` records a frame from
   the EDN each rAF. The GPU does the rasterization; CLJS only records light
   per-frame commands. No Rust, no wasm, no string marshaling.

3. **One EDN spec, many executors.** The same render-IR is (or will be) interpreted
   natively by Rust→wgpu. Description is shared; only the executor is per-platform.

4. **Layering.** *Behaviour* (game logic) stays CLJ → wasm (kototama). *Description*
   (scene, render graph, materials, look) is EDN. *Executor* is `.cljc` data helpers
   + a `.cljs` browser core.

## Consequences

- The kami-web wasm allocator OOB is gone (no wasm in the web render path).
- shadow-cljs must use `:simple` (or `^js` externs) so WebGPU method names survive.
- A known footgun: GPU buffers written with `writeBuffer` need `COPY_DST` usage, or
  the write silently fails (validation error stays in the device scope) and the
  buffer reads as zeros. `mkbuf` always ORs in `COPY_DST`.
- Roadmap: EDN-authored passes / pipelines / materials / WGSL, shadows, PBR, and the
  native Rust executor over the same EDN.
