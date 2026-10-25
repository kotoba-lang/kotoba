# kotoba-lang/org-w3-webcodecs

Raw **W3C WebCodecs** JS API — a thin binding layer, one function per spec
call, for `VideoDecoder`/`VideoEncoder`/`AudioDecoder`/`AudioEncoder` and
their chunk/frame types. Structured after `kotoba-lang/org-w3-webgpu`
(ADR-2607051400) — the video-domain (`eizo`) analog of that repo's role for
3D, per **ADR-2607121400**
(`90-docs/adr/2607121400-kami-ongaku-eizo-commercial-grade-cljs-stack.md`,
`com-junkawasaki/root`).

## Why this repo exists

Same split pattern as `org-w3-webgpu`/`org-materialx`/`org-openusd`: an
external standard's spec gets its own narrow-scope binding repo, and the
kotoba-lang-specific EDN domain vocabulary that consumes it lives one level
up. Here, `kotoba-lang/utsushi` (EDN container/filtergraph/codec layer) is
that consumer — this repo has **zero H.264/AAC/Opus bitstream logic**
(that's `utsushi`'s job); it only exposes the browser's `VideoDecoder`/
`VideoEncoder`/etc. constructors and methods cleanly.

**Scope is deliberately narrow: 1:1 spec bindings only.** Config objects
(`VideoDecoderConfig`, `VideoEncoderConfig`, ...) are plain JS objects with
the spec's own camelCase keys, built by the caller — this wrapper does not
translate Clojure maps into configs, for the same reason `org-w3-webgpu`
doesn't (that translation layer belongs one level up, in `utsushi`).

## One difference from org-w3-webgpu: a portable sub-namespace

Unlike WebGPU, WebCodecs has one piece of logic with **no browser
dependency**: parsing/constructing the `codec` config field's string value
(e.g. `"avc1.42001f"` for AVC/H.264 — profile_idc + constraint_set flags +
level_idc, per the WebCodecs AVC Codec Registration spec / RFC 6381). That
logic lives in `w3.webcodecs.codec-string` (`.cljc`, not `.cljs`) and has a
real `clojure.test`/`cljs.test` suite — see `test/`. Everything else
(`w3.webcodecs`, the actual `VideoDecoder`/`VideoEncoder` binding) stays
`.cljs`-only and untested here, same as `org-w3-webgpu`: there is no JVM or
Node WebCodecs implementation, so correctness for that half is pinned by
`utsushi`'s own browser E2E tests once it wires through this repo.

## API

- `w3.webcodecs` — `VideoDecoder`/`VideoEncoder`/`AudioDecoder`/
  `AudioEncoder` construction, `configure!`, `decode!`/`encode!`,
  `EncodedVideoChunk`/`EncodedAudioChunk`/`VideoFrame`/`AudioData`
  construction, `flush!`/`close!`, and the `isConfigSupported()` capability
  checks for all four codec types (required for capability-gated fallback —
  see ADR-2607121400's completion gates: never assume support, never
  silently degrade).
- `w3.webcodecs.codec-string` — `parse-avc-codec-string`/
  `format-avc-codec-string` (round-trips profile/constraint-flags/level,
  including the level-1b/level-1.1 ambiguity at `level_idc == 11`, which
  depends on `constraint_set3_flag`), plus a pass-through
  `parse-simple-codec` for fixed-token codecs like `"opus"`.

```clj
(require '[w3.webcodecs :as wc]
         '[w3.webcodecs.codec-string :as cs])

(-> (wc/video-decoder-config-supported!
      #js {:codec (cs/format-avc-codec-string {:profile :baseline :level 3.1})
           :codedWidth 1280 :codedHeight 720})
    (.then (fn [^js support]
             (when (.-supported support)
               (let [dec (wc/make-video-decoder
                           #js {:output (fn [frame] (wc/close-video-frame! frame))
                                :error  (fn [e] (js/console.error e))})]
                 (wc/configure-video-decoder! dec (.-config support)))))))
```

## Status

**v0 — thin binding layer + portable codec-string module**, now with a
**real-browser E2E proof** (ADR-2607121400 completion gate: real browser
WebCodecs decode/encode round-trip). No codec bitstream implementation
lives here (that's `utsushi`'s / `org-iso-h264`'s H.264 parameter-set
work) — the E2E below proves the opposite complementary claim: that this
repo's binding correctly drives the **browser's own native codec** for
real pixel-level encode and decode, without either repo needing to
implement DCT/CAVLC/macroblock coding itself. This is the deliberate
strategy for video-domain "commercial-grade" maturity in ADR-2607121400:
delegate actual video compression to the browser's native, hardware-backed
WebCodecs implementation (the same pattern used for 3D — delegate pixel/
GPU work to native WebGPU rather than reimplementing a GPU), and keep
`org-iso-h264` scoped to container/parameter-set framing only.

## Real-browser E2E (`test/e2e/`)

`test/e2e/run_e2e.cljk` (nbb + Playwright, per this workspace's Node-harness
convention — no raw `.mjs`) launches a real headless Chromium, serves
`test/e2e/page/index.html` over a local HTTP server (WebCodecs requires a
secure context — `about:blank`/`file:` do not expose `VideoDecoder`/
`VideoEncoder`), and in the page:

1. draws a 64x64 four-quadrant test image (distinct solid colors) to a
   `<canvas>`
2. wraps it as a real `VideoFrame` and encodes it with this repo's own
   compiled `w3.webcodecs/make-video-encoder` + `configure-video-encoder!`
   + `encode-video-frame!` (codec `avc1.42001f`, H.264 baseline)
3. decodes the resulting `EncodedVideoChunk`(s) back with
   `w3.webcodecs/make-video-decoder` + `configure-video-decoder!` +
   `decode-video-chunk!`, using the `description` (avcC) the encoder
   itself emitted
4. draws the decoded `VideoFrame` to a second canvas and reads back real
   pixel values per quadrant

Real measured result (Chromium 149, Playwright-bundled): all four
quadrants decoded within a few RGB units of the original (e.g. `(230,20,20)`
in -> `(228,21,19)` out), well inside a 40-unit lossy-compression tolerance
— i.e. **actual H.264 pixel-level encode and decode**, not container/
metadata parsing.

Setup and run:

```
npm --prefix test/e2e install         # Playwright
npx --prefix test/e2e playwright install chromium
bash scripts/build-e2e-bundle.sh      # compiles src/w3/webcodecs.cljk -> test/e2e/page/webcodecs-bundle.js
                                       # (JVM/Clojure CLI build step — the ClojureScript
                                       # compiler itself has no alternative; this is a
                                       # build tool, not an app-runtime choice)
kbb --backend sci test/e2e/run_e2e.cljk
```

Exits 0 and prints the JSON result (including per-quadrant decoded RGB
values) on pass; exits 1 on any real failure (codec unsupported, decode
mismatch beyond tolerance, etc.) — no silent degradation.

## Develop

```
kbb -M:test   # w3.webcodecs.codec-string only (portable, no browser needed)
kbb -M:lint
```

`w3.webcodecs` itself (the `VideoDecoder`/`VideoEncoder` binding) has no
runtime test suite here, same reasoning as `org-w3-webgpu`: `VideoDecoder`/
`VideoEncoder` don't exist under JVM/Node, so there's nothing to construct
outside a real browser. A cljs compile-check (see CI) catches
syntax/require errors in that half.
