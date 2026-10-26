# Rust Migration

Status: Rust wrapper removed.

`kototama` is now a CLJC-first contract and organism runtime repository. The
authoritative behavior lives in:

- `src/kototama/contract.cljk`
- `lib/kototama/*.cljc`
- `lib/actor/publish.bb`

Removed native wrapper files:

- `Cargo.toml`
- `src/lib.rs`
- `examples/compile.rs`

Historical Rust wrapper details remain available in git history. New behavior
must be expressed first as CLJC/EDN data and functions. Native hosts may adapt
that contract outside this repository when a platform-specific runtime is
needed.

## Downstream impact: `network-isekai`'s live compiler is now orphaned

**This removal broke a real downstream consumer with no replacement in place.**
`network-isekai` (`gftdcojp/network-isekai`) boots every game by calling
`kototama.compile_game(src)` in the browser — a `wasm-bindgen`-built copy of
*this repo's own* pre-removal `compile_game`/`compile_clj` (the functions
`src/lib.rs` re-exported from `kotoba-clj` + `kami-engine-clj`, see this
commit's parent, `7b7a825`). `public/kototama/README.md` there still documents
`cd ../../kotoba-lang/kototama && wasm-pack build` as the rebuild path — that
path has had nothing to build from since this commit. Full writeup:
`gftdcojp/network-isekai` issue #49.

**The renderer half of the CLJC-first migration this repo family underwent did
land and does work** — `kotoba-lang/webgpu` (`kami.webgpu`/`kami.webgl`/
`kami.scene2d`/`kami.sprite2d`/`kami.ui`/`kami.input`/`kami.audio`/etc., pure
CLJS, no Rust) is a real, tested, in-production replacement for what used to be
Rust/wasm rendering code (verified working via a real headless-Chromium
gameplay test, `gftdcojp/network-isekai` PR #52). The **compiler** half —
"take Clojure-subset source text, emit actual wasm bytecode" — has no such
CLJS-native replacement. That's a fundamentally harder problem than
interpreting render-IR (it needs a real compiler backend targeting wasm
bytecode), and removing `compile_game`'s Rust implementation here without one
being ready is what actually orphaned `network-isekai`'s live-compile feature,
not an oversight downstream.

Two honest paths forward, neither attempted here (owner/architecture
decision, not a docs fix):

1. **Complete the migration**: write a CLJS-native (or any non-Rust) `logic.cljc
   → executable` path with equivalent semantics to the old `compile_game`, so
   the renderer's already-successful CLJC-first pattern extends to the
   compiler too.
2. **Formally accept the frozen artifact**: treat the last Rust-built
   `kototama.js`/`kototama_bg.wasm` (still live on `isekai.network` as of this
   writing) as permanent, version-pin it, and stop implying a rebuild path
   exists anywhere in this repo family's docs.
