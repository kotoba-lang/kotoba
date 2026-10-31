# kami-eizo-compositor

**Node-based VFX compositing data model — chroma-key, roto/mask,
2D point tracking, and blend-mode compositing — for kotoba-lang's
`eizo` (video production) domain.** An L3-authoring
[kotoba-lang](https://github.com/kotoba-lang) capability library per
[ADR-2607121400](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607121400-kami-ongaku-eizo-commercial-grade-cljs-stack.md),
analogous to what Nuke/After Effects/Fusion's node graph models
internally.

Portable `.cljc` across JVM / ClojureScript, zero external dependencies.

## Node-graph execution: compatible with, NOT dependent on, comfyui

The ADR calls for reusing `kotoba-lang/comfyui`'s ComfyUI-style
node-graph execution engine rather than building a second graph
executor. This repo does that at the **data-shape level only**:
`kami.eizo.compositor.nodes/node-pack` is a seq of node-type maps in
exactly the shape `comfyui.node/register!` expects (`:type` string,
`:category`, `:inputs`, `:outputs` vector, `:fn`), and
`kami.eizo.compositor.nodes/example-workflow` is a ComfyUI-API-format
workflow (`{"id" {:class_type ... :inputs ...}}`) wiring them together.

**This repo does NOT take `kotoba-lang/comfyui` as a `deps.edn`
dependency.** `comfyui` is GPL-3.0-licensed (it matches upstream
ComfyUI's license). GPL-3.0 is a strong copyleft license — a work that
requires a GPL-3.0 library is generally obligated to also be licensed
GPL-3.0 (or compatible). Pulling that into this Apache-2.0 capability
library would silently change its license terms for everyone who
depends on it, which is a much bigger decision than "which node-graph
engine to reuse" and isn't this repo's call to make unilaterally. So:
the node types and example workflow here are plain data, importable
and registerable into a `comfyui.node/registry` by any **consumer**
that has separately decided to accept comfyui's GPL-3.0 terms — that
choice lives at the app/integration layer, not baked into this
library's own dependency graph.

Consequence: `example-workflow` is illustrative of graph topology and
has not been executed end-to-end through `comfyui.exec/execute` in
this repo (that would require the GPL dependency this repo
deliberately avoids). What's verified here is that every `:class_type`
in the example workflow resolves to a real node type in `node-pack`
(see `nodes-test`), and that every node type's `:fn` produces correct
output when called directly.

## Scope (v0)

- **In scope**: chroma-key alpha computation (distance-from-key-color
  with a smoothstep soft-edge falloff), roto/mask as a straight-edge
  polygon with ray-casting point-in-polygon (correct for non-convex
  shapes), 2D point tracking with linear interpolation between
  samples, standard blend modes (normal/multiply/screen/add) with
  separate opacity mixing, and comfyui-compatible node-type wrappers
  around all of the above.
- **Not in scope**: actual image/video decoding or pixel-buffer
  iteration (`:pixel`/`:top`/`:bottom` inputs are single RGB triples,
  not images — a real compositor would map these over every pixel of
  a decoded frame, which needs `utsushi`/`org-w3-webcodecs`), bezier
  roto handles (polygon vertices are straight-line only), spline or
  Kalman-smoothed tracking (linear interpolation only), GPU execution,
  and actual node-graph execution (see above — that's a consumer-side
  concern once they accept comfyui's license). `test/e2e/` (below) adds a
  real-browser *proof* that the chroma-key + composite math produces
  correct output when the pixel triples come from a real codec round-trip,
  but it is a narrow test harness, not this repo taking on decode/file-I/O
  responsibility.

## Contract

```clojure
(require '[kami.eizo.compositor.chroma-key :as chroma-key]
         '[kami.eizo.compositor.roto :as roto]
         '[kami.eizo.compositor.tracking :as tracking]
         '[kami.eizo.compositor.blend :as blend]
         '[kami.eizo.compositor.nodes :as nodes])

(chroma-key/key-alpha [0.0 1.0 0.0] {:key-color [0.0 1.0 0.0] :tolerance 0.1 :softness 0.1})
;=> 0.0 (exact key-color match -> fully transparent)

(roto/point-in-polygon? [[0 0] [10 0] [10 5] [5 5] [5 10] [0 10]] [2 8])
;=> true (non-convex L-shape, ray casting)

(def track (tracking/make-track [{:frame 0 :x 0.0 :y 0.0} {:frame 10 :x 100.0 :y 0.0}]))
(tracking/position-at track 5) ;=> [50.0 0.0]

(blend/composite :multiply [1.0 0.5] [0.5 1.0] 0.5) ;=> [0.5 0.75]

nodes/node-pack       ;=> comfyui-compatible node-type maps (data only)
nodes/example-workflow ;=> ComfyUI-API-format workflow wiring them
```

## Real-browser real-pixel-data proof (`test/e2e/`)

**This is a test/proof harness, not a production compositor pipeline.**
Every existing test in `test/` (`chroma_key_test.cljc`, `blend_test.cljc`,
etc.) verifies this repo's math against hand-computed values — synthetic
numbers picked to exercise the formula, never real pixel data. This E2E
closes that specific gap: it proves `kami.eizo.compositor.chroma-key`'s
key-alpha computation and `kami.eizo.compositor.blend`'s composite
formula produce correct output on **real pixel data that has been through
a real, lossy video codec** — not just synthetic triples in a unit test.

It builds directly on `kotoba-lang/org-w3-webcodecs`'s own real-browser
WebCodecs E2E proof (`org-w3-webcodecs` `test/e2e/run_e2e.cljk`, commit
`b14dc397e248`) and mirrors the harness `kami-eizo-timeline`
(`test/e2e/run_e2e.cljk`, commit `c0116940f19e`) and `kami-eizo-grade`
(`test/e2e/run_e2e.cljk`, commit `a19d4ea81b03`) established on top of it
— same nbb+Playwright harness, same local HTTP server (WebCodecs needs a
secure context; `about:blank`/`file:` don't expose
`VideoDecoder`/`VideoEncoder`), same real headless Chromium, same
`avc1.42001f` H.264 baseline codec.

`test/e2e/src/kami/eizo/compositor/e2e/composite_proof.cljk` is a small
portable namespace wrapping `kami.eizo.compositor.chroma-key/key-alpha`
and `kami.eizo.compositor.blend/composite` with a concrete key color
(`[20 220 20]`, a pure saturated green) and the same `:tolerance 0.15
:softness 0.1` already used in `kami.eizo.compositor.nodes/
example-workflow`'s `EizoChromaKey` inputs, plus 8-bit <-> `[0,1]`
conversion helpers. `test/e2e/page/index.html` (plain browser JS, not
compiled, mirroring org-w3-webcodecs's/kami-eizo-timeline's/
kami-eizo-grade's own E2E pages) does four things, in order:

1. Paints a foreground test plate — left half the pure key-color green,
   right half a distinct non-key subject color (red) — and a separate
   background plate (blue), encodes each with a real `VideoEncoder`, and
   decodes them back with a real `VideoDecoder` — `decodedFg`/`decodedBg`
   are the actual decoded pixel averages, a few RGB units off the painted
   input from real H.264 lossy compression.
2. Applies this repo's real chroma-key transform (compiled into the same
   browser bundle) to those real decoded foreground pixels, configured
   against the ideal painted key color but evaluated on the real (lossy)
   decoded one — `alphaByBrowser`.
3. Composites each foreground region over the real decoded background
   plate using `:normal` blend mode with the just-computed alpha as
   opacity (the same `EizoChromaKey`-alpha-feeds-`EizoComposite`-opacity
   wiring `kami.eizo.compositor.nodes/example-workflow` documents) —
   `compositedByBrowser`.
4. Re-encodes `compositedByBrowser`'s key/subject colors and decodes them
   back a second real time — `decodedAfterRecomposite` — proving the
   composited pixels themselves survive a real codec round-trip, not just
   that the arithmetic ran.

`test/e2e/run_e2e.cljk` (nbb) then does the cross-verification this proof
is really about: it requires the *same* `composite_proof.cljc` source
directly (via `kbb --backend sci -cp "src:test/e2e/src"` — a different runtime/execution
path than the browser's compiled bundle) and recomputes the expected
chroma-key alpha and composite result for each foreground region from the
exact `decodedFg`/`decodedBg` values the browser captured, then diffs
that offline result against `alphaByBrowser`/`compositedByBrowser`. A pass
means: the browser-compiled chroma-key + composite math and an
independently-executed copy of the identical transforms agree, **on real
captured pixel data**, not on synthetic numbers picked to make the test
pass.

Real measured result (Chromium, Playwright-bundled, run 2026-07-12):

| region | painted | decoded (real H.264) | alpha (browser) | alpha (nbb expected) | composited (browser) | composited (nbb expected) | decoded after re-encode |
|---|---|---|---|---|---|---|---|
| key (green) | (20,220,20) | (19,220,21) | 0 | 0 | (19,21,217) | (19,21,217) | (19,22,215) |
| subject (red) | (220,20,20) | (219,21,20) | 1 | 1 | (219,21,20) | (219,21,20) | (217,22,20) |

(background plate painted (20,20,220), decoded (19,21,217).)

The key region — a real decoded pixel that is still, despite lossy codec
noise, close to the painted key color — gets alpha `0` (fully keyed out),
so its composited output is the real decoded background pixel unchanged.
The subject region — a real decoded pixel far from the key color in RGB
space — gets alpha `1` (fully kept), so its composited output is its own
real decoded pixel unchanged. The "alpha"/"composited" browser and nbb
columns match exactly for both regions, and "decoded after re-encode"
lands within a few RGB units of "composited (browser)" (well inside the
40-unit H.264 lossy tolerance used there) — i.e. **real decoded pixels,
correctly keyed and composited, and the composited result itself survives
a second real codec round-trip.**

Setup and run:

```bash
npm --prefix test/e2e install               # Playwright
npx --prefix test/e2e playwright install chromium
bash scripts/build-e2e-bundle.sh            # compiles kami.eizo.compositor.e2e.entry
                                             # (this repo's chroma-key + blend math +
                                             # org-w3-webcodecs's binding) ->
                                             # test/e2e/page/composite-proof-bundle.js
                                             # (JVM/Clojure CLI build step, not an
                                             # app-runtime choice — see
                                             # scripts/build-e2e-bundle.sh)
kbb --backend sci -cp "src:test/e2e/src" test/e2e/run_e2e.cljk
```

Exits 0 and prints the JSON result (per-region painted/decoded/alpha/
composited/re-decoded RGB) plus the offline cross-verification map on
pass; exits 1 on any real failure (codec unsupported, browser-vs-offline
chroma-key/composite mismatch, recomposited-and-redecoded pixels beyond
the codec tolerance) — no silent degradation.

The `:e2e` deps.edn alias takes `org-w3-webcodecs` as a real git
dependency (pinned by commit SHA), same as `kami-eizo-timeline`'s and
`kami-eizo-grade`'s; `test/e2e/page/composite-proof-bundle.js` and
`test/e2e/node_modules/` are build artifacts, gitignored. This E2E does
NOT take `kotoba-lang/comfyui` as a dependency either — it drives
`chroma-key/key-alpha` and `blend/composite` directly, not through
`comfyui.exec/execute` (see "Node-graph execution" above; that constraint
is unrelated to this proof, which tests the compositing math functions
themselves, not graph execution).

## Naming note

`kami-eizo-*` mirrors the `kami-engine-*`/`kami-mangaka-*`/
`kami-ongaku-*` domain-authority naming convention (ADR-2607121400
§2.1); `eizo` (映像) is the video-production domain, parallel to
`ongaku` (音楽) for music. This library owns compositing node
*types/data*; it is not a compositor *application* and not
`kotoba-lang/comfyui` (the execution engine, consumed only by data
shape, never as a dependency — see above).
