# douga

Pure video-assembly (動画) planning — the craft library split out of
gftdcojp's private `ai-gftd-dougaka` actor (ADR-2607023000: コードは
kotoba-lang、職能は cloud-itonami-isco、商売は gftdcojp).

`douga.ffmpeg` turns a timeline (scenes + voice lines + frame/bgm assets) into
an ordered render plan and builds ffmpeg command vectors. **No IO**: nothing
here shells out, touches the network, or reads blobs — callers execute the
returned command vectors and attach blob storage themselves.

## Contract

```clojure
(require '[douga.ffmpeg :as ffmpeg])

(ffmpeg/build-render-plan timeline)
;; => {:segments [{:scene-index 0 :frame-blob-key "..." :voice-blob-keys [...]
;;                 :texts [...] :speakers [...]}]
;;     :bgm-blob-key "..." :width 1280 :height 720 :fps 30}

(ffmpeg/scene-segment-cmd frame-path audio-path out-path
                          {:width 1280 :height 720 :fps 30})
;; => ["ffmpeg" "-y" ...]
```

Also: `burn-subtitles-cmd` (libass `subtitles=` burn-in of a sidecar SRT
onto the finished cut, path-escaped for both filter parsers, styled for a
vertical short by default — the MoneyPrinterTurbo-style presentation; the
SRT stays canonical), `parse-resolution`, `concat-audio-cmd`, `silent-audio-cmd`,
`video-segment-cmd`, `concat-segments-cmd`, `bgm-mix-cmd`, `concat-list-text`,
`xfade-transition-cmd` (real `:dissolve`- and `:wipe`-transition
rendering between exactly two clips, see below), and `xfade-chain-cmd`
(the same real transition rendering, generalized to a whole video track
with two or more sequential transitions across three or more clips in a
single ffmpeg invocation, see "Real chained multi-transition render
proof" below).

`scene-segment-cmd` is for a still frame;
`video-segment-cmd` trims a moving source and supplies silent stereo audio so
mixed still/video sequences keep a concat-safe stream layout.

Timeline keys are read leniently (`:sceneIndex` / `:scene-index` /
`"scene_index"` …) so plans built from JSON, EDN, or kebab-case sources all
work.

## `kami-eizo-timeline` input (ADR-2607121400 Wave 4)

`douga.eizo-timeline` is a second, parallel entry point that consumes a
real [`kami.eizo.timeline`](https://github.com/kotoba-lang/kami-eizo-timeline)
EDL value instead of the loose scene/lines/assets shape above, and produces
the *same* render-plan output — so all the existing command builders
(`scene-segment-cmd`, `concat-segments-cmd`, `bgm-mix-cmd`, …) keep working
unchanged downstream. The legacy `douga.ffmpeg/build-render-plan` path is
untouched and still backs the live yukkuri production pipeline
(ADR-2607051600) — this is an addition, not a replacement.

```clojure
(require '[kami.eizo.timeline :as tl]
         '[kami.eizo.timeline.timecode :as tc]
         '[douga.eizo-timeline :as det])

(def video-track
  (tl/track {:id :video-1 :type :video
             :clips [(det/scene-clip {:scene-index 0 :frame-blob-key "frame-0"
                                       :timeline-start 0 :duration-frames 96})]}))
(def audio-track
  (tl/track {:id :audio-1 :type :audio
             :clips [(det/voice-clip {:scene-index 0 :line-index 0
                                       :voice-blob-key "v-0-0" :text "hi" :speaker "left"
                                       :timeline-start 0 :duration-frames 48})]}))
(def timeline
  (assoc (tl/timeline {:timebase (tc/make-timebase 24 1 false)
                        :tracks [video-track audio-track]
                        :markers [(det/bgm-marker* {:bgm-blob-key "bgm-key" :duration-frames 96})]})
         :douga/resolution "1080p"))

(det/render-plan timeline)
;; => {:segments [...] :bgm-blob-key "bgm-key" :width 1920 :height 1080 :fps 24}
```

Mapping: one `:video`-track clip per scene, one `:audio`-track clip per
voice line (ordered by `:douga/scene-index`/`:douga/line-index`), bgm as a
single `"bgm"`-named timeline marker, fps from the timebase (rounded via
`kami.eizo.timeline.timecode/frame-rate-round`), resolution from an extra
`:douga/resolution` key on the timeline map (kami-eizo-timeline's EDL has
no resolution concept of its own).

**Real EDL clips need real durations**: unlike the legacy path (which lets
ffmpeg discover each scene's actual duration at render time via
`-shortest`), a `kami.eizo.timeline` clip's `:clip/source-out` must be a
known frame count up front — supply it from a duration-estimation or
pre-rendered-audio pass if you want this entry point.

**`:dissolve` and `:wipe` video-track transitions now render for real**
(ADR-2607121400 Wave 5 -- dissolve, Wave 6 -- wipe): `render-plan` no
longer rejects a `:dissolve` or `:wipe` transition between two adjacent
`:video`-track clips — it surfaces it as a `:video-transitions` entry
(carrying `:transition-type`), and `douga.ffmpeg/xfade-transition-cmd`
turns that into a real ffmpeg `xfade` `filter_complex` — a genuine
crossfade for `:dissolve` (see "Real dissolve-transition render proof"
below), a genuine moving spatial wipe boundary for `:wipe` (see "Real
wipe-transition render proof" below). Other transition types (`:slide`/
`:wipe-tl`/etc.) are still rejected with `ex-info`, not silently ignored
or silently downgraded to a hard cut — only `:dissolve` and `:wipe` have a
render path today.

```clojure
;; render-plan surfaces a transition (kami.eizo.timeline overlap semantics:
;; clip B's :clip/timeline-start = clip A's clip-end - transition duration)
;; as :video-transitions, keyed by scene-index, carrying :transition-type:
(det/render-plan timeline)
;; => {:segments [{:scene-index 0 :duration-frames 96 ...}
;;                {:scene-index 1 :duration-frames 96 ...}]
;;     :video-transitions [{:from-scene-index 0 :to-scene-index 1 :duration-frames 48
;;                          :transition-type :dissolve}]  ;; or :wipe
;;     ...}

;; feed the bridged pair + the transition's duration/type to xfade-transition-cmd:
(ffmpeg/xfade-transition-cmd frame-a-path frame-b-path out-path
                             {:width 320 :height 240 :fps 24
                              :from-duration-frames 96
                              :to-duration-frames 96
                              :transition-duration-frames 48
                              :transition-type :dissolve})  ;; or :wipe
;; :dissolve => ["ffmpeg" "-y" "-loop" "1" "-t" "4" "-i" frame-a-path
;;               "-loop" "1" "-t" "4" "-i" frame-b-path
;;               "-filter_complex" "...xfade=transition=fade:duration=2:offset=2[v]..."
;;               "-map" "[v]" "-r" "24" "-c:v" "libx264" "-pix_fmt" "yuv420p" out-path]
;; :wipe    => ...xfade=transition=wipeleft:duration=2:offset=2[v]...
;;             (same offset/duration arithmetic -- only the xfade `transition=`
;;             mode differs; :transition-type defaults to :dissolve if omitted,
;;             so existing :dissolve-only callers are unaffected)
```

`:wipe`'s ffmpeg xfade mode is `wipeleft` (chosen from the fuller set ffmpeg's
`xfade` filter exposes — `wipeleft`/`wiperight`/`wipeup`/`wipedown`,
`slideleft`/etc., `circlecrop`, and many more; see `ffmpeg -h filter=xfade`
for the full list on your installed version): a hard-edged boundary sweeps
**right-to-left** across the frame as the transition progresses, revealing
clip B starting from the frame's right edge while clip A remains visible on
the not-yet-swept left portion — a genuinely different render mechanism
from `:dissolve`'s per-pixel alpha blend, not a re-skin of it.

## Real-ffmpeg execution proof (`test/e2e/`)

douga is deliberately I/O-free: `douga.ffmpeg` / `douga.eizo-timeline` only
*return* ffmpeg command vectors, they never shell out. `test/douga/*_test.cljc`
(run via `kbb -M:test`) only assert the **shape** of those vectors (right
flags, right ordering) — nothing in this repo's own test suite has ever
actually handed a generated command vector to a real `ffmpeg` binary and
checked that it runs and produces correct output.

`test/e2e/real_ffmpeg_proof.cljk` (nbb) closes that gap. It:

1. builds a real [`kami.eizo.timeline`](https://github.com/kotoba-lang/kami-eizo-timeline)
   EDL — 3 scenes (red / lime / blue), 2.0s / 1.5s / 2.5s long at 24fps,
   placed back-to-back on the `:video` track with **no transitions** (a hard
   cut — the only kind `douga.eizo-timeline` supports, see "v0 gap" above),
   each with a matching-duration voice tone on the `:audio` track and a bgm
   marker;
2. generates the scenes' still-frame and voice/bgm audio sources locally via
   `ffmpeg -f lavfi` (`color=`/`sine=` — no external assets, no network);
3. drives that EDL through the **real** `douga.eizo-timeline/render-plan` and
   the **real** `douga.ffmpeg/scene-segment-cmd` /
   `douga.ffmpeg/concat-segments-cmd` / `douga.ffmpeg/bgm-mix-cmd` command
   builders (nothing hand-typed — the argv vectors executed are exactly what
   douga's own code returns);
4. executes every returned command vector as a real `ffmpeg` child process,
   synchronously, and checks each output file actually exists and is
   non-empty;
5. verifies the final assembled video with real `ffprobe` (duration,
   dimensions) and by extracting real pixels at 9 timestamps (including right
   before/after each hard cut) via a real `ffmpeg` decode + crop, comparing
   the sampled color against whichever scene
   `kami.eizo.timeline/clip-at-frame` says should be showing at that frame —
   i.e. it doesn't just check "some video came out", it checks the right
   color is on screen at the right time, cross-referenced against the EDL's
   own frame-lookup query.

Last verified run: all 23 checks passed — 320×240 output, ~6.06s duration
(expected 6.00s; the ~60ms delta is normal concat-demuxer `-c copy` DTS
rounding from B-frame reordering across segment boundaries, not a douga
defect), and every sampled pixel matched its expected scene color within a
40/255-channel tolerance (actual observed drift was 1–3/255, from ordinary
H.264/yuv420p lossy encoding of a flat color field).

Requires system `ffmpeg` + `ffprobe` on `PATH`, and a local checkout of
`kotoba-lang/kami-eizo-timeline` (the sha this repo's `deps.edn` pins) whose
`src/` is reachable via classpath:

```bash
kbb --backend sci -cp src:<path-to-kami-eizo-timeline>/src test/e2e/real_ffmpeg_proof.cljk
```

Exits 0 with a PASS report on success, 1 with the failing checks printed on
failure.

## Real dissolve-transition render proof (`test/e2e/real_dissolve_proof.cljk`)

Wave-8's `real_ffmpeg_proof.cljs` above deliberately only covers hard cuts —
that was `douga.eizo-timeline`'s entire v0 scope, and a `:dissolve`
video-track transition was rejected with `ex-info` rather than silently
ignored. `test/e2e/real_dissolve_proof.cljk` is the same real-subprocess
proof pattern applied to the render path that closes that gap: a real
`xfade` crossfade, driven through the real `douga.eizo-timeline/render-plan`
and the real `douga.ffmpeg/xfade-transition-cmd`, not a hand-typed ffmpeg
invocation.

It:

1. builds a real `kami.eizo.timeline` EDL — a 4.0s red clip and a 4.0s blue
   clip, bridged by a 2.0s `:dissolve` transition. Per
   `kami.eizo.timeline`'s overlap semantics (`validate-transition`: clip B's
   `:clip/timeline-start` = clip A's `clip-end` minus the transition's
   duration), the two clips overlap by exactly 2.0s, so the EDL's total
   duration is 4.0+4.0-2.0=**6.0s**, not 8.0s — the proof asserts this via
   `kami.eizo.timeline/timeline-duration` before rendering anything, so a
   regression that ignored the overlap (silently concatenating full clip
   durations) would be caught before it ever reached ffmpeg;
2. generates the two solid-color stills locally via `ffmpeg -f lavfi
   color=...` (no external assets, no network);
3. drives that EDL through the **real** `douga.eizo-timeline/render-plan`
   (which no longer throws for this — confirming the v0 rejection is gone)
   and asserts the returned `:video-transitions` entry matches the EDL's
   transition exactly;
4. builds the **real** `douga.ffmpeg/xfade-transition-cmd` argv from the
   render-plan's segments and executes it as a single real `ffmpeg` child
   process (one invocation produces the entire crossfade-merged output —
   no separate per-clip render + concat step, since `-c copy` concat can't
   express a blend);
5. verifies with real `ffprobe` that the output is exactly 6.0s (not 8.0s),
   at the right resolution;
6. samples real decoded pixels at 5 checkpoints — before the transition
   window, and at 25%/50%/75%/after within/past it — and asserts: pure red
   before, pure blue after, and at 25/50/75% a **genuine, monotonically
   shifting blend** (R strictly decreasing, B strictly increasing across
   all 5 checkpoints, G staying ~0 throughout with no corruption), with an
   almost-exactly-even 50/50 R/B split at the transition's midpoint — this
   is the actual proof that a crossfade is happening, not a hard cut
   (which would show pure red until 4.0s then instantly pure blue) and not
   a broken/no-op filter (which would show a corrupted or black frame).

Last verified run: all 17 checks passed — 320×240 output, exactly 6.000000s
(ffprobe), and real sampled RGB at each checkpoint: `#fc0000` (before,
t=1.0s) → `#bc003d` (25%, t=2.5s) → `#7d007d` (50%, t=3.0s, an almost exact
125/125 R/B split) → `#3d00be` (75%, t=3.5s) → `#0000fd` (after, t=5.0s).
The non-255/non-0 pure-color values (252/253 instead of 255, and the
symmetric-but-not-exactly-half 188/61 and 61/190 at 25%/75%) are ordinary
yuv420p/H.264 lossy-encoding drift from `libx264`, not a douga or filter
defect.

Requires system `ffmpeg` + `ffprobe` on `PATH`, and a local checkout of
`kotoba-lang/kami-eizo-timeline` whose `src/` is reachable via classpath:

```bash
kbb --backend sci -cp src:<path-to-kami-eizo-timeline>/src test/e2e/real_dissolve_proof.cljk
```

Exits 0 with a PASS report on success, 1 with the failing checks printed on
failure.

## Real wipe-transition render proof (`test/e2e/real_wipe_proof.cljk`)

`:wipe` is the same shape of gap the dissolve proof above closed for
`:dissolve`: a `:wipe` video-track transition used to be rejected with
`ex-info` (still true for any *other* transition type — `:slide`/
`:wipe-tl`/etc.). `test/e2e/real_wipe_proof.cljk` is the same
real-subprocess proof pattern, driven through the real
`douga.eizo-timeline/render-plan` and the real
`douga.ffmpeg/xfade-transition-cmd` (with `:transition-type :wipe`, which
selects ffmpeg xfade's `wipeleft` mode instead of `fade`) — but **a
different verification strategy**, because a wipe is a moving *spatial*
boundary, not a *temporal* blend the way a dissolve is: sampling one fixed
pixel across several timestamps (the dissolve proof's strategy) would just
show a hard cut partway through — a wipe has to be caught by sampling
*several x-positions* at one fixed instant to see the two-region spatial
split, repeated at a few instants to prove the split's position genuinely
moves.

It:

1. builds a real `kami.eizo.timeline` EDL — the same 4.0s red / 4.0s blue
   two-clip shape as the dissolve proof, bridged by a 2.0s `:wipe`
   transition instead of `:dissolve` (same overlap semantics, same
   4.0+4.0-2.0=**6.0s** total duration, asserted the same way before
   rendering anything);
2. generates the two solid-color stills locally via `ffmpeg -f lavfi
   color=...` (no external assets, no network);
3. drives that EDL through the **real** `douga.eizo-timeline/render-plan`
   (which no longer throws for `:wipe`) and asserts the returned
   `:video-transitions` entry matches the EDL's transition exactly,
   including the new `:transition-type :wipe` field;
4. builds the **real** `douga.ffmpeg/xfade-transition-cmd` argv (passing
   `:transition-type :wipe` from the render-plan entry) and asserts the
   generated `filter_complex` string literally contains
   `xfade=transition=wipeleft` (not `fade`) before executing it as a
   single real `ffmpeg` child process;
5. verifies with real `ffprobe` that the output is exactly 6.0s (not 8.0s),
   at the right resolution — same overlap-honoring check as the dissolve
   proof, now for `:wipe`;
6. samples real decoded pixels at **5 x-positions (10%/30%/50%/70%/90% of
   frame width, fixed y=center) at each of 3 fixed timestamps** (25%/50%/
   75% through the transition window) and asserts: at every timestamp,
   every sampled x-position classifies as solid red or solid blue (a
   **sharp two-region boundary**, not a smooth per-pixel blend the way
   dissolve's fixed point shows a shifting mix over time); the leftmost
   sample (x=10%) is red at all three checkpoints and the rightmost
   (x=90%) is blue at all three (clip A's still-uncovered region and clip
   B's already-revealed region are stable at the frame's edges); and the
   count of blue-classified positions strictly increases (1→2→4 across
   25%→50%→75%) while red strictly decreases (4→3→1) — this is the actual
   proof that the reveal boundary is genuinely *moving* across space as
   the transition progresses, not a static split or a broken/no-op filter.

Last verified run: all 16 checks passed — 320×240 output, exactly
6.000000s (ffprobe), and real sampled classifications at the 5 x-positions
(10/30/50/70/90% of width) across the 3 checkpoints:

| t (progress) | x=10% | x=30% | x=50% | x=70% | x=90% |
|---|---|---|---|---|---|
| 2.5s (25%) | `#fc0000` red | `#fc0000` red | `#fc0000` red | `#fc0000` red | `#0000fd` blue |
| 3.0s (50%) | `#fc0000` red | `#fc0000` red | `#fc0000` red | `#0000fd` blue | `#0000fd` blue |
| 3.5s (75%) | `#fc0000` red | `#0000fd` blue | `#0000fd` blue | `#0000fd` blue | `#0000fd` blue |

The reveal boundary (`wipeleft`) sweeps right-to-left as progress advances:
at 25% only the rightmost sample has flipped to blue, by 50% the boundary
has swept past the midpoint, and by 75% only the leftmost sample remains
red — a genuinely moving spatial edge, contrasted with dissolve's fixed
50/50 blend-at-every-position at its own transition midpoint. Every sampled
region is a *solid* color (no intermediate blended pixel value observed at
this sampling resolution) — the same 252/253-not-255 drift seen in the
dissolve proof is ordinary `libx264`/yuv420p lossy-encoding rounding, not a
douga or filter defect.

Requires system `ffmpeg` + `ffprobe` on `PATH`, and a local checkout of
`kotoba-lang/kami-eizo-timeline` whose `src/` is reachable via classpath:

```bash
kbb --backend sci -cp src:<path-to-kami-eizo-timeline>/src test/e2e/real_wipe_proof.cljk
```

Exits 0 with a PASS report on success, 1 with the failing checks printed on
failure.

## Real chained multi-transition render proof (`test/e2e/real_chained_transitions_proof.cljk`)

The dissolve and wipe proofs above each only ever exercise ONE transition
between exactly TWO clips — that gap (multi-clip timelines with several
transitions chained end-to-end) used to be an explicit, honestly-documented
unwired extension point (see this section's previous "Maturity note", now
below). It no longer is: `douga.ffmpeg/xfade-chain-cmd` is a new command
builder that generalizes `xfade-transition-cmd` to a whole video track with
**two or more sequential transitions across three or more clips**, all
rendered by a **single ffmpeg invocation** with N-1 chained `xfade`
filter_complex stages.

**The chaining arithmetic this closes a real gap on**: ffmpeg xfade's
`offset` is relative to the start of its own first input stream. For a
chain's first stage, that's clip 1's own duration minus transition 1's
duration — the same arithmetic `xfade-transition-cmd` already used. But a
chain's SECOND (and every later) stage's first input isn't a raw source
clip, it's the PREVIOUS stage's output stream — whose duration already
reflects every upstream transition's overlap-consumption. A naive
per-pair loop that reused each clip's own raw duration for every stage's
offset would get every stage after the first wrong (it would place the
later transition too early, overlapping the earlier one instead of
starting cleanly after it). `xfade-chain-cmd` computes each stage's offset
against the chain's *cumulative* output duration instead:

```
D_0 = duration(clip_0)
D_k = D_(k-1) + duration(clip_k) - duration(transition_k)   (k = 1..n-1)
offset_k = D_(k-1) - duration(transition_k)                 (stage k)
```

and chains each stage's filter_complex clause onto the *previous* stage's
output label (`[vx1]`, `[vx2]`, …), never a raw source label, so the
accumulated overlap is never silently discarded.

`test/e2e/real_chained_transitions_proof.cljk` is the same real-subprocess
proof pattern as the dissolve/wipe proofs, but for a 3-clip, 2-transition
chain, driven through the real `douga.eizo-timeline/render-plan` (which
already supported an arbitrary number of `:video-transitions` per track —
no fix needed there) and the real, new `douga.ffmpeg/xfade-chain-cmd`. It:

1. builds a real `kami.eizo.timeline` EDL — a 4.0s red clip, a 4.0s lime
   clip, and a 4.0s blue clip, bridged by a 1.5s `:dissolve` transition
   (red→lime) then a 1.5s `:wipe` transition (lime→blue). Per
   `kami.eizo.timeline`'s overlap semantics applied transitively down the
   chain, total EDL duration is 4.0+4.0+4.0-1.5-1.5=**9.0s**, not 12.0s —
   asserted via `kami.eizo.timeline/timeline-duration` before rendering
   anything;
2. generates the three solid-color stills locally via `ffmpeg -f lavfi
   color=...` (no external assets, no network);
3. drives that EDL through the **real** `douga.eizo-timeline/render-plan`
   and asserts both `:video-transitions` entries come back in order with
   the right types (`:dissolve` then `:wipe`);
4. builds the **real** `douga.ffmpeg/xfade-chain-cmd` argv from the
   render-plan's 3 segments + 2 transitions and executes it as ONE real
   `ffmpeg` child process — one invocation produces the entire
   dissolve-then-wipe merged output, no per-pair intermediate renders;
5. verifies with real `ffprobe` that the output is exactly 9.0s (not
   12.0s), at the right resolution;
6. the pixel-sampling proof is the crux, chosen specifically so a wrong
   chained offset would be visible, not just plausible-looking: the two
   transition durations (1.5s each) and clip durations (4.0s each) are
   picked so the FINAL merged output has a genuine ~1.0s pure-lime
   **steady gap between the two transition windows** —
   `[0.0,2.5)` pure red → `[2.5,4.0)` dissolve blend → `[4.0,5.0)` **pure
   lime** → `[5.0,6.5)` wipe sweep → `[6.5,9.0)` pure blue. That steady
   gap only exists in the real output if stage 2's offset was computed
   against the chain's *accumulated* duration (6.5s) rather than clip
   B's own raw duration (4.0s) — the exact naive-loop bug the arithmetic
   above targets; get it wrong and the wipe would start 2.5s early,
   colliding with (or overlapping into) the tail of the dissolve. The
   proof reuses both single-transition proofs' techniques within this one
   render: dissolve's fixed-point/multi-timestamp sampling for the
   red→lime blend, wipe's multi-x-position/fixed-timestamp sampling for
   the lime→blue sweep, plus a direct pure-color sample in the steady gap
   itself and after the final transition.

Last verified run: all 26 checks passed — 320×240 output, exactly
9.000000s (ffprobe), and real sampled RGB/classifications at every
checkpoint: `#fc0000` pure red (t=1.0s, before T1) → `#bc3e00`/`#7d7e00`/
`#3cbd00` (T1 25%/50%/75%, a monotonic red→green blend with an almost
exact 125/126 split at the midpoint) → `#00fe00` **pure lime at t=4.5s,
the steady gap between T1 and T2** (the chaining-crux checkpoint) →
a moving lime/blue spatial boundary at T2's 25%/50%/75% checkpoints
(1→2→4 blue-classified x-positions out of 5, sweeping right-to-left, the
same `wipeleft` signature as the standalone wipe proof) → `#0000fd` pure
blue (t=7.5s, after T2). The generated filter_complex graph (for this
proof's exact parameters) was:

```
[0:v]scale=320:240:force_original_aspect_ratio=decrease,pad=320:240:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24[v0];
[1:v]scale=320:240:force_original_aspect_ratio=decrease,pad=320:240:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24[v1];
[2:v]scale=320:240:force_original_aspect_ratio=decrease,pad=320:240:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24[v2];
[v0][v1]xfade=transition=fade:duration=1.5:offset=2.5[vx1];
[vx1][v2]xfade=transition=wipeleft:duration=1.5:offset=5[v]
```

(one line per `;`-terminated clause here for readability — the real argv
is a single `-filter_complex` string). Note stage 2's `offset=5` — the
correct chain-accumulated value (`D_1 - t2` = `6.5 - 1.5`), not the wrong
value a naive per-clip-duration loop would produce (`4.0 - 1.5 = 2.5`,
which would collide with stage 1's own transition window).

Requires system `ffmpeg` + `ffprobe` on `PATH`, and a local checkout of
`kotoba-lang/kami-eizo-timeline` whose `src/` is reachable via classpath:

```bash
kbb --backend sci -cp src:<path-to-kami-eizo-timeline>/src test/e2e/real_chained_transitions_proof.cljk
```

Exits 0 with a PASS report on success, 1 with the failing checks printed on
failure.

**Maturity note**: `:dissolve` and `:wipe` now have a real render path both
for a single transition between two clips (`xfade-transition-cmd`) and for
a chain of two or more sequential transitions across three or more clips on
a single video track in one ffmpeg invocation (`xfade-chain-cmd`, proven
above). Still not wired: transitions combined with per-scene audio/bgm
muxing in the same invocation (the transition proofs are video-track-only;
audio muxing today only exists in the hard-cut path's `bgm-mix-cmd`), other
`:wipe` directions (only `wipeleft` is wired — `wiperight`/`wipeup`/
`wipedown` and the many other `xfade` modes ffmpeg exposes are not), other
transition types entirely (`:slide`/etc.), and non-linear transition
topologies (e.g. two transitions both touching the same clip from
different tracks, or a transition graph that isn't a simple clip-1→clip-2→
clip-3→… chain) — `xfade-chain-cmd` assumes its `segments`/`transitions`
arguments are already in adjacent chain order (sort a track's
`:video-transitions` by `:from-scene-index` first if they weren't authored
in timeline order; see its docstring). See `douga.eizo-timeline`'s
`:video-transitions` output (one entry per transition, already supporting
any number per track — no fix was needed there, only in the ffmpeg
command-building side) as the extension point for further work.

## Real-ffmpeg execution proof for the LEGACY path (`test/e2e/real_ffmpeg_legacy_proof.cljk`)

Everything above this section (`real_ffmpeg_proof.cljs`, `real_dissolve_proof.cljs`)
proves `douga.eizo-timeline`'s `kami.eizo.timeline`-EDL entry point. That path
is real and well-tested, but it is **not** what runs in production today.
**The live, deployed `yukkuri` pipeline uses `douga.ffmpeg/build-render-plan`
directly** — the original, looser "scene/lines/assets" shape (ADR-2607051600)
— and until this proof, that specific function had only ever been checked at
the *shape* level (`test/douga/ffmpeg_test.cljk`): never handed to a real
`ffmpeg` binary.

`test/e2e/real_ffmpeg_legacy_proof.cljk` closes that gap, for the actual
production entry point, with the same rigor as the two proofs above. It:

1. hand-builds a real scene/lines/assets timeline in the exact lenient shape
   `test/douga/ffmpeg_test.cljk`'s own fixture already assumes (`:scenes`
   with `:index`, `:assets` with `:kind`/`:blobKey`/`:meta {:sceneIndex}`,
   `:lines` with `:sceneIndex`/`:lineIndex`/`:voiceBlobKey`/`:speaker`/
   `:text`) — 3 scenes (red / lime / blue), scene 0 with **two** real voice
   takes (1.0s + 1.2s, to exercise `concat-audio-cmd`'s ordering-by-line
   logic), scene 1 with one voice take (1.6s), and scene 2 with **zero**
   lines (a real "silent" scene, to exercise `silent-audio-cmd`);
2. generates every frame/voice/bgm source locally via `ffmpeg -f lavfi`
   (`color=`/`sine=` — no external assets, no network);
3. drives that timeline through the **real, unmodified**
   `douga.ffmpeg/build-render-plan` and asserts its output shape (segment
   order, `:frame-blob-key`, `:voice-blob-keys` ordering, `:texts`,
   `:speakers`, `:bgm-blob-key`, resolution/fps) against the hand-built
   input;
4. for each segment, builds its audio track with the **real**
   `concat-audio-cmd` (non-empty `:voice-blob-keys`, any count) or
   `silent-audio-cmd` (empty `:voice-blob-keys`) and renders it with the
   **real** `scene-segment-cmd`, then the **real**
   `concat-segments-cmd` and `bgm-mix-cmd` — every argv executed is exactly
   what `douga.ffmpeg` returns, nothing hand-typed;
5. executes every command as a real, synchronous `ffmpeg` child process;
6. verifies with real `ffprobe`: each segment's *own* real rendered video
   duration against its *own* real input audio duration (proving
   `-shortest`'s emergent-duration behavior directly, segment by segment —
   see "Known limitations" below), and the final muxed output's dimensions
   and total duration (the sum of the real per-segment durations — nothing
   pre-computed, since the plan itself carries no duration data at all);
7. samples real decoded pixels at 3 timestamps per scene (9 total),
   boundaries derived from the *measured* per-segment durations (not
   assumed round numbers), confirming the right color is on screen at the
   right time.

Last verified run: all 34 checks passed — 320×240 final output, 5.677s
total duration (sum of measured per-segment durations 2.2s + 1.6s + 1.8s =
5.6s; the ~77ms delta is ordinary concat-demuxer/bgm-mix container-duration
rounding, the same class of drift already noted for the newer path above,
not a `build-render-plan` defect), each per-segment video duration matched
its real input audio duration exactly (0s delta, well within the 1-frame/
24fps ≈ 41.7ms tolerance asserted), and every sampled pixel matched its
scene's expected color within a 40/255-channel tolerance (actual observed
drift was 1–3/255, ordinary H.264/yuv420p lossy-encoding drift).

Requires system `ffmpeg` + `ffprobe` on `PATH`. No extra classpath needed —
this path has no `kami-eizo-timeline` dependency:

```bash
kbb --backend sci -cp src test/e2e/real_ffmpeg_legacy_proof.cljk
```

Exits 0 with a PASS report on success, 1 with the failing checks printed on
failure.

### Known limitations / notable behaviors of the legacy path (found while proving it, none fixed — this proof is read-only verification of unmodified production code)

- **`build-render-plan`'s segments carry no duration information at all**
  (no `:duration-frames`, no timing field of any kind) — this is a real
  structural difference from `douga.eizo-timeline/render-plan`'s explicit
  `:duration-frames`, not an oversight: the legacy design's entire duration
  model is "whatever `-shortest` discovers from the real audio at render
  time." A caller cannot ask the plan "how long will this be" ahead of
  render — the answer only exists after the fact, from `ffprobe`-ing the
  rendered output. This proof asserts that emergent duration directly
  (segment audio duration in -> segment video duration out, measured before
  and after rendering) rather than assuming a fixed value.
- **`build-render-plan` never synthesizes silence for a scene with zero
  voice lines** — it simply reports `:voice-blob-keys []`. The existing
  `silent-audio-cmd` helper exists precisely to cover this case, but it is
  the caller's responsibility to notice an empty `:voice-blob-keys` and
  invoke it; `scene-segment-cmd` has no default audio and will fail without
  *some* audio path. This proof exercises that exact caller-side branch
  (scene 2, zero lines) to confirm the intended pattern actually works
  end-to-end, but a caller that forgets this check for a genuinely
  dialogue-less scene would produce a broken command, not a silently wrong
  video.
- **`concat-audio-cmd` also works correctly with a single input
  (`n=1`)** — ffmpeg's `concat` filter accepts `n=1` as a valid no-op
  passthrough, so a caller may run every segment's voice lines through
  `concat-audio-cmd` uniformly (regardless of line count) rather than
  special-casing the single-line case. Confirmed empirically in this proof
  (scene 1's single voice take), not previously exercised by any test in
  this repo.
- No incorrect or unexpected behavior was found in `build-render-plan`
  itself during this work — the above are documented characteristics of its
  intentionally loose, ffmpeg-emergent design, not bugs. If a future change
  were considered (e.g. adding an estimated-duration field), that is a
  deliberate design decision for owners of the live `yukkuri` pipeline to
  make, not something this proof changes.

## Occupation

ISCO-08 `2654` (Film, Stage and Related Directors and Producers) —
[cloud-itonami-isco-2654](https://github.com/cloud-itonami/cloud-itonami-isco-2654).

## Test

```bash
kbb -M:test
```

## License

Apache-2.0.
