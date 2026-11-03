# kami-eizo-grade

Portable `.cljc` color-grading data model + math — the `eizo` (映像,
video) domain analog of what DaVinci Resolve's Color page computes
internally. Part of the `kami-eizo` family defined by ADR-2607121400.

- `kami.eizo.grade.cdl` — ASC CDL (Slope/Offset/Power) primary color
  correction (`out = ((in * slope) + offset) ^ power` per channel, the
  same math underlying every "Lift/Gamma/Gain" 3-wheel UI), plus
  luma-preserving saturation (Rec. 709 luma coefficients).
- `kami.eizo.grade.curve` — per-channel tone curves via monotone cubic
  Hermite interpolation (Fritsch-Carlson tangent limiting): monotonic
  control points are guaranteed to produce a monotonic curve between
  them (no overshoot), unlike plain Catmull-Rom.
- `kami.eizo.grade.lut` — Adobe/Iridas `.cube` 3D LUT parser + trilinear
  sampling.
- `kami.eizo.grade.scope` — waveform (luma histogram) and vectorscope
  (Rec. 709 YCbCr chroma-plane) *data* computation over a flat pixel
  sequence.
- `kami.eizo.grade` — composes CDL -> curves -> LUT into one pipeline
  (`apply-grade`) and wraps it as the opaque effect-instance shape
  `kami-eizo-timeline` expects on a clip/track's effect stack
  (`effect-instance`).
- `kami.eizo.grade.mathutil` — portable `:clj`/`:cljs` scalar math
  (`Math/pow` et al. under different symbols per platform).

## v0 scope — what this is NOT

- No image/video decode or file I/O of its own — a "frame" is just a flat
  sequence of `[r g b]` pixel triples you provide. `test/e2e/` (below)
  adds a real-browser *proof* that this math produces correct output when
  the pixel triples come from a real codec round-trip, but it is a narrow
  test harness, not this repo taking on decode/file-I/O responsibility —
  that remains `org-w3-webcodecs`'s (codec binding) and `utsushi`'s
  (container/file) job.
- No viewport/GPU rendering of the waveform/vectorscope — this computes
  the underlying data (histogram / chroma-vector points) only; drawing
  it is an app/GPU-layer concern (existing `webgpu`/`webgl` per
  ADR-2607121400 §2.1, no second renderer here).
- Curve interpolation is monotone cubic Hermite, not a full spline
  editor (no per-segment tension/bias controls).
- `.cube` parsing assumes the common `DOMAIN_MIN 0 0 0` / `DOMAIN_MAX 1
  1 1` case; non-default domain remapping is not implemented.

## Usage

```clojure
(require '[kami.eizo.grade :as g]
         '[kami.eizo.grade.cdl :as cdl]
         '[kami.eizo.grade.curve :as curve]
         '[kami.eizo.grade.lut :as lut])

(def node (g/grade {:cdl-node (cdl/cdl {:slope [1.1 1.0 0.95] :offset [0.02 0.0 0.0] :power [1.0 1.0 1.05]})
                     :curves {:r (curve/curve [[0.0 0.0] [0.5 0.55] [1.0 1.0]])}}))

(g/apply-grade node [0.4 0.5 0.6])
;; => [r g b] with primary + curve applied

(g/effect-instance node)
;; => {:type :grade :params node :enabled? true}   ; drop into a
;;    kami-eizo-timeline clip/track effect stack
```

## Real-browser real-pixel-data proof (`test/e2e/`)

**This is a test/proof harness, not a production render pipeline.** Every
existing test in `test/` (`cdl_test.cljc`, `curve_test.cljc`, etc.)
verifies this repo's math against hand-computed values — synthetic
numbers picked to exercise the formula, never real pixel data. This E2E
closes that specific gap: it proves `kami.eizo.grade.cdl`'s ASC CDL
transform produces correct output on **real pixel data that has been
through a real, lossy video codec** — not just synthetic triples in a
unit test.

It builds directly on `kotoba-lang/org-w3-webcodecs`'s own real-browser
WebCodecs E2E proof (`org-w3-webcodecs` `test/e2e/run_e2e.cljk`, commit
`b14dc397e248`) and mirrors the harness `kami-eizo-timeline` established on
top of it (`kami-eizo-timeline` `test/e2e/run_e2e.cljk`, commit
`c0116940f19e`) — same nbb+Playwright harness, same local HTTP server
(WebCodecs needs a secure context; `about:blank`/`file:` don't expose
`VideoDecoder`/`VideoEncoder`), same real headless Chromium, same
`avc1.42001f` H.264 baseline codec.

