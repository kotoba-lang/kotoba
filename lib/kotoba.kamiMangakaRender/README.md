# kami-mangaka-render-clj

Work-agnostic **2D manga panel render commons** — the Tier-1 `mangaka` platform
layer for prompt composition + image generation (ADR-2606282100).

It is the generic half extracted from `kami-app-sip-clj`'s `sip.render`. It
hard-codes **no story, character, world, emotion vocabulary, or location** — a
work injects those as `:mappers`. Fix the recipe here once and every work +
every panel re-derives.

Sibling crates in the `kami-mangaka-*` family:

| crate | language | role |
|---|---|---|
| `kami-mangaka-scene` | Rust/PyO3 | 3D scene composition (VRM + render + postfx) |
| **`kami-mangaka-render-clj`** | clj | **this** — 2D prompt compose + image-gen client |
| `kami-mangaka-scene-clj` | clj | EDN authoring tier over `kami-mangaka-scene` |
| `kami-mangaka-page-clj` | clj | page / komawari layout (planned) |

## Origin

This repository was split out of `kotoba-lang/kami-engine`'s
[`kami-mangaka-render-clj/`](https://github.com/kotoba-lang/kami-engine/tree/main/kami-mangaka-render-clj)
subtree, following the same split pattern already used for the sibling
`kami-mangaka-genko-clj` -> `kotoba-lang/kami-genko`. The source in
`kami-engine` is a live Clojure project (never part of that monorepo's
deleted Rust workspace) — this copy preserves its full `src/`, `test/`,
`resources/`, `deps.edn`, and `bb.edn` unchanged. The original in
`kami-engine` was left untouched (copy-out, not a move).

## API

```clojure
(require '[kami.mangaka.render :as r])

;; pure composition — STYLE-FIRST, CLIP-77-word-budgeted
(r/compose
  {:anchors  (r/load-anchors "render_anchors.edn")  ; the work's anchor bible
   :panel    panel                                  ; a storyboard panel map
   :mappers  {:focal-character my-focal-fn          ; panel → one anchor key
              :location->env   my-env-fn            ; location → env anchor key
              :emotion->tags   my-mood-fn}})        ; emotion → [booru tags]
;; => {:tags [...] :prompt "..." :neg [...] :refs [...] :aspect :2x3 :dims [768 1152]}

;; drive the image-gen server (AnimagineXL 4.0 on MPS @ :8100, tag-only)
(r/render! spec "out.png" :seed 4242 :steps 28)
;; => {:path "out.png" :seed 4242 :ms 9123}
```

The three mappers are how a work keeps its semantics out of the commons:
`sip.render` injects its Nei light/embodied focal rule, its `事務所→:schwa-office`
location map, and its `静寂→serene` emotion table — none of which appear here.

## Test

Verified working standalone in this repo, with no `:local/root` deps on
sibling monorepo directories — nothing to fix:

```bash
kbb --backend sci scripts/run-task.cljk test   # pure: compose / take-budget / framing / dims / injected-mappers
# or directly:
kbb -M:test
```

Both ran clean out of the box (8 tests, 37 assertions, 0 failures, 0 errors —
re-measured 2026-08-13 through the nbb task registry, which replaced `kbb -M:test`
when babashka was retired by ADR-2607173000) — no GPU, no DB, no network required. `render!` only
touches the network when actually called.
