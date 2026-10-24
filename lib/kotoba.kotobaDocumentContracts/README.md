# kotoba-lang/kotoba-document-contracts

Zero-dep portable `.cljc` — the shared data-shape CONTRACT for kotoba's
document-rendering pipeline (parse → cascade → layout → paint), split out so
that both the existing JVM/ClojureScript implementation
(`kotoba-lang/htmldom` + `kotoba-lang/cssom`, consumed by
`kotoba-lang/browser`) and a future `aiueos`-side implementation of its own
system UI ("mainuiux") can conform to the SAME interchange shapes without
either side owning the other's runtime.

`aiueos`'s own documented direction is a "self-hosting" trajectory: move
semantic authority out of Rust and into `.kotoba` source (safe Kotoba, a
Clojure-shaped capability-safe language), compiled to a Wasm component and
run under `aiueos`'s own broker/policy layer — Rust stays only as adapter/
bootstrap, never the semantic authority (`kotoba-lang/kotoba-lang`'s own
`ADR-safe-capability-language.md`). `kotoba-lang/kotoba` already completed an
analogous move for its OWN compiler path, replacing a Rust `kotoba-clj`
compiler with a JVM-Clojure implementation running on Chicory. A future
mainuiux renderer conforming to this contract is expected to follow the same
pattern: `.kotoba` source, not hand-written Rust. (Honesty check: `aiueos`'s
own checked-out repo today still has a real `Cargo.toml`/Rust `src/` — this
is the documented DIRECTION, not yet aiueos's own shipped state.)

## Status

**Stub / contract-only** (ADR-2607061930). This repo defines DATA SHAPES and
lightweight structural predicates — it contains **no parser, no cascade
engine, no layout algorithm**. Those stay in `htmldom`/`cssom` as the
reference implementation; a future `aiueos`-side renderer (in `.kotoba`, per
the self-hosting direction above) implements its own algorithm independently
and validates its OUTPUT against these same shapes. This mirrors the
existing `kotoba-core-contracts`/`kotoba-adapter-contracts` pattern in this
org: "native hosts adapt to the CLJC contract in their own repositories"
(see `kototama`'s own README) rather than the contract owning the semantics.

## Contract surface

- `src/kotoba/document/dom.cljk` — the trusted-subset DOM tree node shape
  (`:node/id`/`:tag`/`:attrs`/`:children`, plus the text-node variant) that
  `kotoba.wasm.dom` (in `dom-gpu`) already produces and `htmldom` already
  parses into.
- `src/kotoba/document/style.cljk` — the resolved-style map shape `cssom`'s
  cascade already produces (a flat map of CSS-property keywords to resolved
  values), scoped to the properties this stack actually supports today (box
  model, flexbox, grid, basic text styling) — NOT full CSS.
- `src/kotoba/document/draw_ops.cljk` — the draw-ops vocabulary (`:rect`/
  `:text`/`:clip`/`:node`) `cssom.layout` already emits and both
  `dom-gpu` paint hosts (WebGL/WebGPU) already consume. This is the single
  most directly reusable piece for a future `aiueos` renderer: any painter
  that can consume this exact op vocabulary can reuse the existing
  `htmldom` → `cssom` pipeline's output regardless of what language or
  runtime painted it.
- `src/kotoba/document/change.cljk` — domain-neutral append-only document
  change events and deterministic replay, shared by collaborative editors.
- `src/kotoba/document/artifact_graph.cljk` — domain-neutral, incremental
  dependency execution for derived artifacts such as drawings, analysis
  results, exchange documents, previews, and publication payloads.

## Non-goals (why this is a narrow stub, not a general document/UI framework)

Scoped deliberately to what a capability-secure, Wasm-component OS's OWN
system UI needs — NOT what a general-purpose web browser needs (see
`kotoba-lang/browser`'s own ADR-0001, "kotoba-only, WASM-only... WHATWG HTML/JS
compatibility is a non-goal", and `aiueos`'s own "deny-by-default capabilities,
a deliberately small TCB" design principle). Explicitly out of scope for this
contract:

- Full WHATWG HTML5 tree-construction semantics (foreign content, the
  adoption agency algorithm, encoding sniffing) — this is a TRUSTED, authored
  document/UI shape, not a hostile-input parser target.
- Ambient network/filesystem/DOM/clipboard access from documents — any I/O a
  document needs is a capability request at the host ABI boundary (already
  `kotoba-lang/browser`'s own model), never ambient.
- General Web Platform API surface (IndexedDB, WebRTC, WebAuthn, Payment
  Request, Web Audio, Service Workers, ...) — a system UI's own capability
  needs go through the OS's own capability/broker layer (`aiueos`'s own
  manifest/policy model), not a browser-style ambient API surface.
- A JIT-class JS execution requirement — the contract has no opinion on
  script execution at all; it only describes the tree/style/paint data
  shapes a renderer produces and consumes.
- Multi-process sandboxing / site isolation — `aiueos` already provides
  Wasm-component isolation externally; this contract doesn't need to
  re-derive an isolation boundary.
- Font shaping/kerning/bidi, image/video codecs, a GPU compositor — real,
  further gaps in the CURRENT reference implementation
  (`kotoba-lang/browser`'s own maturity matrix documents these), inherited
  here as the same open follow-ups, not solved by this contract.

## Develop

```bash
kbb -M:test
```