`test/e2e/src/kami/eizo/grade/e2e/grade_proof.cljk` is a small portable
namespace wrapping `kami.eizo.grade.cdl/apply-cdl` with a concrete,
**non-identity** CDL node (`slope [0.95 0.9 0.85]`, `offset [0.02 -0.02
0.02]`, `power [0.95 1.05 1.1]`, `saturation 1.05` — picked so no channel
of the four proof colors below hard-clamps to 0/255, which would make the
tolerance check trivially pass regardless of precision) plus 8-bit
<-> `[0,1]` conversion helpers. `test/e2e/page/index.html` (plain
browser JS, not compiled, mirroring org-w3-webcodecs's/kami-eizo-timeline's
own E2E pages) does three things, in order:

1. Paints the same four-quadrant idea as org-w3-webcodecs's own E2E /
   kami-eizo-timeline's per-clip colors (red/green/blue/yellow solid
   regions), encodes it with a real `VideoEncoder`, and decodes it back
   with a real `VideoDecoder` — `decodedBeforeGrading` is the actual
   decoded pixel average per quadrant, a few RGB units off the painted
   input from real H.264 lossy compression.
2. Applies this repo's real CDL transform (compiled into the same browser
   bundle) to those real decoded pixels — `gradedByBrowser`.
3. Re-encodes `gradedByBrowser`'s quadrant colors and decodes them back a
   second real time — `decodedAfterRegrade` — proving the graded pixels
   themselves survive a real codec round-trip, not just that the
   arithmetic ran.

`test/e2e/run_e2e.cljk` (nbb) then does the cross-verification this
proof is really about: it requires the *same* `grade_proof.cljc` source
directly (via `kbb --backend sci -cp "src:test/e2e/src"` — a different runtime/execution
path than the browser's compiled bundle) and recomputes the expected
graded value for each quadrant from the exact `decodedBeforeGrading`
values the browser captured, then diffs that offline result against
`gradedByBrowser`. A pass means: the browser-compiled CDL math and an
independently-executed copy of the identical transform agree, **on real
captured pixel data**, not on synthetic numbers picked to make the test
pass.

Real measured result (Chromium, Playwright-bundled, run 2026-07-12):

| quadrant | painted | decoded (real H.264, pre-grade) | graded (browser) | offline (nbb) expected | decoded after re-encode |
|---|---|---|---|---|---|
| TL (red) | (230,20,20) | (228,21,19) | (232,10,15) | (232,10,15) | (230,11,15) |
| TR (green) | (20,200,20) | (19,201,20) | (21,175,12) | (21,175,12) | (21,175,13) |
| BL (blue) | (20,20,230) | (20,21,226) | (27,11,200) | (27,11,200) | (26,12,197) |
| BR (yellow) | (230,220,20) | (229,220,22) | (226,190,10) | (226,190,10) | (225,191,10) |

The "graded (browser)" and "offline (nbb) expected" columns match exactly
for all four quadrants (well inside the 1-unit integer-rounding tolerance
used for that comparison), and "decoded after re-encode" lands within a
few RGB units of "graded (browser)" (well inside the 40-unit H.264 lossy
tolerance used there) — i.e. **real decoded pixels, correctly graded, and
the graded result itself survives a second real codec round-trip.**

Setup and run:

```bash
npm --prefix test/e2e install               # Playwright
npx --prefix test/e2e playwright install chromium
bash scripts/build-e2e-bundle.sh            # compiles kami.eizo.grade.e2e.entry
                                             # (this repo's CDL math + org-w3-webcodecs's
                                             # binding) -> test/e2e/page/grade-proof-bundle.js
                                             # (JVM/Clojure CLI build step, not an
                                             # app-runtime choice — see
                                             # scripts/build-e2e-bundle.sh)
kbb --backend sci -cp "src:test/e2e/src" test/e2e/run_e2e.cljk
```

Exits 0 and prints the JSON result (per-quadrant painted/decoded/graded/
re-decoded RGB) plus the offline cross-verification map on pass; exits 1
on any real failure (codec unsupported, browser-vs-offline grading
mismatch beyond tolerance, regraded-and-redecoded pixels beyond the codec
tolerance) — no silent degradation.

The `:e2e` deps.edn alias takes `org-w3-webcodecs` as a real git dependency
(pinned by commit SHA), same as `kami-eizo-timeline`'s;
`test/e2e/page/grade-proof-bundle.js` and `test/e2e/node_modules/` are
build artifacts, gitignored.

## Test

```bash
kbb -M:test
kbb -M:lint
```

## License

Apache-2.0
