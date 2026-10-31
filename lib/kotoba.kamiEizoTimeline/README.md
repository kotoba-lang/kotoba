# kami-eizo-timeline

Portable `.cljc` EDL/timeline data model — the video-domain analog of what
Premiere Pro / DaVinci Resolve / Avid Media Composer store internally as an
Edit Decision List. Part of the `kami-eizo` (映像, video) family defined by
ADR-2607121400.

- Frame-accurate integer timecode over an explicit rational timebase
  (`kami.eizo.timeline.timecode`) — no float seconds, no native Clojure
  ratios (ClojureScript has no ratio type). Includes correct SMPTE
  drop-frame timecode math for 29.97/59.94fps.
- Track / clip / transition / effect-stack / marker / timeline data model
  (`kami.eizo.timeline`) with a referential-integrity validator: unbridged
  clip overlaps, transitions longer than an adjacent clip, out-of-bounds
  markers, and drop-frame flags on ineligible frame rates are all rejected.

## v0 scope — what this is NOT

- No interchange-format export (CMX3600 / OpenTimelineIO / FCPXML) yet.
- **Still no production render pipeline** — the core library
  (`kami.eizo.timeline`/`.timecode`) remains pure data + validation, with
  zero rendering, effects, grading, or compositing logic in `src/`.
  `test/e2e/` (below) adds a real-browser *proof* that this data model's
  frame math can correctly drive a real codec render, but it is a narrow
  test harness, not a rewiring of production render/codec execution onto
  this IR — that remains `utsushi`'s job (`douga` builds ffmpeg
  command-vectors and is expected to be rewired onto this IR in a later
  wave).
- Effect and plugin *implementations* are out of scope — a clip/track just
  carries an ordered list of opaque effect-instance references with
  enable/bypass state. The render proof below is solid-color clips only —
  no effects, no grading, no compositing.

## Usage

```clojure
(require '[kami.eizo.timeline :as tl]
         '[kami.eizo.timeline.timecode :as tc])

(def c1 (tl/clip {:id :v1 :source-id :src-a :source-in 0 :source-out 120 :timeline-start 0}))
(def c2 (tl/clip {:id :v2 :source-id :src-b :source-in 0 :source-out 90 :timeline-start 105}))
(def tr (tl/transition {:id :t1 :type :dissolve :from-clip :v1 :to-clip :v2 :duration 15}))
(def track (tl/track {:id :video-1 :type :video :clips [c1 c2] :transitions [tr]}))
(def timeline (tl/timeline {:timebase tc/ntsc-2997-df :tracks [track]}))

(tl/validate-timeline timeline)
;; => {:valid? true :errors []}

(tc/format-timecode 1800 tc/ntsc-2997-df)
;; => "00:01:00;02"   (drop-frame: labels :00/:01 skipped at the minute-1 boundary)
```

`kami.eizo.timeline/clip-at-frame` answers "which clip is live at global
timeline frame N" — the frame/timecode query a render pass needs:

```clojure
(tl/clip-at-frame track 4)  ;; => the clip covering frame 4 (or nil if none does)
```

## Real-browser render proof (`test/e2e/`)

**This is a test/proof harness, not a production render pipeline.** It
exists to demonstrate one specific, previously-unverified claim: that this
repo's own frame-accurate timeline/clip data model, unmodified, can
correctly drive a *real* video render — real `VideoEncoder`/`VideoDecoder`
H.264 encode and decode in a real browser, with the decoded pixel content
landing exactly on the cut boundaries the timeline data implies. It has no
effects, grading, or compositing, and it is not the render/codec execution
path `utsushi`/`douga` will eventually wire onto this IR — see "v0 scope"
above.

It builds directly on `kotoba-lang/org-w3-webcodecs`'s own real-browser
WebCodecs E2E proof (`org-w3-webcodecs` `test/e2e/run_e2e.cljk`,
commit `b14dc397e248`) — same nbb+Playwright harness pattern, same local
HTTP server (WebCodecs needs a secure context; `about:blank`/`file:` don't
expose `VideoDecoder`/`VideoEncoder`), same real headless Chromium, same
`avc1.42001f` H.264 baseline codec proven working there.

`test/e2e/src/kami/eizo/timeline/e2e/render-proof.cljs` builds a real
`kami.eizo.timeline` value using this repo's own constructors: three
5-frame solid-color clips at a film-24 (24fps) timebase, back to back with
two hard cuts (no gaps, no transitions needed for validity) —

```
clip-a [0,5)   src-red    (230,20,20)
clip-b [5,10)  src-green  ( 20,200,20)
clip-c [10,15) src-blue   ( 20, 20,230)
```

— and exposes one query, `color-at-frame`, driven *only* by
`kami.eizo.timeline/clip-at-frame`. `test/e2e/page/index.html` (plain
browser JS, not compiled, mirroring org-w3-webcodecs's own E2E page) calls
that single query both to paint each of the 15 frames before encoding
*and*, after a full encode -> decode round-trip through
`org-w3-webcodecs`'s `w3.webcodecs` binding, to check what each decoded
frame's pixels should be. Render and verification oracle therefore share
exactly one source of frame-accuracy truth — this repo's own
`clip-at-frame` — so a pass is proof the timeline's frame math drove the
render correctly, not a separately-hardcoded stand-in for it.

Real measured result (Chromium, Playwright-bundled, run 2026-07-12): all 15
frames decoded within a few RGB units of their expected clip color (e.g.
clip-a's `(230,20,20)` -> `(228,21,19)`), and both cut boundaries land
exactly where the timeline says: frame 4 is still clip-a, frame 5 is
already clip-b; frame 9 is still clip-b, frame 10 is already clip-c — with
no off-by-one drift on either boundary.

Setup and run:

```bash
npm --prefix test/e2e install              # Playwright
npx --prefix test/e2e playwright install chromium
bash scripts/build-e2e-bundle.sh           # compiles kami.eizo.timeline.e2e.entry
                                            # (this repo's timeline/render-proof query
                                            # layer + org-w3-webcodecs's binding) ->
                                            # test/e2e/page/render-proof-bundle.js
                                            # (JVM/Clojure CLI build step, not an
                                            # app-runtime choice — see
                                            # scripts/build-e2e-bundle.sh)
kbb --backend sci test/e2e/run_e2e.cljk
```

Exits 0 and prints the JSON result (per-frame expected vs. decoded RGB,
plus the two detected cut-boundary checks) on pass; exits 1 on any real
failure (codec unsupported, wrong frame count, a boundary landing on the
wrong frame, pixel mismatch beyond tolerance) — no silent degradation.

The `:e2e` deps.edn alias takes `org-w3-webcodecs` as a real git dependency
(pinned by commit SHA); `test/e2e/page/render-proof-bundle.js` and
`test/e2e/node_modules/` are build artifacts, gitignored.

## Test

```bash
kbb -M:test
kbb -M:lint
```

## License

Apache-2.0
