# anime

Work-agnostic anime production pipeline vocabulary — the craft library split
out of gftdcojp's private `ai-gftd-animeka` actor (ADR-2607023000: コードは
kotoba-lang、職能は cloud-itonami-isco、商売は gftdcojp).

The creative atom is the **cut** (a shot, time-axis) — the anime counterpart
of the manga page (`kami-mangaka-*` / `kami-genko`):

```
work → episode → scene → cut → {storyboard layout conceptKeyframe keyframe
                                inbetween colorTrace background composite
                                soundCue}
retake → targets a cut (or a cut child)
```

`anime.production` provides:

- `stages` / `default-stage-status` / `derive-cut-priority` — the 12
  parallel production stages (script … delivery) and per-cut rollup
- `layer-specs` — the 8 generated cut-child layers (record ns, rkey prefix,
  stage advanced, wire envelope keys)
- `schema` — DataScript-style unique-id declarations for the hierarchy
- `collection` / `vertex-uri` / `rkey-from-id` / `slug` — identity helpers,
  parameterized by DID and NSID prefix (no studio authority baked in)

Nothing here knows about a specific studio, work, store, or DID authority —
that wiring stays in the consuming actor.

## `anime.timeline` — kami-eizo-timeline adapter (ADR-2607121400 Wave 4)

`anime.production` deliberately has no duration/timecode attribute for a cut
— that stays with the consuming actor's own entity data. `anime.timeline`
bridges the gap: given an ordered sequence of cut entities (each optionally
carrying a caller-supplied `:cut/duration-frames` and/or `:cut/stage-status`),
`cut-sequence->timeline` produces a real
[`kami-eizo-timeline`](https://github.com/kotoba-lang/kami-eizo-timeline)
value — the canonical EDL data model for the `eizo` domain — with cuts
placed sequentially as clips on one video track.

```clojure
(require '[anime.timeline :as at]
         '[kami.eizo.timeline.timecode :as tc])

(at/cut-sequence->timeline
  [{:cut/id :c1 :cut/duration-frames 48}
   {:cut/id :c2 :cut/duration-frames 24 :cut/stage-status retake-status}]
  {:timebase tc/film-24 :default-duration-frames 12})
```

Two deliberate non-mappings, and why:

- **The 12 production stages are NOT timeline markers.** The stage board is
  explicitly parallel, not serial (`anime.production/stages` docstring:
  "board columns run in parallel") — a stage boundary has no meaningful
  playback-time position, so forcing one onto the timeline would be
  fabricated, not derived. What IS meaningful: a cut whose derived priority
  is `"retake"` (`anime.production/derive-cut-priority`) becomes a real
  timeline marker, since that's a genuine fact about a specific point in the
  cut sequence.
- **The 8 cut-child layers are NOT separate tracks.** They're sequential
  *production states* of one cut's visual content (storyboard → … →
  composite), not simultaneous compositing layers at playback — so one cut
  maps to one clip. A richer source reference (e.g. a real `composite_uri`)
  is left to the caller via `:clip/source-id`, not this adapter's concern.

`cut-sequence->timeline`'s output passes `kami.eizo.timeline/validate-timeline`
— see `test/anime/timeline_test.cljk`.

## Real cross-repo render proof (`test/e2e/`)

`test/anime/timeline_test.cljk` only proves `cut-sequence->timeline`'s output
*validates* as a `kami.eizo.timeline` EDL — it never proves that EDL can
actually be turned into a video. `test/e2e/real_anime_douga_ffmpeg_proof.cljk`
(nbb) closes that gap: it drives a real anime cut-sequence all the way through
to a real, correct rendered `.mp4`, exercising `anime` + `kami-eizo-timeline`
+ [`douga`](https://github.com/kotoba-lang/douga) together for the first time.
Nothing here is hand-simulated — every step is the real library function,
executed against a real `ffmpeg` subprocess.

Pipeline: `anime.production`-shaped cut entities (4 cuts, one scene, real
`anime.production/slug` + `vertex-uri` identity helpers, one cut marked
`"retake"` via a real `:cut/stage-status`, one marked all-`"approved"`) →
the real `anime.timeline/cut-sequence->timeline` → a real
`kami.eizo.timeline` EDL (validated with `validate-timeline`) → **a real
bridging step** → the real `douga.eizo-timeline/render-plan` → the real
`douga.ffmpeg/scene-segment-cmd` / `concat-segments-cmd` / `bgm-mix-cmd`
command builders → real `ffmpeg` child processes → a real output video,
verified with real `ffprobe` (duration, dimensions) and real sampled pixel
colors at 9 timestamps (including right before/after each of the 3 cut
boundaries), cross-checked against `kami.eizo.timeline/clip-at-frame`.

**A genuine integration gap surfaced, not designed away**:
`anime.timeline`'s adapter deliberately only knows anime's own vocabulary —
a clip's `:clip/source-id` is the bare `:cut/id` (an opaque production
identifier, not a renderable asset path), and clips carry no
`:douga/scene-index` (a douga-specific key anime has no reason to know
about, per its own docstring — the adapter produces a *generic*
`kami.eizo.timeline` value). `douga.eizo-timeline/render-plan` requires
both. A real caller sitting between the two needs a real "cut id → rendered
asset" resolution step (exactly what a production pipeline's finish/composite
blob store provides) plus scene numbering; the proof script writes that
bridge out explicitly (`attach-douga-keys`) rather than hiding it inside
either library, and re-validates the bridged timeline before handing it to
douga.

Last verified run: **all 29 checks passed** — 64×64 output, 7.835s duration
(expected 7.75s; the ~85ms delta is the same concat-demuxer `-c copy` DTS
rounding douga's own proof documents, not an anime or douga defect), and
every sampled pixel matched its expected cut's color within a 40/255-channel
tolerance (actual observed drift was 1–3/255, ordinary H.264/yuv420p lossy
encoding of a flat color field).

Requires system `ffmpeg` + `ffprobe` on `PATH`, and local checkouts of
`kotoba-lang/douga` and `kotoba-lang/kami-eizo-timeline` whose `src/` are
reachable via classpath:

```bash
kbb --backend sci -cp src:test/e2e:<path-to-douga>/src:<path-to-kami-eizo-timeline>/src \
    test/e2e/real_anime_douga_ffmpeg_proof.cljk
```

Exits 0 with a PASS report on success, 1 with the failing checks printed on
failure.

**Maturity**: this proves the `anime` → `kami-eizo-timeline` →  `douga` →
`ffmpeg` data path is real end-to-end for a straight hard-cut sequence (no
transitions — `douga.eizo-timeline`'s v0 only emits hard cuts, see douga's
README). It does not yet cover: video-track transitions/retakes actually
re-cutting footage (the retake marker here is informational, not acted on),
per-cut voice/dialogue lines (anime's adapter is video-only; this proof
supplies silent placeholder audio via `douga.ffmpeg/silent-audio-cmd`), or
real production assets (frames here are flat lavfi test colors, not real
composite renders). The asset-resolution bridge (`attach-douga-keys`) is a
worked example of the shape a real caller needs, not a reusable library
function — promoting it into `anime.timeline` or a new integration
namespace is a natural follow-up once a real consuming actor needs it.

## Occupation

ISCO-08 `2166` (Graphic and Multimedia Designers — includes animation
designers) —
[cloud-itonami-isco-2166](https://github.com/cloud-itonami/cloud-itonami-isco-2166).

## Test

```bash
kbb -M:test
kbb -M:lint
```

## License

Apache-2.0.
